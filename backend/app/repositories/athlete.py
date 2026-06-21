import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.athlete import Athlete

logger = logging.getLogger(__name__)


class AthleteRepository:
    """Repositório para a entidade Athlete."""

    @staticmethod
    async def get_by_id(db: AsyncSession, athlete_id: int) -> Athlete | None:
        """Busca atleta pelo ID.

        Args:
            db: Sessão assíncrona.
            athlete_id: ID do atleta.

        Returns:
            Objeto Athlete ou None.
        """
        result = await db.execute(
            select(Athlete).options(selectinload(Athlete.team)).where(Athlete.id == athlete_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_competition(
        db: AsyncSession,
        competition_id: int,
        category_id: int | None = None,
        team_id: int | None = None,
    ) -> list[Athlete]:
        """Lista atletas de uma competição com filtros opcionais.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro opcional por categoria.
            team_id: Filtro opcional por equipe.

        Returns:
            Lista de atletas.
        """
        stmt = (
            select(Athlete)
            .options(selectinload(Athlete.team))
            .where(Athlete.competition_id == competition_id)
        )
        if category_id is not None:
            stmt = stmt.where(Athlete.category_id == category_id)
        if team_id is not None:
            stmt = stmt.where(Athlete.team_id == team_id)
        stmt = stmt.order_by(Athlete.name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, athlete: Athlete) -> Athlete:
        """Persiste um novo atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a criar.

        Returns:
            Athlete com ID populado.
        """
        db.add(athlete)
        await db.flush()
        await db.refresh(athlete)
        return athlete

    @staticmethod
    async def update(db: AsyncSession, athlete: Athlete) -> Athlete:
        """Persiste alterações em um atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete com dados atualizados.

        Returns:
            Athlete atualizado.
        """
        await db.flush()
        await db.refresh(athlete)
        return athlete

    @staticmethod
    async def delete(db: AsyncSession, athlete: Athlete) -> None:
        """Remove um atleta do banco.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a remover.
        """
        await db.delete(athlete)
        await db.flush()
