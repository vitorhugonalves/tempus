import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.competition import CompetitionStatus
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.competition import CompetitionCreate, CompetitionResponse, CompetitionUpdate
from app.services.category import CategoryService

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Competições ───────────────────────────────────────────────────────────────


@router.get("/competitions", response_model=list[CompetitionResponse])
async def list_competitions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[CompetitionResponse]:
    """Lista todas as competições (acesso público)."""
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
    from app.models.competition import Competition

    competition = Competition(**payload.model_dump())
    created = await CompetitionRepository.create(db, competition)
    logger.info("Competição criada: id=%s nome=%s", created.id, created.name)
    return CompetitionResponse.model_validate(created)


@router.get("/competitions/{competition_id}", response_model=CompetitionResponse)
async def get_competition(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Retorna uma competição pelo ID (acesso público)."""
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
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Atualiza dados de uma competição (Operador/Admin).

    Regra RN-05: apenas Admin pode reabrir competição encerrada.
    """
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    # RN-05: só Admin pode reabrir competição encerrada
    if (
        competition.status == CompetitionStatus.finished
        and payload.status is not None
        and payload.status != CompetitionStatus.finished
        and current_user.role.value != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas o Administrador pode reabrir uma competição encerrada",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(competition, field, value)

    updated = await CompetitionRepository.update(db, competition)
    logger.info("Competição atualizada: id=%s status=%s", updated.id, updated.status)
    return CompetitionResponse.model_validate(updated)


@router.delete("/competitions/{competition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competition(
    competition_id: int,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove uma competição (Admin apenas)."""
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )
    if competition.status == CompetitionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível excluir uma competição ativa",
        )
    await db.delete(competition)
    await db.flush()
    logger.info("Competição excluída: id=%s", competition_id)


# ── Categorias (RF-20 a RF-22) ────────────────────────────────────────────────


@router.get(
    "/competitions/{competition_id}/categories",
    response_model=list[CategoryResponse],
)
async def list_categories(
    competition_id: int,
    only_active: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    """Lista categorias de uma competição (acesso público)."""
    categories = await CategoryService.list_by_competition(db, competition_id, only_active)
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post(
    "/competitions/{competition_id}/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    competition_id: int,
    payload: CategoryCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Cria uma categoria em uma competição (Operador/Admin)."""
    category = await CategoryService.create(db, competition_id, payload)
    return CategoryResponse.model_validate(category)


@router.patch(
    "/competitions/{competition_id}/categories/{category_id}",
    response_model=CategoryResponse,
)
async def update_category(
    competition_id: int,
    category_id: int,
    payload: CategoryUpdate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """Atualiza uma categoria (Operador/Admin)."""
    category = await CategoryService.update(db, competition_id, category_id, payload)
    return CategoryResponse.model_validate(category)


@router.delete(
    "/competitions/{competition_id}/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_category(
    competition_id: int,
    category_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Desativa uma categoria (Operador/Admin). Não remove do banco."""
    category = await CategoryService.get_or_404(db, competition_id, category_id)
    from app.schemas.category import CategoryUpdate as CU
    await CategoryService.update(db, competition_id, category_id, CU(is_active=False))
    logger.info("Categoria desativada: id=%s competition_id=%s", category.id, competition_id)


# ── Clonagem de competição (RF-19) ────────────────────────────────────────────


@router.post(
    "/competitions/{competition_id}/clone",
    response_model=CompetitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_competition(
    competition_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Clona uma competição como template (RF-19).

    Copia nome, local, modalidade, max_athletes e categorias.
    O clone inicia com status 'draft'.
    """
    from app.models.competition import Competition
    from app.models.category import Category

    source = await CompetitionRepository.get_by_id(db, competition_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    clone = Competition(
        name=f"{source.name} (cópia)",
        location=source.location,
        modality=source.modality,
        max_athletes=source.max_athletes,
        rules=source.rules,
        status=CompetitionStatus.draft,
    )
    db.add(clone)
    await db.flush()

    # Clonar categorias
    source_categories = await CategoryService.list_by_competition(db, competition_id)
    for cat in source_categories:
        db.add(Category(
            competition_id=clone.id,
            name=cat.name,
            category_type=cat.category_type,
            max_team_size=cat.max_team_size,
        ))

    await db.flush()
    await db.refresh(clone)
    logger.info("Competição clonada: source=%s clone=%s", competition_id, clone.id)
    return CompetitionResponse.model_validate(clone)
