"""Testes de integração para endpoints de WodResult."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.category import Category, CategoryType
from app.models.team import Team
from app.models.wod import Wod, WodType


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(
        name="CrossFit Results Test",
        status=CompetitionStatus.active,
        scoring_model="most_points",
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def competition_lowest_time(db: AsyncSession) -> Competition:
    comp = Competition(
        name="Lowest Time Test",
        status=CompetitionStatus.active,
        scoring_model="lowest_time",
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Elite",
        category_type=CategoryType.team,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@pytest.fixture
async def wod(db: AsyncSession, competition: Competition) -> Wod:
    w = Wod(
        competition_id=competition.id,
        name="Fran",
        wod_type=WodType.for_time,
        order=1,
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


@pytest.fixture
async def team(db: AsyncSession, competition: Competition, category: Category) -> Team:
    t = Team(
        competition_id=competition.id,
        name="Alpha",
        category_id=category.id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


# ── GET /wod-results ──────────────────────────────────────────────────────────


async def test_listar_resultados_retorna_estrutura_vazia(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.get(
        f"/api/v1/competitions/{competition.id}/wod-results",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["wods"] == []
    assert data["teams"] == []
    assert data["results"] == []


async def test_listar_resultados_requer_autenticacao(
    client: AsyncClient, competition: Competition
):
    r = await client.get(f"/api/v1/competitions/{competition.id}/wod-results")
    assert r.status_code == 401


# ── POST /wod-results ─────────────────────────────────────────────────────────


async def test_criar_resultado_for_time(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id, "time_seconds": 480},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["time_seconds"] == 480
    assert data["team_id"] == team.id
    assert data["wod_id"] == wod.id


async def test_criar_resultado_reps(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    db: AsyncSession,
    category: Category,
    team: Team,
):
    wod_amrap = Wod(
        competition_id=competition.id,
        name="AMRAP 20",
        wod_type=WodType.amrap,
        order=2,
    )
    db.add(wod_amrap)
    await db.commit()
    await db.refresh(wod_amrap)

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod_amrap.id, "team_id": team.id, "reps": 150},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["reps"] == 150


async def test_upsert_sobrescreve_resultado_existente(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    payload = {"wod_id": wod.id, "team_id": team.id, "time_seconds": 300}

    await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json=payload,
        cookies={"session_id": admin_token},
    )
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={**payload, "time_seconds": 250},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["time_seconds"] == 250

    # Verificar que só existe um resultado
    list_r = await client.get(
        f"/api/v1/competitions/{competition.id}/wod-results",
        cookies={"session_id": admin_token},
    )
    assert len(list_r.json()["results"]) == 1


async def test_sem_time_nem_reps_retorna_422(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 422


async def test_wod_de_outra_competicao_retorna_404(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    db: AsyncSession,
    category: Category,
    team: Team,
):
    other_comp = Competition(name="Outra", status=CompetitionStatus.draft)
    db.add(other_comp)
    await db.commit()
    await db.refresh(other_comp)

    other_wod = Wod(
        competition_id=other_comp.id, name="WOD Outro", wod_type=WodType.for_time, order=1
    )
    db.add(other_wod)
    await db.commit()
    await db.refresh(other_wod)

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": other_wod.id, "team_id": team.id, "time_seconds": 300},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 404


async def test_judge_nao_pode_criar_resultado(
    client: AsyncClient,
    judge_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id, "time_seconds": 300},
        cookies={"session_id": judge_token},
    )
    assert r.status_code == 403


# ── DELETE /wod-results/{id} ──────────────────────────────────────────────────


async def test_deletar_resultado_retorna_204(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id, "time_seconds": 300},
        cookies={"session_id": admin_token},
    )
    result_id = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/competitions/{competition.id}/wod-results/{result_id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 204


async def test_deletar_resultado_inexistente_retorna_404(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.delete(
        f"/api/v1/competitions/{competition.id}/wod-results/99999",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 404


# ── GET /wod-leaderboard ─────────────────────────────────────────────────────


async def test_leaderboard_publico_sem_autenticacao(
    client: AsyncClient, competition: Competition
):
    r = await client.get(f"/api/v1/competitions/{competition.id}/wod-leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data
    assert data["scoring_model"] == "most_points"


async def test_leaderboard_most_points_ordena_corretamente(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    db: AsyncSession,
    category: Category,
):
    wod1 = Wod(
        competition_id=competition.id, name="WOD A", wod_type=WodType.for_time, order=1
    )
    wod2 = Wod(
        competition_id=competition.id, name="WOD B", wod_type=WodType.amrap, order=2
    )
    db.add_all([wod1, wod2])
    team_alpha = Team(competition_id=competition.id, name="Alpha", category_id=category.id)
    team_beta = Team(competition_id=competition.id, name="Beta", category_id=category.id)
    db.add_all([team_alpha, team_beta])
    await db.commit()
    for obj in [wod1, wod2, team_alpha, team_beta]:
        await db.refresh(obj)

    # Alpha: 1º no WOD A (menor tempo), 2º no WOD B (menos reps) → total 3 pts
    # Beta: 2º no WOD A (maior tempo), 1º no WOD B (mais reps) → total 3 pts → empate
    for wod_id, team_id, time_s, reps in [
        (wod1.id, team_alpha.id, 300, None),
        (wod1.id, team_beta.id, 400, None),
        (wod2.id, team_alpha.id, None, 80),
        (wod2.id, team_beta.id, None, 100),
    ]:
        await client.post(
            f"/api/v1/competitions/{competition.id}/wod-results",
            json={"wod_id": wod_id, "team_id": team_id, "time_seconds": time_s, "reps": reps},
            cookies={"session_id": admin_token},
        )

    r = await client.get(f"/api/v1/competitions/{competition.id}/wod-leaderboard")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 2
    # Beta: rank2 FOR_TIME(490pts) + AMRAP 100 reps×10(1000pts) = 1490pts → 1º
    # Alpha: rank1 FOR_TIME(500pts) + AMRAP 80 reps×10(800pts) = 1300pts → 2º
    assert entries[0]["total_points"] == 1490
    assert entries[0]["position"] == 1
    assert entries[0]["team_name"] == "Beta"
    assert entries[1]["total_points"] == 1300
    assert entries[1]["position"] == 2
    assert entries[1]["team_name"] == "Alpha"
