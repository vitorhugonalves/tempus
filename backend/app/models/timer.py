import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimerStatus(str, enum.Enum):
    """Máquina de estados do cronômetro.

    Transições válidas:
        created  → ready | running | cancelled
        ready    → running | cancelled
        running  → paused | finished
        paused   → running | finished
        finished → (terminal)
        cancelled → (terminal)
    """

    created = "created"      # timer criado, aguardando preparação
    ready = "ready"          # preparado para iniciar (ex: atleta na raia)
    running = "running"      # cronômetro em contagem
    paused = "paused"        # pausado temporariamente
    finished = "finished"    # tempo finalizado — resultado oficial
    cancelled = "cancelled"  # cancelado antes de iniciar


# Transições válidas por estado atual
VALID_TRANSITIONS: dict[TimerStatus, set[TimerStatus]] = {
    TimerStatus.created: {TimerStatus.ready, TimerStatus.running, TimerStatus.cancelled},
    TimerStatus.ready: {TimerStatus.running, TimerStatus.cancelled},
    TimerStatus.running: {TimerStatus.paused, TimerStatus.finished},
    TimerStatus.paused: {TimerStatus.running, TimerStatus.finished},
    TimerStatus.finished: set(),
    TimerStatus.cancelled: set(),
}


class TimerEventType(str, enum.Enum):
    """Tipos de eventos auditáveis do cronômetro."""

    ready = "ready"          # timer marcado como pronto
    started = "started"      # cronômetro iniciado
    paused = "paused"        # cronômetro pausado (accumulated_ms registrado)
    resumed = "resumed"      # cronômetro retomado após pausa
    finished = "finished"    # cronômetro finalizado
    cancelled = "cancelled"  # timer cancelado
    reset = "reset"          # timer reiniciado (accumulated_ms zerado)
    adjusted = "adjusted"    # ajuste manual de tempo (requer autorização)
    split = "split"          # parcial registrada


class Timer(Base):
    """Cronômetro associado a um atleta ou equipe em uma competição (RF-26).

    O estado de tempo em execução (accumulated_ms, timestamps) é gerenciado
    pelo Redis (Etapa 3). No banco, apenas o status lógico e os metadados
    estruturais são persistidos. O histórico completo e auditável fica em
    timer_events, onde cada evento registra accumulated_ms no momento da ação.
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
    heat_id: Mapped[int | None] = mapped_column(
        ForeignKey("heats.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[TimerStatus] = mapped_column(
        Enum(TimerStatus), nullable=False, default=TimerStatus.created
    )
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
    heat: Mapped["Heat | None"] = relationship("Heat", back_populates="timers")  # noqa: F821
    events: Mapped[list["TimerEvent"]] = relationship(
        "TimerEvent", back_populates="timer", cascade="all, delete-orphan"
    )
    penalties: Mapped[list["Penalty"]] = relationship(  # noqa: F821
        "Penalty", back_populates="timer", cascade="all, delete-orphan"
    )
    official_result: Mapped["OfficialResult | None"] = relationship(
        "OfficialResult", back_populates="timer", uselist=False, cascade="all, delete-orphan"
    )


class TimerEvent(Base):
    """Histórico de eventos de um cronômetro — fonte oficial de verdade temporal (RF-31).

    Imutável após criação. Cada evento registra:
    - event_at: momento exato da ação (UTC)
    - accumulated_ms: tempo total acumulado até este evento
    - payload_json: contexto adicional (ajustes, notas, parciais)

    Com esses campos é possível reconstruir o estado completo do timer
    sem depender do Redis (resiliência a falhas).
    """

    __tablename__ = "timer_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timer_id: Mapped[int] = mapped_column(
        ForeignKey("timers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[TimerEventType] = mapped_column(Enum(TimerEventType), nullable=False)
    event_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )
    accumulated_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    timer: Mapped["Timer"] = relationship("Timer", back_populates="events")
    triggered_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", back_populates="timer_events"
    )


class OfficialResult(Base):
    """Resultado oficial de um cronômetro finalizado.

    Criado automaticamente ao chamar finish(). Não possui fluxo de aprovação —
    o resultado é imediatamente oficial no momento da finalização (RN-04).
    """

    __tablename__ = "official_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timer_id: Mapped[int] = mapped_column(
        ForeignKey("timers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    final_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    finished_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    finished_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    timer: Mapped["Timer"] = relationship("Timer", back_populates="official_result")
    finished_by: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[finished_by_user_id]
    )


class AuditLog(Base):
    """Trilha de auditoria para ações críticas no sistema.

    Registra toda operação sensível com antes/depois para rastreabilidade completa.
    Imutável após criação — sem cascade delete.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)

    actor: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[actor_user_id]
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
