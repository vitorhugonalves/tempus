import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompetitionStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    finished = "finished"


class EventType(str, enum.Enum):
    hyrox = "hyrox"
    crossfit = "crossfit"


class ScoringModel(str, enum.Enum):
    lowest_time = "lowest_time"
    most_points = "most_points"


class TiebreakCriterion(str, enum.Enum):
    last_checkpoint = "last_checkpoint"
    registration_date = "registration_date"
    alphabetical = "alphabetical"


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_type: Mapped[EventType | None] = mapped_column(Enum(EventType), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scoring_model: Mapped[ScoringModel | None] = mapped_column(Enum(ScoringModel), nullable=True)
    tiebreak_criterion: Mapped[TiebreakCriterion | None] = mapped_column(
        Enum(TiebreakCriterion), nullable=True
    )
    status: Mapped[CompetitionStatus] = mapped_column(
        Enum(CompetitionStatus), nullable=False, default=CompetitionStatus.draft
    )
    # Divulgação
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    regulations_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registration_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    whatsapp_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    banner_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    banner_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

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
    athletes: Mapped[list["Athlete"]] = relationship(  # noqa: F821
        "Athlete", back_populates="competition", cascade="all, delete-orphan"
    )
    wods: Mapped[list["Wod"]] = relationship(  # noqa: F821
        "Wod", back_populates="competition", cascade="all, delete-orphan", order_by="Wod.order"
    )
