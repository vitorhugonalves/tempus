from datetime import datetime

from pydantic import BaseModel

from app.models.wod import WodType


class WodCreate(BaseModel):
    """Payload para criação de um WOD."""

    name: str
    wod_type: WodType
    duration_minutes: int | None = None
    description: str | None = None
    order: int = 0
    category_ids: list[int] = []


class WodResponse(BaseModel):
    """Resposta serializada de um WOD."""

    id: int
    competition_id: int
    name: str
    wod_type: WodType
    duration_minutes: int | None
    description: str | None
    order: int
    created_at: datetime
    updated_at: datetime
    category_ids: list[int] = []

    model_config = {"from_attributes": True}
