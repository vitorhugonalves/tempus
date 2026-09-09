"""athlete user_id — bridge to self-registered User accounts

Revision ID: 20260909_athlete_user_link
Revises: 20260909_athlete_team_required
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_athlete_user_link"
down_revision = "20260909_athlete_team_required"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_athletes_user_id", ["user_id"])
        batch_op.create_unique_constraint(
            "uq_athlete_user_per_competition", ["competition_id", "user_id"]
        )
        batch_op.create_foreign_key(
            "fk_athletes_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.drop_constraint("fk_athletes_user_id", type_="foreignkey")
        batch_op.drop_constraint("uq_athlete_user_per_competition", type_="unique")
        batch_op.drop_index("ix_athletes_user_id")
        batch_op.drop_column("user_id")
