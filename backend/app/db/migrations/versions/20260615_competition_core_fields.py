"""competition_core_fields

Revision ID: 20260615_competition_core_fields
Revises: 20260328_sort_order_heats
Create Date: 2026-06-15
"""
import sqlalchemy as sa
from alembic import op

revision = "20260615_competition_core_fields"
down_revision = "20260328_sort_order_heats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("competitions") as batch_op:
        # Renomeia event_date → start_date
        batch_op.alter_column(
            "event_date",
            new_column_name="start_date",
            existing_type=sa.Date(),
            nullable=True,
        )
        # Adiciona novos campos
        batch_op.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "event_type",
                sa.Enum("hyrox", "crossfit", name="eventtype"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "scoring_model",
                sa.Enum("lowest_time", "most_points", name="scoringmodel"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "tiebreak_criterion",
                sa.Enum(
                    "last_checkpoint",
                    "registration_date",
                    "alphabetical",
                    name="tiebreakcriterion",
                ),
                nullable=True,
            )
        )
        # Remove campos antigos
        batch_op.drop_index("ix_competitions_modality_id")
        batch_op.drop_constraint("fk_competitions_modality_id", type_="foreignkey")
        batch_op.drop_column("modality_id")
        batch_op.drop_column("duration_seconds")
        batch_op.drop_column("max_athletes")
        batch_op.drop_column("rules")


def downgrade() -> None:
    with op.batch_alter_table("competitions") as batch_op:
        batch_op.add_column(sa.Column("rules", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("max_athletes", sa.Integer(), nullable=False, server_default="300")
        )
        batch_op.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("modality_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_competitions_modality_id", "modalities", ["modality_id"], ["id"]
        )
        batch_op.create_index("ix_competitions_modality_id", ["modality_id"], unique=False)
        batch_op.drop_column("tiebreak_criterion")
        batch_op.drop_column("scoring_model")
        batch_op.drop_column("is_public")
        batch_op.drop_column("event_type")
        batch_op.drop_column("end_date")
        batch_op.alter_column(
            "start_date", new_column_name="event_date", existing_type=sa.Date(), nullable=True
        )
