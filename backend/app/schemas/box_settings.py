from datetime import datetime

from pydantic import BaseModel, Field


class BoxSettingsUpdate(BaseModel):
    """Campos editáveis das configurações do Box."""

    name: str | None = Field(None, max_length=200)
    address: str | None = None
    website: str | None = Field(None, max_length=500)
    instagram: str | None = Field(None, max_length=200)


class BoxSettingsResponse(BaseModel):
    """Resposta das configurações do Box (sem expor bytes do logotipo)."""

    id: int
    name: str
    address: str | None
    website: str | None
    instagram: str | None
    has_logo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
