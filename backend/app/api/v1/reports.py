import csv
import io
import logging
from collections.abc import Awaitable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.report_issuance import ReportIssuance
from app.models.user import User
from app.schemas.timer import CrossfitRankingEntry, RankingEntry
from app.services.report import ReportService
from app.services.report_rendering import PdfRendererUnavailableError
from app.services.report_rendering import seconds_to_hms as _seconds_to_hms
from app.services.report_signing import ReportSigningKeyError
from app.services.timer import RankingService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _issue_or_http_error(issue: Awaitable[ReportIssuance]) -> ReportIssuance:
    """Traduz falhas de infraestrutura da emissão em respostas HTTP explícitas."""
    try:
        return await issue
    except PdfRendererUnavailableError as exc:
        logger.error("PDF não gerado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gerador de PDF indisponível no servidor",
        ) from exc
    except ReportSigningKeyError as exc:
        logger.error("PDF não gerado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assinatura de relatórios não configurada no servidor",
        ) from exc


def _signed_pdf_response(issuance: ReportIssuance, filename: str) -> Response:
    return Response(
        content=issuance.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Verification-Code": issuance.verification_code,
        },
    )


@router.get("/competitions/{competition_id}/ranking", response_model=list[RankingEntry])
async def get_ranking(
    competition_id: int,
    category_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[RankingEntry]:
    """Retorna ranking em tempo real de uma competição (RF-36, RF-39 — acesso público)."""
    return await RankingService.get_ranking(db, competition_id, category_id)


@router.get("/competitions/{competition_id}/export/csv")
async def export_ranking_csv(
    competition_id: int,
    category_id: int | None = None,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporta ranking em CSV (RF-40)."""
    ranking = await RankingService.get_ranking(db, competition_id, category_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Posição", "Atleta/Equipe", "Categoria", "Tempo Cronometrado",
        "Penalidades (s)", "Tempo Final", "Status",
    ])
    for entry in ranking:
        writer.writerow([
            entry.position or "-",
            entry.athlete_name,
            entry.category_name or "-",
            _seconds_to_hms(entry.elapsed_seconds),
            entry.total_penalty_seconds,
            _seconds_to_hms(entry.final_seconds),
            entry.status.value,
        ])

    output.seek(0)
    logger.info("CSV exportado: competition_id=%s", competition_id)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ranking_{competition_id}.csv"},
    )


@router.get("/competitions/{competition_id}/export/pdf")
async def export_ranking_pdf(
    competition_id: int,
    category_id: int | None = None,
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Exporta ranking em PDF assinado, com justificativa de ajustes (RF-40, ADR-012)."""
    issuance = await _issue_or_http_error(
        ReportService.issue_ranking_pdf(db, competition_id, category_id, current_user)
    )
    return _signed_pdf_response(issuance, f"ranking_{competition_id}.pdf")


# ── CrossFit Ranking ─────────────────────────────────────────────────────────


@router.get("/competitions/{competition_id}/crossfit-ranking", response_model=list[CrossfitRankingEntry])
async def get_crossfit_ranking(
    competition_id: int,
    category_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[CrossfitRankingEntry]:
    """Ranking CrossFit por pontos de colocação por WOD (acesso público)."""
    return await RankingService.get_crossfit_ranking(db, competition_id, category_id)


@router.get("/competitions/{competition_id}/export/crossfit-csv")
async def export_crossfit_ranking_csv(
    competition_id: int,
    category_id: int | None = None,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporta leaderboard de WODs em CSV (espelha o que é exibido em /ranking)."""
    from app.services.wod_result import WodResultService

    leaderboard = await WodResultService.compute_leaderboard(db, competition_id, category_id)

    output = io.StringIO()
    writer = csv.writer(output)

    wod_headers = (
        [f"{we.wod_name} ({we.wod_type})" for we in leaderboard.entries[0].wod_entries]
        if leaderboard.entries
        else []
    )
    writer.writerow(["Posição", "Equipe"] + wod_headers + ["Total (pts)"])

    for entry in leaderboard.entries:
        wod_cells = []
        for we in entry.wod_entries:
            if we.walkover:
                wod_cells.append("W.O.")
            elif we.points == 0 and we.rank is None and we.reps is None and we.time_seconds is None:
                wod_cells.append("N/A")
            elif we.wod_type == "amrap":
                wod_cells.append(f"{we.reps or 0} reps ({we.points} pts)" if we.reps is not None else "—")
            elif we.wod_type == "for_time":
                if we.time_seconds is not None:
                    t = _seconds_to_hms(we.time_seconds)
                    wod_cells.append(f"{t}{f' +{we.reps}r' if we.reps else ''} ({we.points} pts)")
                else:
                    wod_cells.append("—")
            else:
                wod_cells.append("N/D")
        writer.writerow([entry.position, entry.team_name] + wod_cells + [entry.total_points])

    output.seek(0)
    logger.info("CSV WOD leaderboard exportado: competition_id=%s", competition_id)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leaderboard_wods_{competition_id}.csv"},
    )


@router.get("/competitions/{competition_id}/export/crossfit-pdf")
async def export_crossfit_ranking_pdf(
    competition_id: int,
    category_id: int | None = None,
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Exporta leaderboard de WODs em PDF assinado (espelha /ranking, ADR-012)."""
    issuance = await _issue_or_http_error(
        ReportService.issue_wod_leaderboard_pdf(
            db, competition_id, category_id, current_user
        )
    )
    return _signed_pdf_response(issuance, f"leaderboard_wods_{competition_id}.pdf")


# ── Certificados individuais (RF-41, RF-42, RF-43) ───────────────────────────


@router.get("/competitions/{competition_id}/certificate/{user_id}")
async def get_certificate_pdf(
    competition_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Gera certificado de participação em PDF para um atleta (RF-41, RF-43).

    O próprio competidor pode gerar o seu certificado (RF-43).
    Operadores e admins podem gerar para qualquer atleta.
    Disponível apenas após encerramento da competição (RN-06).
    """
    from app.services.certificate import generate_certificate_pdf

    # Competidor só acessa o próprio certificado
    if current_user.role.value == "competitor" and current_user.id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Acesso negado")

    pdf_bytes = await generate_certificate_pdf(db, competition_id, user_id)
    media_type = "application/pdf" if pdf_bytes[:4] == b"%PDF" else "text/html"
    ext = "pdf" if media_type == "application/pdf" else "html"
    logger.info("Certificado gerado: competition=%s user=%s", competition_id, user_id)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=certificado_{user_id}.{ext}"},
    )


@router.get("/competitions/{competition_id}/social-image/{user_id}")
async def get_social_image(
    competition_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Gera imagem PNG 1080×1080 para redes sociais (RF-42, RF-43).

    Disponível apenas após encerramento da competição (RN-06).
    """
    from app.services.certificate import generate_social_image

    if current_user.role.value == "competitor" and current_user.id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Acesso negado")

    png_bytes = await generate_social_image(db, competition_id, user_id)
    logger.info("Imagem social gerada: competition=%s user=%s", competition_id, user_id)
    return StreamingResponse(
        iter([png_bytes]),
        media_type="image/png",
        headers={"Content-Disposition": f"attachment; filename=resultado_{user_id}.png"},
    )
