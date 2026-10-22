"""Emissão e verificação de PDFs de relatório assinados (ADR-012)."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    REPORT_TYPE_RANKING,
    REPORT_TYPE_WOD_LEADERBOARD,
    REPORT_VERIFICATION_CODE_BYTES,
)
from app.models.report_issuance import ReportIssuance
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.competition import CompetitionRepository
from app.repositories.report_issuance import ReportIssuanceRepository
from app.services import report_rendering
from app.services.report_signing import IssuancePayload, ReportSigningService
from app.services.timer import RankingService
from app.services.wod_result import WodResultService

logger = logging.getLogger(__name__)


def _utcnow_seconds() -> datetime:
    # Truncado em segundos: o valor entra no payload assinado e precisa voltar
    # idêntico do banco (SQLite/Postgres tratam microssegundos de forma diferente).
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def payload_from_issuance(issuance: ReportIssuance) -> IssuancePayload:
    """Monta o payload assinável a partir de uma emissão (nova ou do banco)."""
    return IssuancePayload(
        code=issuance.verification_code,
        report_type=issuance.report_type,
        competition_id=issuance.competition_id,
        competition_name=issuance.competition_name,
        category_id=issuance.category_id,
        category_name=issuance.category_name,
        issued_at=issuance.issued_at,
        issued_by_user_id=issuance.issued_by_user_id,
        issued_by_role=issuance.issued_by_role,
        sha256=issuance.sha256,
    )


class ReportService:
    """Gera PDFs de ranking assinados e registra cada emissão."""

    @staticmethod
    async def _competition_name(db: AsyncSession, competition_id: int) -> str:
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if competition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competição não encontrada",
            )
        return competition.name

    @staticmethod
    async def _category_name(db: AsyncSession, category_id: int | None) -> str | None:
        if category_id is None:
            return None
        category = await CategoryRepository.get_by_id(db, category_id)
        return category.name if category else None

    @staticmethod
    async def _issue(
        db: AsyncSession,
        *,
        report_type: str,
        competition_id: int,
        competition_name: str,
        category_id: int | None,
        category_name: str | None,
        issued_by: User,
        title: str,
        table_html: str,
        font_size_px: int,
    ) -> ReportIssuance:
        """Renderiza, assina e grava uma emissão.

        Args:
            db: Sessão assíncrona.
            report_type: REPORT_TYPE_RANKING ou REPORT_TYPE_WOD_LEADERBOARD.
            competition_id: ID da competição.
            competition_name: Nome da competição (snapshot).
            category_id: Filtro de categoria usado, se houver.
            category_name: Nome da categoria (snapshot), se houver.
            issued_by: Usuário que exportou.
            title: Título do documento.
            table_html: Tabela já montada (dados escapados).
            font_size_px: Tamanho da fonte do corpo.

        Returns:
            Emissão persistida (com pdf_data em memória).

        Raises:
            PdfRendererUnavailableError: WeasyPrint ausente.
            ReportSigningKeyError: chave de assinatura ausente/inválida.
        """
        code = secrets.token_urlsafe(REPORT_VERIFICATION_CODE_BYTES)
        issued_at = _utcnow_seconds()
        document_html = report_rendering.build_document_html(
            title=title,
            table_html=table_html,
            issued_at=issued_at,
            code=code,
            font_size_px=font_size_px,
        )
        pdf_bytes = report_rendering.html_to_pdf(document_html)
        issuance = ReportIssuance(
            verification_code=code,
            report_type=report_type,
            competition_id=competition_id,
            competition_name=competition_name,
            category_id=category_id,
            category_name=category_name,
            issued_by_user_id=issued_by.id,
            issued_by_role=issued_by.role.value,
            issued_at=issued_at,
            sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            signature="",
            pdf_data=pdf_bytes,
        )
        issuance.signature = ReportSigningService.sign(payload_from_issuance(issuance))
        await ReportIssuanceRepository.create(db, issuance)
        logger.info(
            "Relatório emitido: type=%s competition_id=%s code=%s",
            report_type,
            competition_id,
            code,
        )
        return issuance

    @staticmethod
    async def issue_ranking_pdf(
        db: AsyncSession, competition_id: int, category_id: int | None, issued_by: User
    ) -> ReportIssuance:
        """Emite o PDF assinado do ranking de tempo (com coluna de justificativa).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro de categoria (opcional).
            issued_by: Usuário que exportou.

        Returns:
            Emissão persistida.

        Raises:
            HTTPException 404: competição inexistente.
        """
        competition_name = await ReportService._competition_name(db, competition_id)
        entries = await RankingService.get_ranking(db, competition_id, category_id)
        return await ReportService._issue(
            db,
            report_type=REPORT_TYPE_RANKING,
            competition_id=competition_id,
            competition_name=competition_name,
            category_id=category_id,
            category_name=await ReportService._category_name(db, category_id),
            issued_by=issued_by,
            title=f"Ranking — {competition_name}",
            table_html=report_rendering.ranking_table_html(entries),
            font_size_px=11,
        )

    @staticmethod
    async def issue_wod_leaderboard_pdf(
        db: AsyncSession, competition_id: int, category_id: int | None, issued_by: User
    ) -> ReportIssuance:
        """Emite o PDF assinado do Leaderboard WODs (CrossFit).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro de categoria (opcional).
            issued_by: Usuário que exportou.

        Returns:
            Emissão persistida.

        Raises:
            HTTPException 404: competição inexistente.
        """
        competition_name = await ReportService._competition_name(db, competition_id)
        leaderboard = await WodResultService.compute_leaderboard(
            db, competition_id, category_id
        )
        return await ReportService._issue(
            db,
            report_type=REPORT_TYPE_WOD_LEADERBOARD,
            competition_id=competition_id,
            competition_name=competition_name,
            category_id=category_id,
            category_name=await ReportService._category_name(db, category_id),
            issued_by=issued_by,
            title=f"Leaderboard WODs — {competition_name}",
            table_html=report_rendering.wod_leaderboard_table_html(leaderboard),
            font_size_px=11,
        )
