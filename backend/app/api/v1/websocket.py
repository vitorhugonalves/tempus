"""Endpoint WebSocket para atualizações em tempo real de timers (Etapa 4 — RF-36).

Canal por competição: /ws/competition/{competition_id}

Fluxo de mensagens:
  1. Cliente conecta.
  2. Servidor envia mensagem ``{"type": "init", ...}`` com estado atual de todos
     os timers da competição (calculado com Redis para timers em execução).
  3. Servidor reenvia eventos Redis Pub/Sub como mensagens JSON enquanto a
     conexão estiver aberta.
  4. Servidor envia ``{"type": "ping"}`` a cada 30 s para keepalive.
  5. Desconexão limpa assinatura do canal Redis.
"""

import json
import logging
from contextlib import suppress

import anyio
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import competition_channel, get_redis, timer_key
from app.db.session import get_db
from app.repositories.timer import TimerRepository
from app.schemas.timer import TimerResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Intervalo entre pings de keepalive (segundos)
_PING_INTERVAL = 30


@router.websocket("/ws/competition/{competition_id}")
async def competition_websocket(
    websocket: WebSocket,
    competition_id: int,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> None:
    """WebSocket em tempo real para uma competição.

    Acesso público — sem autenticação obrigatória (display boards, placar).

    Protocolo de mensagens (JSON):

    * ``{"type": "init", "competition_id": int, "timers": [...]}``
      — enviado imediatamente após a conexão.
    * ``{"type": "ping"}``
      — heartbeat a cada 30 segundos.
    * ``{"event_type": "<started|paused|...>", "timer_id": int, ...}``
      — eventos de timer republicados do Redis Pub/Sub.

    Args:
        websocket: Conexão WebSocket do cliente.
        competition_id: ID da competição a monitorar.
        db: Sessão do banco de dados (para carga inicial).
        redis: Conexão Redis (para pub/sub e estado quente dos timers).
    """
    await websocket.accept()
    logger.info(
        "WebSocket conectado: competition_id=%s client=%s",
        competition_id,
        websocket.client,
    )

    # ── 1. Estado inicial ────────────────────────────────────────────────────
    try:
        timers = await TimerRepository.get_by_competition(db, competition_id)

        if timers:
            pipe = redis.pipeline()
            for t in timers:
                pipe.get(timer_key(t.id))
            raw_states = await pipe.execute()
        else:
            raw_states = []

        timer_list = []
        for t, raw in zip(timers, raw_states):
            redis_state = json.loads(raw) if raw else None
            timer_list.append(TimerResponse.from_orm(t, redis_state).model_dump(mode="json"))

        await websocket.send_json({
            "type": "init",
            "competition_id": competition_id,
            "timers": timer_list,
        })
    except (WebSocketDisconnect, RuntimeError):
        logger.info("WebSocket desconectou antes do init: competition_id=%s", competition_id)
        return
    except Exception:
        logger.exception("Erro ao enviar estado inicial: competition_id=%s", competition_id)
        with suppress(Exception):
            await websocket.close(code=1011)
        return

    # ── 2. Assinatura Redis Pub/Sub + loop de eventos ────────────────────────
    pubsub = redis.pubsub()
    channel = competition_channel(competition_id)
    await pubsub.subscribe(channel)
    logger.debug("Inscrito no canal Redis: %s", channel)

    # Intervalo de polling Redis em segundos.
    # Baixo o suficiente para latência imperceptível (~10 ms) e que garante
    # um ponto de cancelamento a cada iteração (anyio.sleep é cancellable).
    _POLL_MS = 0.01

    async def _redis_to_ws() -> None:
        """Recebe mensagens do Redis e repassa ao WebSocket (polling)."""
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])
            else:
                # Cede o controle ao event loop — ponto de cancelamento garantido
                await anyio.sleep(_POLL_MS)

    async def _disconnect_watcher(cancel_scope: anyio.CancelScope) -> None:
        """Detecta desconexão do cliente e cancela o grupo de tarefas."""
        try:
            while True:
                # Recebe mensagens do cliente (keepalive/ping do cliente)
                await websocket.receive_text()
        except (WebSocketDisconnect, RuntimeError):
            cancel_scope.cancel()

    async def _periodic_ping(cancel_scope: anyio.CancelScope) -> None:
        """Envia ping periódico para manter a conexão ativa."""
        while True:
            await anyio.sleep(_PING_INTERVAL)
            try:
                await websocket.send_json({"type": "ping"})
            except (WebSocketDisconnect, RuntimeError):
                cancel_scope.cancel()
                break

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(_redis_to_ws)
            tg.start_soon(_disconnect_watcher, tg.cancel_scope)
            tg.start_soon(_periodic_ping, tg.cancel_scope)
    except Exception:
        # Scope cancelado ou exceção inesperada — tratado no finally
        pass
    finally:
        with suppress(Exception):
            await pubsub.unsubscribe(channel)
        with suppress(Exception):
            await pubsub.aclose()
        logger.info(
            "WebSocket desconectado: competition_id=%s client=%s",
            competition_id,
            websocket.client,
        )
