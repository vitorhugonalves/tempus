import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wod import Wod

logger = logging.getLogger(__name__)


class WodRepository:
    """Repositório de acesso ao banco para a entidade Wod."""

    @staticmethod
    async def get_by_id(db: AsyncSession, wod_id: int) -> Wod | None:
        """Busca um WOD pelo ID.

        Args:
            db: Sessão assíncrona do banco de dados.
            wod_id: Identificador único do WOD.

        Returns:
            Objeto Wod ou None se não encontrado.
        """
        result = await db.execute(select(Wod).where(Wod.id == wod_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_competition(db: AsyncSession, competition_id: int) -> list[Wod]:
        """Lista todos os WODs de uma competição ordenados por `order`.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição.

        Returns:
            Lista de objetos Wod.
        """
        result = await db.execute(
            select(Wod)
            .where(Wod.competition_id == competition_id)
            .order_by(Wod.order)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, wod: Wod) -> Wod:
        """Persiste um novo WOD no banco de dados.

        Args:
            db: Sessão assíncrona do banco de dados.
            wod: Objeto Wod a ser criado.

        Returns:
            Objeto Wod com ID populado.
        """
        db.add(wod)
        await db.flush()
        await db.refresh(wod)
        logger.info("WOD criado: id=%s competition_id=%s", wod.id, wod.competition_id)
        return wod

    @staticmethod
    async def delete(db: AsyncSession, wod: Wod) -> None:
        """Remove um WOD do banco de dados.

        Args:
            db: Sessão assíncrona do banco de dados.
            wod: Objeto Wod a ser removido.
        """
        await db.delete(wod)
        await db.flush()
        logger.info("WOD removido: id=%s", wod.id)
