import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """Lista todos os usuários (Operador/Admin)."""
    from app.repositories.user import UserRepository

    users = await UserRepository.get_all(db, skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Cria um novo usuário (Operador/Admin)."""
    from app.core.security import hash_password
    from app.repositories.user import UserRepository

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
    from app.repositories.user import UserRepository

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
    from app.repositories.user import UserRepository

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
