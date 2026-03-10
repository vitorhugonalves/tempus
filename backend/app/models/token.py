from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PasswordResetToken(Base):
    """Token de uso único para redefinição de senha (RF-05, RNF-07).

    Expira em 72 horas e só pode ser usado uma vez.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="password_reset_tokens")  # noqa: F821


class InviteToken(Base):
    """Token de convite para auto-cadastro de competidor (RF-06, RF-13, RNF-07).

    Vinculado a um e-mail específico — não pode ser usado por outro endereço (RN-07).
    Expira em 72 horas.
    """

    __tablename__ = "invite_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    competition_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    invited_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    competition: Mapped["Competition | None"] = relationship("Competition")  # noqa: F821
    category: Mapped["Category | None"] = relationship("Category")  # noqa: F821
    invited_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", back_populates="sent_invites"
    )
