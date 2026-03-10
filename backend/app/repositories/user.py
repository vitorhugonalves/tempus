import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


class UserRepository:
    """Repositório responsável pelo acesso ao banco de dados para a entidade User."""

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
        """Busca um usuário pelo ID.

        Args:
            db: Sessão assíncrona do banco de dados.
            user_id: Identificador único do usuário.

        Returns:
            Objeto User ou None se não encontrado.
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """Busca um usuário pelo e-mail.

        Args:
            db: Sessão assíncrona do banco de dados.
            email: Endereço de e-mail do usuário.

        Returns:
            Objeto User ou None se não encontrado.
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
        """Retorna uma lista paginada de usuários.

        Args:
            db: Sessão assíncrona do banco de dados.
            skip: Número de registros a pular.
            limit: Número máximo de registros a retornar.

        Returns:
            Lista de objetos User.
        """
        result = await db.execute(select(User).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, user: User) -> User:
        """Persiste um novo usuário no banco de dados.

        Args:
            db: Sessão assíncrona do banco de dados.
            user: Objeto User a ser criado.

        Returns:
            Objeto User com ID populado.
        """
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info("Usuário criado: id=%s, email=%s", user.id, user.email)
        return user

    @staticmethod
    async def update(db: AsyncSession, user: User) -> User:
        """Persiste alterações em um usuário existente.

        Args:
            db: Sessão assíncrona do banco de dados.
            user: Objeto User com dados atualizados.

        Returns:
            Objeto User atualizado.
        """
        await db.flush()
        await db.refresh(user)
        return user
