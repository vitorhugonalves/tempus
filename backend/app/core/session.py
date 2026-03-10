import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_session_token

logger = logging.getLogger(__name__)


async def create_session(db: AsyncSession, user_id: int) -> str:
    """Cria uma nova sessão server-side para o usuário.

    Args:
        db: Sessão assíncrona do banco de dados.
        user_id: ID do usuário autenticado.

    Returns:
        Token de sessão gerado.
    """
    from app.models.session import Session as SessionModel

    token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.SESSION_TTL_SECONDS)

    session = SessionModel(
        token=token,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()

    logger.info("Sessão criada para user_id=%s", user_id)
    return token


async def get_session_user_id(db: AsyncSession, token: str) -> int | None:
    """Recupera o user_id associado ao token de sessão, se válido e não expirado.

    Args:
        db: Sessão assíncrona do banco de dados.
        token: Token de sessão extraído do cookie.

    Returns:
        ID do usuário ou None se a sessão for inválida ou expirada.
    """
    from app.models.session import Session as SessionModel

    result = await db.execute(
        select(SessionModel).where(
            SessionModel.token == token,
            SessionModel.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        return None

    return session.user_id


async def invalidate_session(db: AsyncSession, token: str) -> None:
    """Remove a sessão do banco de dados (logout).

    Args:
        db: Sessão assíncrona do banco de dados.
        token: Token de sessão a ser invalidado.
    """
    from app.models.session import Session as SessionModel

    await db.execute(delete(SessionModel).where(SessionModel.token == token))
    await db.commit()
    logger.info("Sessão invalidada")


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Remove todas as sessões expiradas do banco.

    Args:
        db: Sessão assíncrona do banco de dados.

    Returns:
        Número de sessões removidas.
    """
    from app.models.session import Session as SessionModel

    result = await db.execute(
        delete(SessionModel).where(SessionModel.expires_at <= datetime.now(timezone.utc))
    )
    await db.commit()
    count = result.rowcount
    logger.info("Sessões expiradas removidas: %s", count)
    return count
