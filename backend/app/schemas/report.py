from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ReportVerificationStatus(StrEnum):
    valid = "valid"
    # Assinatura não confere OU o PDF guardado não bate com o hash assinado.
    tampered = "tampered"


class ReportVerificationResponse(BaseModel):
    status: ReportVerificationStatus
    verification_code: str
    report_type: str
    competition_name: str
    category_name: str | None
    issued_at: datetime  # UTC com timezone explícito
    issued_by_role: str | None
    sha256: str
