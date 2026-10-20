"""wod_results table

Revision ID: 20260621_wod_results
Revises: 20260620_divulgacao_wods
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op

revision = "20260621_wod_results"
down_revision = "20260620_divulgacao_wods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wod_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wod_id",
            sa.Integer(),
            sa.ForeignKey("wods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("time_seconds", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("wod_id", "team_id", name="uq_wod_result"),
        sa.Index("ix_wod_results_competition_id", "competition_id"),
        sa.Index("ix_wod_results_wod_id", "wod_id"),
        sa.Index("ix_wod_results_team_id", "team_id"),
    )


def downgrade() -> None:
    op.drop_table("wod_results")
