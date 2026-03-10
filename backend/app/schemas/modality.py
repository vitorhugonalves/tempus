from datetime import datetime

from pydantic import BaseModel, Field


class ModalityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    default_duration_seconds: int | None = Field(None, ge=1)


class ModalityUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    default_duration_seconds: int | None = Field(None, ge=1)


class ModalityResponse(BaseModel):
    id: int
    name: str
    description: str | None
    default_duration_seconds: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
