"""add_box_settings

Revision ID: 20260319_box_settings
Revises: 20260319_box_name
Create Date: 2026-03-19

Cria a tabela box_settings para armazenar as configurações do Box/Centro de Treinamento.
Padrão singleton: sempre haverá no máximo um registro (id=1).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260319_box_settings"
down_revision = "20260319_box_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "box_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("instagram", sa.String(200), nullable=True),
        sa.Column("logo_data", sa.LargeBinary(), nullable=True),
        sa.Column("logo_mime_type", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_box_settings_id"), "box_settings", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_box_settings_id"), table_name="box_settings")
    op.drop_table("box_settings")
