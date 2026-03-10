"""add team_id to invite_tokens

Revision ID: 20260310_invite_team
Revises: 20260310_heat_capacity
Create Date: 2026-03-10

Mudanças:
- Adiciona coluna team_id (nullable FK → teams) em invite_tokens
  para permitir associação de equipe no fluxo de convite
"""

from alembic import op
import sqlalchemy as sa

revision = "20260310_invite_team"
down_revision = "20260310_heat_capacity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("invite_tokens") as batch_op:
        batch_op.add_column(
            sa.Column("team_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_invite_tokens_team_id",
            "teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("invite_tokens") as batch_op:
        batch_op.drop_constraint("fk_invite_tokens_team_id", type_="foreignkey")
        batch_op.drop_column("team_id")
