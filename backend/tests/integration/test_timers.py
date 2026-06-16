"""Testes de integração para timers, penalidades e ranking (RF-26 a RF-39)."""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def active_competition(client: AsyncClient, admin_token: str) -> dict:
    """Cria uma competição ativa."""
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": "Comp Ativa"},
        cookies={"session_id": admin_token},
    )
    comp = resp.json()
    await client.patch(
        f"/api/v1/competitions/{comp['id']}",
        json={"status": "active"},
        cookies={"session_id": admin_token},
    )
    return comp


@pytest.fixture
async def draft_competition(client: AsyncClient, admin_token: str) -> dict:
    """Cria uma competição em rascunho."""
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": "Comp Rascunho"},
        cookies={"session_id": admin_token},
    )
    return resp.json()


@pytest.fixture
async def timer_id(
    client: AsyncClient, active_competition: dict, competitor_user, admin_token: str
) -> int:
    """Cria um timer para o competidor na competição ativa."""
    resp = await client.post(
        "/api/v1/timers",
        json={
            "competition_id": active_competition["id"],
            "user_id": competitor_user.id,
        },
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Criação ───────────────────────────────────────────────────────────────────


async def test_criar_timer_como_admin_retorna_201(
    client: AsyncClient, active_competition: dict, competitor_user, admin_token: str
):
    """RF-26: Admin pode criar timer."""
    resp = await client.post(
        "/api/v1/timers",
        json={"competition_id": active_competition["id"], "user_id": competitor_user.id},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "created"
    assert data["accumulated_ms"] == 0


async def test_criar_timer_como_competidor_retorna_403(
    client: AsyncClient, active_competition: dict, competitor_user, competitor_token: str
):
    """RF-26: Competidor não pode criar timer."""
    resp = await client.post(
        "/api/v1/timers",
        json={"competition_id": active_competition["id"], "user_id": competitor_user.id},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403


async def test_criar_timer_duplicado_retorna_409(
    client: AsyncClient, active_competition: dict, competitor_user, admin_token: str
):
    """RF-26: Não deve criar dois timers para o mesmo atleta na mesma competição."""
    payload = {"competition_id": active_competition["id"], "user_id": competitor_user.id}
    await client.post("/api/v1/timers", json=payload, cookies={"session_id": admin_token})
    resp = await client.post("/api/v1/timers", json=payload, cookies={"session_id": admin_token})
    assert resp.status_code == 409


async def test_criar_timer_sem_user_e_team_retorna_422(
    client: AsyncClient, active_competition: dict, admin_token: str
):
    """RF-26: Deve informar user_id ou team_id."""
    resp = await client.post(
        "/api/v1/timers",
        json={"competition_id": active_competition["id"]},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 422


# ── Start ─────────────────────────────────────────────────────────────────────


async def test_iniciar_timer_como_judge_retorna_200(
    client: AsyncClient, timer_id: int, judge_token: str
):
    """RF-27: Judge pode iniciar timer."""
    resp = await client.post(
        f"/api/v1/timers/{timer_id}/start",
        json={},
        cookies={"session_id": judge_token},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


async def test_iniciar_timer_como_competidor_retorna_403(
    client: AsyncClient, timer_id: int, competitor_token: str
):
    """RF-27: Competidor não pode iniciar timer."""
    resp = await client.post(
        f"/api/v1/timers/{timer_id}/start",
        json={},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403


async def test_iniciar_timer_ja_running_retorna_409(
    client: AsyncClient, timer_id: int, judge_token: str
):
    """RF-27: Timer já em execução retorna conflito."""
    await client.post(f"/api/v1/timers/{timer_id}/start", json={}, cookies={"session_id": judge_token})
    resp = await client.post(f"/api/v1/timers/{timer_id}/start", json={}, cookies={"session_id": judge_token})
    assert resp.status_code == 409


async def test_iniciar_timer_com_competicao_inativa_retorna_403(
    client: AsyncClient, draft_competition: dict, competitor_user, admin_token: str, judge_token: str
):
    """RN-01: Timer não pode ser iniciado se competição não está ativa."""
    timer_resp = await client.post(
        "/api/v1/timers",
        json={"competition_id": draft_competition["id"], "user_id": competitor_user.id},
        cookies={"session_id": admin_token},
    )
    tid = timer_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/timers/{tid}/start",
        json={},
        cookies={"session_id": judge_token},
    )
    assert resp.status_code == 403


# ── Stop / Finish ─────────────────────────────────────────────────────────────


async def test_parar_timer_running_retorna_200(
    client: AsyncClient, timer_id: int, judge_token: str
):
    """RF-28: Parar timer em execução."""
    await client.post(f"/api/v1/timers/{timer_id}/start", json={}, cookies={"session_id": judge_token})
    resp = await client.post(f"/api/v1/timers/{timer_id}/stop", json={}, cookies={"session_id": judge_token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


async def test_parar_timer_nao_running_retorna_409(
    client: AsyncClient, timer_id: int, judge_token: str
):
    """RF-28: Timer parado não pode ser parado novamente."""
    resp = await client.post(f"/api/v1/timers/{timer_id}/stop", json={}, cookies={"session_id": judge_token})
    assert resp.status_code == 409


async def test_finalizar_timer_retorna_finished(
    client: AsyncClient, timer_id: int, judge_token: str
):
    """RF-28: Finalizar timer muda status para finished."""
    await client.post(f"/api/v1/timers/{timer_id}/start", json={}, cookies={"session_id": judge_token})
    resp = await client.post(f"/api/v1/timers/{timer_id}/finish", json={}, cookies={"session_id": judge_token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "finished"


# ── Restart ───────────────────────────────────────────────────────────────────


async def test_reiniciar_timer_sem_motivo_retorna_422(
    client: AsyncClient, timer_id: int, judge_token: str
):
    """RF-29: Motivo do reinício é obrigatório."""
    resp = await client.post(
        f"/api/v1/timers/{timer_id}/restart",
        json={},
        cookies={"session_id": judge_token},
    )
    assert resp.status_code == 422


async def test_reiniciar_timer_com_motivo_zera_tempo(
    client: AsyncClient, timer_id: int, admin_token: str, judge_token: str
):
    """RF-29: Reiniciar zera elapsed_seconds e muda status para idle."""
    await client.post(f"/api/v1/timers/{timer_id}/start", json={}, cookies={"session_id": judge_token})
    await client.post(f"/api/v1/timers/{timer_id}/stop", json={}, cookies={"session_id": judge_token})

    resp = await client.post(
        f"/api/v1/timers/{timer_id}/restart",
        json={"note": "Falsa largada — árbitro confirmou"},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    assert data["accumulated_ms"] == 0


# ── Eventos ───────────────────────────────────────────────────────────────────


async def test_historico_eventos_timer(
    client: AsyncClient, timer_id: int, judge_token: str
):
    """RF-31: Histórico registra start e stop."""
    await client.post(f"/api/v1/timers/{timer_id}/start", json={}, cookies={"session_id": judge_token})
    await client.post(f"/api/v1/timers/{timer_id}/stop", json={}, cookies={"session_id": judge_token})

    resp = await client.get(
        f"/api/v1/timers/{timer_id}/events",
        cookies={"session_id": judge_token},
    )
    assert resp.status_code == 200
    events = resp.json()
    event_types = [e["event_type"] for e in events]
    assert "started" in event_types
    assert "paused" in event_types


# ── Penalidades ───────────────────────────────────────────────────────────────


@pytest.fixture
async def penalty_type_id(
    client: AsyncClient, active_competition: dict, admin_token: str
) -> int:
    """Cria um tipo de penalidade."""
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/penalty-types",
        json={"name": "Burpee Penalty", "kind": "time_increment", "seconds": 30},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_aplicar_penalidade_como_judge(
    client: AsyncClient, timer_id: int, penalty_type_id: int, judge_token: str
):
    """RF-33: Judge pode aplicar penalidade."""
    resp = await client.post(
        f"/api/v1/timers/{timer_id}/penalties",
        json={"penalty_type_id": penalty_type_id, "justification": "Atleta pulou estação"},
        cookies={"session_id": judge_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["seconds_added"] == 30
    assert data["justification"] == "Atleta pulou estação"


async def test_aplicar_penalidade_como_competidor_retorna_403(
    client: AsyncClient, timer_id: int, penalty_type_id: int, competitor_token: str
):
    """RF-33: Competidor não pode aplicar penalidade."""
    resp = await client.post(
        f"/api/v1/timers/{timer_id}/penalties",
        json={"penalty_type_id": penalty_type_id, "justification": "Teste"},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403


async def test_penalidade_soma_no_tempo_final(
    client: AsyncClient, timer_id: int, penalty_type_id: int, judge_token: str
):
    """RF-37: Tempo final inclui penalidades."""
    await client.post(
        f"/api/v1/timers/{timer_id}/penalties",
        json={"penalty_type_id": penalty_type_id, "justification": "Infração"},
        cookies={"session_id": judge_token},
    )
    resp = await client.get(f"/api/v1/timers/{timer_id}", cookies={"session_id": judge_token})
    data = resp.json()
    assert data["total_penalty_seconds"] == 30
    assert data["final_seconds"] == data["elapsed_seconds"] + 30


async def test_listar_penalidades_do_timer(
    client: AsyncClient, timer_id: int, penalty_type_id: int, judge_token: str
):
    """RF-35: Competidor pode ver penalidades."""
    await client.post(
        f"/api/v1/timers/{timer_id}/penalties",
        json={"penalty_type_id": penalty_type_id, "justification": "Erro de percurso"},
        cookies={"session_id": judge_token},
    )
    resp = await client.get(f"/api/v1/timers/{timer_id}/penalties")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Ranking ───────────────────────────────────────────────────────────────────


async def test_ranking_acesso_publico(
    client: AsyncClient, active_competition: dict
):
    """RF-39: Ranking público sem autenticação."""
    resp = await client.get(
        f"/api/v1/competitions/{active_competition['id']}/ranking"
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_ranking_ordena_por_tempo_final(
    client: AsyncClient,
    active_competition: dict,
    competitor_user,
    admin_token: str,
    judge_token: str,
    penalty_type_id: int,
):
    """RF-36, RF-37: Ranking ordenado por tempo final (elapsed + penalidades)."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    # Cria segundo competidor via API
    await client.post(
        "/api/v1/users",
        json={
            "full_name": "Segundo Atleta",
            "email": "segundo@example.com",
            "password": "senha-123",
            "role": "competitor",
        },
        cookies={"session_id": admin_token},
    )
    users_resp = await client.get("/api/v1/users", cookies={"session_id": admin_token})
    segundo_id = next(u["id"] for u in users_resp.json() if u["email"] == "segundo@example.com")

    # Cria timers
    t1_resp = await client.post(
        "/api/v1/timers",
        json={"competition_id": active_competition["id"], "user_id": competitor_user.id},
        cookies={"session_id": admin_token},
    )
    t2_resp = await client.post(
        "/api/v1/timers",
        json={"competition_id": active_competition["id"], "user_id": segundo_id},
        cookies={"session_id": admin_token},
    )
    t1_id = t1_resp.json()["id"]
    t2_id = t2_resp.json()["id"]

    # Finaliza t1 (timer vai ter elapsed muito baixo, mas com penalidade de 30s)
    await client.post(f"/api/v1/timers/{t1_id}/start", json={}, cookies={"session_id": judge_token})
    await client.post(f"/api/v1/timers/{t1_id}/finish", json={}, cookies={"session_id": judge_token})
    await client.post(
        f"/api/v1/timers/{t1_id}/penalties",
        json={"penalty_type_id": penalty_type_id, "justification": "Penalidade"},
        cookies={"session_id": judge_token},
    )

    # Finaliza t2 (sem penalidade)
    await client.post(f"/api/v1/timers/{t2_id}/start", json={}, cookies={"session_id": judge_token})
    await client.post(f"/api/v1/timers/{t2_id}/finish", json={}, cookies={"session_id": judge_token})

    ranking = await client.get(
        f"/api/v1/competitions/{active_competition['id']}/ranking"
    )
    data = ranking.json()
    # t2 deve estar antes de t1 (sem penalidade → tempo menor)
    positions = {e["timer_id"]: e["position"] for e in data}
    assert positions[t2_id] < positions[t1_id]


async def test_exportar_csv_como_admin(
    client: AsyncClient, active_competition: dict, admin_token: str
):
    """RF-40: Admin exporta ranking em CSV."""
    resp = await client.get(
        f"/api/v1/competitions/{active_competition['id']}/export/csv",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Posição" in resp.text


async def test_exportar_csv_como_competidor_retorna_403(
    client: AsyncClient, active_competition: dict, competitor_token: str
):
    """RF-40: Competidor não exporta CSV."""
    resp = await client.get(
        f"/api/v1/competitions/{active_competition['id']}/export/csv",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403
