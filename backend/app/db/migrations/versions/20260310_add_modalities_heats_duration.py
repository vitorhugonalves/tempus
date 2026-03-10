"""add_modalities_heats_duration

Revision ID: a1b2c3d4e5f6
Revises: d3b149500ba0
Create Date: 2026-03-10 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d3b149500ba0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tabela de modalidades ─────────────────────────────────────────────────
    op.create_table(
        "modalities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_modality_name"),
    )
    op.create_index(op.f("ix_modalities_id"), "modalities", ["id"], unique=False)

    # Seed: modalidades pré-cadastradas
    op.execute(
        sa.text(
            "INSERT INTO modalities (name, description, default_duration_seconds) VALUES "
            "('Hyrox', 'Competição de fitness funcional com circuito padronizado.', 3600), "
            "('CrossFit', 'Treinamento funcional de alta intensidade com workouts variados.', NULL)"
        )
    )

    # ── Tabela de baterias (heats) ────────────────────────────────────────────
    op.create_table(
        "heats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "finished", name="heatstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_heats_id"), "heats", ["id"], unique=False)
    op.create_index(op.f("ix_heats_competition_id"), "heats", ["competition_id"], unique=False)

    # ── Novos campos em competitions via batch (SQLite) ───────────────────────
    with op.batch_alter_table("competitions") as batch_op:
        batch_op.add_column(sa.Column("modality_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
        batch_op.drop_column("modality")
        batch_op.create_foreign_key(
            "fk_competitions_modality_id",
            "modalities",
            ["modality_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_competitions_modality_id", ["modality_id"], unique=False)

    # ── heat_id em timers via batch (SQLite) ──────────────────────────────────
    with op.batch_alter_table("timers") as batch_op:
        batch_op.add_column(sa.Column("heat_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_timers_heat_id", "heats", ["heat_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_timers_heat_id", ["heat_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("timers") as batch_op:
        batch_op.drop_index("ix_timers_heat_id")
        batch_op.drop_constraint("fk_timers_heat_id", type_="foreignkey")
        batch_op.drop_column("heat_id")

    with op.batch_alter_table("competitions") as batch_op:
        batch_op.drop_index("ix_competitions_modality_id")
        batch_op.drop_constraint("fk_competitions_modality_id", type_="foreignkey")
        batch_op.drop_column("duration_seconds")
        batch_op.drop_column("modality_id")
        batch_op.add_column(sa.Column("modality", sa.String(length=100), nullable=True))

    op.drop_index(op.f("ix_heats_competition_id"), table_name="heats")
    op.drop_index(op.f("ix_heats_id"), table_name="heats")
    op.drop_table("heats")

    op.drop_index(op.f("ix_modalities_id"), table_name="modalities")
    op.drop_table("modalities")
