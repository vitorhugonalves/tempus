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
    """Exporta ranking CrossFit em CSV."""
    ranking = await RankingService.get_crossfit_ranking(db, competition_id, category_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Posição", "Atleta/Equipe", "Categoria", "WODs Concluídos", "Pontos Total", "Status"])
    for entry in ranking:
        writer.writerow([
            entry.position,
            entry.athlete_name,
            entry.category_name or "-",
            entry.wods_completed,
            entry.total_points,
            entry.status,
        ])

    output.seek(0)
    logger.info("CSV CrossFit exportado: competition_id=%s", competition_id)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ranking_crossfit_{competition_id}.csv"},
    )


@router.get("/competitions/{competition_id}/export/crossfit-pdf")
async def export_crossfit_ranking_pdf(
    competition_id: int,
    category_id: int | None = None,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporta ranking CrossFit em PDF."""
    from app.repositories.competition import CompetitionRepository

    competition = await CompetitionRepository.get_by_id(db, competition_id)
    comp_name = competition.name if competition else f"Competição #{competition_id}"

    ranking = await RankingService.get_crossfit_ranking(db, competition_id, category_id)

    rows_html = ""
    for entry in ranking:
        rows_html += (
            f"<tr>"
            f"<td>{entry.position}</td>"
            f"<td>{html.escape(entry.athlete_name)}</td>"
            f"<td>{html.escape(entry.category_name or '-')}</td>"
            f"<td>{entry.wods_completed}</td>"
            f"<td><strong>{entry.total_points}</strong></td>"
            f"<td>{html.escape(entry.status)}</td>"
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
<h1>Ranking CrossFit — {html.escape(comp_name)}</h1>
<table>
<thead>
  <tr>
    <th>Pos.</th><th>Atleta/Equipe</th><th>Categoria</th>
    <th>WODs Concluídos</th><th>Pontos Total</th><th>Status</th>
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
            headers={"Content-Disposition": f"attachment; filename=ranking_crossfit_{competition_id}.html"},
        )

    logger.info("PDF CrossFit exportado: competition_id=%s", competition_id)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ranking_crossfit_{competition_id}.pdf"},
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
