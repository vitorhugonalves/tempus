import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TshirtSize(str, enum.Enum):
    P = "P"
    M = "M"
    G = "G"
    GG = "GG"
    XG = "XG"


class Athlete(Base):
    """Atleta participante de uma competição.

    Registro independente — não requer conta de sistema.
    """

    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    document: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tshirt_size: Mapped[TshirtSize | None] = mapped_column(Enum(TshirtSize), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="athletes"
    )
    category: Mapped["Category | None"] = relationship(  # noqa: F821
        "Category", back_populates="athletes"
    )
    team: Mapped["Team | None"] = relationship(  # noqa: F821
        "Team", back_populates="athletes"
    )
