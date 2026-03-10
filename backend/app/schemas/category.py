from datetime import datetime

from pydantic import BaseModel, Field

from app.models.category import CategoryType


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category_type: CategoryType = CategoryType.individual
    max_team_size: int | None = Field(None, ge=2, le=50)


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category_type: CategoryType | None = None
    max_team_size: int | None = Field(None, ge=2, le=50)
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: int
    competition_id: int
    name: str
    category_type: CategoryType
    max_team_size: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
