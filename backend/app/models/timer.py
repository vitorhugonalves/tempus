import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimerStatus(str, enum.Enum):
    idle = "idle"
    running = "running"
    stopped = "stopped"
    finished = "finished"


class TimerEventType(str, enum.Enum):
    start = "start"
    stop = "stop"
    restart = "restart"
    finish = "finish"


class Timer(Base):
    """Cronômetro associado a um atleta ou equipe em uma competição (RF-26).

    elapsed_seconds acumula o tempo já corrido em sessões anteriores (após restarts).
    O tempo total em andamento = elapsed_seconds + (now - started_at) se status == running.
    """

    __tablename__ = "timers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Exatamente um dos dois deve ser preenchido (atleta individual ou equipe)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[TimerStatus] = mapped_column(
        Enum(TimerStatus), nullable=False, default=TimerStatus.idle
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(nullable=True)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="timers"
    )
    category: Mapped["Category | None"] = relationship(  # noqa: F821
        "Category", back_populates="timers"
    )
    user: Mapped["User | None"] = relationship("User", back_populates="timers")  # noqa: F821
    team: Mapped["Team | None"] = relationship("Team", back_populates="timers")  # noqa: F821
    events: Mapped[list["TimerEvent"]] = relationship(
        "TimerEvent", back_populates="timer", cascade="all, delete-orphan"
    )
    penalties: Mapped[list["Penalty"]] = relationship(  # noqa: F821
        "Penalty", back_populates="timer", cascade="all, delete-orphan"
    )


class TimerEvent(Base):
    """Histórico de eventos de um timer (RF-31).

    Imutável após criação — nunca deletar ou editar registros de evento.
    """

    __tablename__ = "timer_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timer_id: Mapped[int] = mapped_column(
        ForeignKey("timers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[TimerEventType] = mapped_column(Enum(TimerEventType), nullable=False)
    triggered_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    timer: Mapped["Timer"] = relationship("Timer", back_populates="events")
    triggered_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", back_populates="timer_events"
    )


class PenaltyType(Base):
    """Tipo de penalidade configurável por competição (RF-32)."""

    __tablename__ = "penalty_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # time_increment: adiciona seconds ao tempo final
    # mandatory_stop: parada obrigatória (burpees, repetições)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="time_increment")
    seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="penalty_types"
    )
    penalties: Mapped[list["Penalty"]] = relationship(
        "Penalty", back_populates="penalty_type"
    )


class Penalty(Base):
    """Penalidade aplicada a um atleta/equipe (RF-33, RF-34).

    Imutável após criação — RN-03: penalidades não podem ser removidas.
    """

    __tablename__ = "penalties"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timer_id: Mapped[int] = mapped_column(
        ForeignKey("timers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    penalty_type_id: Mapped[int] = mapped_column(
        ForeignKey("penalty_types.id", ondelete="RESTRICT"), nullable=False
    )
    applied_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    # Valor desnormalizado para garantir imutabilidade mesmo se o PenaltyType mudar
    seconds_added: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    timer: Mapped["Timer"] = relationship("Timer", back_populates="penalties")
    penalty_type: Mapped["PenaltyType"] = relationship(
        "PenaltyType", back_populates="penalties"
    )
    applied_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", back_populates="applied_penalties"
    )
