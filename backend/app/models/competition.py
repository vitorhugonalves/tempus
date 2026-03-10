import enum
from datetime import date, datetime

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompetitionStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    finished = "finished"


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    modality_id: Mapped[int | None] = mapped_column(
        ForeignKey("modalities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_athletes: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    status: Mapped[CompetitionStatus] = mapped_column(
        Enum(CompetitionStatus), nullable=False, default=CompetitionStatus.draft
    )
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    modality_rel: Mapped["Modality | None"] = relationship(  # noqa: F821
        "Modality", back_populates="competitions"
    )
    categories: Mapped[list["Category"]] = relationship(  # noqa: F821
        "Category", back_populates="competition", cascade="all, delete-orphan"
    )
    registrations: Mapped[list["CompetitorRegistration"]] = relationship(  # noqa: F821
        "CompetitorRegistration", back_populates="competition", cascade="all, delete-orphan"
    )
    teams: Mapped[list["Team"]] = relationship(  # noqa: F821
        "Team", back_populates="competition", cascade="all, delete-orphan"
    )
    heats: Mapped[list["Heat"]] = relationship(  # noqa: F821
        "Heat", back_populates="competition", cascade="all, delete-orphan"
    )
    timers: Mapped[list["Timer"]] = relationship(  # noqa: F821
        "Timer", back_populates="competition", cascade="all, delete-orphan"
    )
    penalty_types: Mapped[list["PenaltyType"]] = relationship(  # noqa: F821
        "PenaltyType", back_populates="competition", cascade="all, delete-orphan"
    )
