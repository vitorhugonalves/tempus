import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition

logger = logging.getLogger(__name__)


class CompetitionRepository:
    """Repositório responsável pelo acesso ao banco de dados para a entidade Competition."""

    @staticmethod
    async def get_by_id(db: AsyncSession, competition_id: int) -> Competition | None:
        """Busca uma competição pelo ID.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: Identificador único da competição.

        Returns:
            Objeto Competition ou None se não encontrado.
        """
        result = await db.execute(select(Competition).where(Competition.id == competition_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[Competition]:
        """Retorna uma lista paginada de competições.

        Args:
            db: Sessão assíncrona do banco de dados.
            skip: Número de registros a pular.
            limit: Número máximo de registros a retornar.

        Returns:
            Lista de objetos Competition.
        """
        result = await db.execute(select(Competition).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, competition: Competition) -> Competition:
        """Persiste uma nova competição no banco de dados.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition: Objeto Competition a ser criado.

        Returns:
            Objeto Competition com ID populado.
        """
        db.add(competition)
        await db.commit()
        await db.refresh(competition)
        logger.info("Competição criada: id=%s, nome=%s", competition.id, competition.name)
        return competition

    @staticmethod
    async def update(db: AsyncSession, competition: Competition) -> Competition:
        """Persiste alterações em uma competição existente.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition: Objeto Competition com dados atualizados.

        Returns:
            Objeto Competition atualizado.
        """
        await db.commit()
        await db.refresh(competition)
        return competition
