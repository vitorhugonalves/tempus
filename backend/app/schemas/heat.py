from datetime import datetime

from pydantic import BaseModel, Field

from app.models.heat import HeatStatus


class HeatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    scheduled_at: datetime | None = None
    max_participants: int | None = Field(None, ge=1)


class HeatTimerAdd(BaseModel):
    timer_id: int


class HeatTeamResponse(BaseModel):
    team_id: int
    team_name: str

    model_config = {"from_attributes": True}


class HeatResponse(BaseModel):
    id: int
    competition_id: int
    name: str
    status: HeatStatus
    scheduled_at: datetime | None
    max_participants: int | None
    timer_count: int
    team_count: int
    teams: list[HeatTeamResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
