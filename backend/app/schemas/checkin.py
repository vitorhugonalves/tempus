from typing import Literal

from pydantic import BaseModel


class CheckinCandidate(BaseModel):
    """Resultado de busca de check-in — já é Athlete, ou só CompetitorRegistration."""

    kind: Literal["athlete", "registration"]
    source_id: int  # athlete.id ou registration.id, conforme `kind`
    name: str
    email: str | None
    team_name: str | None
    has_athlete_record: bool


class CheckinEnsureRequest(BaseModel):
    kind: Literal["athlete", "registration"]
    source_id: int
