from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.checkin import CheckinCandidate, CheckinEnsureRequest
from app.services.checkin import CheckinService

router = APIRouter()


@router.get(
    "/competitions/{competition_id}/checkin/search",
    response_model=list[CheckinCandidate],
)
async def search_checkin_candidates(
    competition_id: int,
    q: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> list[CheckinCandidate]:
    """Busca candidatos ao check-in por nome/e-mail (Operador/Admin)."""
    return await CheckinService.search(db, competition_id, q)


@router.post(
    "/competitions/{competition_id}/checkin/ensure",
)
async def ensure_checkin_athlete(
    competition_id: int,
    payload: CheckinEnsureRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
):
    """Garante o Athlete do candidato, criando-o se preciso (Operador/Admin)."""
    from app.api.v1.athletes import _to_response

    athlete = await CheckinService.ensure_athlete(db, competition_id, payload)
    return _to_response(athlete)
