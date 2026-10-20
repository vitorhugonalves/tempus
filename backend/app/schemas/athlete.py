from datetime import datetime

from pydantic import BaseModel, Field

from app.models.athlete import TshirtSize


class AthleteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str | None = Field(None, max_length=200)
    document: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=30)
    category_id: int | None = None
    team_id: int | None = None
    tshirt_size: TshirtSize | None = None


class AthleteUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    email: str | None = Field(None, max_length=200)
    document: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=30)
    category_id: int | None = None
    team_id: int | None = None
    tshirt_size: TshirtSize | None = None


class AthleteResponse(BaseModel):
    id: int
    competition_id: int
    category_id: int | None
    team_id: int | None
    team_name: str | None = None
    name: str
    email: str | None
    document: str | None
    phone: str | None
    tshirt_size: TshirtSize | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AthleteBulkError(BaseModel):
    row: int
    name: str
    error: str


class AthleteBulkResult(BaseModel):
    created: int
    errors: list[AthleteBulkError]
