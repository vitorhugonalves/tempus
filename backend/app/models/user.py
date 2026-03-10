import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    competitor = "competitor"
    judge = "judge"
    operator = "operator"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False, default=UserRole.competitor
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    registrations: Mapped[list["CompetitorRegistration"]] = relationship(  # noqa: F821
        "CompetitorRegistration", back_populates="user", cascade="all, delete-orphan"
    )
    captained_teams: Mapped[list["Team"]] = relationship(  # noqa: F821
        "Team", foreign_keys="Team.captain_id", back_populates="captain"
    )
    team_memberships: Mapped[list["TeamMember"]] = relationship(  # noqa: F821
        "TeamMember", back_populates="user", cascade="all, delete-orphan"
    )
    timers: Mapped[list["Timer"]] = relationship(  # noqa: F821
        "Timer", back_populates="user", cascade="all, delete-orphan"
    )
    timer_events: Mapped[list["TimerEvent"]] = relationship(  # noqa: F821
        "TimerEvent", back_populates="triggered_by"
    )
    applied_penalties: Mapped[list["Penalty"]] = relationship(  # noqa: F821
        "Penalty", back_populates="applied_by"
    )
