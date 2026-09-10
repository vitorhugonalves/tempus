"""consent term — termo de consentimento opcional por competição

Revision ID: 20260910_consent_term
Revises: 20260909_athlete_user_link
Create Date: 2026-09-10

Cria a tabela consent_terms (singleton por competição, armazena o PDF em binário)
e adiciona os campos de rastreio de aceite em competitor_registrations.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260910_consent_term"
down_revision = "20260909_athlete_user_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_terms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
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
    op.create_index(op.f("ix_consent_terms_id"), "consent_terms", ["id"], unique=False)
    op.create_index(
        op.f("ix_consent_terms_competition_id"),
        "consent_terms",
        ["competition_id"],
        unique=True,
    )

    with op.batch_alter_table("competitor_registrations") as batch_op:
        batch_op.add_column(
            sa.Column("consent_term_hash", sa.String(64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("consent_accepted_at", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("competitor_registrations") as batch_op:
        batch_op.drop_column("consent_accepted_at")
        batch_op.drop_column("consent_term_hash")

    op.drop_index(op.f("ix_consent_terms_competition_id"), table_name="consent_terms")
    op.drop_index(op.f("ix_consent_terms_id"), table_name="consent_terms")
    op.drop_table("consent_terms")
