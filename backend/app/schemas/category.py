from datetime import datetime

from pydantic import BaseModel, Field

from app.models.category import CategoryType, Gender


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category_type: CategoryType = CategoryType.individual
    gender: Gender | None = None
    age_restriction_enabled: bool = False
    age_min: int | None = Field(None, ge=0, le=120)
    age_max: int | None = Field(None, ge=0, le=120)
    max_team_size: int | None = Field(None, ge=2, le=50)


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category_type: CategoryType | None = None
    gender: Gender | None = None
    age_restriction_enabled: bool | None = None
    age_min: int | None = Field(None, ge=0, le=120)
    age_max: int | None = Field(None, ge=0, le=120)
    max_team_size: int | None = Field(None, ge=2, le=50)
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: int
    competition_id: int
    name: str
    category_type: CategoryType
    gender: Gender | None
    age_restriction_enabled: bool
    age_min: int | None
    age_max: int | None
    max_team_size: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
