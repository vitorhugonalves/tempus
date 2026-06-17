"""category_gender_age

Revision ID: 20260615_category_gender_age
Revises: 20260615_competition_core_fields
Create Date: 2026-06-15
"""
import sqlalchemy as sa
from alembic import op

revision = "20260615_category_gender_age"
down_revision = "20260615_competition_core_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(
            sa.Column(
                "gender",
                sa.Enum("male", "female", "mixed", name="gender"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "age_restriction_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("age_min", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("age_max", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("age_max")
        batch_op.drop_column("age_min")
        batch_op.drop_column("age_restriction_enabled")
        batch_op.drop_column("gender")
