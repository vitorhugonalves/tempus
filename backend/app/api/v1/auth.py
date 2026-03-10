import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.session import create_session, invalidate_session
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Autentica o usuário e cria uma sessão server-side."""
    from app.services.auth import AuthService

    user = await AuthService.authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )

    from app.core.config import settings

    token = await create_session(db, user.id)
    response.set_cookie(
        key="session_id",
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.SESSION_TTL_SECONDS,
    )

    logger.info("Login bem-sucedido para user_id=%s", user.id)
    return LoginResponse.model_validate(user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    session_id: str | None = Cookie(default=None),
    current_user: User = Depends(get_current_user),
) -> None:
    """Encerra a sessão do usuário autenticado e invalida o cookie."""
    if session_id:
        await invalidate_session(db, session_id)
    response.delete_cookie("session_id")
    logger.info("Logout para user_id=%s", current_user.id)


@router.get("/auth/me", response_model=LoginResponse)
async def me(current_user: User = Depends(get_current_user)) -> LoginResponse:
    """Retorna os dados do usuário autenticado na sessão atual."""
    return LoginResponse.model_validate(current_user)
