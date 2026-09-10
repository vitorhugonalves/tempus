"""Repositório para ConsentTerm (singleton por competição)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent_term import ConsentTerm


class ConsentTermRepository:
    """Acesso ao banco para termos de consentimento."""

    @staticmethod
    async def get_by_competition_id(
        db: AsyncSession, competition_id: int
    ) -> ConsentTerm | None:
        """Busca o termo de consentimento de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            ConsentTerm ou None se a competição não possui termo cadastrado.
        """
        result = await db.execute(
            select(ConsentTerm).where(ConsentTerm.competition_id == competition_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        competition_id: int,
        file_data: bytes,
        file_name: str,
        file_hash: str,
    ) -> ConsentTerm:
        """Cria ou substitui o termo de consentimento de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            file_data: Bytes do PDF.
            file_name: Nome original do arquivo.
            file_hash: Hash SHA-256 do conteúdo do arquivo.

        Returns:
            ConsentTerm persistido (criado ou atualizado).
        """
        existing = await ConsentTermRepository.get_by_competition_id(db, competition_id)
        if existing:
            existing.file_data = file_data
            existing.file_name = file_name
            existing.file_hash = file_hash
            await db.flush()
            await db.refresh(existing)
            return existing

        term = ConsentTerm(
            competition_id=competition_id,
            file_data=file_data,
            file_name=file_name,
            file_hash=file_hash,
        )
        db.add(term)
        await db.flush()
        await db.refresh(term)
        return term

    @staticmethod
    async def delete(db: AsyncSession, term: ConsentTerm) -> None:
        """Remove um termo de consentimento.

        Args:
            db: Sessão assíncrona.
            term: Instância a ser removida.
        """
        await db.delete(term)
        await db.flush()
