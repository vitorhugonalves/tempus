"""Repositório para ConsentTerm (log de versões append-only por competição)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent_term import ConsentTerm


class ConsentTermRepository:
    """Acesso ao banco para termos de consentimento."""

    @staticmethod
    async def get_by_competition_id(
        db: AsyncSession, competition_id: int
    ) -> ConsentTerm | None:
        """Busca a versão vigente do termo de consentimento de uma competição.

        Vigente = a linha mais recente (maior `id`) ainda não excluída
        (soft delete). Versões antigas ou removidas nunca são retornadas aqui,
        mas continuam no banco para preservar o histórico.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            ConsentTerm vigente ou None se a competição não possui termo ativo.
        """
        result = await db.execute(
            select(ConsentTerm)
            .where(
                ConsentTerm.competition_id == competition_id,
                ConsentTerm.deleted_at.is_(None),
            )
            .order_by(ConsentTerm.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_version(
        db: AsyncSession,
        competition_id: int,
        file_data: bytes,
        file_name: str,
        file_hash: str,
    ) -> ConsentTerm:
        """Cria uma nova versão do termo de consentimento de uma competição.

        Sempre insere uma linha nova — nunca sobrescreve uma versão existente,
        para preservar o histórico (uma inscrição antiga referencia o hash de
        uma versão anterior, que precisa continuar recuperável).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            file_data: Bytes do PDF.
            file_name: Nome original do arquivo.
            file_hash: Hash SHA-256 do conteúdo do arquivo.

        Returns:
            ConsentTerm recém-criado (nova versão vigente).
        """
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
    async def soft_delete(db: AsyncSession, competition_id: int) -> None:
        """Marca todas as versões vigentes do termo de uma competição como não-vigentes.

        Marca TODA versão ainda ativa (`deleted_at IS NULL`), não só a mais
        recente — se marcasse apenas uma linha, `get_by_competition_id`
        (que busca a mais recente ainda não excluída) voltaria a encontrar uma
        versão anterior mais antiga e não excluída, "ressuscitando-a" como
        vigente. Não remove nenhuma linha nem bytes de PDF — apenas define
        `deleted_at`, para que a competição volte a não exigir aceite em
        novas inscrições, mantendo o histórico íntegro.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
        """
        result = await db.execute(
            select(ConsentTerm).where(
                ConsentTerm.competition_id == competition_id,
                ConsentTerm.deleted_at.is_(None),
            )
        )
        now = datetime.now(UTC)
        for term in result.scalars().all():
            term.deleted_at = now
        await db.flush()
