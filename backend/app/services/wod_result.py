import logging
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wod import Wod, WodType
from app.models.wod_result import WodResult
from app.repositories.competition import CompetitionRepository
from app.repositories.team import TeamRepository
from app.repositories.wod import WodRepository
from app.repositories.wod_result import WodResultRepository
from app.schemas.wod import WodResponse
from app.schemas.wod_result import (
    LeaderboardWodEntry,
    TeamSimple,
    WodLeaderboard,
    WodLeaderboardEntry,
    WodResultResponse,
    WodResultsData,
    WodResultUpsert,
)

logger = logging.getLogger(__name__)


def _compute_leaderboard(
    scoring_model: str | None,
    wods: Sequence[Wod],
    teams: Sequence,
    results: Sequence[WodResult],
) -> WodLeaderboard:
    """Calcula o leaderboard a partir de resultados brutos.

    Args:
        scoring_model: 'most_points', 'lowest_time' ou None.
        wods: WODs da competição em ordem.
        teams: Equipes da competição (precisam ter category_id).
        results: Resultados cadastrados.

    Returns:
        WodLeaderboard com entries ordenados por posição.
    """
    if not wods or not teams:
        return WodLeaderboard(scoring_model=scoring_model, entries=[])

    result_map: dict[tuple[int, int], WodResult] = {
        (r.wod_id, r.team_id): r for r in results
    }

    # Pré-computar categorias por WOD
    wod_cat_ids: dict[int, set[int]] = {
        wod.id: {c.id for c in wod.categories} for wod in wods
    }

    # Rankear equipes dentro de cada WOD (apenas participantes do WOD)
    wod_rank_map: dict[int, dict[int, tuple[int, int]]] = {}
    for wod in wods:
        cat_ids = wod_cat_ids[wod.id]
        participating = [t for t in teams if not cat_ids or t.category_id in cat_ids]
        n_participating = len(participating)

        team_results = [
            (t.id, result_map[(wod.id, t.id)])
            for t in participating
            if (wod.id, t.id) in result_map
        ]

        if wod.wod_type == WodType.for_time:
            team_results.sort(
                key=lambda x: (x[1].time_seconds is None, x[1].time_seconds or 0)
            )
        else:
            team_results.sort(
                key=lambda x: (x[1].reps is None, -(x[1].reps or 0))
            )

        wod_ranks: dict[int, tuple[int, int]] = {}
        prev_key = None
        current_rank = 0
        for i, (team_id, r) in enumerate(team_results):
            if wod.wod_type == WodType.for_time:
                sort_key = r.time_seconds
            else:
                sort_key = r.reps
            if sort_key != prev_key:
                current_rank = i + 1
            prev_key = sort_key
            points = n_participating + 1 - current_rank
            wod_ranks[team_id] = (current_rank, points)
        wod_rank_map[wod.id] = wod_ranks

    # Calcular total por equipe
    team_totals = []
    for team in teams:
        wod_entries = []
        total = 0
        has_missing = False

        for wod in wods:
            cat_ids = wod_cat_ids[wod.id]
            participates = not cat_ids or team.category_id in cat_ids

            if not participates:
                wod_entries.append(
                    LeaderboardWodEntry(
                        wod_id=wod.id,
                        wod_name=wod.name,
                        time_seconds=None,
                        reps=None,
                        points=0,
                        rank=None,
                    )
                )
                continue

            r = result_map.get((wod.id, team.id))
            rank_info = wod_rank_map.get(wod.id, {}).get(team.id)
            rank = rank_info[0] if rank_info else None
            points = rank_info[1] if rank_info else 0

            if scoring_model == "lowest_time":
                if r and r.time_seconds is not None:
                    total += r.time_seconds
                else:
                    has_missing = True
            else:
                total += points

            wod_entries.append(
                LeaderboardWodEntry(
                    wod_id=wod.id,
                    wod_name=wod.name,
                    time_seconds=r.time_seconds if r else None,
                    reps=r.reps if r else None,
                    points=points,
                    rank=rank,
                )
            )

        team_totals.append(
            {
                "team_id": team.id,
                "team_name": team.name,
                "total": total,
                "has_missing": has_missing,
                "wod_entries": wod_entries,
            }
        )

    # Ordenar
    if scoring_model == "lowest_time":
        team_totals.sort(
            key=lambda x: (x["has_missing"], x["total"], x["team_name"])
        )
    else:
        team_totals.sort(key=lambda x: (-x["total"], x["team_name"]))

    # Atribuir posições com suporte a empates
    entries: list[WodLeaderboardEntry] = []
    prev_total: int | None = None
    prev_missing: bool | None = None
    current_pos = 0

    for i, t in enumerate(team_totals):
        if t["total"] != prev_total or t["has_missing"] != prev_missing:
            current_pos = i + 1
        prev_total = t["total"]
        prev_missing = t["has_missing"]

        entries.append(
            WodLeaderboardEntry(
                position=current_pos,
                team_id=t["team_id"],
                team_name=t["team_name"],
                total_points=t["total"],
                wod_entries=t["wod_entries"],
            )
        )

    return WodLeaderboard(scoring_model=scoring_model, entries=entries)


class WodResultService:
    """Serviço de regras de negócio para resultados de WOD."""

    @staticmethod
    async def get_results_data(
        db: AsyncSession, competition_id: int
    ) -> WodResultsData:
        """Retorna WODs, equipes e resultados para a página de entrada.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            WodResultsData com wods, teams e results.
        """
        wods = await WodRepository.list_by_competition(db, competition_id)
        teams = await TeamRepository.get_by_competition(db, competition_id)
        results = await WodResultRepository.get_by_competition(db, competition_id)

        return WodResultsData(
            wods=[WodResponse.model_validate(w) for w in wods],
            teams=[TeamSimple.model_validate(t) for t in teams],
            results=[WodResultResponse.model_validate(r) for r in results],
        )

    @staticmethod
    async def upsert(
        db: AsyncSession, competition_id: int, data: WodResultUpsert
    ) -> WodResult:
        """Cria ou atualiza um resultado para um par (wod_id, team_id).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: Payload de upsert.

        Returns:
            WodResult persistido.

        Raises:
            HTTPException 404: WOD ou equipe não pertencem à competição.
        """
        wod = await WodRepository.get_by_id(db, data.wod_id)
        if not wod or wod.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WOD não encontrado nesta competição",
            )

        team = await TeamRepository.get_by_id(db, data.team_id)
        if not team or team.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipe não encontrada nesta competição",
            )

        existing = await WodResultRepository.get_by_wod_and_team(
            db, data.wod_id, data.team_id
        )
        if existing:
            existing.time_seconds = data.time_seconds
            existing.reps = data.reps
            existing.notes = data.notes
            await db.flush()
            await db.refresh(existing)
            return existing

        new_result = WodResult(
            competition_id=competition_id,
            wod_id=data.wod_id,
            team_id=data.team_id,
            time_seconds=data.time_seconds,
            reps=data.reps,
            notes=data.notes,
        )
        return await WodResultRepository.create(db, new_result)

    @staticmethod
    async def delete(
        db: AsyncSession, competition_id: int, result_id: int
    ) -> None:
        """Remove um resultado.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição (para validar posse).
            result_id: ID do resultado a remover.

        Raises:
            HTTPException 404: Resultado não encontrado.
        """
        result = await WodResultRepository.get_by_id(db, result_id)
        if not result or result.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resultado não encontrado",
            )
        await WodResultRepository.delete(db, result)

    @staticmethod
    async def compute_leaderboard(
        db: AsyncSession, competition_id: int
    ) -> WodLeaderboard:
        """Calcula o leaderboard de WOD results para uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            WodLeaderboard com entries ordenados por posição.
        """
        comp = await CompetitionRepository.get_by_id(db, competition_id)
        if not comp:
            return WodLeaderboard(scoring_model=None, entries=[])

        wods = await WodRepository.list_by_competition(db, competition_id)
        teams = await TeamRepository.get_by_competition(db, competition_id)
        results = await WodResultRepository.get_by_competition(db, competition_id)

        return _compute_leaderboard(comp.scoring_model, wods, teams, results)
