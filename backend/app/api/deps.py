import logging

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.session import get_session_user_id
from app.db.session import get_db
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


async def get_current_user(
    session_id: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Recupera o usuário autenticado a partir do cookie de sessão.

    Args:
        session_id: Token de sessão extraído do cookie HttpOnly.
        db: Sessão de banco de dados.

    Returns:
        Objeto User autenticado e ativo.

    Raises:
        HTTPException: 401 se não autenticado ou sessão inválida/expirada.
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado",
        )

    user_id = await get_session_user_id(db, session_id)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        )

    from app.repositories.user import UserRepository

    user = await UserRepository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo",
        )

    return user


def require_roles(*roles: str):
    """Retorna uma dependência FastAPI que exige um dos roles especificados.

    Args:
        *roles: Roles permitidos para acessar o endpoint (ex: "judge", "admin").

    Returns:
        Função de dependência que valida o role do usuário autenticado.
    """
    allowed = [UserRole(r) for r in roles]

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente",
            )
        return current_user

    return dependency
