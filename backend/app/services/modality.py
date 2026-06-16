"""Serviço de modalidades esportivas."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modality import Modality
from app.repositories.modality import ModalityRepository
from app.schemas.modality import ModalityCreate, ModalityUpdate



class ModalityService:
    """Regras de negócio para modalidades."""

    @staticmethod
    async def list_all(db: AsyncSession) -> list[Modality]:
        """Retorna todas as modalidades.

        Args:
            db: Sessão assíncrona.

        Returns:
            Lista de Modality.
        """
        return await ModalityRepository.get_all(db)

    @staticmethod
    async def get_or_404(db: AsyncSession, modality_id: int) -> Modality:
        """Retorna modalidade ou lança 404.

        Args:
            db: Sessão assíncrona.
            modality_id: ID da modalidade.

        Returns:
            Modality.

        Raises:
            HTTPException 404.
        """
        m = await ModalityRepository.get_by_id(db, modality_id)
        if not m:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Modalidade não encontrada"
            )
        return m

    @staticmethod
    async def create(db: AsyncSession, data: ModalityCreate) -> Modality:
        """Cria nova modalidade (nome único).

        Args:
            db: Sessão assíncrona.
            data: Dados validados.

        Returns:
            Modality criada.

        Raises:
            HTTPException 409: Nome já existe.
        """
        existing = await ModalityRepository.get_by_name(db, data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma modalidade com este nome",
            )
        modality = Modality(**data.model_dump())
        return await ModalityRepository.create(db, modality)

    @staticmethod
    async def update(
        db: AsyncSession, modality_id: int, data: ModalityUpdate
    ) -> Modality:
        """Atualiza modalidade existente.

        Args:
            db: Sessão assíncrona.
            modality_id: ID da modalidade.
            data: Campos a atualizar.

        Returns:
            Modality atualizada.
        """
        modality = await ModalityService.get_or_404(db, modality_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(modality, field, value)
        return await ModalityRepository.update(db, modality)

    @staticmethod
    async def delete(db: AsyncSession, modality_id: int) -> None:
        """Remove modalidade.

        Args:
            db: Sessão assíncrona.
            modality_id: ID da modalidade.
        """
        modality = await ModalityService.get_or_404(db, modality_id)
        await ModalityRepository.delete(db, modality)
