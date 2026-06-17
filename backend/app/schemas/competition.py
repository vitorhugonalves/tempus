from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models.competition import (
    CompetitionStatus,
    EventType,
    ScoringModel,
    TiebreakCriterion,
)


class CompetitionCreate(BaseModel):
    name: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    event_type: EventType | None = None
    is_public: bool = False
    scoring_model: ScoringModel | None = None
    tiebreak_criterion: TiebreakCriterion | None = None

    @field_validator("start_date")
    @classmethod
    def start_date_not_in_past(cls, v: date | None) -> date | None:
        """Rejeita datas de início no passado."""
        if v is not None and v < date.today():
            raise ValueError("A data de início não pode ser no passado")
        return v


class CompetitionUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    event_type: EventType | None = None
    is_public: bool | None = None
    scoring_model: ScoringModel | None = None
    tiebreak_criterion: TiebreakCriterion | None = None
    status: CompetitionStatus | None = None

    @field_validator("start_date")
    @classmethod
    def start_date_not_in_past(cls, v: date | None) -> date | None:
        """Rejeita datas de início no passado."""
        if v is not None and v < date.today():
            raise ValueError("A data de início não pode ser no passado")
        return v


class CompetitionResponse(BaseModel):
    id: int
    name: str
    location: str | None
    start_date: date | None
    end_date: date | None
    event_type: EventType | None
    is_public: bool
    scoring_model: ScoringModel | None
    tiebreak_criterion: TiebreakCriterion | None
    status: CompetitionStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
