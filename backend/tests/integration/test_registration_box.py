"""Testes de integração para o campo box_name na inscrição de equipes."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryType
from app.models.competition import Competition, CompetitionStatus
from app.models.team import Team


@pytest.fixture
async def active_comp(db: AsyncSession) -> Competition:
    """Competição ativa para testes de inscrição."""
    comp = Competition(
        name="Competição Box Test",
        status=CompetitionStatus.active,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def individual_cat(db: AsyncSession, active_comp: Competition) -> Category:
    """Categoria individual para testes."""
    cat = Category(
        competition_id=active_comp.id,
        name="Individual",
        category_type=CategoryType.individual,
        max_team_size=1,
        is_active=True,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@pytest.fixture
async def team_cat(db: AsyncSession, active_comp: Competition) -> Category:
    """Categoria de equipe para testes."""
    cat = Category(
        competition_id=active_comp.id,
        name="Dupla",
        category_type=CategoryType.team,
        max_team_size=2,
        is_active=True,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@pytest.mark.asyncio
async def test_register_individual_with_box_name_persists_field(
    client: AsyncClient,
    competitor_token: str,
    active_comp: Competition,
    individual_cat: Category,
    db: AsyncSession,
):
    """box_name enviado na inscrição individual é persistido na tabela teams."""
    response = await client.post(
        f"/api/v1/competitions/{active_comp.id}/register",
        json={
            "category_id": individual_cat.id,
            "box_name": "CrossFit Test Box",
        },
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 201
    data = response.json()
    team_id = data["team_id"]

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    assert team is not None
    assert team.box_name == "CrossFit Test Box"


@pytest.mark.asyncio
async def test_register_without_box_name_defaults_to_null(
    client: AsyncClient,
    competitor_token: str,
    active_comp: Competition,
    individual_cat: Category,
    db: AsyncSession,
):
    """box_name omitido na inscrição resulta em NULL na tabela teams."""
    response = await client.post(
        f"/api/v1/competitions/{active_comp.id}/register",
        json={"category_id": individual_cat.id},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 201
    team_id = response.json()["team_id"]

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    assert team is not None
    assert team.box_name is None


@pytest.mark.asyncio
async def test_register_team_with_box_name_persists_field(
    client: AsyncClient,
    competitor_token: str,
    active_comp: Competition,
    team_cat: Category,
    db: AsyncSession,
):
    """box_name enviado na inscrição de equipe é persistido na tabela teams."""
    response = await client.post(
        f"/api/v1/competitions/{active_comp.id}/register",
        json={
            "category_id": team_cat.id,
            "team_name": "Equipe Testadora",
            "box_name": "Box Exemplo",
            "additional_members": [],
        },
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 201
    team_id = response.json()["team_id"]

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    assert team is not None
    assert team.box_name == "Box Exemplo"


@pytest.mark.asyncio
async def test_register_box_name_too_long_returns_422(
    client: AsyncClient,
    competitor_token: str,
    active_comp: Competition,
    individual_cat: Category,
):
    """box_name com mais de 200 caracteres retorna 422."""
    response = await client.post(
        f"/api/v1/competitions/{active_comp.id}/register",
        json={
            "category_id": individual_cat.id,
            "box_name": "X" * 201,
        },
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 422
