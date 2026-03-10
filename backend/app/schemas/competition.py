from datetime import date

from pydantic import BaseModel

from app.models.competition import CompetitionStatus


class CompetitionCreate(BaseModel):
    name: str
    location: str | None = None
    event_date: date | None = None
    modality: str | None = None
    max_athletes: int = 300
    rules: str | None = None


class CompetitionUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    event_date: date | None = None
    modality: str | None = None
    max_athletes: int | None = None
    rules: str | None = None
    status: CompetitionStatus | None = None


class CompetitionResponse(BaseModel):
    id: int
    name: str
    location: str | None
    event_date: date | None
    modality: str | None
    max_athletes: int
    status: CompetitionStatus
    rules: str | None

    model_config = {"from_attributes": True}
