"""drop competitions.regulations_url e registration_url — obsoletos após inscrição pública nativa

Revision ID: 20260911_drop_competition_links
Revises: 20260910_consent_term
Create Date: 2026-09-11
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_drop_competition_links"
down_revision = "20260910_consent_term"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("competitions") as batch_op:
        batch_op.drop_column("registration_url")
        batch_op.drop_column("regulations_url")


def downgrade() -> None:
    with op.batch_alter_table("competitions") as batch_op:
        batch_op.add_column(sa.Column("regulations_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("registration_url", sa.String(500), nullable=True))
