from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modality import Modality


class ModalityRepository:
    """Acesso ao banco para modalidades."""

    @staticmethod
    async def get_all(db: AsyncSession) -> list[Modality]:
        """Lista todas as modalidades.

        Args:
            db: Sessão assíncrona.

        Returns:
            Lista de Modality ordenada por nome.
        """
        result = await db.execute(select(Modality).order_by(Modality.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, modality_id: int) -> Modality | None:
        """Retorna modalidade pelo ID.

        Args:
            db: Sessão assíncrona.
            modality_id: ID da modalidade.

        Returns:
            Modality ou None.
        """
        result = await db.execute(
            select(Modality).where(Modality.id == modality_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Modality | None:
        """Retorna modalidade pelo nome (case-insensitive).

        Args:
            db: Sessão assíncrona.
            name: Nome da modalidade.

        Returns:
            Modality ou None.
        """
        result = await db.execute(
            select(Modality).where(Modality.name.ilike(name))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, modality: Modality) -> Modality:
        """Persiste uma nova modalidade.

        Args:
            db: Sessão assíncrona.
            modality: Instância ORM não persistida.

        Returns:
            Modality criada.
        """
        db.add(modality)
        await db.flush()
        await db.refresh(modality)
        return modality

    @staticmethod
    async def update(db: AsyncSession, modality: Modality) -> Modality:
        """Persiste alterações em uma modalidade.

        Args:
            db: Sessão assíncrona.
            modality: Instância ORM modificada.

        Returns:
            Modality atualizada.
        """
        await db.flush()
        await db.refresh(modality)
        return modality

    @staticmethod
    async def delete(db: AsyncSession, modality: Modality) -> None:
        """Remove uma modalidade.

        Args:
            db: Sessão assíncrona.
            modality: Instância ORM a remover.
        """
        await db.delete(modality)
        await db.flush()
