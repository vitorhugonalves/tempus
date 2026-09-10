from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.schemas.athlete import AthleteResponse
from app.schemas.checkin import CheckinCandidate, CheckinEnsureRequest
from app.services.checkin import CheckinService

router = APIRouter()


def _competition_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
    )


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
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()
    return await CheckinService.search(db, competition_id, q)


@router.post(
    "/competitions/{competition_id}/checkin/ensure",
    response_model=AthleteResponse,
)
async def ensure_checkin_athlete(
    competition_id: int,
    payload: CheckinEnsureRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> AthleteResponse:
    """Garante o Athlete do candidato, criando-o se preciso (Operador/Admin)."""
    from app.api.v1.athletes import _to_response

    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()
    athlete = await CheckinService.ensure_athlete(db, competition_id, payload)
    return _to_response(athlete)
