import enum
from datetime import datetime

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WodType(str, enum.Enum):
    amrap = "amrap"
    for_time = "for_time"
    emom = "emom"
    max_load = "max_load"


wod_categories = Table(
    "wod_categories",
    Base.metadata,
    Column("wod_id", Integer, ForeignKey("wods.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Wod(Base):
    """WOD (Workout of the Day) vinculado a uma competição CrossFit."""

    __tablename__ = "wods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    wod_type: Mapped[WodType] = mapped_column(Enum(WodType), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="wods"
    )
    categories: Mapped[list["Category"]] = relationship(  # noqa: F821
        "Category", secondary=wod_categories, lazy="selectin"
    )

    @property
    def category_ids(self) -> list[int]:
        return [c.id for c in self.categories]
