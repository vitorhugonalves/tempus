import csv
import io
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.timer import RankingEntry
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
            f"<td>{entry.athlete_name}</td>"
            f"<td>{entry.category_name or '-'}</td>"
            f"<td>{_seconds_to_hms(entry.elapsed_seconds)}</td>"
            f"<td>{entry.total_penalty_seconds}s</td>"
            f"<td><strong>{_seconds_to_hms(entry.final_seconds)}</strong></td>"
            f"<td>{entry.status.value}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
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
<h1>Ranking — {comp_name}</h1>
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

    try:
        import weasyprint  # type: ignore[import]
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    except ImportError:
        # WeasyPrint não instalado: retorna HTML como fallback
        logger.warning("WeasyPrint não disponível — retornando HTML")
        return StreamingResponse(
            iter([html.encode()]),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=ranking_{competition_id}.html"},
        )

    logger.info("PDF exportado: competition_id=%s", competition_id)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ranking_{competition_id}.pdf"},
    )
