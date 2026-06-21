"""competition_divulgacao_wods

Revision ID: 20260620_divulgacao_wods
Revises: 20260615_athletes_table
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from alembic import op

revision = "20260620_divulgacao_wods"
down_revision = "20260615_athletes_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Campos de divulgação na tabela competitions
    with op.batch_alter_table("competitions") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("regulations_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("registration_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("instagram_url", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("whatsapp_url", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("logo_data", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("logo_mime_type", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("banner_data", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("banner_mime_type", sa.String(50), nullable=True))

    # 2. Tabela wods — SQLAlchemy cria o ENUM wodtype automaticamente via create_table
    op.create_table(
        "wods",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "wod_type",
            sa.Enum("amrap", "for_time", "emom", "max_load", name="wodtype"),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("wods")
    op.execute("DROP TYPE IF EXISTS wodtype")

    with op.batch_alter_table("competitions") as batch_op:
        batch_op.drop_column("banner_mime_type")
        batch_op.drop_column("banner_data")
        batch_op.drop_column("logo_mime_type")
        batch_op.drop_column("logo_data")
        batch_op.drop_column("whatsapp_url")
        batch_op.drop_column("instagram_url")
        batch_op.drop_column("registration_url")
        batch_op.drop_column("regulations_url")
        batch_op.drop_column("description")
