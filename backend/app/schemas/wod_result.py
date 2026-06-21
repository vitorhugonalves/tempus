from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.wod import WodResponse


class TeamSimple(BaseModel):
    """Representação mínima de equipe para a página de resultados."""

    id: int
    name: str
    category_id: int

    model_config = {"from_attributes": True}


class WodResultUpsert(BaseModel):
    """Payload para criar ou atualizar um resultado de WOD."""

    wod_id: int
    team_id: int
    time_seconds: int | None = None
    reps: int | None = None
    notes: str | None = Field(None, max_length=500)
    walkover: bool = False

    @model_validator(mode="after")
    def validate_at_least_one_value(self) -> Self:
        if not self.walkover and self.time_seconds is None and self.reps is None:
            raise ValueError("Informe pelo menos 'time_seconds' ou 'reps'")
        return self


class WodResultResponse(BaseModel):
    """Resultado serializado de uma equipe em um WOD."""

    id: int
    competition_id: int
    wod_id: int
    team_id: int
    time_seconds: int | None
    reps: int | None
    notes: str | None
    walkover: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WodResultsData(BaseModel):
    """Dados completos para renderizar a página de resultados."""

    wods: list[WodResponse]
    teams: list[TeamSimple]
    results: list[WodResultResponse]


class LeaderboardWodEntry(BaseModel):
    """Resultado de uma equipe em um WOD específico para o leaderboard."""

    wod_id: int
    wod_name: str
    wod_type: str
    time_seconds: int | None
    reps: int | None
    points: int
    rank: int | None
    walkover: bool = False


class WodLeaderboardEntry(BaseModel):
    """Linha do leaderboard por equipe."""

    position: int
    team_id: int
    team_name: str
    total_points: int  # segundos quando scoring_model=lowest_time
    wod_entries: list[LeaderboardWodEntry]


class WodLeaderboard(BaseModel):
    """Leaderboard completo de WOD results."""

    scoring_model: str | None
    entries: list[WodLeaderboardEntry]
