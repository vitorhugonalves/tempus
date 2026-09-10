from pydantic import BaseModel, Field


class CheckinCandidate(BaseModel):
    """Resultado de busca de check-in — já é Athlete, ou só CompetitorRegistration."""

    kind: str  # "athlete" | "registration"
    source_id: int  # athlete.id ou registration.id, conforme `kind`
    name: str
    email: str | None
    team_name: str | None
    has_athlete_record: bool


class CheckinEnsureRequest(BaseModel):
    kind: str = Field(..., pattern="^(athlete|registration)$")
    source_id: int
