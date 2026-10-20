import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.wod import Wod
from app.repositories.competition import CompetitionRepository
from app.repositories.wod import WodRepository
from app.schemas.wod import WodCreate

logger = logging.getLogger(__name__)


class WodService:
    """Serviço de regras de negócio para WODs."""

    @staticmethod
    async def create_wod(db: AsyncSession, competition_id: int, payload: WodCreate) -> Wod:
        """Cria um novo WOD vinculado a uma competição.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição pai.
            payload: Dados do WOD a ser criado.

        Returns:
            Objeto Wod criado.

        Raises:
            HTTPException 404: Se a competição não existir.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if competition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competição não encontrada",
            )
        wod = Wod(competition_id=competition_id, **payload.model_dump(exclude={"category_ids"}))
        if payload.category_ids:
            result = await db.execute(
                select(Category).where(Category.id.in_(payload.category_ids))
            )
            wod.categories = list(result.scalars().all())
        return await WodRepository.create(db, wod)

    @staticmethod
    async def list_wods(db: AsyncSession, competition_id: int) -> list[Wod]:
        """Lista WODs de uma competição ordenados por order.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição.

        Returns:
            Lista de WODs.

        Raises:
            HTTPException 404: Se a competição não existir.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if competition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competição não encontrada",
            )
        return await WodRepository.list_by_competition(db, competition_id)

    @staticmethod
    async def delete_wod(db: AsyncSession, competition_id: int, wod_id: int) -> None:
        """Remove um WOD, verificando que pertence à competição informada.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição.
            wod_id: ID do WOD a ser removido.

        Raises:
            HTTPException 404: Se o WOD não existir ou não pertencer à competição.
        """
        wod = await WodRepository.get_by_id(db, wod_id)
        if wod is None or wod.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WOD não encontrado",
            )
        await WodRepository.delete(db, wod)
