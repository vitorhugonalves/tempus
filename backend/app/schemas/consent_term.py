"""Schemas Pydantic para o termo de consentimento."""

from datetime import datetime

from pydantic import BaseModel


class ConsentTermResponse(BaseModel):
    """Metadados do termo de consentimento — nunca expõe os bytes do arquivo."""

    has_term: bool
    file_name: str | None = None
    uploaded_at: datetime | None = None
