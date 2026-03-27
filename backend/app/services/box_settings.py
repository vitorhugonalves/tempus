"""Serviço de configurações do Box/Centro de Treinamento."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.box_settings import BoxSettings
from app.repositories.box_settings import BoxSettingsRepository
from app.schemas.box_settings import BoxSettingsUpdate


class BoxSettingsService:
    """Regras de negócio para as configurações do Box."""

    @staticmethod
    async def get(db: AsyncSession) -> BoxSettings | None:
        """Retorna as configurações atuais do Box.

        Args:
            db: Sessão assíncrona.

        Returns:
            BoxSettings ou None se ainda não configurado.
        """
        return await BoxSettingsRepository.get(db)

    @staticmethod
    async def update(db: AsyncSession, data: BoxSettingsUpdate) -> BoxSettings:
        """Cria ou atualiza as configurações do Box (exceto logotipo).

        Args:
            db: Sessão assíncrona.
            data: Campos a atualizar.

        Returns:
            BoxSettings persistido.
        """
        existing = await BoxSettingsRepository.get(db)
        if existing is None:
            existing = BoxSettings(name="")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        return await BoxSettingsRepository.upsert(db, existing)

    @staticmethod
    async def update_logo(
        db: AsyncSession, logo_data: bytes, mime_type: str
    ) -> BoxSettings:
        """Atualiza apenas o logotipo do Box.

        Args:
            db: Sessão assíncrona.
            logo_data: Bytes da imagem.
            mime_type: MIME type da imagem (ex: 'image/png').

        Returns:
            BoxSettings persistido.
        """
        existing = await BoxSettingsRepository.get(db)
        if existing is None:
            existing = BoxSettings(name="")
        existing.logo_data = logo_data
        existing.logo_mime_type = mime_type
        return await BoxSettingsRepository.upsert(db, existing)
