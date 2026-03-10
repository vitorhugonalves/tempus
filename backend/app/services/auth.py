import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    """Serviço responsável pela lógica de autenticação."""

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
        """Autentica um usuário verificando e-mail e senha.

        Args:
            db: Sessão assíncrona do banco de dados.
            email: E-mail informado pelo usuário.
            password: Senha em texto puro informada pelo usuário.

        Returns:
            Objeto User se as credenciais forem válidas, None caso contrário.
        """
        user = await UserRepository.get_by_email(db, email)
        if user is None:
            logger.warning("Tentativa de login com e-mail inexistente: %s", email)
            return None

        if not user.is_active:
            logger.warning("Tentativa de login de usuário inativo: id=%s", user.id)
            return None

        if not verify_password(password, user.hashed_password):
            logger.warning("Senha incorreta para user_id=%s", user.id)
            return None

        return user
