from datetime import datetime

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category_id: int
    captain_id: int | None = None
    box_name: str | None = Field(None, max_length=200)


class TeamUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category_id: int | None = None
    captain_id: int | None = None
    box_name: str | None = Field(None, max_length=200)


class TeamMemberAdd(BaseModel):
    user_id: int


class TeamMemberResponse(BaseModel):
    id: int
    team_id: int
    user_id: int
    user_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamResponse(BaseModel):
    id: int
    competition_id: int
    category_id: int
    name: str
    box_name: str | None = None
    captain_id: int | None
    member_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamBulkError(BaseModel):
    row: int
    name: str
    error: str


class TeamBulkResult(BaseModel):
    created: int
    errors: list[TeamBulkError]
