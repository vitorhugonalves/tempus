import pytest
from httpx import AsyncClient


# ── Listagem ───────────────────────────────────────────────────────────────────

async def test_listar_modalidades_publico_retorna_200(client: AsyncClient):
    response = await client.get("/api/v1/modalities")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── Criação ────────────────────────────────────────────────────────────────────

async def test_criar_modalidade_como_admin_retorna_201(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/modalities",
        json={"name": "Triathlon", "description": "Nado, bike e corrida.", "default_duration_seconds": 7200},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Triathlon"
    assert data["default_duration_seconds"] == 7200


async def test_criar_modalidade_sem_autenticacao_retorna_401(client: AsyncClient):
    response = await client.post(
        "/api/v1/modalities",
        json={"name": "Triathlon"},
    )
    assert response.status_code == 401


async def test_criar_modalidade_como_judge_retorna_403(
    client: AsyncClient, judge_token: str
):
    response = await client.post(
        "/api/v1/modalities",
        json={"name": "Triathlon"},
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 403


async def test_criar_modalidade_nome_duplicado_retorna_409(
    client: AsyncClient, admin_token: str
):
    payload = {"name": "Natação"}
    await client.post(
        "/api/v1/modalities",
        json=payload,
        cookies={"session_id": admin_token},
    )
    response = await client.post(
        "/api/v1/modalities",
        json=payload,
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409


# ── Busca por ID ───────────────────────────────────────────────────────────────

async def test_obter_modalidade_existente_retorna_200(
    client: AsyncClient, admin_token: str
):
    create = await client.post(
        "/api/v1/modalities",
        json={"name": "Rugby"},
        cookies={"session_id": admin_token},
    )
    mod_id = create.json()["id"]
    response = await client.get(f"/api/v1/modalities/{mod_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Rugby"


async def test_obter_modalidade_inexistente_retorna_404(client: AsyncClient):
    response = await client.get("/api/v1/modalities/9999")
    assert response.status_code == 404


# ── Atualização ────────────────────────────────────────────────────────────────

async def test_atualizar_modalidade_como_admin_retorna_200(
    client: AsyncClient, admin_token: str
):
    create = await client.post(
        "/api/v1/modalities",
        json={"name": "Polo Aquático"},
        cookies={"session_id": admin_token},
    )
    mod_id = create.json()["id"]
    response = await client.patch(
        f"/api/v1/modalities/{mod_id}",
        json={"description": "Esporte aquático em equipe."},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Esporte aquático em equipe."


# ── Exclusão ───────────────────────────────────────────────────────────────────

async def test_excluir_modalidade_sem_competicoes_retorna_204(
    client: AsyncClient, admin_token: str
):
    create = await client.post(
        "/api/v1/modalities",
        json={"name": "Levantamento de Peso"},
        cookies={"session_id": admin_token},
    )
    mod_id = create.json()["id"]
    response = await client.delete(
        f"/api/v1/modalities/{mod_id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204


async def test_excluir_modalidade_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    response = await client.delete(
        "/api/v1/modalities/9999",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 404
