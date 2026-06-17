"""Testes de integração para categorias (RF-20 a RF-22)."""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def competition(client: AsyncClient, admin_token: str) -> dict:
    """Cria uma competição de teste."""
    response = await client.post(
        "/api/v1/competitions",
        json={"name": "Competição Teste"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    return response.json()


async def test_listar_categorias_vazia_retorna_200(client: AsyncClient, competition: dict):
    """RF-20: Listar categorias de competição sem categorias retorna lista vazia."""
    response = await client.get(f"/api/v1/competitions/{competition['id']}/categories")
    assert response.status_code == 200
    assert response.json() == []


async def test_criar_categoria_individual_como_admin(
    client: AsyncClient, competition: dict, admin_token: str
):
    """RF-20, RF-21: Criar categoria individual."""
    response = await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Elite Masculino", "category_type": "individual"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Elite Masculino"
    assert data["category_type"] == "individual"
    assert data["is_active"] is True


async def test_criar_categoria_equipe_sem_max_team_size_retorna_422(
    client: AsyncClient, competition: dict, admin_token: str
):
    """RF-21: Categoria de equipe exige max_team_size."""
    response = await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Equipe Mista", "category_type": "team"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 422


async def test_criar_categoria_equipe_com_max_team_size(
    client: AsyncClient, competition: dict, admin_token: str
):
    """RF-21: Categoria de equipe com max_team_size válido."""
    response = await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Equipe Mista", "category_type": "team", "max_team_size": 4},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    assert response.json()["max_team_size"] == 4


async def test_criar_categoria_como_competidor_retorna_403(
    client: AsyncClient, competition: dict, competitor_token: str
):
    """RF-20: Competidor não pode criar categorias."""
    response = await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Elite", "category_type": "individual"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_listar_categorias_retorna_lista(
    client: AsyncClient, competition: dict, admin_token: str
):
    """RF-22: Categorias listadas pertencem à competição."""
    # Cria duas categorias
    await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Elite Masculino", "category_type": "individual"},
        cookies={"session_id": admin_token},
    )
    await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Master 40+", "category_type": "individual"},
        cookies={"session_id": admin_token},
    )

    response = await client.get(f"/api/v1/competitions/{competition['id']}/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {c["name"] for c in data}
    assert "Elite Masculino" in names
    assert "Master 40+" in names


async def test_desativar_categoria(
    client: AsyncClient, competition: dict, admin_token: str
):
    """RF-20: Desativar categoria não remove do banco."""
    create_resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Temporária", "category_type": "individual"},
        cookies={"session_id": admin_token},
    )
    cat_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/competitions/{competition['id']}/categories/{cat_id}",
        cookies={"session_id": admin_token},
    )
    assert del_resp.status_code == 204

    # Categoria ainda existe mas inativa
    list_all = await client.get(f"/api/v1/competitions/{competition['id']}/categories")
    assert any(c["id"] == cat_id and not c["is_active"] for c in list_all.json())

    # Filtro only_active oculta
    list_active = await client.get(
        f"/api/v1/competitions/{competition['id']}/categories?only_active=true"
    )
    assert not any(c["id"] == cat_id for c in list_active.json())


async def test_clonar_competicao_copia_categorias(
    client: AsyncClient, competition: dict, admin_token: str
):
    """RF-19: Clonar competição copia categorias."""
    await client.post(
        f"/api/v1/competitions/{competition['id']}/categories",
        json={"name": "Elite Masculino", "category_type": "individual"},
        cookies={"session_id": admin_token},
    )

    clone_resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/clone",
        cookies={"session_id": admin_token},
    )
    assert clone_resp.status_code == 201
    clone = clone_resp.json()
    assert clone["status"] == "draft"
    assert "(cópia)" in clone["name"]

    cats_clone = await client.get(f"/api/v1/competitions/{clone['id']}/categories")
    assert len(cats_clone.json()) == 1
    assert cats_clone.json()[0]["name"] == "Elite Masculino"


async def test_criar_categoria_com_genero_retorna_201(
    client: AsyncClient, admin_token: str
):
    comp_r = await client.post(
        "/api/v1/competitions",
        json={"name": "Comp Gênero"},
        cookies={"session_id": admin_token},
    )
    comp_id = comp_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{comp_id}/categories",
        json={
            "name": "Elite Feminino",
            "category_type": "individual",
            "gender": "female",
        },
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["gender"] == "female"
    assert data["age_restriction_enabled"] is False
    assert data["age_min"] is None


async def test_criar_categoria_com_restricao_etaria(
    client: AsyncClient, admin_token: str
):
    comp_r = await client.post(
        "/api/v1/competitions",
        json={"name": "Comp Etária"},
        cookies={"session_id": admin_token},
    )
    comp_id = comp_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{comp_id}/categories",
        json={
            "name": "Master 40+",
            "category_type": "individual",
            "age_restriction_enabled": True,
            "age_min": 40,
        },
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["age_restriction_enabled"] is True
    assert data["age_min"] == 40
    assert data["age_max"] is None
