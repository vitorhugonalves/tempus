from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timer import AuditLog


class AuditLogRepository:
    """Acesso ao banco para a trilha de auditoria."""

    @staticmethod
    async def create(db: AsyncSession, log: AuditLog) -> AuditLog:
        """Persiste um registro de auditoria.

        Args:
            db: Sessão assíncrona.
            log: Instância ORM não persistida.

        Returns:
            AuditLog persistido.
        """
        db.add(log)
        await db.flush()
        return log
