"""athletes_table

Revision ID: 20260615_athletes_table
Revises: 20260615_category_gender_age
Create Date: 2026-06-15
"""
import sqlalchemy as sa
from alembic import op

revision = "20260615_athletes_table"
down_revision = "20260615_category_gender_age"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athletes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("document", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column(
            "tshirt_size",
            sa.Enum("P", "M", "G", "GG", "XG", name="tshirtsize"),
            nullable=True,
        ),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("athletes")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS tshirtsize")
