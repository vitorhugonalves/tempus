import enum
from datetime import date, datetime

from sqlalchemy import Date, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

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
    modality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_athletes: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    status: Mapped[CompetitionStatus] = mapped_column(
        Enum(CompetitionStatus), nullable=False, default=CompetitionStatus.draft
    )
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
