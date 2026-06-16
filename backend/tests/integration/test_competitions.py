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
            "event_type": "hyrox",
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


async def test_criar_competicao_com_event_type_retorna_201(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/competitions",
        json={"name": "Hyrox SP 2026", "event_type": "hyrox"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "hyrox"
    assert data["is_public"] is False
    assert "start_date" in data
    assert "end_date" in data
    assert "max_athletes" not in data
    assert "modality_id" not in data
    assert "rules" not in data


async def test_criar_competicao_crossfit_retorna_201(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/competitions",
        json={"name": "CrossFit Open 2026", "event_type": "crossfit", "scoring_model": "most_points"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "crossfit"
    assert data["scoring_model"] == "most_points"
