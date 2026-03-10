import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/competitions/{competition_id}/ranking")
async def get_ranking(
    competition_id: int,
    category_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retorna o ranking em tempo real de uma competição (acesso público).

    Regra RF-39: Exibição pública sem necessidade de login.
    """
    # TODO: implementar RankingService.get_ranking
    return {"competition_id": competition_id, "category_id": category_id, "ranking": []}


@router.get("/competitions/{competition_id}/export/csv")
async def export_ranking_csv(
    competition_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Exporta o ranking em CSV (Operador/Admin).

    Regra RF-40: Ranking geral exportável em CSV.
    """
    # TODO: implementar ReportService.export_csv
    return {"competition_id": competition_id, "format": "csv"}


@router.get("/competitions/{competition_id}/export/pdf")
async def export_ranking_pdf(
    competition_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Exporta o ranking em PDF (Operador/Admin).

    Regra RF-40: Ranking geral exportável em PDF.
    """
    # TODO: implementar ReportService.export_pdf
    return {"competition_id": competition_id, "format": "pdf"}
