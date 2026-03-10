import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/timers/{timer_id}/start", status_code=200)
async def start_timer(
    timer_id: int,
    _current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Inicia o timer de um atleta/equipe (Judge, Operador, Admin).

    Regra RN-01: A competição deve estar com status 'ativa'.
    """
    # TODO: implementar TimerService.start
    return {"timer_id": timer_id, "status": "started"}


@router.post("/timers/{timer_id}/stop", status_code=200)
async def stop_timer(
    timer_id: int,
    _current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Para o timer de um atleta/equipe (Judge, Operador, Admin)."""
    # TODO: implementar TimerService.stop
    return {"timer_id": timer_id, "status": "stopped"}


@router.post("/timers/{timer_id}/restart", status_code=200)
async def restart_timer(
    timer_id: int,
    reason: str,
    _current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reinicia o timer registrando o motivo (Judge, Operador, Admin)."""
    # TODO: implementar TimerService.restart
    return {"timer_id": timer_id, "status": "restarted", "reason": reason}
