import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.limiter import limiter as _limiter
from app.core.session import create_session, invalidate_session
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas locais ────────────────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class InviteRequest(BaseModel):
    email: EmailStr
    competition_id: int | None = None
    category_id: int | None = None
    team_id: int | None = None


class RegisterViaInviteRequest(BaseModel):
    token: str
    full_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8)


class InviteResponse(BaseModel):
    invite_link: str
    email: str
    expires_hours: int = 72


# ── Autenticação ──────────────────────────────────────────────────────────────


@router.post("/auth/login", response_model=LoginResponse)
@_limiter.limit("10/minute")  # RNF-06: máx. 10 tentativas por minuto por IP
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Autentica o usuário e cria uma sessão server-side (RF-01, RF-02)."""
    from app.services.auth import AuthService

    user = await AuthService.authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )

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
    """Encerra a sessão do usuário autenticado e invalida o cookie (RF-04)."""
    if session_id:
        await invalidate_session(db, session_id)
    response.delete_cookie("session_id")
    logger.info("Logout para user_id=%s", current_user.id)


@router.get("/auth/me", response_model=LoginResponse)
async def me(current_user: User = Depends(get_current_user)) -> LoginResponse:
    """Retorna os dados do usuário autenticado na sessão atual."""
    return LoginResponse.model_validate(current_user)


# ── Recuperação de senha (RF-05) ──────────────────────────────────────────────


@router.post("/auth/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@_limiter.limit("5/minute")  # RNF-06
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Envia e-mail com link de redefinição de senha (RF-05).

    Sempre retorna 204 para não revelar se o e-mail existe.
    """
    from app.services.auth_tokens import PasswordResetService
    from app.services.email import send_password_reset

    token = await PasswordResetService.create_token(db, str(payload.email))
    if token:
        base_url = str(request.base_url).rstrip("/")
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token.token}"
        try:
            await send_password_reset(str(payload.email), reset_link)
        except Exception:
            # Não falha a requisição se o SMTP não estiver configurado
            logger.warning("SMTP não configurado — link de reset: %s", reset_link)


@router.post("/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Redefine a senha usando o token de uso único (RF-05, RNF-07)."""
    from app.services.auth_tokens import PasswordResetService

    await PasswordResetService.consume_token(db, payload.token, payload.new_password)


# ── Convite e auto-cadastro (RF-06, RF-13) ────────────────────────────────────


@router.post(
    "/auth/invite",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_invite(
    payload: InviteRequest,
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> InviteResponse:
    """Cria token de convite e envia e-mail para o competidor (RF-13).

    Apenas Operador e Admin podem enviar convites.
    """
    from app.services.auth_tokens import InviteService
    from app.services.email import send_competitor_invite
    from app.repositories.competition import CompetitionRepository

    invite = await InviteService.create_invite(
        db,
        email=str(payload.email),
        competition_id=payload.competition_id,
        category_id=payload.category_id,
        team_id=payload.team_id,
        invited_by=current_user,
    )

    invite_link = f"{settings.FRONTEND_URL}/register?token={invite.token}"

    comp_name = "Tempus"
    if payload.competition_id:
        comp = await CompetitionRepository.get_by_id(db, payload.competition_id)
        if comp:
            comp_name = comp.name

    if settings.SMTP_USER:
        try:
            await send_competitor_invite(
                str(payload.email), invite_link, comp_name, current_user.full_name
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao enviar e-mail de convite: {exc}",
            )
    else:
        logger.warning("SMTP não configurado — link de convite: %s", invite_link)

    logger.info("Convite criado para %s por user_id=%s", payload.email, current_user.id)
    return InviteResponse(invite_link=invite_link, email=str(payload.email))


@router.post("/auth/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register_via_invite(
    payload: RegisterViaInviteRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Registra competidor via token de convite (RF-06, RN-07).

    Cria a conta, inicia sessão automaticamente e define o cookie.
    """
    from app.services.auth_tokens import InviteService

    user = await InviteService.register_via_invite(
        db, payload.token, payload.full_name, payload.password, str(payload.email)
    )

    token = await create_session(db, user.id)
    response.set_cookie(
        key="session_id",
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.SESSION_TTL_SECONDS,
    )

    logger.info("Competidor registrado via convite: user_id=%s", user.id)
    return LoginResponse.model_validate(user)
