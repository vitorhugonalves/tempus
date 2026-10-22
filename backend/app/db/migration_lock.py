"""Serialização de migrations Alembic entre processos concorrentes.

O Alembic não tem lock próprio: duas execuções simultâneas de `upgrade head` (ex.:
container reiniciando + execução manual) leem a mesma revisão e colidem no DDL.
Incidentes em 2026-09-11 (DeadlockDetectedError) e 2026-10-22 (UniqueViolationError
em pg_class ao criar report_issuances).
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.constants import MIGRATION_ADVISORY_LOCK_KEY

_POSTGRES_DIALECT = "postgresql"


def acquire_migration_lock(connection: Connection) -> None:
    """Bloqueia até ser o único processo migrando o banco.

    Usa `pg_advisory_xact_lock`: o lock pertence à transação das migrations e é
    liberado sozinho no commit/rollback — nunca fica preso se o processo morrer.
    Deve ser chamado dentro da transação, ANTES de `context.run_migrations()`, para
    que o processo que esperou leia a revisão já atualizada e não reaplique nada.
    Em SQLite (testes/dev) não há concorrência a tratar: no-op.

    Args:
        connection: Conexão síncrona usada pelo Alembic, com transação aberta.
    """
    if connection.dialect.name != _POSTGRES_DIALECT:
        return
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": MIGRATION_ADVISORY_LOCK_KEY},
    )
