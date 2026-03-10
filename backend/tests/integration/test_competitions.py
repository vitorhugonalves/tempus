import pytest
from httpx import AsyncClient


async def test_listar_competicoes_sem_autenticacao_retorna_200(client: AsyncClient):
    response = await client.get("/api/v1/competitions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_criar_competicao_como_admin_retorna_201(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/competitions",
        json={
            "name": "Hyrox São Paulo 2026",
            "location": "São Paulo, SP",
            "modality": "Hyrox",
            "max_athletes": 200,
        },
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Hyrox São Paulo 2026"
    assert data["status"] == "draft"


async def test_criar_competicao_como_competidor_retorna_403(
    client: AsyncClient, competitor_token: str
):
    response = await client.post(
        "/api/v1/competitions",
        json={"name": "Competição Não Permitida"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_buscar_competicao_inexistente_retorna_404(client: AsyncClient):
    response = await client.get("/api/v1/competitions/99999")
    assert response.status_code == 404


async def test_health_check_retorna_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
