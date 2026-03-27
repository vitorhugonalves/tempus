"""add_box_name_to_teams

Revision ID: 20260319_box_name
Revises: 20260311_timer_v2
Create Date: 2026-03-19

Adiciona o campo box_name (Centro de Treinamento/Box) à tabela teams.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260319_box_name"
down_revision = "20260311_timer_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("box_name", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("box_name")
