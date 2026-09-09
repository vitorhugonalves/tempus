"""athlete team_id required — backfill solo teams for orphan athletes

Revision ID: 20260909_athlete_team_required
Revises: 20260621_wod_walkover
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_athlete_team_required"
down_revision = "20260621_wod_walkover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    orphans = bind.execute(
        sa.text("SELECT id, name, category_id FROM athletes WHERE team_id IS NULL")
    ).fetchall()

    blocked = [row for row in orphans if row.category_id is None]
    if blocked:
        ids = ", ".join(str(row.id) for row in blocked)
        raise RuntimeError(
            "Não é possível tornar athletes.team_id obrigatório: os atletas com IDs "
            f"[{ids}] não têm equipe NEM categoria — não há como criar uma equipe solo "
            "automaticamente para eles. Atribua uma categoria (ou uma equipe) a esses "
            "atletas manualmente antes de rodar esta migration novamente."
        )

    for row in orphans:
        result = bind.execute(
            sa.text(
                "INSERT INTO teams "
                "(competition_id, name, category_id, created_at, updated_at) "
                "SELECT competition_id, :team_name, category_id, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
                "FROM athletes WHERE id = :athlete_id"
            ),
            {"team_name": f"Equipe {row.name}", "athlete_id": row.id},
        )
        new_team_id = result.lastrowid
        bind.execute(
            sa.text("UPDATE athletes SET team_id = :team_id WHERE id = :athlete_id"),
            {"team_id": new_team_id, "athlete_id": row.id},
        )

    with op.batch_alter_table("athletes") as batch_op:
        batch_op.alter_column("team_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.alter_column("team_id", existing_type=sa.Integer(), nullable=True)
