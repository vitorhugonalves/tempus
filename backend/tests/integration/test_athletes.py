"""Testes de integração para CRUD de atletas."""
import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.category import Category, CategoryType


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Atletas", status=CompetitionStatus.active)
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Elite",
        category_type=CategoryType.individual,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


# ── Testes CRUD ───────────────────────────────────────────────────────────────


async def test_listar_atletas_vazio_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_criar_atleta_retorna_201(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={
            "name": "Carlos Mendes",
            "email": "carlos@example.com",
            "category_id": category.id,
        },
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Carlos Mendes"
    assert data["email"] == "carlos@example.com"
    assert data["competition_id"] == competition.id
    assert data["category_id"] == category.id


async def test_criar_atleta_campos_minimos(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Ana Lima"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Ana Lima"


async def test_editar_atleta_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "João Silva"},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"name": "João P. Silva", "phone": "(11)99999-0000"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "João P. Silva"
    assert data["phone"] == "(11)99999-0000"


async def test_remover_atleta_retorna_204(
    client: AsyncClient, admin_token: str, competition: Competition
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Maria Costa"},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 204

    list_r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    assert all(a["id"] != athlete_id for a in list_r.json())


async def test_competidor_nao_pode_criar_atleta(
    client: AsyncClient, competitor_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Intruso"},
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403


async def test_listar_atletas_filtra_por_categoria(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Com Categoria", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Sem Categoria"},
        cookies={"session_id": admin_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes?category_id={category.id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Com Categoria"


async def test_importar_atletas_csv_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome,email,documento,telefone,categoria,tamanho_camiseta\n"
        f"Pedro Alves,pedro@example.com,123.456.789-00,(11)91111-2222,{category.name},M\n"
        "Rita Souza,,,,,"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []


async def test_importar_atletas_csv_sem_nome_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition
):
    csv_content = b"nome,email\n,pedro@example.com"

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 1
