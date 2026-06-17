import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.schemas.athlete import AthleteBulkResult, AthleteCreate, AthleteResponse, AthleteUpdate
from app.services.athlete import AthleteService
from app.services.category import CategoryService

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_CSV_BYTES = 1 * 1024 * 1024  # 1 MB


def _competition_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
    )


@router.get(
    "/competitions/{competition_id}/athletes",
    response_model=list[AthleteResponse],
)
async def list_athletes(
    competition_id: int,
    category_id: int | None = None,
    team_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("judge", "operator", "admin")),
) -> list[AthleteResponse]:
    """Lista atletas de uma competição com filtros opcionais."""
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()
    athletes = await AthleteService.list_by_competition(
        db, competition_id, category_id=category_id, team_id=team_id
    )
    return [AthleteResponse.model_validate(a) for a in athletes]


@router.post(
    "/competitions/{competition_id}/athletes",
    response_model=AthleteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_athlete(
    competition_id: int,
    payload: AthleteCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> AthleteResponse:
    """Cria um atleta em uma competição (Operador/Admin)."""
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()
    athlete = await AthleteService.create(db, competition_id, payload)
    logger.info("Atleta criado: id=%s competition_id=%s", athlete.id, competition_id)
    return AthleteResponse.model_validate(athlete)


@router.put(
    "/competitions/{competition_id}/athletes/{athlete_id}",
    response_model=AthleteResponse,
)
async def update_athlete(
    competition_id: int,
    athlete_id: int,
    payload: AthleteUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> AthleteResponse:
    """Atualiza dados de um atleta (Operador/Admin)."""
    athlete = await AthleteService.get_or_404(db, athlete_id)
    if athlete.competition_id != competition_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado"
        )
    updated = await AthleteService.update(db, athlete, payload)
    return AthleteResponse.model_validate(updated)


@router.delete(
    "/competitions/{competition_id}/athletes/{athlete_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_athlete(
    competition_id: int,
    athlete_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> None:
    """Remove um atleta (Operador/Admin)."""
    athlete = await AthleteService.get_or_404(db, athlete_id)
    if athlete.competition_id != competition_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado"
        )
    await AthleteService.delete(db, athlete)
    logger.info("Atleta removido: id=%s", athlete_id)


@router.post(
    "/competitions/{competition_id}/athletes/import",
    response_model=AthleteBulkResult,
)
async def import_athletes_csv(
    competition_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> AthleteBulkResult:
    """Importa atletas de arquivo CSV (Operador/Admin). Máximo 1 MB."""
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()

    content = await file.read()
    if len(content) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo CSV excede o tamanho máximo de 1 MB",
        )

    categories = await CategoryService.list_by_competition(db, competition_id)
    result = await AthleteService.import_csv(db, competition_id, content, categories)
    logger.info(
        "Import CSV atletas: competition_id=%s created=%s errors=%s",
        competition_id,
        result.created,
        len(result.errors),
    )
    return result
