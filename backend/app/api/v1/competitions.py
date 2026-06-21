import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.competition import Competition, CompetitionStatus
from app.models.competitor import CompetitorRegistration
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.competition import (
    CompetitionCreate,
    CompetitionResponse,
    CompetitionUpdate,
)
from app.schemas.heat import (
    HeatCreate,
    HeatResponse,
    HeatTeamResponse,
    HeatTimerAdd,
    HeatUpdate,
)
from app.schemas.team import (
    TeamBulkResult,
    TeamCreate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)
from app.schemas.wod import WodCreate, WodResponse
from app.services.category import CategoryService
from app.services.heat import HeatService
from app.services.registration import (
    CompetitorRegisterRequest,
    CompetitorRegisterResponse,
    RegistrationService,
)
from app.services.team import TeamService
from app.services.wod import WodService

logger = logging.getLogger(__name__)

_ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
_EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _resolve_image_mime(file: UploadFile) -> str | None:
    """Retorna MIME type do arquivo, inferindo pela extensão quando necessário."""
    ct = (file.content_type or "").lower()
    if ct in _ALLOWED_IMAGE_MIME:
        return ct
    if file.filename:
        ext = (
            "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        )
        if ext in _EXT_TO_MIME:
            return _EXT_TO_MIME[ext]
    return None


def _to_response(c: Competition) -> CompetitionResponse:
    """Constrói CompetitionResponse com flags has_logo e has_banner."""
    resp = CompetitionResponse.model_validate(c)
    resp.has_logo = c.logo_data is not None
    resp.has_banner = c.banner_data is not None
    return resp


router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _heat_to_response(heat: object) -> HeatResponse:
    h = heat  # type: ignore[assignment]
    teams = [
        HeatTeamResponse(team_id=ht.team_id, team_name=ht.team.name)
        for ht in h.heat_teams
    ]
    return HeatResponse(
        id=h.id,
        competition_id=h.competition_id,
        name=h.name,
        status=h.status,
        sort_order=h.sort_order,
        scheduled_at=h.scheduled_at,
        max_participants=h.max_participants,
        timer_count=len(h.timers),
        team_count=len(h.heat_teams),
        teams=teams,
        created_at=h.created_at,
        updated_at=h.updated_at,
    )


def _team_to_response(team: object) -> TeamResponse:
    t = team  # type: ignore[assignment]
    return TeamResponse(
        id=t.id,
        competition_id=t.competition_id,
        category_id=t.category_id,
        name=t.name,
        captain_id=t.captain_id,
        member_count=len(t.members),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _member_to_response(member: object) -> TeamMemberResponse:
    m = member  # type: ignore[assignment]
    return TeamMemberResponse(
        id=m.id,
        team_id=m.team_id,
        user_id=m.user_id,
        user_name=m.user.full_name if m.user else f"Usuário #{m.user_id}",
        created_at=m.created_at,
    )


# ── Competições ───────────────────────────────────────────────────────────────


@router.get("/competitions", response_model=list[CompetitionResponse])
async def list_competitions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[CompetitionResponse]:
    """Lista todas as competições (acesso público)."""
    competitions = await CompetitionRepository.get_all(db, skip=skip, limit=limit)
    return [_to_response(c) for c in competitions]


@router.post(
    "/competitions", response_model=CompetitionResponse, status_code=status.HTTP_201_CREATED
)
async def create_competition(
    payload: CompetitionCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Cria nova competição (Operador/Admin)."""
    competition = Competition(**payload.model_dump())
    created = await CompetitionRepository.create(db, competition)
    logger.info("Competição criada: id=%s nome=%s", created.id, created.name)
    return _to_response(created)


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
    return _to_response(competition)


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
    return _to_response(updated)


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


# ── Auto-inscrição do competidor ──────────────────────────────────────────────


@router.post(
    "/competitions/{competition_id}/register",
    response_model=CompetitorRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def self_register(
    competition_id: int,
    payload: CompetitorRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompetitorRegisterResponse:
    """Auto-inscrição do competidor em uma competição ativa.

    Disponível para qualquer usuário autenticado. Cria a inscrição e a equipe
    automaticamente. Para categorias de equipe, aceita lista de membros adicionais;
    contas inexistentes são criadas e um e-mail de boas-vindas é enviado.
    """
    login_url = f"{settings.FRONTEND_URL}/login"
    return await RegistrationService.register(
        db=db,
        current_user=current_user,
        competition_id=competition_id,
        data=payload,
        login_url=login_url,
    )


@router.get("/competitions/{competition_id}/my-registration")
async def get_my_registration(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verifica se o usuário autenticado está inscrito nesta competição."""
    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.user_id == current_user.id,
            CompetitorRegistration.competition_id == competition_id,
        )
    )
    reg = result.scalar_one_or_none()
    return {"is_registered": reg is not None, "competition_id": competition_id}


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
    """Clona uma competição como template (RF-19)."""
    from app.models.category import Category

    source = await CompetitionRepository.get_by_id(db, competition_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    clone = Competition(
        name=f"{source.name} (cópia)",
        location=source.location,
        event_type=source.event_type,
        scoring_model=source.scoring_model,
        tiebreak_criterion=source.tiebreak_criterion,
        status=CompetitionStatus.draft,
    )
    db.add(clone)
    await db.flush()

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
    return _to_response(clone)


# ── Equipes (RF-23 a RF-25) ───────────────────────────────────────────────────


@router.get(
    "/competitions/{competition_id}/teams",
    response_model=list[TeamResponse],
)
async def list_teams(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[TeamResponse]:
    """Lista equipes de uma competição (acesso público)."""
    teams = await TeamService.list_by_competition(db, competition_id)
    return [_team_to_response(t) for t in teams]


@router.post(
    "/competitions/{competition_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    competition_id: int,
    payload: TeamCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    """Cria equipe em uma competição (Operador/Admin)."""
    team = await TeamService.create(db, competition_id, payload)
    logger.info("Equipe criada: id=%s competition_id=%s", team.id, competition_id)
    return _team_to_response(team)


@router.patch(
    "/competitions/{competition_id}/teams/{team_id}",
    response_model=TeamResponse,
)
async def update_team(
    competition_id: int,
    team_id: int,
    payload: TeamUpdate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    """Atualiza dados de uma equipe (Operador/Admin)."""
    team = await TeamService.get_or_404(db, team_id)
    if team.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada")
    updated = await TeamService.update(db, team_id, payload)
    return _team_to_response(updated)


@router.delete(
    "/competitions/{competition_id}/teams/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_team(
    competition_id: int,
    team_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove equipe (Operador/Admin)."""
    team = await TeamService.get_or_404(db, team_id)
    if team.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada")
    await TeamService.delete(db, team_id)
    logger.info("Equipe removida: id=%s", team_id)


@router.post(
    "/competitions/{competition_id}/teams/import",
    response_model=TeamBulkResult,
    status_code=status.HTTP_200_OK,
)
async def import_teams_csv(
    competition_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> TeamBulkResult:
    """Importa equipes de arquivo CSV (Operador/Admin). Máximo 1 MB.

    Formato: nome_equipe;categoria (separador ponto-e-vírgula).
    """
    _max_csv_bytes = 1 * 1024 * 1024
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )
    content = await file.read()
    if len(content) > _max_csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo CSV excede o tamanho máximo de 1 MB",
        )
    categories = await CategoryService.list_by_competition(db, competition_id)
    result = await TeamService.import_csv(db, competition_id, content, categories)
    logger.info(
        "Import CSV equipes: competition_id=%s created=%s errors=%s",
        competition_id,
        result.created,
        len(result.errors),
    )
    return result


@router.get(
    "/competitions/{competition_id}/teams/{team_id}/members",
    response_model=list[TeamMemberResponse],
)
async def list_team_members(
    competition_id: int,
    team_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[TeamMemberResponse]:
    """Lista membros de uma equipe."""
    team = await TeamService.get_or_404(db, team_id)
    if team.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada")
    return [_member_to_response(m) for m in team.members]


@router.post(
    "/competitions/{competition_id}/teams/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    competition_id: int,
    team_id: int,
    payload: TeamMemberAdd,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    """Adiciona membro a uma equipe (Operador/Admin)."""
    team = await TeamService.get_or_404(db, team_id)
    if team.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada")
    member = await TeamService.add_member(db, team_id, payload)
    # Carregar relacionamento user para response
    from app.repositories.user import UserRepository
    user = await UserRepository.get_by_id(db, member.user_id)
    member.user = user  # type: ignore[assignment]
    return _member_to_response(member)


@router.delete(
    "/competitions/{competition_id}/teams/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_team_member(
    competition_id: int,
    team_id: int,
    user_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove membro de uma equipe (Operador/Admin)."""
    team = await TeamService.get_or_404(db, team_id)
    if team.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipe não encontrada")
    await TeamService.remove_member(db, team_id, user_id)


# ── Baterias (Heats) ──────────────────────────────────────────────────────────


@router.get(
    "/competitions/{competition_id}/heats",
    response_model=list[HeatResponse],
)
async def list_heats(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[HeatResponse]:
    """Lista baterias de uma competição."""
    heats = await HeatService.list_by_competition(db, competition_id)
    return [_heat_to_response(h) for h in heats]


@router.post(
    "/competitions/{competition_id}/heats",
    response_model=HeatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_heat(
    competition_id: int,
    payload: HeatCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HeatResponse:
    """Cria bateria em uma competição (Operador/Admin)."""
    heat = await HeatService.create(db, competition_id, payload)
    logger.info("Bateria criada: id=%s competition_id=%s", heat.id, competition_id)
    return _heat_to_response(heat)


@router.patch(
    "/competitions/{competition_id}/heats/{heat_id}",
    response_model=HeatResponse,
)
async def update_heat(
    competition_id: int,
    heat_id: int,
    payload: HeatUpdate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HeatResponse:
    """Atualiza o nome de uma bateria (Operador/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    updated = await HeatService.update(db, heat_id, payload)
    return _heat_to_response(updated)


@router.delete(
    "/competitions/{competition_id}/heats/{heat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_heat(
    competition_id: int,
    heat_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove bateria (Operador/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    await HeatService.delete(db, heat_id)
    logger.info("Bateria removida: id=%s", heat_id)


@router.post(
    "/competitions/{competition_id}/heats/{heat_id}/timers",
    response_model=HeatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_timer_to_heat(
    competition_id: int,
    heat_id: int,
    payload: HeatTimerAdd,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HeatResponse:
    """Adiciona timer a uma bateria (Operador/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    updated_heat = await HeatService.add_timer(db, heat_id, payload.timer_id)
    return _heat_to_response(updated_heat)


@router.delete(
    "/competitions/{competition_id}/heats/{heat_id}/timers/{timer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_timer_from_heat(
    competition_id: int,
    heat_id: int,
    timer_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove timer de uma bateria (Operador/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    await HeatService.remove_timer(db, heat_id, timer_id)


@router.post(
    "/competitions/{competition_id}/heats/{heat_id}/start",
    response_model=HeatResponse,
)
async def start_heat(
    competition_id: int,
    heat_id: int,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> HeatResponse:
    """Inicia todos os timers da bateria simultaneamente (Judge/Operator/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    updated_heat = await HeatService.start_all(db, heat_id, current_user, redis)
    logger.info(
        "Bateria iniciada: id=%s por user_id=%s", heat_id, current_user.id
    )
    return _heat_to_response(updated_heat)


# ── Equipes nas Baterias ───────────────────────────────────────────────────────


class HeatTeamAdd(BaseModel):
    team_id: int


@router.post(
    "/competitions/{competition_id}/heats/{heat_id}/teams",
    response_model=HeatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_to_heat(
    competition_id: int,
    heat_id: int,
    payload: HeatTeamAdd,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HeatResponse:
    """Associa equipe a uma bateria com validação de capacidade (Operador/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    updated = await HeatService.add_team(db, heat_id, payload.team_id)
    logger.info("Equipe %s adicionada à bateria %s", payload.team_id, heat_id)
    return _heat_to_response(updated)


@router.delete(
    "/competitions/{competition_id}/heats/{heat_id}/teams/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_team_from_heat(
    competition_id: int,
    heat_id: int,
    team_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove equipe de uma bateria (Operador/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    await HeatService.remove_team(db, heat_id, team_id)
    logger.info("Equipe %s removida da bateria %s", team_id, heat_id)


@router.post(
    "/competitions/{competition_id}/heats/{heat_id}/teams/{team_id}/start",
    response_model=HeatResponse,
)
async def start_team_in_heat(
    competition_id: int,
    heat_id: int,
    team_id: int,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> HeatResponse:
    """Cria e inicia o timer de uma única equipe da bateria (Judge/Operator/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    updated_heat = await HeatService.start_team(db, heat_id, team_id, current_user, redis)
    logger.info("Timer da equipe %s iniciado na bateria %s por user_id=%s", team_id, heat_id, current_user.id)
    return _heat_to_response(updated_heat)


@router.post(
    "/competitions/{competition_id}/heats/{heat_id}/finish",
    response_model=HeatResponse,
)
async def finish_heat(
    competition_id: int,
    heat_id: int,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HeatResponse:
    """Encerra uma bateria em andamento (Judge/Operator/Admin)."""
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    updated_heat = await HeatService.finish(db, heat_id)
    logger.info("Bateria %s encerrada por user_id=%s", heat_id, current_user.id)
    return _heat_to_response(updated_heat)


class HeatMovePayload(BaseModel):
    direction: str  # "up" | "down"


@router.patch(
    "/competitions/{competition_id}/heats/{heat_id}/move",
    response_model=list[HeatResponse],
)
async def move_heat(
    competition_id: int,
    heat_id: int,
    payload: HeatMovePayload,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> list[HeatResponse]:
    """Move uma bateria para cima ou para baixo na ordem (Operador/Admin)."""
    if payload.direction not in ("up", "down"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="direction deve ser 'up' ou 'down'",
        )
    heat = await HeatService.get_or_404(db, heat_id)
    if heat.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bateria não encontrada")
    reordered = await HeatService.move(db, competition_id, heat_id, payload.direction)
    return [_heat_to_response(h) for h in reordered]


# ── Logo e Banner da competição ───────────────────────────────────────────────


@router.post(
    "/competitions/{competition_id}/logo",
    response_model=CompetitionResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_competition_logo(
    competition_id: int,
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Faz upload do logotipo de uma competição (Operador/Admin).

    Formatos aceitos: PNG, JPEG, GIF, WebP. Tamanho máximo: 5 MB.
    """
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    mime_type = _resolve_image_mime(file)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato não suportado. Aceitos: PNG, JPEG, GIF, WebP",
        )
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Imagem muito grande. Máximo: 5 MB",
        )
    competition.logo_data = data
    competition.logo_mime_type = mime_type
    updated = await CompetitionRepository.update(db, competition)
    return _to_response(updated)


@router.get("/competitions/{competition_id}/logo")
async def get_competition_logo(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Retorna o logotipo da competição como imagem binária (público)."""
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None or not competition.logo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Logo não encontrado"
        )
    return Response(
        content=competition.logo_data,
        media_type=competition.logo_mime_type or "image/png",
    )


@router.post(
    "/competitions/{competition_id}/banner",
    response_model=CompetitionResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_competition_banner(
    competition_id: int,
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Faz upload do banner de uma competição (Operador/Admin).

    Formatos aceitos: PNG, JPEG, GIF, WebP. Tamanho máximo: 5 MB.
    """
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    mime_type = _resolve_image_mime(file)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato não suportado. Aceitos: PNG, JPEG, GIF, WebP",
        )
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Imagem muito grande. Máximo: 5 MB",
        )
    competition.banner_data = data
    competition.banner_mime_type = mime_type
    updated = await CompetitionRepository.update(db, competition)
    return _to_response(updated)


@router.get("/competitions/{competition_id}/banner")
async def get_competition_banner(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Retorna o banner da competição como imagem binária (público)."""
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None or not competition.banner_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Banner não encontrado"
        )
    return Response(
        content=competition.banner_data,
        media_type=competition.banner_mime_type or "image/png",
    )


# ── WODs ─────────────────────────────────────────────────────────────────────


@router.get("/competitions/{competition_id}/wods", response_model=list[WodResponse])
async def list_wods(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[WodResponse]:
    """Lista WODs de uma competição ordenados por order (público)."""
    wods = await WodService.list_wods(db, competition_id)
    return [WodResponse.model_validate(w) for w in wods]


@router.post(
    "/competitions/{competition_id}/wods",
    response_model=WodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_wod(
    competition_id: int,
    payload: WodCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> WodResponse:
    """Cria um WOD vinculado à competição (Operador/Admin)."""
    wod = await WodService.create_wod(db, competition_id, payload)
    return WodResponse.model_validate(wod)


@router.delete(
    "/competitions/{competition_id}/wods/{wod_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wod(
    competition_id: int,
    wod_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove um WOD (Operador/Admin)."""
    await WodService.delete_wod(db, competition_id, wod_id)
