"""add_sort_order_to_heats

Revision ID: 20260328_sort_order_heats
Revises: 20260319_box_settings
Create Date: 2026-03-28

Adiciona coluna sort_order à tabela heats para permitir ordenação manual das baterias.
Baterias existentes recebem sort_order = id como valor padrão.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260328_sort_order_heats"
down_revision = "20260319_box_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("heats") as batch_op:
        batch_op.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))

    # Inicializa sort_order com o valor do id para preservar a ordem atual
    op.execute("UPDATE heats SET sort_order = id")


def downgrade() -> None:
    with op.batch_alter_table("heats") as batch_op:
        batch_op.drop_column("sort_order")
