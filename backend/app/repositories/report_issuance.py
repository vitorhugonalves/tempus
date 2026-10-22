from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report_issuance import ReportIssuance


class ReportIssuanceRepository:
    """Acesso ao banco para emissões de relatório. Sem update/delete: imutável."""

    @staticmethod
    async def create(db: AsyncSession, issuance: ReportIssuance) -> ReportIssuance:
        """Persiste uma emissão (só flush; commit é do get_db).

        Args:
            db: Sessão assíncrona.
            issuance: Instância ORM não persistida.

        Returns:
            Emissão persistida.
        """
        db.add(issuance)
        await db.flush()
        return issuance

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> ReportIssuance | None:
        """Busca uma emissão pelo código de verificação impresso no PDF.

        Args:
            db: Sessão assíncrona.
            code: Código de verificação.

        Returns:
            Emissão ou None se não existir.
        """
        result = await db.execute(
            select(ReportIssuance).where(ReportIssuance.verification_code == code)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_sha256(db: AsyncSession, sha256: str) -> ReportIssuance | None:
        """Busca uma emissão pelo hash dos bytes do PDF.

        Args:
            db: Sessão assíncrona.
            sha256: Hash hex (64 chars).

        Returns:
            Emissão ou None se nenhum PDF emitido tiver esse hash.
        """
        result = await db.execute(
            select(ReportIssuance).where(ReportIssuance.sha256 == sha256).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def load_pdf_data(db: AsyncSession, issuance: ReportIssuance) -> bytes:
        """Carrega os bytes do PDF (coluna deferred) de forma explícita.

        Acesso direto a `issuance.pdf_data` fora do greenlet quebra com
        MissingGreenlet em AsyncSession — por isso o refresh explícito.

        Args:
            db: Sessão assíncrona.
            issuance: Emissão já carregada na sessão.

        Returns:
            Bytes do PDF original.
        """
        await db.refresh(issuance, attribute_names=["pdf_data"])
        return issuance.pdf_data

    @staticmethod
    async def exists_for_competition(db: AsyncSession, competition_id: int) -> bool:
        """Indica se a competição já tem algum relatório emitido.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            True se houver ao menos uma emissão.
        """
        result = await db.execute(
            select(exists().where(ReportIssuance.competition_id == competition_id))
        )
        return bool(result.scalar())
