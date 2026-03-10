import pytest
from httpx import AsyncClient


# ── Fixtures helpers ──────────────────────────────────────────────────────────

async def _create_competition(
    client: AsyncClient, token: str, name: str = "Copa Heat", active: bool = True
) -> int:
    r = await client.post(
        "/api/v1/competitions",
        json={"name": name},
        cookies={"session_id": token},
    )
    assert r.status_code == 201
    comp_id = r.json()["id"]
    if active:
        r2 = await client.patch(
            f"/api/v1/competitions/{comp_id}",
            json={"status": "active"},
            cookies={"session_id": token},
        )
        assert r2.status_code == 200
    return comp_id


async def _create_heat(
    client: AsyncClient, token: str, competition_id: int, name: str = "Bateria 1"
) -> dict:
    r = await client.post(
        f"/api/v1/competitions/{competition_id}/heats",
        json={"name": name},
        cookies={"session_id": token},
    )
    assert r.status_code == 201
    return r.json()


async def _create_timer(
    client: AsyncClient, token: str, competition_id: int, user_id: int
) -> int:
    r = await client.post(
        "/api/v1/timers",
        json={"competition_id": competition_id, "user_id": user_id},
        cookies={"session_id": token},
    )
    assert r.status_code == 201
    return r.json()["id"]


# ── Listagem ───────────────────────────────────────────────────────────────────

async def test_listar_baterias_publico_retorna_200(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Lista Heat")
    response = await client.get(f"/api/v1/competitions/{comp_id}/heats")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── Criação ────────────────────────────────────────────────────────────────────

async def test_criar_bateria_como_admin_retorna_201(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Criar Heat")
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/heats",
        json={"name": "Bateria A"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Bateria A"
    assert data["competition_id"] == comp_id
    assert data["status"] == "pending"
    assert data["timer_count"] == 0


async def test_criar_bateria_sem_autenticacao_retorna_401(client: AsyncClient):
    # Auth check happens before 404, so any competition_id works
    response = await client.post(
        "/api/v1/competitions/1/heats",
        json={"name": "Bateria Anon"},
    )
    assert response.status_code == 401


async def test_criar_bateria_como_competidor_retorna_403(
    client: AsyncClient, admin_token: str, competitor_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Comp Heat")
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/heats",
        json={"name": "Bateria Negada"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_criar_bateria_competicao_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/competitions/9999/heats",
        json={"name": "Bateria Fantasma"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 404


# ── Timer na bateria ──────────────────────────────────────────────────────────

async def test_adicionar_timer_a_bateria_retorna_201(
    client: AsyncClient, admin_token: str, competitor_user
):
    comp_id = await _create_competition(client, admin_token, "Copa Timer Heat")
    heat = await _create_heat(client, admin_token, comp_id, "Bateria Timer")
    timer_id = await _create_timer(client, admin_token, comp_id, competitor_user.id)
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/timers",
        json={"timer_id": timer_id},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    assert response.json()["timer_count"] == 1


async def test_remover_timer_da_bateria_retorna_204(
    client: AsyncClient, admin_token: str, competitor_user
):
    comp_id = await _create_competition(client, admin_token, "Copa Remove Timer Heat")
    heat = await _create_heat(client, admin_token, comp_id, "Bateria Remover")
    timer_id = await _create_timer(client, admin_token, comp_id, competitor_user.id)
    await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/timers",
        json={"timer_id": timer_id},
        cookies={"session_id": admin_token},
    )
    response = await client.delete(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/timers/{timer_id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204


# ── Iniciar bateria ───────────────────────────────────────────────────────────

async def test_iniciar_bateria_como_judge_retorna_200(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    comp_id = await _create_competition(client, admin_token, "Copa Start Heat")
    heat = await _create_heat(client, admin_token, comp_id, "Bateria Start")
    timer_id = await _create_timer(client, admin_token, comp_id, competitor_user.id)
    await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/timers",
        json={"timer_id": timer_id},
        cookies={"session_id": admin_token},
    )
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/start",
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "running"


async def test_iniciar_bateria_competicao_inativa_retorna_403(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    # draft competition (não está ativa)
    r = await client.post(
        "/api/v1/competitions",
        json={"name": "Copa Draft Heat"},
        cookies={"session_id": admin_token},
    )
    comp_id = r.json()["id"]
    heat = await _create_heat(client, admin_token, comp_id, "Bateria Draft")
    timer_id = await _create_timer(client, admin_token, comp_id, competitor_user.id)
    await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/timers",
        json={"timer_id": timer_id},
        cookies={"session_id": admin_token},
    )
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/start",
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 403


async def test_iniciar_bateria_sem_timers_retorna_409(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Vazia Heat")
    heat = await _create_heat(client, admin_token, comp_id, "Bateria Vazia")
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/start",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409


async def test_iniciar_bateria_como_competidor_retorna_403(
    client: AsyncClient, admin_token: str, competitor_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Comp Start")
    heat = await _create_heat(client, admin_token, comp_id, "Bateria Comp")
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}/start",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


# ── Exclusão ───────────────────────────────────────────────────────────────────

async def test_excluir_bateria_como_admin_retorna_204(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Delete Heat")
    heat = await _create_heat(client, admin_token, comp_id, "Bateria Excluída")
    response = await client.delete(
        f"/api/v1/competitions/{comp_id}/heats/{heat['id']}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204
