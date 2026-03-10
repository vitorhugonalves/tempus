from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.timer import TimerEventType, TimerStatus


class TimerCreate(BaseModel):
    competition_id: int
    category_id: int | None = None
    user_id: int | None = None
    team_id: int | None = None

    @model_validator(mode="after")
    def validate_subject(self) -> "TimerCreate":
        if self.user_id is None and self.team_id is None:
            raise ValueError("Informe user_id (individual) ou team_id (equipe)")
        if self.user_id is not None and self.team_id is not None:
            raise ValueError("Informe apenas user_id ou team_id, não ambos")
        return self


class TimerActionRequest(BaseModel):
    note: str | None = Field(None, max_length=500)


class PenaltyTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field("time_increment", pattern="^(time_increment|mandatory_stop)$")
    seconds: int = Field(0, ge=0)
    description: str | None = None


class PenaltyTypeResponse(BaseModel):
    id: int
    competition_id: int
    name: str
    kind: str
    seconds: int
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PenaltyApply(BaseModel):
    penalty_type_id: int
    justification: str = Field(..., min_length=1, max_length=1000)


class PenaltyResponse(BaseModel):
    id: int
    timer_id: int
    penalty_type_id: int
    penalty_type_name: str
    applied_by_id: int | None
    justification: str
    seconds_added: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_type(cls, penalty: object) -> "PenaltyResponse":
        return cls(
            id=penalty.id,  # type: ignore[attr-defined]
            timer_id=penalty.timer_id,  # type: ignore[attr-defined]
            penalty_type_id=penalty.penalty_type_id,  # type: ignore[attr-defined]
            penalty_type_name=penalty.penalty_type.name,  # type: ignore[attr-defined]
            applied_by_id=penalty.applied_by_id,  # type: ignore[attr-defined]
            justification=penalty.justification,  # type: ignore[attr-defined]
            seconds_added=penalty.seconds_added,  # type: ignore[attr-defined]
            created_at=penalty.created_at,  # type: ignore[attr-defined]
        )


class TimerEventResponse(BaseModel):
    id: int
    timer_id: int
    event_type: TimerEventType
    triggered_by_id: int | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TimerResponse(BaseModel):
    id: int
    competition_id: int
    category_id: int | None
    user_id: int | None
    team_id: int | None
    status: TimerStatus
    started_at: datetime | None
    stopped_at: datetime | None
    elapsed_seconds: int
    total_penalty_seconds: int
    final_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, timer: object) -> "TimerResponse":
        """Calcula campos derivados ao construir a resposta."""
        from datetime import timezone

        t = timer  # type: ignore[assignment]
        penalty_seconds = sum(p.seconds_added for p in t.penalties)

        # Tempo corrido atual (se running, inclui tempo desde started_at)
        elapsed = t.elapsed_seconds
        if t.status == TimerStatus.running and t.started_at:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            started = t.started_at.replace(tzinfo=None) if t.started_at.tzinfo else t.started_at
            elapsed += int((now - started).total_seconds())

        return cls(
            id=t.id,
            competition_id=t.competition_id,
            category_id=t.category_id,
            user_id=t.user_id,
            team_id=t.team_id,
            status=t.status,
            started_at=t.started_at,
            stopped_at=t.stopped_at,
            elapsed_seconds=elapsed,
            total_penalty_seconds=penalty_seconds,
            final_seconds=elapsed + penalty_seconds,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )


class RankingEntry(BaseModel):
    position: int
    timer_id: int
    user_id: int | None
    team_id: int | None
    athlete_name: str
    team_name: str | None
    category_name: str | None
    elapsed_seconds: int
    total_penalty_seconds: int
    final_seconds: int
    infractions_count: int
    remaining_seconds: int | None
    status: TimerStatus
