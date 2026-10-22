"""report issuances — registro assinado de PDFs de relatório emitidos

Revision ID: 20261022_report_issuances
Revises: 20260911_drop_competition_links
Create Date: 2026-10-22

Cria a tabela report_issuances (ADR-012): uma linha imutável por PDF de ranking
emitido, com código de verificação, SHA-256, assinatura Ed25519 e os bytes do PDF.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261022_report_issuances"
down_revision = "20260911_drop_competition_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_issuances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("verification_code", sa.String(32), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("competition_name", sa.String(200), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("category_name", sa.String(200), nullable=True),
        # Sem FK: o id é assinado; SET NULL invalidaria a assinatura (ADR-012).
        sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
        sa.Column("issued_by_role", sa.String(20), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=False),
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
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_issuances_id"), "report_issuances", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_report_issuances_verification_code"),
        "report_issuances",
        ["verification_code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_report_issuances_competition_id"),
        "report_issuances",
        ["competition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_issuances_sha256"),
        "report_issuances",
        ["sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_report_issuances_sha256"), table_name="report_issuances")
    op.drop_index(
        op.f("ix_report_issuances_competition_id"), table_name="report_issuances"
    )
    op.drop_index(
        op.f("ix_report_issuances_verification_code"), table_name="report_issuances"
    )
    op.drop_index(op.f("ix_report_issuances_id"), table_name="report_issuances")
    op.drop_table("report_issuances")
