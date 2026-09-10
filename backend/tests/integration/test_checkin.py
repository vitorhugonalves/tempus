"""Testes de integração para o fluxo de check-in (unificação Athlete/User)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryType
from app.models.competition import Competition, CompetitionStatus


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Checkin", status=CompetitionStatus.active)
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


async def test_busca_encontra_atleta_importado_em_massa(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Carlos Bulk", "category_id": category.id},
        cookies={"session_id": admin_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search?q=Carlos",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["kind"] == "athlete"
    assert results[0]["has_athlete_record"] is True


async def test_busca_encontra_inscricao_online_sem_atleta_ainda(
    client: AsyncClient,
    admin_token: str,
    competitor_token: str,
    competition: Competition,
    category: Category,
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search?q=Competidor",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["kind"] == "registration"
    assert results[0]["has_athlete_record"] is False


async def test_ensure_athlete_cria_atleta_a_partir_de_inscricao_online(
    client: AsyncClient,
    admin_token: str,
    competitor_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    from sqlalchemy import select

    from app.models.competitor import CompetitorRegistration

    reg_r = await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )
    team_id = reg_r.json()["team_id"]

    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.competition_id == competition.id
        )
    )
    registration = result.scalar_one()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["team_id"] == team_id
    assert data["name"] == "Competidor Teste"

    # Idempotente: chamar de novo não cria um segundo Athlete
    r2 = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]


async def test_ensure_athlete_com_kind_athlete_retorna_o_proprio(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Ja Existe", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "athlete", "source_id": athlete_id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json()["id"] == athlete_id
