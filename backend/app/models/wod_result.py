from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WodResult(Base):
    """Resultado de uma equipe em um WOD de competição CrossFit."""

    __tablename__ = "wod_results"
    __table_args__ = (UniqueConstraint("wod_id", "team_id", name="uq_wod_result"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wod_id: Mapped[int] = mapped_column(
        ForeignKey("wods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    walkover: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    wod: Mapped["Wod"] = relationship("Wod")  # noqa: F821
    team: Mapped["Team"] = relationship("Team")  # noqa: F821
