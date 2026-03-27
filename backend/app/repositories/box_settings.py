"""Repositório para BoxSettings (singleton — id sempre = 1)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.box_settings import BoxSettings


class BoxSettingsRepository:
    """Acesso ao banco para as configurações do Box."""

    SINGLETON_ID = 1

    @staticmethod
    async def get(db: AsyncSession) -> BoxSettings | None:
        """Retorna o registro singleton de configurações (id=1).

        Args:
            db: Sessão assíncrona.

        Returns:
            BoxSettings ou None se ainda não foi criado.
        """
        result = await db.execute(
            select(BoxSettings).where(BoxSettings.id == BoxSettingsRepository.SINGLETON_ID)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(db: AsyncSession, settings: BoxSettings) -> BoxSettings:
        """Cria ou atualiza o registro singleton (id forçado para 1).

        Args:
            db: Sessão assíncrona.
            settings: Instância ORM com dados atualizados.

        Returns:
            BoxSettings persistido.
        """
        settings.id = BoxSettingsRepository.SINGLETON_ID
        merged = await db.merge(settings)
        await db.flush()
        await db.refresh(merged)
        return merged
