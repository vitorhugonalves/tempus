"""Categoria no ranking de timers.

Timers criados pelas baterias (`HeatService.start_all`/`start_team`) não recebem
`category_id` — a categoria vive na equipe (`Team.category_id`, obrigatório).
O ranking precisa exibir e filtrar pela categoria da equipe.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.competition import Competition
from app.models.team import Team
from app.models.timer import Timer


async def _seed_two_categories(db: AsyncSession) -> tuple[int, int, int]:
    """Competição com duas categorias e uma equipe (com timer sem categoria) em cada."""
    competition = Competition(name="Comp Categorias")
    db.add(competition)
    await db.flush()

    rx = Category(competition_id=competition.id, name="RX")
    scaled = Category(competition_id=competition.id, name="Scaled")
    db.add_all([rx, scaled])
    await db.flush()

    team_rx = Team(competition_id=competition.id, category_id=rx.id, name="Equipe RX")
    team_scaled = Team(
        competition_id=competition.id, category_id=scaled.id, name="Equipe Scaled"
    )
    db.add_all([team_rx, team_scaled])
    await db.flush()

    # Igual ao HeatService: timer de equipe sem category_id
    db.add_all(
        [
            Timer(competition_id=competition.id, team_id=team_rx.id),
            Timer(competition_id=competition.id, team_id=team_scaled.id),
        ]
    )
    await db.flush()
    return competition.id, rx.id, scaled.id


async def test_ranking_team_timer_without_category_shows_team_category(
    client: AsyncClient, db: AsyncSession
):
    comp_id, _, _ = await _seed_two_categories(db)

    entries = (await client.get(f"/api/v1/competitions/{comp_id}/ranking")).json()

    names = {e["team_name"]: e["category_name"] for e in entries}
    assert names == {"Equipe RX": "RX", "Equipe Scaled": "Scaled"}


async def test_ranking_filter_by_category_uses_team_category(
    client: AsyncClient, db: AsyncSession
):
    comp_id, rx_id, _ = await _seed_two_categories(db)

    entries = (
        await client.get(
            f"/api/v1/competitions/{comp_id}/ranking", params={"category_id": rx_id}
        )
    ).json()

    assert [e["team_name"] for e in entries] == ["Equipe RX"]


async def test_crossfit_ranking_filter_by_category_uses_team_category(
    client: AsyncClient, db: AsyncSession
):
    comp_id, _, scaled_id = await _seed_two_categories(db)

    entries = (
        await client.get(
            f"/api/v1/competitions/{comp_id}/crossfit-ranking",
            params={"category_id": scaled_id},
        )
    ).json()

    assert [(e["team_name"], e["category_name"]) for e in entries] == [
        ("Equipe Scaled", "Scaled")
    ]


async def _finished_timer(
    db: AsyncSession, competition_id: int, team_id: int, seconds: int
) -> None:
    """Timer de equipe finalizado com `seconds` de tempo acumulado."""
    from datetime import datetime

    from app.models.timer import TimerEvent, TimerEventType, TimerStatus

    timer = Timer(
        competition_id=competition_id, team_id=team_id, status=TimerStatus.finished
    )
    db.add(timer)
    await db.flush()
    db.add(
        TimerEvent(
            timer_id=timer.id,
            event_type=TimerEventType.finished,
            event_at=datetime(2026, 1, 1),
            accumulated_ms=seconds * 1000,
        )
    )
    await db.flush()


async def test_ranking_general_sorted_by_category_with_overall_position(
    client: AsyncClient, db: AsyncSession
):
    competition = Competition(name="Comp Ordenada")
    db.add(competition)
    await db.flush()
    scaled = Category(competition_id=competition.id, name="Scaled")
    rx = Category(competition_id=competition.id, name="RX")
    db.add_all([scaled, rx])
    await db.flush()

    # Scaled tem o tempo mais rápido, mas RX vem antes (ordem alfabética)
    times = [
        ("Scaled Rápida", scaled, 1000),
        ("RX Lenta", rx, 3000),
        ("RX Rápida", rx, 2000),
        ("Scaled Lenta", scaled, 4000),
    ]
    for name, category, seconds in times:
        team = Team(competition_id=competition.id, category_id=category.id, name=name)
        db.add(team)
        await db.flush()
        await _finished_timer(db, competition.id, team.id, seconds)

    entries = (
        await client.get(f"/api/v1/competitions/{competition.id}/ranking")
    ).json()

    assert [(e["position"], e["team_name"], e["category_name"]) for e in entries] == [
        (1, "RX Rápida", "RX"),
        (2, "RX Lenta", "RX"),
        (3, "Scaled Rápida", "Scaled"),
        (4, "Scaled Lenta", "Scaled"),
    ]
