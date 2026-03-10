import pytest
from httpx import AsyncClient


# ── Fixtures helpers ──────────────────────────────────────────────────────────

async def _create_competition(client: AsyncClient, token: str, name: str = "Copa Test") -> int:
    r = await client.post(
        "/api/v1/competitions",
        json={"name": name},
        cookies={"session_id": token},
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _create_category(client: AsyncClient, token: str, competition_id: int) -> int:
    r = await client.post(
        f"/api/v1/competitions/{competition_id}/categories",
        json={"name": "Geral", "category_type": "individual"},
        cookies={"session_id": token},
    )
    assert r.status_code == 201
    return r.json()["id"]


async def _create_team(
    client: AsyncClient, token: str, competition_id: int, name: str = "Equipe Alpha",
    category_id: int | None = None,
) -> dict:
    if category_id is None:
        category_id = await _create_category(client, token, competition_id)
    r = await client.post(
        f"/api/v1/competitions/{competition_id}/teams",
        json={"name": name, "category_id": category_id},
        cookies={"session_id": token},
    )
    assert r.status_code == 201
    return r.json()


# ── Listagem ───────────────────────────────────────────────────────────────────

async def test_listar_equipes_publico_retorna_200(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Campeonato Público")
    response = await client.get(f"/api/v1/competitions/{comp_id}/teams")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── Criação ────────────────────────────────────────────────────────────────────

async def test_criar_equipe_como_admin_retorna_201(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Admin")
    cat_id = await _create_category(client, admin_token, comp_id)
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/teams",
        json={"name": "Equipe Bravo", "category_id": cat_id},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Equipe Bravo"
    assert data["competition_id"] == comp_id


async def test_criar_equipe_sem_autenticacao_retorna_401(client: AsyncClient):
    # Auth check happens before 404, so any competition_id works
    response = await client.post(
        "/api/v1/competitions/1/teams",
        json={"name": "Equipe Anon", "category_id": 1},
    )
    assert response.status_code == 401


async def test_criar_equipe_como_competidor_retorna_403(
    client: AsyncClient, admin_token: str, competitor_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Competidor")
    cat_id = await _create_category(client, admin_token, comp_id)
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/teams",
        json={"name": "Equipe Negada", "category_id": cat_id},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_criar_equipe_competicao_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/competitions/9999/teams",
        json={"name": "Equipe Fantasma", "category_id": 1},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 404


# ── Atualização ────────────────────────────────────────────────────────────────

async def test_atualizar_equipe_como_admin_retorna_200(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Update")
    team = await _create_team(client, admin_token, comp_id, "Equipe Antiga")
    response = await client.patch(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}",
        json={"name": "Equipe Nova"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Equipe Nova"


# ── Exclusão ───────────────────────────────────────────────────────────────────

async def test_excluir_equipe_como_admin_retorna_204(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa Delete")
    team = await _create_team(client, admin_token, comp_id, "Equipe Removida")
    response = await client.delete(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204


# ── Membros ────────────────────────────────────────────────────────────────────

async def test_adicionar_membro_retorna_201(
    client: AsyncClient, admin_token: str, competitor_user
):
    comp_id = await _create_competition(client, admin_token, "Copa Membros")
    team = await _create_team(client, admin_token, comp_id, "Equipe Com Membro")
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members",
        json={"user_id": competitor_user.id},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == competitor_user.id
    assert data["team_id"] == team["id"]


async def test_adicionar_membro_duplicado_retorna_409(
    client: AsyncClient, admin_token: str, competitor_user
):
    comp_id = await _create_competition(client, admin_token, "Copa Duplicado")
    team = await _create_team(client, admin_token, comp_id, "Equipe Duplicado")
    payload = {"user_id": competitor_user.id}
    await client.post(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members",
        json=payload,
        cookies={"session_id": admin_token},
    )
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members",
        json=payload,
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409


async def test_adicionar_membro_usuario_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "Copa User404")
    team = await _create_team(client, admin_token, comp_id, "Equipe 404")
    response = await client.post(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members",
        json={"user_id": 9999},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 404


async def test_listar_membros_retorna_lista(
    client: AsyncClient, admin_token: str, competitor_user
):
    comp_id = await _create_competition(client, admin_token, "Copa Lista Membros")
    team = await _create_team(client, admin_token, comp_id, "Equipe Lista")
    await client.post(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members",
        json={"user_id": competitor_user.id},
        cookies={"session_id": admin_token},
    )
    response = await client.get(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members"
    )
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 1
    assert members[0]["user_id"] == competitor_user.id


async def test_remover_membro_retorna_204(
    client: AsyncClient, admin_token: str, competitor_user
):
    comp_id = await _create_competition(client, admin_token, "Copa Remove Membro")
    team = await _create_team(client, admin_token, comp_id, "Equipe Remover")
    await client.post(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members",
        json={"user_id": competitor_user.id},
        cookies={"session_id": admin_token},
    )
    response = await client.delete(
        f"/api/v1/competitions/{comp_id}/teams/{team['id']}/members/{competitor_user.id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204
