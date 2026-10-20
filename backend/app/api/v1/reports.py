import csv
import html
import io
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.timer import CrossfitRankingEntry, RankingEntry
from app.services.timer import RankingService

logger = logging.getLogger(__name__)

router = APIRouter()


def _seconds_to_hms(seconds: int) -> str:
    """Converte segundos para formato HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


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
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporta ranking em PDF (RF-40)."""
    from app.repositories.competition import CompetitionRepository

    competition = await CompetitionRepository.get_by_id(db, competition_id)
    comp_name = competition.name if competition else f"Competição #{competition_id}"

    ranking = await RankingService.get_ranking(db, competition_id, category_id)

    # Gera HTML para conversão com WeasyPrint
    rows_html = ""
    for entry in ranking:
        rows_html += (
            f"<tr>"
            f"<td>{entry.position or '-'}</td>"
            f"<td>{html.escape(entry.athlete_name)}</td>"
            f"<td>{html.escape(entry.category_name or '-')}</td>"
            f"<td>{_seconds_to_hms(entry.elapsed_seconds)}</td>"
            f"<td>{entry.total_penalty_seconds}s</td>"
            f"<td><strong>{_seconds_to_hms(entry.final_seconds)}</strong></td>"
            f"<td>{html.escape(entry.status.value)}</td>"
            f"</tr>"
        )

    doc_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; }}
  h1 {{ text-align: center; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  th {{ background: #1a1a2e; color: white; padding: 8px; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #ddd; text-align: center; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
</style>
</head>
<body>
<h1>Ranking — {html.escape(comp_name)}</h1>
<table>
<thead>
  <tr>
    <th>Pos.</th><th>Atleta/Equipe</th><th>Categoria</th>
    <th>Cronometrado</th><th>Penalidades</th><th>Tempo Final</th><th>Status</th>
  </tr>
</thead>
<tbody>{rows_html}</tbody>
</table>
</body>
</html>"""

    # url_fetcher bloqueado: impede WeasyPrint de buscar file:// ou IPs internos
    def _deny_url_fetcher(url: str, **_kw: object) -> dict:
        return {"string": b"", "mime_type": "text/plain"}

    try:
        import weasyprint  # type: ignore[import]
        pdf_bytes = weasyprint.HTML(string=doc_html, url_fetcher=_deny_url_fetcher).write_pdf()
    except ImportError:
        # WeasyPrint não instalado: retorna HTML como fallback
        logger.warning("WeasyPrint não disponível — retornando HTML")
        return StreamingResponse(
            iter([doc_html.encode()]),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=ranking_{competition_id}.html"},
        )

    logger.info("PDF exportado: competition_id=%s", competition_id)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ranking_{competition_id}.pdf"},
    )


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
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporta leaderboard de WODs em PDF (espelha o que é exibido em /ranking)."""
    from app.repositories.competition import CompetitionRepository
    from app.services.wod_result import WodResultService

    competition = await CompetitionRepository.get_by_id(db, competition_id)
    comp_name = competition.name if competition else f"Competição #{competition_id}"

    leaderboard = await WodResultService.compute_leaderboard(db, competition_id, category_id)

    wod_headers_html = "".join(
        f"<th>{html.escape(we.wod_name)}<br><small>({we.wod_type})</small></th>"
        for we in (leaderboard.entries[0].wod_entries if leaderboard.entries else [])
    )

    rows_html = ""
    for entry in leaderboard.entries:
        wod_cells_html = ""
        for we in entry.wod_entries:
            if we.walkover:
                cell = "<span style='color:#dc2626;font-weight:bold'>W.O.</span>"
            elif we.points == 0 and we.rank is None and we.reps is None and we.time_seconds is None:
                cell = "N/A"
            elif we.wod_type == "amrap":
                cell = f"{we.reps or 0} reps<br><small>({we.points} pts)</small>" if we.reps is not None else "—"
            elif we.wod_type == "for_time":
                if we.time_seconds is not None:
                    t = _seconds_to_hms(we.time_seconds)
                    reps_part = f" +{we.reps}r" if we.reps else ""
                    cell = f"{t}{reps_part}<br><small>({we.points} pts)</small>"
                else:
                    cell = "—"
            else:
                cell = "N/D"
            wod_cells_html += f"<td>{cell}</td>"

        rows_html += (
            f"<tr>"
            f"<td>{entry.position}º</td>"
            f"<td>{html.escape(entry.team_name)}</td>"
            f"{wod_cells_html}"
            f"<td><strong>{entry.total_points} pts</strong></td>"
            f"</tr>"
        )

    doc_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11px; }}
  h1 {{ text-align: center; font-size: 16px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  th {{ background: #1a1a2e; color: white; padding: 6px 4px; font-size: 10px; }}
  td {{ padding: 5px 4px; border-bottom: 1px solid #ddd; text-align: center; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  small {{ color: #666; }}
</style>
</head>
<body>
<h1>Leaderboard WODs — {html.escape(comp_name)}</h1>
<table>
<thead>
  <tr>
    <th>Pos.</th><th>Equipe</th>{wod_headers_html}<th>Total</th>
  </tr>
</thead>
<tbody>{rows_html}</tbody>
</table>
</body>
</html>"""

    def _deny_url_fetcher(url: str, **_kw: object) -> dict:
        return {"string": b"", "mime_type": "text/plain"}

    try:
        import weasyprint  # type: ignore[import]
        pdf_bytes = weasyprint.HTML(string=doc_html, url_fetcher=_deny_url_fetcher).write_pdf()
    except ImportError:
        logger.warning("WeasyPrint não disponível — retornando HTML")
        return StreamingResponse(
            iter([doc_html.encode()]),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=leaderboard_wods_{competition_id}.html"},
        )

    logger.info("PDF WOD leaderboard exportado: competition_id=%s", competition_id)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=leaderboard_wods_{competition_id}.pdf"},
    )


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
