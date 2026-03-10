import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.modality import ModalityCreate, ModalityResponse, ModalityUpdate
from app.services.modality import ModalityService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/modalities", response_model=list[ModalityResponse])
async def list_modalities(
    db: AsyncSession = Depends(get_db),
) -> list[ModalityResponse]:
    """Lista todas as modalidades (acesso público)."""
    modalities = await ModalityService.list_all(db)
    return [ModalityResponse.model_validate(m) for m in modalities]


@router.post(
    "/modalities",
    response_model=ModalityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_modality(
    payload: ModalityCreate,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> ModalityResponse:
    """Cria modalidade (Admin apenas)."""
    modality = await ModalityService.create(db, payload)
    logger.info("Modalidade criada: id=%s nome=%s", modality.id, modality.name)
    return ModalityResponse.model_validate(modality)


@router.get("/modalities/{modality_id}", response_model=ModalityResponse)
async def get_modality(
    modality_id: int,
    db: AsyncSession = Depends(get_db),
) -> ModalityResponse:
    """Retorna modalidade pelo ID."""
    modality = await ModalityService.get_or_404(db, modality_id)
    return ModalityResponse.model_validate(modality)


@router.patch("/modalities/{modality_id}", response_model=ModalityResponse)
async def update_modality(
    modality_id: int,
    payload: ModalityUpdate,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> ModalityResponse:
    """Atualiza modalidade (Admin apenas)."""
    modality = await ModalityService.update(db, modality_id, payload)
    return ModalityResponse.model_validate(modality)


@router.delete("/modalities/{modality_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_modality(
    modality_id: int,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove modalidade sem competições vinculadas (Admin apenas)."""
    await ModalityService.delete(db, modality_id)
    logger.info("Modalidade removida: id=%s", modality_id)
