"""Testes de integração para o endpoint WebSocket (Etapa 4 — RF-36).

Usa ``starlette.testclient.TestClient`` (com suporte nativo a WebSocket) em vez
de ``httpx.AsyncClient`` (que não suporta WebSocket).

As dependências ``get_db`` e ``get_redis`` são substituídas por implementações
em memória (SQLite :memory: + FakeRedis) para isolamento total dos testes.

O ``FakeServer`` compartilhado garante que mensagens publicadas pelo teste
cheguem ao assinante dentro do endpoint (mesmo processo, memória compartilhada).

Estratégia de isolamento:

Redis:
  ``app.core.redis._redis_pool`` é pré-populado com FakeRedis antes de cada
  TestClient. O ``get_redis_pool()`` original retorna o pool existente sem
  abrir conexão real ao Redis.

SQLite:
  Usa arquivo temporário (não ``:memory:``) com ``NullPool``. O NullPool cria uma
  nova conexão por sessão e a fecha ao terminar, sem reutilizar o pool. Isso
  evita "locked connection" quando o cleanup da sessão falha com CancelledError
  (originado pelo cancel_scope.cancel() do task_group no handler WebSocket).
"""

import json
import os
import tempfile

import fakeredis
import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient

from app.core.redis import competition_channel, get_redis
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Servidor fake compartilhado: endpoint e publicador do teste usam o mesmo estado
_fake_server = fakeredis.FakeServer()


# ---------------------------------------------------------------------------
# Fixture de cliente WebSocket isolado
# ---------------------------------------------------------------------------


@pytest.fixture()
def ws_client(tmp_path):
    """TestClient com SQLite em arquivo e FakeRedis para testes de WebSocket.

    O lifespan da app é interceptado pré-populando ``_redis_pool`` com FakeRedis,
    evitando qualquer tentativa de conexão ao Redis real.

    O banco de dados usa um arquivo SQLite temporário com NullPool: cada sessão
    abre e fecha sua própria conexão sem pool compartilhado — evita deadlocks
    quando o cleanup da sessão é interrompido por CancelledError.
    """
    import app.core.redis as _redis_mod

    # Banco de dados em arquivo temporário (não :memory:) para suportar NullPool
    db_path = tmp_path / "test_ws.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    # FakeRedis conectado ao servidor fake compartilhado
    _fake = fakeredis.aioredis.FakeRedis(server=_fake_server, decode_responses=True)

    # Pré-popula o pool global: get_redis_pool() retorna este FakeRedis sem conectar
    # ao Redis real (a função original só cria nova conexão quando _redis_pool is None)
    _orig_pool = _redis_mod._redis_pool
    _redis_mod._redis_pool = _fake

    _schema_created = {}

    async def _override_get_db():
        """Cria sessão com NullPool — conexão independente por requisição."""
        engine = create_async_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
        if not _schema_created:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            _schema_created["done"] = True
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _override_get_redis():
        """Injeta FakeRedis via Depends(get_redis) nas rotas."""
        redis = fakeredis.aioredis.FakeRedis(server=_fake_server, decode_responses=True)
        yield redis
        await redis.aclose()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    # raise_server_exceptions=False: impede que CancelledError do cleanup anyio
    # (evento normal quando WebSocket fecha) propague como falha de teste.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()
    # Restaura o pool original (close_redis_pool() no lifespan já fechou _fake
    # e zerou _redis_pool; esta linha garante restauração mesmo se algo falhar)
    _redis_mod._redis_pool = _orig_pool


# ---------------------------------------------------------------------------
# Helper: publicador Redis síncrono (usa o mesmo FakeServer)
# ---------------------------------------------------------------------------


def _publish_event(channel: str, event: dict) -> None:
    """Publica evento no canal Redis usando conexão síncrona (FakeRedis)."""
    r = fakeredis.FakeRedis(server=_fake_server, decode_responses=True)
    r.publish(channel, json.dumps(event))
    r.close()


# ---------------------------------------------------------------------------
# Testes de conexão e protocolo
# ---------------------------------------------------------------------------


def test_ws_aceita_conexao(ws_client: TestClient) -> None:
    """Endpoint deve aceitar a conexão WebSocket."""
    with ws_client.websocket_connect("/ws/competition/1") as ws:
        data = ws.receive_json()
        assert data["type"] == "init"


def test_ws_mensagem_init_formato(ws_client: TestClient) -> None:
    """Mensagem init deve conter competition_id e lista de timers."""
    with ws_client.websocket_connect("/ws/competition/42") as ws:
        data = ws.receive_json()
        assert data["type"] == "init"
        assert data["competition_id"] == 42
        assert isinstance(data["timers"], list)


def test_ws_init_sem_timers_retorna_lista_vazia(ws_client: TestClient) -> None:
    """Competição sem timers cadastrados retorna lista vazia no init."""
    with ws_client.websocket_connect("/ws/competition/999") as ws:
        data = ws.receive_json()
        assert data["type"] == "init"
        assert data["timers"] == []


def test_ws_repassa_evento_redis(ws_client: TestClient) -> None:
    """Evento publicado no Redis deve ser recebido pelo WebSocket conectado."""
    competition_id = 7
    channel = competition_channel(competition_id)
    event = {"event_type": "started", "timer_id": 42, "accumulated_ms": 0, "started_at_ms": 1710000000000}

    with ws_client.websocket_connect(f"/ws/competition/{competition_id}") as ws:
        # Descarta mensagem de init
        ws.receive_json()

        # Publica evento no Redis (sincrono, mesmo FakeServer)
        _publish_event(channel, event)

        # Verifica que o WebSocket recebeu o evento
        received = ws.receive_json()
        assert received["event_type"] == "started"
        assert received["timer_id"] == 42


def test_ws_repassa_multiplos_eventos(ws_client: TestClient) -> None:
    """Múltiplos eventos publicados devem ser recebidos na ordem correta."""
    competition_id = 8
    channel = competition_channel(competition_id)
    events = [
        {"event_type": "started", "timer_id": 1},
        {"event_type": "paused", "timer_id": 1, "accumulated_ms": 30000},
        {"event_type": "finished", "timer_id": 2, "accumulated_ms": 120000},
    ]

    with ws_client.websocket_connect(f"/ws/competition/{competition_id}") as ws:
        ws.receive_json()  # init

        for e in events:
            _publish_event(channel, e)

        for expected in events:
            received = ws.receive_json()
            assert received["event_type"] == expected["event_type"]
            assert received["timer_id"] == expected["timer_id"]


def test_ws_competicoes_diferentes_nao_interferem(ws_client: TestClient) -> None:
    """Eventos de competição A não chegam ao WebSocket da competição B."""
    ch_a = competition_channel(10)
    ch_b = competition_channel(20)

    with ws_client.websocket_connect("/ws/competition/20") as ws_b:
        ws_b.receive_json()  # init

        # Publica em A (não deve chegar em B)
        _publish_event(ch_a, {"event_type": "started", "timer_id": 1})
        # Publica em B (deve chegar)
        _publish_event(ch_b, {"event_type": "started", "timer_id": 99})

        received = ws_b.receive_json()
        assert received["timer_id"] == 99  # só evento de B chegou


def test_ws_desconexao_graceful(ws_client: TestClient) -> None:
    """Fechar o WebSocket não deve gerar exceção no servidor."""
    with ws_client.websocket_connect("/ws/competition/1") as ws:
        ws.receive_json()  # init
    # Sair do with block fecha a conexão — sem exceção = sucesso
