import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/judges/penalties", status_code=201)
async def apply_penalty(
    timer_id: int,
    penalty_seconds: int,
    reason: str,
    _current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aplica uma penalidade a um atleta/equipe (Judge, Operador, Admin).

    Regra RN-03: Penalidades não podem ser removidas após aplicadas.
    """
    # TODO: implementar PenaltyService.apply
    return {"timer_id": timer_id, "penalty_seconds": penalty_seconds, "reason": reason}
