import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.timer import PenaltyApply, PenaltyResponse
from app.services.timer import PenaltyService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/timers/{timer_id}/penalties",
    response_model=PenaltyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_penalty(
    timer_id: int,
    payload: PenaltyApply,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> PenaltyResponse:
    """Aplica penalidade a um atleta/equipe (RF-33, RF-34).

    Regra RN-03: penalidades não podem ser removidas após aplicadas.
    Regra RN-04: não pode aplicar após encerramento da competição.
    """
    penalty = await PenaltyService.apply(db, timer_id, payload, current_user)
    logger.info(
        "Penalidade aplicada: timer=%s tipo=%s seconds=%s por user=%s",
        timer_id,
        penalty.penalty_type_id,
        penalty.seconds_added,
        current_user.id,
    )
    return PenaltyResponse.from_orm_with_type(penalty)


@router.get("/timers/{timer_id}/penalties", response_model=list[PenaltyResponse])
async def list_penalties(
    timer_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[PenaltyResponse]:
    """Lista penalidades de um timer (RF-35, acesso público)."""
    from app.services.timer import TimerService

    timer = await TimerService.get_or_404(db, timer_id)
    return [PenaltyResponse.from_orm_with_type(p) for p in timer.penalties]
