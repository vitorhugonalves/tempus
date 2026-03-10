import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models.team import Team, TeamMember
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserResponse, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """Lista todos os usuários (Operador/Admin)."""
    users = await UserRepository.get_all(db, skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Cria um novo usuário (Operador/Admin)."""
    existing = await UserRepository.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado",
        )

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    created = await UserRepository.create(db, user)
    return UserResponse.model_validate(created)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Retorna um usuário pelo ID. Competidor só pode ver a si mesmo."""
    if current_user.role not in ("operator", "admin") and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Atualiza dados de um usuário (Operador/Admin)."""
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    updated = await UserRepository.update(db, user)
    return UserResponse.model_validate(updated)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove usuário permanentemente (Admin apenas).

    Não é possível remover a si mesmo.
    """
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não é possível remover o próprio usuário",
        )
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado"
        )
    await db.delete(user)
    await db.flush()
    logger.info("Usuário removido: id=%s por admin_id=%s", user_id, current_user.id)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: int,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Redefine senha de um usuário.

    - O próprio usuário pode alterar sua senha.
    - Operador e Admin podem alterar a senha de qualquer usuário.
    """
    is_self = current_user.id == user_id
    is_privileged = current_user.role.value in ("operator", "admin")

    if not is_self and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para alterar a senha deste usuário",
        )

    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado"
        )

    user.hashed_password = hash_password(payload.new_password)
    await UserRepository.update(db, user)
    logger.info(
        "Senha redefinida para user_id=%s por user_id=%s", user_id, current_user.id
    )


# ── Perfil do competidor — gestão de equipes ──────────────────────────────────


class CompetitorTeamInfo(BaseModel):
    team_id: int
    team_name: str
    competition_id: int
    category_id: int
    is_captain: bool

    model_config = {"from_attributes": True}


class UpdateTeamNameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


@router.get("/users/me/teams", response_model=list[CompetitorTeamInfo])
async def get_my_teams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CompetitorTeamInfo]:
    """Retorna as equipes em que o usuário autenticado é membro.

    Disponível para todos os perfis.
    """
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == current_user.id)
    )
    memberships = result.scalars().all()
    return [
        CompetitorTeamInfo(
            team_id=m.team_id,
            team_name=m.team.name,
            competition_id=m.team.competition_id,
            category_id=m.team.category_id,
            is_captain=m.team.captain_id == current_user.id,
        )
        for m in memberships
    ]


@router.patch("/users/me/teams/{team_id}", response_model=CompetitorTeamInfo)
async def update_my_team_name(
    team_id: int,
    payload: UpdateTeamNameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompetitorTeamInfo:
    """Permite ao capitão da equipe alterar o nome (RF: competitor manages team name).

    Apenas o capitão pode renomear sua equipe.
    """
    # Verifica que o usuário é membro da equipe
    member_result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.team_id == team_id, TeamMember.user_id == current_user.id)
    )
    membership = member_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipe não encontrada ou você não é membro",
        )

    team = membership.team
    if team.captain_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas o capitão pode renomear a equipe",
        )

    team.name = payload.name
    await db.flush()
    await db.refresh(team)
    logger.info("Equipe %s renomeada para '%s' pelo capitão user_id=%s", team_id, payload.name, current_user.id)

    return CompetitorTeamInfo(
        team_id=team.id,
        team_name=team.name,
        competition_id=team.competition_id,
        category_id=team.category_id,
        is_captain=True,
    )
