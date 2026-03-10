"""add heat capacity and heat_teams table

Revision ID: 20260310_heat_capacity
Revises: 20260310_add_modalities_heats_duration
Create Date: 2026-03-10

Mudanças:
- Adiciona coluna max_participants (nullable) em heats
- Cria tabela heat_teams (associação bateria ↔ equipe)
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_heat_capacity"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adiciona max_participants em heats
    with op.batch_alter_table("heats") as batch_op:
        batch_op.add_column(
            sa.Column("max_participants", sa.Integer(), nullable=True)
        )

    # Cria tabela heat_teams
    op.create_table(
        "heat_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("heat_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["heat_id"], ["heats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("heat_id", "team_id", name="uq_heat_team"),
    )
    op.create_index("ix_heat_teams_heat_id", "heat_teams", ["heat_id"])
    op.create_index("ix_heat_teams_team_id", "heat_teams", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_heat_teams_team_id", table_name="heat_teams")
    op.drop_index("ix_heat_teams_heat_id", table_name="heat_teams")
    op.drop_table("heat_teams")

    with op.batch_alter_table("heats") as batch_op:
        batch_op.drop_column("max_participants")
