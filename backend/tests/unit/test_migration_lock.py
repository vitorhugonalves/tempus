from unittest.mock import MagicMock

from app.core.constants import MIGRATION_ADVISORY_LOCK_KEY
from app.db.migration_lock import acquire_migration_lock


def _connection(dialect_name: str) -> MagicMock:
    connection = MagicMock()
    connection.dialect.name = dialect_name
    return connection


def test_acquire_migration_lock_on_postgres_takes_transaction_advisory_lock():
    connection = _connection("postgresql")
    acquire_migration_lock(connection)
    [call] = connection.execute.call_args_list
    statement, params = call.args
    assert "pg_advisory_xact_lock(:key)" in str(statement)
    assert params == {"key": MIGRATION_ADVISORY_LOCK_KEY}


def test_acquire_migration_lock_on_sqlite_is_noop():
    connection = _connection("sqlite")
    acquire_migration_lock(connection)
    connection.execute.assert_not_called()
