import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wod_result import WodResult

logger = logging.getLogger(__name__)


class WodResultRepository:
    """Repositório de acesso ao banco para a entidade WodResult."""

    @staticmethod
    async def get_by_competition(
        db: AsyncSession, competition_id: int
    ) -> list[WodResult]:
        """Lista todos os resultados de uma competição."""
        result = await db.execute(
            select(WodResult).where(WodResult.competition_id == competition_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, result_id: int) -> WodResult | None:
        """Busca um resultado pelo ID."""
        result = await db.execute(
            select(WodResult).where(WodResult.id == result_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_wod_and_team(
        db: AsyncSession, wod_id: int, team_id: int
    ) -> WodResult | None:
        """Busca resultado pelo par (wod_id, team_id)."""
        result = await db.execute(
            select(WodResult)
            .where(WodResult.wod_id == wod_id)
            .where(WodResult.team_id == team_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, wod_result: WodResult) -> WodResult:
        """Persiste um novo resultado."""
        db.add(wod_result)
        await db.flush()
        await db.refresh(wod_result)
        logger.info(
            "WodResult criado: id=%s wod_id=%s team_id=%s",
            wod_result.id,
            wod_result.wod_id,
            wod_result.team_id,
        )
        return wod_result

    @staticmethod
    async def delete(db: AsyncSession, wod_result: WodResult) -> None:
        """Remove um resultado."""
        await db.delete(wod_result)
        await db.flush()
        logger.info("WodResult removido: id=%s", wod_result.id)
