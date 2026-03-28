"""timer v2: nova máquina de estados, timer_events expandido, official_results e audit_logs

Revision ID: 20260311_timer_v2
Revises: 20260310_invite_team
Create Date: 2026-03-11

Mudanças:
- timers: renomeia status (idle→created, stopped→paused), adiciona ready/cancelled
- timers: remove started_at, stopped_at, elapsed_seconds (movidos para Redis/TimerEvent)
- timer_events: renomeia event_type (start→started, stop→paused, restart→reset, finish→finished)
- timer_events: adiciona event_at, accumulated_ms, payload_json
- Nova tabela: official_results
- Nova tabela: audit_logs

Notas de compatibilidade:
- SQLite: ENUMs são VARCHAR — UPDATE direto funciona.
- PostgreSQL: ENUMs são tipos reais — é necessário converter a coluna para text,
  dropar o tipo antigo, atualizar os dados, criar o novo tipo e reconverter.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260311_timer_v2"
down_revision = "20260310_invite_team"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgres()

    # ── 1. Atualizar valores de status em timers ──────────────────────────────
    # idle → created, stopped → paused
    # No PostgreSQL: converter para text → dropar tipo → update → novo tipo → reconverter
    if is_pg:
        op.execute("ALTER TABLE timers ALTER COLUMN status TYPE text")
        op.execute("DROP TYPE timerstatus")

    op.execute("UPDATE timers SET status = 'created' WHERE status = 'idle'")
    op.execute("UPDATE timers SET status = 'paused'  WHERE status = 'stopped'")

    if is_pg:
        op.execute(
            "CREATE TYPE timerstatus AS ENUM "
            "('created', 'ready', 'running', 'paused', 'finished', 'cancelled')"
        )
        op.execute(
            "ALTER TABLE timers ALTER COLUMN status "
            "TYPE timerstatus USING status::timerstatus"
        )

    # ── 2. Remover colunas de tempo do timer (movidas para Redis + TimerEvent) ─
    with op.batch_alter_table("timers") as batch_op:
        batch_op.drop_column("started_at")
        batch_op.drop_column("stopped_at")
        batch_op.drop_column("elapsed_seconds")

    # ── 3. Atualizar event_type em timer_events ───────────────────────────────
    # start→started, stop→paused, restart→reset, finish→finished
    if is_pg:
        op.execute("ALTER TABLE timer_events ALTER COLUMN event_type TYPE text")
        op.execute("DROP TYPE timereventtype")

    op.execute("UPDATE timer_events SET event_type = 'started'  WHERE event_type = 'start'")
    op.execute("UPDATE timer_events SET event_type = 'paused'   WHERE event_type = 'stop'")
    op.execute("UPDATE timer_events SET event_type = 'reset'    WHERE event_type = 'restart'")
    op.execute("UPDATE timer_events SET event_type = 'finished' WHERE event_type = 'finish'")

    if is_pg:
        op.execute(
            "CREATE TYPE timereventtype AS ENUM "
            "('started', 'ready', 'resumed', 'paused', 'reset', 'finished', 'cancelled', 'adjusted', 'split')"
        )
        op.execute(
            "ALTER TABLE timer_events ALTER COLUMN event_type "
            "TYPE timereventtype USING event_type::timereventtype"
        )

    # ── 4. Adicionar novos campos em timer_events ─────────────────────────────
    with op.batch_alter_table("timer_events") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("accumulated_ms", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("payload_json", sa.Text(), nullable=True)
        )

    # Backfill: event_at = created_at para eventos existentes
    # No PostgreSQL o server_default já popula linhas existentes no ADD COLUMN;
    # a comparação com '' é inválida para timestamp — skip.
    if not is_pg:
        op.execute("UPDATE timer_events SET event_at = created_at WHERE event_at IS NULL OR event_at = ''")

    # Índice em event_at para queries temporais
    op.create_index("ix_timer_events_event_at", "timer_events", ["event_at"])

    # ── 5. Nova tabela: official_results ──────────────────────────────────────
    op.create_table(
        "official_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timer_id", sa.Integer(), nullable=False),
        sa.Column("final_time_ms", sa.Integer(), nullable=False),
        sa.Column("finished_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "finished_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["timer_id"], ["timers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["finished_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("timer_id", name="uq_official_results_timer_id"),
    )
    op.create_index("ix_official_results_id", "official_results", ["id"])
    op.create_index("ix_official_results_timer_id", "official_results", ["timer_id"])

    # ── 6. Nova tabela: audit_logs ────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    is_pg = _is_postgres()

    # Remover tabelas novas
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_official_results_timer_id", table_name="official_results")
    op.drop_index("ix_official_results_id", table_name="official_results")
    op.drop_table("official_results")

    # Remover campos adicionados em timer_events
    op.drop_index("ix_timer_events_event_at", table_name="timer_events")
    with op.batch_alter_table("timer_events") as batch_op:
        batch_op.drop_column("payload_json")
        batch_op.drop_column("accumulated_ms")
        batch_op.drop_column("event_at")

    # Reverter event_type
    if is_pg:
        op.execute("ALTER TABLE timer_events ALTER COLUMN event_type TYPE text")
        op.execute("DROP TYPE timereventtype")

    op.execute("UPDATE timer_events SET event_type = 'start'   WHERE event_type = 'started'")
    op.execute("UPDATE timer_events SET event_type = 'stop'    WHERE event_type = 'paused'")
    op.execute("UPDATE timer_events SET event_type = 'restart' WHERE event_type = 'reset'")
    op.execute("UPDATE timer_events SET event_type = 'finish'  WHERE event_type = 'finished'")

    if is_pg:
        op.execute(
            "CREATE TYPE timereventtype AS ENUM ('start', 'stop', 'restart', 'finish')"
        )
        op.execute(
            "ALTER TABLE timer_events ALTER COLUMN event_type "
            "TYPE timereventtype USING event_type::timereventtype"
        )

    # Restaurar colunas de tempo em timers
    with op.batch_alter_table("timers") as batch_op:
        batch_op.add_column(
            sa.Column("elapsed_seconds", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("stopped_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))

    # Reverter status
    if is_pg:
        op.execute("ALTER TABLE timers ALTER COLUMN status TYPE text")
        op.execute("DROP TYPE timerstatus")

    op.execute("UPDATE timers SET status = 'idle'    WHERE status = 'created'")
    op.execute("UPDATE timers SET status = 'stopped' WHERE status = 'paused'")

    if is_pg:
        op.execute(
            "CREATE TYPE timerstatus AS ENUM ('idle', 'running', 'stopped', 'finished')"
        )
        op.execute(
            "ALTER TABLE timers ALTER COLUMN status "
            "TYPE timerstatus USING status::timerstatus"
        )
