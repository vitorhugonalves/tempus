"""Testes de integração para importação CSV de equipes."""
import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.category import Category, CategoryType


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Equipes CSV", status=CompetitionStatus.active)
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Masters",
        category_type=CategoryType.team,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def test_importar_equipes_csv_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome_equipe;categoria\n"
        f"Thunder Force;{category.name}\n"
        f"Iron Squad;{category.name}\n"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []


async def test_importar_equipes_csv_categoria_invalida_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome_equipe;categoria\n"
        "Equipe Valida;{}\n".format(category.name) +
        "Equipe Invalida;CategoriaInexistente\n"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 2


async def test_importar_equipes_csv_nome_vazio_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome_equipe;categoria\n"
        f";{category.name}\n"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1


async def test_importar_equipes_csv_duplicata_ignorada(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    """Equipe com mesmo nome já existente é pulada silenciosamente."""
    # importar duas vezes o mesmo CSV
    csv_content = (
        "nome_equipe;categoria\n"
        f"Única Equipe;{category.name}\n"
    ).encode("utf-8")

    await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    r2 = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    data = r2.json()
    assert data["created"] == 0  # já existia, pulada
    assert data["errors"] == []


async def test_importar_equipes_csv_requer_autenticacao(
    client: AsyncClient, competition: Competition
):
    csv_content = b"nome_equipe;categoria\nTime X;Elite\n"
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert r.status_code == 401


async def test_importar_equipes_csv_competidor_retorna_403(
    client: AsyncClient, competitor_token: str, competition: Competition
):
    csv_content = b"nome_equipe;categoria\nTime X;Elite\n"
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403
