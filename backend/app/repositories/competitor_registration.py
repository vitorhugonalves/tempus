from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.competitor import CompetitorRegistration
from app.models.user import User


class CompetitorRegistrationRepository:
    """Acesso ao banco para inscrições de competidores autoinscritos."""

    @staticmethod
    async def search(
        db: AsyncSession, competition_id: int, query: str
    ) -> list[CompetitorRegistration]:
        """Busca inscrições de uma competição por nome ou e-mail do usuário.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            query: Termo de busca (case-insensitive, aplicado a nome e e-mail).

        Returns:
            Lista de CompetitorRegistration com `.user` carregado.
        """
        like = f"%{query.lower()}%"
        result = await db.execute(
            select(CompetitorRegistration)
            .join(User)
            .options(selectinload(CompetitorRegistration.user))
            .where(
                CompetitorRegistration.competition_id == competition_id,
                (User.full_name.ilike(like)) | (User.email.ilike(like)),
            )
            .order_by(User.full_name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        db: AsyncSession, registration_id: int
    ) -> CompetitorRegistration | None:
        """Busca uma inscrição pelo ID, com usuário carregado.

        Args:
            db: Sessão assíncrona.
            registration_id: ID da inscrição.

        Returns:
            CompetitorRegistration ou None.
        """
        result = await db.execute(
            select(CompetitorRegistration)
            .options(selectinload(CompetitorRegistration.user))
            .where(CompetitorRegistration.id == registration_id)
        )
        return result.scalar_one_or_none()
