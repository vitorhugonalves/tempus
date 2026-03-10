import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HeatStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    finished = "finished"


class Heat(Base):
    """Bateria de uma competição — agrupa timers que iniciam simultaneamente.

    Uma bateria pode conter timers de atletas individuais ou equipes.
    O comando start_all dispara todos os timers da bateria ao mesmo tempo.
    max_participants define o limite de participantes (pessoas) na bateria.
    """

    __tablename__ = "heats"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[HeatStatus] = mapped_column(
        Enum(HeatStatus), nullable=False, default=HeatStatus.pending
    )
    max_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="heats"
    )
    timers: Mapped[list["Timer"]] = relationship(  # noqa: F821
        "Timer", back_populates="heat"
    )
    heat_teams: Mapped[list["HeatTeam"]] = relationship(
        "HeatTeam", back_populates="heat", cascade="all, delete-orphan"
    )


class HeatTeam(Base):
    """Associação entre bateria e equipe.

    Permite vincular equipes a baterias com validação de capacidade.
    Uma equipe não pode estar na mesma bateria mais de uma vez.
    """

    __tablename__ = "heat_teams"
    __table_args__ = (UniqueConstraint("heat_id", "team_id", name="uq_heat_team"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    heat_id: Mapped[int] = mapped_column(
        ForeignKey("heats.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    heat: Mapped["Heat"] = relationship("Heat", back_populates="heat_teams")
    team: Mapped["Team"] = relationship("Team")  # noqa: F821
