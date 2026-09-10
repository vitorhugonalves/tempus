"""Modelo do termo de consentimento (LGPD/waiver) de uma competição."""

from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConsentTerm(Base):
    """Termo de consentimento em PDF vinculado a uma competição.

    Padrão singleton por competição: no máximo um registro por `competition_id`
    (garantido por índice único). Upload substitui o arquivo existente.
    """

    __tablename__ = "consent_terms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    file_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    competition: Mapped["Competition"] = relationship("Competition")  # noqa: F821
