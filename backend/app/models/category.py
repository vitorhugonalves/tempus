import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CategoryType(str, enum.Enum):
    individual = "individual"
    team = "team"


class Category(Base):
    """Categoria de participação dentro de uma competição.

    Exemplos: Elite Masculino, Master 40+, Equipe Mista.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType), nullable=False, default=CategoryType.individual
    )
    max_team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="categories"
    )
    registrations: Mapped[list["CompetitorRegistration"]] = relationship(  # noqa: F821
        "CompetitorRegistration", back_populates="category", cascade="all, delete-orphan"
    )
    teams: Mapped[list["Team"]] = relationship(  # noqa: F821
        "Team", back_populates="category", cascade="all, delete-orphan"
    )
    timers: Mapped[list["Timer"]] = relationship(  # noqa: F821
        "Timer", back_populates="category"
    )
