from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompetitorRegistration(Base):
    """Vínculo entre um usuário competidor, uma competição e uma categoria.

    RF-15: Um competidor só pode estar em uma categoria por competição (RN-02).
    """

    __tablename__ = "competitor_registrations"
    __table_args__ = (
        UniqueConstraint("user_id", "competition_id", name="uq_competitor_competition"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Dados do atleta no momento da inscrição (RF-11)
    document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bib_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="registrations")  # noqa: F821
    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="registrations"
    )
    category: Mapped["Category"] = relationship(  # noqa: F821
        "Category", back_populates="registrations"
    )
