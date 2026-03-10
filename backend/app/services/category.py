from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.repositories.competition import CompetitionRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    """Regras de negócio para categorias de competição (RF-20 a RF-22)."""

    @staticmethod
    async def list_by_competition(
        db: AsyncSession,
        competition_id: int,
        only_active: bool = False,
    ) -> list[Category]:
        """Lista categorias de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            only_active: Filtrar apenas ativas.

        Returns:
            Lista de Category.

        Raises:
            HTTPException 404: Competição não encontrada.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if not competition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")
        return await CategoryRepository.get_by_competition(db, competition_id, only_active)

    @staticmethod
    async def create(
        db: AsyncSession,
        competition_id: int,
        data: CategoryCreate,
    ) -> Category:
        """Cria uma categoria em uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: Dados validados.

        Returns:
            Category criada.

        Raises:
            HTTPException 404: Competição não encontrada.
            HTTPException 422: max_team_size obrigatório para categorias de equipe.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if not competition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")

        from app.models.category import CategoryType
        if data.category_type == CategoryType.team and not data.max_team_size:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="max_team_size é obrigatório para categorias de equipe",
            )

        return await CategoryRepository.create(db, competition_id, data)

    @staticmethod
    async def update(
        db: AsyncSession,
        competition_id: int,
        category_id: int,
        data: CategoryUpdate,
    ) -> Category:
        """Atualiza uma categoria.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição (para validar pertencimento).
            category_id: ID da categoria.
            data: Campos a atualizar.

        Returns:
            Category atualizada.

        Raises:
            HTTPException 404: Categoria não encontrada ou não pertence à competição.
        """
        category = await CategoryRepository.get_by_id(db, category_id)
        if not category or category.competition_id != competition_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
        return await CategoryRepository.update(db, category, data)

    @staticmethod
    async def get_or_404(db: AsyncSession, competition_id: int, category_id: int) -> Category:
        """Retorna categoria ou lança 404.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: ID da categoria.

        Returns:
            Category.

        Raises:
            HTTPException 404.
        """
        category = await CategoryRepository.get_by_id(db, category_id)
        if not category or category.competition_id != competition_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
        return category
