import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.competition import CompetitionCreate, CompetitionResponse, CompetitionUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/competitions", response_model=list[CompetitionResponse])
async def list_competitions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[CompetitionResponse]:
    """Lista todas as competições (acesso público)."""
    from app.repositories.competition import CompetitionRepository

    competitions = await CompetitionRepository.get_all(db, skip=skip, limit=limit)
    return [CompetitionResponse.model_validate(c) for c in competitions]


@router.post(
    "/competitions", response_model=CompetitionResponse, status_code=status.HTTP_201_CREATED
)
async def create_competition(
    payload: CompetitionCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Cria uma nova competição (Operador/Admin)."""
    from app.repositories.competition import CompetitionRepository
    from app.models.competition import Competition

    competition = Competition(**payload.model_dump())
    created = await CompetitionRepository.create(db, competition)
    return CompetitionResponse.model_validate(created)


@router.get("/competitions/{competition_id}", response_model=CompetitionResponse)
async def get_competition(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Retorna uma competição pelo ID (acesso público)."""
    from app.repositories.competition import CompetitionRepository

    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )
    return CompetitionResponse.model_validate(competition)


@router.patch("/competitions/{competition_id}", response_model=CompetitionResponse)
async def update_competition(
    competition_id: int,
    payload: CompetitionUpdate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Atualiza dados de uma competição (Operador/Admin)."""
    from app.repositories.competition import CompetitionRepository

    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(competition, field, value)

    updated = await CompetitionRepository.update(db, competition)
    return CompetitionResponse.model_validate(updated)
