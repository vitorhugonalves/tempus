from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryRepository:
    """Acesso ao banco para categorias de competição."""

    @staticmethod
    async def get_by_id(db: AsyncSession, category_id: int) -> Category | None:
        """Retorna uma categoria pelo ID.

        Args:
            db: Sessão assíncrona.
            category_id: ID da categoria.

        Returns:
            Category ou None.
        """
        result = await db.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_competition(
        db: AsyncSession,
        competition_id: int,
        only_active: bool = False,
    ) -> list[Category]:
        """Lista categorias de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            only_active: Se True, retorna apenas categorias ativas.

        Returns:
            Lista de categorias.
        """
        query = select(Category).where(Category.competition_id == competition_id)
        if only_active:
            query = query.where(Category.is_active.is_(True))
        query = query.order_by(Category.name)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        competition_id: int,
        data: CategoryCreate,
    ) -> Category:
        """Cria uma nova categoria.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição dona da categoria.
            data: Dados validados pelo schema.

        Returns:
            Category criada e persistida.
        """
        category = Category(
            competition_id=competition_id,
            **data.model_dump(),
        )
        db.add(category)
        await db.flush()
        await db.refresh(category)
        return category

    @staticmethod
    async def update(
        db: AsyncSession,
        category: Category,
        data: CategoryUpdate,
    ) -> Category:
        """Atualiza campos da categoria.

        Args:
            db: Sessão assíncrona.
            category: Instância ORM existente.
            data: Campos a atualizar (apenas os não-None).

        Returns:
            Category atualizada.
        """
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(category, field, value)
        await db.flush()
        await db.refresh(category)
        return category
