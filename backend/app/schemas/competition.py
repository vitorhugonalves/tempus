from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models.competition import CompetitionStatus


class CompetitionCreate(BaseModel):
    name: str
    location: str | None = None
    event_date: date | None = None
    modality_id: int | None = None
    duration_seconds: int | None = None
    max_athletes: int = 300
    rules: str | None = None

    @field_validator("event_date")
    @classmethod
    def event_date_not_in_past(cls, v: date | None) -> date | None:
        """Rejeita datas de evento no passado."""
        if v is not None and v < date.today():
            raise ValueError("A data do evento não pode ser no passado")
        return v


class CompetitionUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    event_date: date | None = None
    modality_id: int | None = None
    duration_seconds: int | None = None
    max_athletes: int | None = None
    rules: str | None = None
    status: CompetitionStatus | None = None

    @field_validator("event_date")
    @classmethod
    def event_date_not_in_past(cls, v: date | None) -> date | None:
        """Rejeita datas de evento no passado."""
        if v is not None and v < date.today():
            raise ValueError("A data do evento não pode ser no passado")
        return v


class CompetitionResponse(BaseModel):
    id: int
    name: str
    location: str | None
    event_date: date | None
    modality_id: int | None
    modality_name: str | None
    duration_seconds: int | None
    max_athletes: int
    status: CompetitionStatus
    rules: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, comp: object) -> "CompetitionResponse":
        c = comp  # type: ignore[assignment]
        return cls(
            id=c.id,
            name=c.name,
            location=c.location,
            event_date=c.event_date,
            modality_id=c.modality_id,
            modality_name=c.modality_rel.name if c.modality_rel else None,
            duration_seconds=c.duration_seconds,
            max_athletes=c.max_athletes,
            status=c.status,
            rules=c.rules,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
