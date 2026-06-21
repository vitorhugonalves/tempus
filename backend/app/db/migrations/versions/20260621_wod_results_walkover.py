"""add walkover column to wod_results

Revision ID: 20260621_wod_walkover
Revises: 20260621_wod_results
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op

revision = "20260621_wod_walkover"
down_revision = "20260621_wod_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wod_results") as batch_op:
        batch_op.add_column(
            sa.Column(
                "walkover",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("wod_results") as batch_op:
        batch_op.drop_column("walkover")
