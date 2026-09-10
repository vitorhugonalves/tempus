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
    async def soft_delete(db: AsyncSession, term: ConsentTerm) -> None:
        """Marca uma versão do termo de consentimento como não-vigente.

        Não remove a linha nem os bytes do PDF — apenas define `deleted_at`,
        para que deixe de ser retornada por `get_by_competition_id` (a
        competição volta a não exigir aceite em novas inscrições) mantendo o
        histórico íntegro para inscrições antigas que a referenciam.

        Args:
            db: Sessão assíncrona.
            term: Instância a ser marcada como excluída.
        """
        term.deleted_at = datetime.now(UTC)
        await db.flush()
