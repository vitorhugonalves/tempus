"""wod_categories join table

Revision ID: 20260621_wod_categories
Revises: 20260621_wod_results
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op

revision = "20260621_wod_categories"
down_revision = "20260621_wod_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wod_categories",
        sa.Column("wod_id", sa.Integer(), sa.ForeignKey("wods.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("wod_categories")
