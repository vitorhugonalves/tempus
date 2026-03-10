import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.timer import (
    PenaltyTypeCreate,
    PenaltyTypeResponse,
    TimerActionRequest,
    TimerCreate,
    TimerEventResponse,
    TimerResponse,
)
from app.services.timer import PenaltyService, TimerService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/timers", response_model=TimerResponse, status_code=status.HTTP_201_CREATED)
async def create_timer(
    payload: TimerCreate,
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TimerResponse:
    """Cria um timer para atleta ou equipe em uma competição (RF-26)."""
    timer = await TimerService.create(db, payload, current_user)
    logger.info("Timer criado: id=%s competition=%s", timer.id, timer.competition_id)
    return TimerResponse.from_orm(timer)


@router.get("/timers/{timer_id}", response_model=TimerResponse)
async def get_timer(
    timer_id: int,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TimerResponse:
    """Retorna dados atuais de um timer (RF-30)."""
    timer = await TimerService.get_or_404(db, timer_id)
    return TimerResponse.from_orm(timer)


@router.get("/competitions/{competition_id}/timers", response_model=list[TimerResponse])
async def list_timers(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[TimerResponse]:
    """Lista todos os timers de uma competição (acesso público, RF-30)."""
    from app.repositories.timer import TimerRepository

    timers = await TimerRepository.get_by_competition(db, competition_id)
    return [TimerResponse.from_orm(t) for t in timers]


@router.get("/timers/{timer_id}/events", response_model=list[TimerEventResponse])
async def list_timer_events(
    timer_id: int,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TimerEventResponse]:
    """Histórico de eventos de um timer (RF-31)."""
    timer = await TimerService.get_or_404(db, timer_id)
    return [TimerEventResponse.model_validate(e) for e in timer.events]


@router.post("/timers/{timer_id}/start", response_model=TimerResponse)
async def start_timer(
    timer_id: int,
    payload: TimerActionRequest,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TimerResponse:
    """Inicia o timer (RF-27). Regra RN-01: competição deve estar ativa."""
    timer = await TimerService.start(db, timer_id, payload.note, current_user)
    logger.info("Timer iniciado: id=%s por user=%s", timer_id, current_user.id)
    return TimerResponse.from_orm(timer)


@router.post("/timers/{timer_id}/stop", response_model=TimerResponse)
async def stop_timer(
    timer_id: int,
    payload: TimerActionRequest,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TimerResponse:
    """Para o timer (RF-28)."""
    timer = await TimerService.stop(db, timer_id, payload.note, current_user)
    logger.info("Timer parado: id=%s por user=%s", timer_id, current_user.id)
    return TimerResponse.from_orm(timer)


@router.post("/timers/{timer_id}/finish", response_model=TimerResponse)
async def finish_timer(
    timer_id: int,
    payload: TimerActionRequest,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TimerResponse:
    """Finaliza o timer com tempo definitivo (RF-28, RN-04)."""
    timer = await TimerService.finish(db, timer_id, payload.note, current_user)
    logger.info("Timer finalizado: id=%s por user=%s", timer_id, current_user.id)
    return TimerResponse.from_orm(timer)


@router.post("/timers/{timer_id}/restart", response_model=TimerResponse)
async def restart_timer(
    timer_id: int,
    payload: TimerActionRequest,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TimerResponse:
    """Reinicia o timer com registro de motivo (RF-29)."""
    timer = await TimerService.restart(db, timer_id, payload.note, current_user)
    logger.info("Timer reiniciado: id=%s motivo=%s", timer_id, payload.note)
    return TimerResponse.from_orm(timer)


# ── Tipos de penalidade (RF-32) ───────────────────────────────────────────────


@router.post(
    "/competitions/{competition_id}/penalty-types",
    response_model=PenaltyTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_penalty_type(
    competition_id: int,
    payload: PenaltyTypeCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> PenaltyTypeResponse:
    """Cria tipo de penalidade para uma competição (RF-32)."""
    pt = await PenaltyService.create_type(db, competition_id, payload)
    return PenaltyTypeResponse.model_validate(pt)


@router.get(
    "/competitions/{competition_id}/penalty-types",
    response_model=list[PenaltyTypeResponse],
)
async def list_penalty_types(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[PenaltyTypeResponse]:
    """Lista tipos de penalidade de uma competição (acesso público)."""
    from app.repositories.timer import PenaltyTypeRepository

    types = await PenaltyTypeRepository.get_by_competition(db, competition_id)
    return [PenaltyTypeResponse.model_validate(pt) for pt in types]
