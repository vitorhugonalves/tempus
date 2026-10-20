# Resultados WOD + Leaderboard Público — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar página de entrada de resultados por WOD e leaderboard público calculado automaticamente com base em `competition.scoring_model`.

**Architecture:** `WodResult` é uma nova entidade (um resultado por equipe por WOD). A pontuação é calculada no service a partir de todos os resultados da competição — sem lógica no banco. O leaderboard é exposto como endpoint público e consumido pela `RankingPage` existente.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.x async · Alembic · Pydantic v2 · React 18 + TypeScript + TailwindCSS

## Global Constraints

- `flush()` em repositories — NUNCA `commit()` dentro de services/repositories
- Nomes de revisão Alembic: `revision = "20260621_wod_results"`, `down_revision = "20260620_divulgacao_wods"`
- Padrão de resposta: `model_config = {"from_attributes": True}` em todos os schemas response
- Testes com SQLite `:memory:` — fixtures existentes em `tests/conftest.py`: `client`, `db`, `admin_token`, `judge_token`, `competitor_token`
- Rota nova: `<Route path="resultados" element={<ResultsPage />} />` dentro do bloco do CompetitionDashboardLayout em `App.tsx`
- Endpoint `/competitions/{id}/wod-leaderboard` é **público** (sem `require_roles`)
- String `"/wod-leaderboard"` deve ser adicionada a `PUBLIC_PATHS` em `frontend/src/api/client.ts`
- Convenção de commit: `feat(results): ...`, `test(results): ...`, `db(migrations): ...`

---

## Arquivos Criados / Modificados

| Arquivo | Ação |
|---|---|
| `backend/app/models/wod_result.py` | Criar |
| `backend/app/db/migrations/versions/20260621_wod_results.py` | Criar |
| `backend/app/schemas/wod_result.py` | Criar |
| `backend/app/repositories/wod_result.py` | Criar |
| `backend/app/services/wod_result.py` | Criar |
| `backend/app/api/v1/competitions.py` | Modificar (4 endpoints) |
| `backend/tests/unit/test_wod_result_service.py` | Criar |
| `backend/tests/integration/test_wod_results.py` | Criar |
| `frontend/src/types/index.ts` | Modificar |
| `frontend/src/api/wod_results.ts` | Criar |
| `frontend/src/api/client.ts` | Modificar (PUBLIC_PATHS) |
| `frontend/src/pages/dashboard/ResultsPage.tsx` | Criar |
| `frontend/src/App.tsx` | Modificar (rota `resultados`) |
| `frontend/src/pages/RankingPage.tsx` | Modificar (seção WOD leaderboard) |

---

## Task 1: Modelo + Migration

**Files:**
- Create: `backend/app/models/wod_result.py`
- Create: `backend/app/db/migrations/versions/20260621_wod_results.py`

**Interfaces:**
- Produces: classe `WodResult` com campos `id`, `competition_id`, `wod_id`, `team_id`, `time_seconds`, `reps`, `notes`, `created_at`, `updated_at`

- [ ] **Step 1: Criar o model**

```python
# backend/app/models/wod_result.py
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WodResult(Base):
    """Resultado de uma equipe em um WOD de competição CrossFit."""

    __tablename__ = "wod_results"
    __table_args__ = (UniqueConstraint("wod_id", "team_id", name="uq_wod_result"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wod_id: Mapped[int] = mapped_column(
        ForeignKey("wods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    wod: Mapped["Wod"] = relationship("Wod")  # noqa: F821
    team: Mapped["Team"] = relationship("Team")  # noqa: F821
```

- [ ] **Step 2: Criar a migration**

```python
# backend/app/db/migrations/versions/20260621_wod_results.py
"""wod_results table

Revision ID: 20260621_wod_results
Revises: 20260620_divulgacao_wods
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op

revision = "20260621_wod_results"
down_revision = "20260620_divulgacao_wods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wod_results",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "wod_id",
            sa.Integer(),
            sa.ForeignKey("wods.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("time_seconds", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("wod_id", "team_id", name="uq_wod_result"),
    )


def downgrade() -> None:
    op.drop_table("wod_results")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/wod_result.py backend/app/db/migrations/versions/20260621_wod_results.py
git commit -m "db(migrations): cria tabela wod_results"
```

---

## Task 2: Schema + Repository + Service + Testes unitários

**Files:**
- Create: `backend/app/schemas/wod_result.py`
- Create: `backend/app/repositories/wod_result.py`
- Create: `backend/app/services/wod_result.py`
- Create: `backend/tests/unit/test_wod_result_service.py`

**Interfaces:**
- Consumes: `WodResult` model (Task 1), `WodRepository.list_by_competition`, `WodRepository.get_by_id`, `TeamRepository.get_by_competition`, `TeamRepository.get_by_id`, `CompetitionRepository.get_by_id`
- Produces:
  - `WodResultUpsert` — schema de request
  - `WodResultResponse` — schema de response
  - `WodResultsData` — envelope do GET /wod-results
  - `WodLeaderboard` — envelope do GET /wod-leaderboard
  - `WodResultRepository.get_by_competition(db, competition_id) -> list[WodResult]`
  - `WodResultRepository.get_by_id(db, result_id) -> WodResult | None`
  - `WodResultRepository.get_by_wod_and_team(db, wod_id, team_id) -> WodResult | None`
  - `WodResultRepository.create(db, obj) -> WodResult`
  - `WodResultRepository.delete(db, obj) -> None`
  - `WodResultService.get_results_data(db, competition_id) -> WodResultsData`
  - `WodResultService.upsert(db, competition_id, data) -> WodResult`
  - `WodResultService.delete(db, competition_id, result_id) -> None`
  - `WodResultService.compute_leaderboard(db, competition_id) -> WodLeaderboard`

- [ ] **Step 1: Escrever os testes unitários do leaderboard (failing)**

```python
# backend/tests/unit/test_wod_result_service.py
"""Testes unitários para a lógica de leaderboard de WOD results."""
from unittest.mock import MagicMock

from app.models.wod import WodType
from app.services.wod_result import _compute_leaderboard


def _make_wod(id: int, wod_type: str) -> MagicMock:
    w = MagicMock()
    w.id = id
    w.name = f"WOD {id}"
    w.wod_type = WodType(wod_type)
    return w


def _make_team(id: int, name: str) -> MagicMock:
    t = MagicMock()
    t.id = id
    t.name = name
    return t


def _make_result(wod_id: int, team_id: int, time_seconds=None, reps=None) -> MagicMock:
    r = MagicMock()
    r.wod_id = wod_id
    r.team_id = team_id
    r.time_seconds = time_seconds
    r.reps = reps
    return r


def test_leaderboard_vazio_sem_wods():
    lb = _compute_leaderboard("most_points", [], [], [])
    assert lb.entries == []


def test_leaderboard_vazio_sem_equipes():
    wod = _make_wod(1, "for_time")
    lb = _compute_leaderboard("most_points", [wod], [], [])
    assert lb.entries == []


def test_leaderboard_most_points_for_time_ordena_por_tempo_asc():
    """Equipe com menor tempo recebe mais pontos e fica em 1º."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=600),   # Alpha: 10 min
        _make_result(1, 2, time_seconds=480),   # Beta: 8 min (melhor)
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    assert lb.entries[0].team_id == 2  # Beta em 1º
    assert lb.entries[0].position == 1
    assert lb.entries[0].total_points == 2  # 2 equipes, 1º = 2 pts
    assert lb.entries[1].team_id == 1  # Alpha em 2º
    assert lb.entries[1].total_points == 1


def test_leaderboard_most_points_amrap_ordena_por_reps_desc():
    """Equipe com mais reps recebe mais pontos e fica em 1º."""
    wod = _make_wod(1, "amrap")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, reps=120),  # Alpha: 120 reps (melhor)
        _make_result(1, 2, reps=90),   # Beta: 90 reps
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    assert lb.entries[0].team_id == 1  # Alpha em 1º
    assert lb.entries[0].total_points == 2


def test_leaderboard_sem_resultado_recebe_zero_pontos():
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [_make_result(1, 1, time_seconds=300)]  # Beta sem resultado

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b], results)

    beta_entry = next(e for e in lb.entries if e.team_id == 2)
    assert beta_entry.total_points == 0
    assert beta_entry.wod_entries[0].rank is None


def test_leaderboard_lowest_time_soma_tempos():
    wod1 = _make_wod(1, "for_time")
    wod2 = _make_wod(2, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=300),
        _make_result(2, 1, time_seconds=240),   # Alpha total: 540
        _make_result(1, 2, time_seconds=200),
        _make_result(2, 2, time_seconds=200),   # Beta total: 400 (melhor)
    ]

    lb = _compute_leaderboard("lowest_time", [wod1, wod2], [team_a, team_b], results)

    assert lb.entries[0].team_id == 2  # Beta com menor tempo total
    assert lb.entries[0].total_points == 400  # total_points = total_seconds aqui
    assert lb.entries[1].total_points == 540


def test_leaderboard_lowest_time_incompleto_vai_ao_fim():
    """Equipe sem resultado em algum WOD vai para o final do leaderboard."""
    wod1 = _make_wod(1, "for_time")
    wod2 = _make_wod(2, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    results = [
        _make_result(1, 1, time_seconds=300),
        _make_result(2, 1, time_seconds=240),  # Alpha completo: 540
        _make_result(1, 2, time_seconds=100),  # Beta só tem WOD1
    ]

    lb = _compute_leaderboard("lowest_time", [wod1, wod2], [team_a, team_b], results)

    assert lb.entries[0].team_id == 1   # Alpha em 1º (completo)
    assert lb.entries[1].team_id == 2   # Beta ao fim (incompleto)


def test_leaderboard_empate_mesma_posicao():
    """Equipes empatadas em pontos recebem a mesma posição."""
    wod = _make_wod(1, "for_time")
    team_a = _make_team(1, "Alpha")
    team_b = _make_team(2, "Beta")
    team_c = _make_team(3, "Gamma")
    results = [
        _make_result(1, 1, time_seconds=300),
        _make_result(1, 2, time_seconds=300),  # Empate com Alpha
        _make_result(1, 3, time_seconds=600),
    ]

    lb = _compute_leaderboard("most_points", [wod], [team_a, team_b, team_c], results)

    positions = {e.team_id: e.position for e in lb.entries}
    assert positions[1] == positions[2]   # Empate em 1º
    assert positions[3] == 3             # Gamma em 3º (não em 2º)
```

- [ ] **Step 2: Rodar testes para confirmar falha**

```bash
cd backend
python -m pytest tests/unit/test_wod_result_service.py -v 2>&1 | tail -15
```

Esperado: erros de importação ou `FAILED` — `_compute_leaderboard` ainda não existe.

- [ ] **Step 3: Criar o schema**

```python
# backend/app/schemas/wod_result.py
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

    @model_validator(mode="after")
    def validate_at_least_one_value(self) -> Self:
        if self.time_seconds is None and self.reps is None:
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
    time_seconds: int | None
    reps: int | None
    points: int
    rank: int | None


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
```

- [ ] **Step 4: Criar o repository**

```python
# backend/app/repositories/wod_result.py
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wod_result import WodResult

logger = logging.getLogger(__name__)


class WodResultRepository:
    """Repositório de acesso ao banco para a entidade WodResult."""

    @staticmethod
    async def get_by_competition(
        db: AsyncSession, competition_id: int
    ) -> list[WodResult]:
        """Lista todos os resultados de uma competição."""
        result = await db.execute(
            select(WodResult).where(WodResult.competition_id == competition_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, result_id: int) -> WodResult | None:
        """Busca um resultado pelo ID."""
        result = await db.execute(
            select(WodResult).where(WodResult.id == result_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_wod_and_team(
        db: AsyncSession, wod_id: int, team_id: int
    ) -> WodResult | None:
        """Busca resultado pelo par (wod_id, team_id)."""
        result = await db.execute(
            select(WodResult)
            .where(WodResult.wod_id == wod_id)
            .where(WodResult.team_id == team_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, wod_result: WodResult) -> WodResult:
        """Persiste um novo resultado."""
        db.add(wod_result)
        await db.flush()
        await db.refresh(wod_result)
        logger.info(
            "WodResult criado: id=%s wod_id=%s team_id=%s",
            wod_result.id,
            wod_result.wod_id,
            wod_result.team_id,
        )
        return wod_result

    @staticmethod
    async def delete(db: AsyncSession, wod_result: WodResult) -> None:
        """Remove um resultado."""
        await db.delete(wod_result)
        await db.flush()
        logger.info("WodResult removido: id=%s", wod_result.id)
```

- [ ] **Step 5: Criar o service com a função `_compute_leaderboard`**

```python
# backend/app/services/wod_result.py
import logging
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wod import Wod, WodType
from app.models.wod_result import WodResult
from app.repositories.competition import CompetitionRepository
from app.repositories.team import TeamRepository
from app.repositories.wod import WodRepository
from app.repositories.wod_result import WodResultRepository
from app.schemas.wod import WodResponse
from app.schemas.wod_result import (
    LeaderboardWodEntry,
    TeamSimple,
    WodLeaderboard,
    WodLeaderboardEntry,
    WodResultResponse,
    WodResultsData,
    WodResultUpsert,
)

logger = logging.getLogger(__name__)


def _compute_leaderboard(
    scoring_model: str | None,
    wods: Sequence[Wod],
    teams: Sequence,
    results: Sequence[WodResult],
) -> WodLeaderboard:
    """Calcula o leaderboard a partir de resultados brutos.

    Args:
        scoring_model: 'most_points', 'lowest_time' ou None.
        wods: WODs da competição em ordem.
        teams: Equipes da competição.
        results: Resultados cadastrados.

    Returns:
        WodLeaderboard com entries ordenados por posição.
    """
    if not wods or not teams:
        return WodLeaderboard(scoring_model=scoring_model, entries=[])

    n_teams = len(teams)
    result_map: dict[tuple[int, int], WodResult] = {
        (r.wod_id, r.team_id): r for r in results
    }

    # Rankear equipes dentro de cada WOD
    wod_rank_map: dict[int, dict[int, tuple[int, int]]] = {}
    for wod in wods:
        team_results = [
            (t.id, result_map[(wod.id, t.id)])
            for t in teams
            if (wod.id, t.id) in result_map
        ]

        if wod.wod_type == WodType.for_time:
            team_results.sort(
                key=lambda x: (x[1].time_seconds is None, x[1].time_seconds or 0)
            )
        else:
            team_results.sort(
                key=lambda x: (x[1].reps is None, -(x[1].reps or 0))
            )

        wod_rank_map[wod.id] = {
            team_id: (rank, n_teams + 1 - rank)
            for rank, (team_id, _) in enumerate(team_results, start=1)
        }

    # Calcular total por equipe
    team_totals = []
    for team in teams:
        wod_entries = []
        total = 0
        has_missing = False

        for wod in wods:
            r = result_map.get((wod.id, team.id))
            rank_info = wod_rank_map.get(wod.id, {}).get(team.id)
            rank = rank_info[0] if rank_info else None
            points = rank_info[1] if rank_info else 0

            if scoring_model == "lowest_time":
                if r and r.time_seconds is not None:
                    total += r.time_seconds
                else:
                    has_missing = True
            else:
                total += points

            wod_entries.append(
                LeaderboardWodEntry(
                    wod_id=wod.id,
                    wod_name=wod.name,
                    time_seconds=r.time_seconds if r else None,
                    reps=r.reps if r else None,
                    points=points,
                    rank=rank,
                )
            )

        team_totals.append(
            {
                "team_id": team.id,
                "team_name": team.name,
                "total": total,
                "has_missing": has_missing,
                "wod_entries": wod_entries,
            }
        )

    # Ordenar
    if scoring_model == "lowest_time":
        team_totals.sort(
            key=lambda x: (x["has_missing"], x["total"], x["team_name"])
        )
    else:
        team_totals.sort(key=lambda x: (-x["total"], x["team_name"]))

    # Atribuir posições com suporte a empates
    entries: list[WodLeaderboardEntry] = []
    prev_total: int | None = None
    prev_missing: bool | None = None
    current_pos = 0

    for i, t in enumerate(team_totals):
        if t["total"] != prev_total or t["has_missing"] != prev_missing:
            current_pos = i + 1
        prev_total = t["total"]
        prev_missing = t["has_missing"]

        entries.append(
            WodLeaderboardEntry(
                position=current_pos,
                team_id=t["team_id"],
                team_name=t["team_name"],
                total_points=t["total"],
                wod_entries=t["wod_entries"],
            )
        )

    return WodLeaderboard(scoring_model=scoring_model, entries=entries)


class WodResultService:
    """Serviço de regras de negócio para resultados de WOD."""

    @staticmethod
    async def get_results_data(
        db: AsyncSession, competition_id: int
    ) -> WodResultsData:
        """Retorna WODs, equipes e resultados para a página de entrada.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            WodResultsData com wods, teams e results.
        """
        wods = await WodRepository.list_by_competition(db, competition_id)
        teams = await TeamRepository.get_by_competition(db, competition_id)
        results = await WodResultRepository.get_by_competition(db, competition_id)

        return WodResultsData(
            wods=[WodResponse.model_validate(w) for w in wods],
            teams=[TeamSimple.model_validate(t) for t in teams],
            results=[WodResultResponse.model_validate(r) for r in results],
        )

    @staticmethod
    async def upsert(
        db: AsyncSession, competition_id: int, data: WodResultUpsert
    ) -> WodResult:
        """Cria ou atualiza um resultado para um par (wod_id, team_id).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: Payload de upsert.

        Returns:
            WodResult persistido.

        Raises:
            HTTPException 404: WOD ou equipe não pertencem à competição.
        """
        wod = await WodRepository.get_by_id(db, data.wod_id)
        if not wod or wod.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WOD não encontrado nesta competição",
            )

        team = await TeamRepository.get_by_id(db, data.team_id)
        if not team or team.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipe não encontrada nesta competição",
            )

        existing = await WodResultRepository.get_by_wod_and_team(
            db, data.wod_id, data.team_id
        )
        if existing:
            existing.time_seconds = data.time_seconds
            existing.reps = data.reps
            existing.notes = data.notes
            await db.flush()
            await db.refresh(existing)
            return existing

        new_result = WodResult(
            competition_id=competition_id,
            wod_id=data.wod_id,
            team_id=data.team_id,
            time_seconds=data.time_seconds,
            reps=data.reps,
            notes=data.notes,
        )
        return await WodResultRepository.create(db, new_result)

    @staticmethod
    async def delete(
        db: AsyncSession, competition_id: int, result_id: int
    ) -> None:
        """Remove um resultado.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição (para validar posse).
            result_id: ID do resultado a remover.

        Raises:
            HTTPException 404: Resultado não encontrado.
        """
        result = await WodResultRepository.get_by_id(db, result_id)
        if not result or result.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resultado não encontrado",
            )
        await WodResultRepository.delete(db, result)

    @staticmethod
    async def compute_leaderboard(
        db: AsyncSession, competition_id: int
    ) -> WodLeaderboard:
        """Calcula o leaderboard de WOD results para uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            WodLeaderboard com entries ordenados por posição.
        """
        comp = await CompetitionRepository.get_by_id(db, competition_id)
        if not comp:
            return WodLeaderboard(scoring_model=None, entries=[])

        wods = await WodRepository.list_by_competition(db, competition_id)
        teams = await TeamRepository.get_by_competition(db, competition_id)
        results = await WodResultRepository.get_by_competition(db, competition_id)

        return _compute_leaderboard(comp.scoring_model, wods, teams, results)
```

- [ ] **Step 6: Rodar testes unitários**

```bash
cd backend
python -m pytest tests/unit/test_wod_result_service.py -v 2>&1 | tail -20
```

Esperado: `8 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/wod_result.py backend/app/repositories/wod_result.py backend/app/services/wod_result.py backend/tests/unit/test_wod_result_service.py
git commit -m "feat(results): schema, repository e service de WodResult com leaderboard"
```

---

## Task 3: Endpoints da API + Testes de Integração

**Files:**
- Modify: `backend/app/api/v1/competitions.py`
- Create: `backend/tests/integration/test_wod_results.py`

**Interfaces:**
- Consumes: `WodResultService`, `WodResultsData`, `WodResultResponse`, `WodResultUpsert`, `WodLeaderboard` (Task 2)
- Produces:
  - `GET /competitions/{competition_id}/wod-results` → `WodResultsData` (roles: judge/operator/admin)
  - `POST /competitions/{competition_id}/wod-results` → `WodResultResponse` 201 (roles: operator/admin)
  - `DELETE /competitions/{competition_id}/wod-results/{result_id}` → 204 (roles: operator/admin)
  - `GET /competitions/{competition_id}/wod-leaderboard` → `WodLeaderboard` (público)

- [ ] **Step 1: Escrever os testes de integração (failing)**

```python
# backend/tests/integration/test_wod_results.py
"""Testes de integração para endpoints de WodResult."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.category import Category, CategoryType
from app.models.team import Team
from app.models.wod import Wod, WodType


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(
        name="CrossFit Results Test",
        status=CompetitionStatus.active,
        scoring_model="most_points",
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def competition_lowest_time(db: AsyncSession) -> Competition:
    comp = Competition(
        name="Lowest Time Test",
        status=CompetitionStatus.active,
        scoring_model="lowest_time",
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Elite",
        category_type=CategoryType.team,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@pytest.fixture
async def wod(db: AsyncSession, competition: Competition) -> Wod:
    w = Wod(
        competition_id=competition.id,
        name="Fran",
        wod_type=WodType.for_time,
        order=1,
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


@pytest.fixture
async def team(db: AsyncSession, competition: Competition, category: Category) -> Team:
    t = Team(
        competition_id=competition.id,
        name="Alpha",
        category_id=category.id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


# ── GET /wod-results ──────────────────────────────────────────────────────────


async def test_listar_resultados_retorna_estrutura_vazia(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.get(
        f"/api/v1/competitions/{competition.id}/wod-results",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["wods"] == []
    assert data["teams"] == []
    assert data["results"] == []


async def test_listar_resultados_requer_autenticacao(
    client: AsyncClient, competition: Competition
):
    r = await client.get(f"/api/v1/competitions/{competition.id}/wod-results")
    assert r.status_code == 401


# ── POST /wod-results ─────────────────────────────────────────────────────────


async def test_criar_resultado_for_time(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id, "time_seconds": 480},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["time_seconds"] == 480
    assert data["team_id"] == team.id
    assert data["wod_id"] == wod.id


async def test_criar_resultado_reps(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    db: AsyncSession,
    category: Category,
    team: Team,
):
    wod_amrap = Wod(
        competition_id=competition.id,
        name="AMRAP 20",
        wod_type=WodType.amrap,
        order=2,
    )
    db.add(wod_amrap)
    await db.commit()
    await db.refresh(wod_amrap)

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod_amrap.id, "team_id": team.id, "reps": 150},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["reps"] == 150


async def test_upsert_sobrescreve_resultado_existente(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    payload = {"wod_id": wod.id, "team_id": team.id, "time_seconds": 300}

    await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json=payload,
        cookies={"session_id": admin_token},
    )
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={**payload, "time_seconds": 250},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["time_seconds"] == 250

    # Verificar que só existe um resultado
    list_r = await client.get(
        f"/api/v1/competitions/{competition.id}/wod-results",
        cookies={"session_id": admin_token},
    )
    assert len(list_r.json()["results"]) == 1


async def test_sem_time_nem_reps_retorna_422(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 422


async def test_wod_de_outra_competicao_retorna_404(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    db: AsyncSession,
    category: Category,
    team: Team,
):
    other_comp = Competition(name="Outra", status=CompetitionStatus.draft)
    db.add(other_comp)
    await db.commit()
    await db.refresh(other_comp)

    other_wod = Wod(
        competition_id=other_comp.id, name="WOD Outro", wod_type=WodType.for_time, order=1
    )
    db.add(other_wod)
    await db.commit()
    await db.refresh(other_wod)

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": other_wod.id, "team_id": team.id, "time_seconds": 300},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 404


async def test_judge_nao_pode_criar_resultado(
    client: AsyncClient,
    judge_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id, "time_seconds": 300},
        cookies={"session_id": judge_token},
    )
    assert r.status_code == 403


# ── DELETE /wod-results/{id} ──────────────────────────────────────────────────


async def test_deletar_resultado_retorna_204(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    wod: Wod,
    team: Team,
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/wod-results",
        json={"wod_id": wod.id, "team_id": team.id, "time_seconds": 300},
        cookies={"session_id": admin_token},
    )
    result_id = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/competitions/{competition.id}/wod-results/{result_id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 204


async def test_deletar_resultado_inexistente_retorna_404(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.delete(
        f"/api/v1/competitions/{competition.id}/wod-results/99999",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 404


# ── GET /wod-leaderboard ─────────────────────────────────────────────────────


async def test_leaderboard_publico_sem_autenticacao(
    client: AsyncClient, competition: Competition
):
    r = await client.get(f"/api/v1/competitions/{competition.id}/wod-leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data
    assert data["scoring_model"] == "most_points"


async def test_leaderboard_most_points_ordena_corretamente(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    db: AsyncSession,
    category: Category,
):
    wod1 = Wod(
        competition_id=competition.id, name="WOD A", wod_type=WodType.for_time, order=1
    )
    wod2 = Wod(
        competition_id=competition.id, name="WOD B", wod_type=WodType.amrap, order=2
    )
    db.add_all([wod1, wod2])
    team_alpha = Team(competition_id=competition.id, name="Alpha", category_id=category.id)
    team_beta = Team(competition_id=competition.id, name="Beta", category_id=category.id)
    db.add_all([team_alpha, team_beta])
    await db.commit()
    for obj in [wod1, wod2, team_alpha, team_beta]:
        await db.refresh(obj)

    # Alpha: 1º no WOD A (menor tempo), 2º no WOD B (menos reps) → total 3 pts
    # Beta: 2º no WOD A (maior tempo), 1º no WOD B (mais reps) → total 3 pts → empate
    for wod_id, team_id, time_s, reps in [
        (wod1.id, team_alpha.id, 300, None),
        (wod1.id, team_beta.id, 400, None),
        (wod2.id, team_alpha.id, None, 80),
        (wod2.id, team_beta.id, None, 100),
    ]:
        await client.post(
            f"/api/v1/competitions/{competition.id}/wod-results",
            json={"wod_id": wod_id, "team_id": team_id, "time_seconds": time_s, "reps": reps},
            cookies={"session_id": admin_token},
        )

    r = await client.get(f"/api/v1/competitions/{competition.id}/wod-leaderboard")
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 2
    # Ambos têm 3 pts → mesma posição (empate)
    assert entries[0]["total_points"] == 3
    assert entries[1]["total_points"] == 3
    assert entries[0]["position"] == entries[1]["position"] == 1
```

- [ ] **Step 2: Rodar testes para confirmar falha**

```bash
cd backend
python -m pytest tests/integration/test_wod_results.py -v 2>&1 | tail -15
```

Esperado: `FAILED` — endpoints ainda não existem.

- [ ] **Step 3: Adicionar imports e endpoints em `competitions.py`**

No topo de `backend/app/api/v1/competitions.py`, adicionar aos imports existentes:

```python
from app.schemas.wod_result import (
    WodLeaderboard,
    WodResultResponse,
    WodResultsData,
    WodResultUpsert,
)
from app.services.wod_result import WodResultService
```

Adicionar os 4 endpoints ao final do arquivo (antes de qualquer `if __name__` ou no bloco de WODs):

```python
# ── WOD Results ───────────────────────────────────────────────────────────────


@router.get(
    "/competitions/{competition_id}/wod-results",
    response_model=WodResultsData,
)
async def list_wod_results(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("judge", "operator", "admin")),
) -> WodResultsData:
    """Retorna WODs, equipes e resultados para a página de entrada (RF-results-01)."""
    return await WodResultService.get_results_data(db, competition_id)


@router.post(
    "/competitions/{competition_id}/wod-results",
    response_model=WodResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_wod_result(
    competition_id: int,
    payload: WodResultUpsert,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> WodResultResponse:
    """Cria ou atualiza resultado de uma equipe em um WOD (upsert por wod_id+team_id)."""
    result = await WodResultService.upsert(db, competition_id, payload)
    return WodResultResponse.model_validate(result)


@router.delete(
    "/competitions/{competition_id}/wod-results/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wod_result(
    competition_id: int,
    result_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> None:
    """Remove um resultado de WOD."""
    await WodResultService.delete(db, competition_id, result_id)


@router.get(
    "/competitions/{competition_id}/wod-leaderboard",
    response_model=WodLeaderboard,
)
async def get_wod_leaderboard(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> WodLeaderboard:
    """Retorna leaderboard calculado de WOD results (público — sem autenticação)."""
    return await WodResultService.compute_leaderboard(db, competition_id)
```

- [ ] **Step 4: Rodar todos os testes**

```bash
cd backend
python -m pytest tests/integration/test_wod_results.py tests/unit/test_wod_result_service.py -v 2>&1 | tail -25
```

Esperado: todos passando.

- [ ] **Step 5: Rodar suite completa para verificar regressões**

```bash
cd backend
python -m pytest 2>&1 | tail -5
```

Esperado: sem novos falhos.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/competitions.py backend/tests/integration/test_wod_results.py
git commit -m "feat(results): endpoints GET/POST/DELETE wod-results e GET wod-leaderboard"
```

---

## Task 4: Frontend — Tipos + API Client + ResultsPage + Rota

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/wod_results.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/dashboard/ResultsPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: endpoints de Task 3
- Produces:
  - `WodResult`, `WodResultsData`, `LeaderboardWodEntry`, `WodLeaderboardEntry`, `WodLeaderboard` (types)
  - `wodResultsApi.getData`, `wodResultsApi.upsert`, `wodResultsApi.delete`, `wodResultsApi.getLeaderboard` (API client)
  - Componente `ResultsPage` em `/competitions/:id/dashboard/resultados`

- [ ] **Step 1: Adicionar tipos em `frontend/src/types/index.ts`**

Adicionar ao final do arquivo, antes do último `}` ou após as interfaces existentes:

```typescript
export interface WodResult {
  id: number;
  competition_id: number;
  wod_id: number;
  team_id: number;
  time_seconds: number | null;
  reps: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface WodResultsData {
  wods: Wod[];
  teams: { id: number; name: string; category_id: number }[];
  results: WodResult[];
}

export interface LeaderboardWodEntry {
  wod_id: number;
  wod_name: string;
  time_seconds: number | null;
  reps: number | null;
  points: number;
  rank: number | null;
}

export interface WodLeaderboardEntry {
  position: number;
  team_id: number;
  team_name: string;
  total_points: number;
  wod_entries: LeaderboardWodEntry[];
}

export interface WodLeaderboard {
  scoring_model: string | null;
  entries: WodLeaderboardEntry[];
}
```

- [ ] **Step 2: Criar o API client**

```typescript
// frontend/src/api/wod_results.ts
import apiClient from "./client";
import type { WodLeaderboard, WodResult, WodResultsData } from "../types";

export interface WodResultUpsert {
  wod_id: number;
  team_id: number;
  time_seconds?: number | null;
  reps?: number | null;
  notes?: string | null;
}

export const wodResultsApi = {
  getData: (competitionId: number) =>
    apiClient
      .get<WodResultsData>(`/api/v1/competitions/${competitionId}/wod-results`)
      .then((r) => r.data),

  upsert: (competitionId: number, data: WodResultUpsert) =>
    apiClient
      .post<WodResult>(`/api/v1/competitions/${competitionId}/wod-results`, data)
      .then((r) => r.data),

  delete: (competitionId: number, resultId: number) =>
    apiClient.delete(
      `/api/v1/competitions/${competitionId}/wod-results/${resultId}`
    ),

  getLeaderboard: (competitionId: number) =>
    apiClient
      .get<WodLeaderboard>(
        `/api/v1/competitions/${competitionId}/wod-leaderboard`
      )
      .then((r) => r.data),
};
```

- [ ] **Step 3: Adicionar `/wod-leaderboard` a PUBLIC_PATHS em `client.ts`**

Em `frontend/src/api/client.ts`, localizar a linha:

```typescript
const PUBLIC_PATHS = ["/login", "/reset-password", "/forgot-password", "/register", "/signup", "/ranking"];
```

E substituir por:

```typescript
const PUBLIC_PATHS = ["/login", "/reset-password", "/forgot-password", "/register", "/signup", "/ranking", "/wod-leaderboard"];
```

- [ ] **Step 4: Criar `ResultsPage.tsx`**

```tsx
// frontend/src/pages/dashboard/ResultsPage.tsx
import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { wodResultsApi, type WodResultUpsert } from "../../api/wod_results";
import Alert from "../../components/ui/Alert";
import type { Competition, WodResult, WodResultsData } from "../../types";
import { useAuthStore } from "../../store/auth";

interface OutletCtx {
  competition: Competition;
}

function formatTime(seconds: number | null): string {
  if (seconds === null) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function parseTimeInput(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const match = trimmed.match(/^(\d+):([0-5]\d)$/);
  if (!match) return null;
  return parseInt(match[1]) * 60 + parseInt(match[2]);
}

interface EditingCell {
  teamId: number;
  wodId: number;
  existingId?: number;
}

export default function ResultsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  useOutletContext<OutletCtx>();
  const id = Number(competitionId);
  const { user } = useAuthStore();
  const canEdit = user?.role === "operator" || user?.role === "admin";

  const [data, setData] = useState<WodResultsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditingCell | null>(null);
  const [editTime, setEditTime] = useState("");
  const [editReps, setEditReps] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadData() {
    try {
      const d = await wodResultsApi.getData(id);
      setData(d);
    } catch {
      setError("Erro ao carregar resultados");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [id]);

  function getResult(teamId: number, wodId: number): WodResult | undefined {
    return data?.results.find((r) => r.team_id === teamId && r.wod_id === wodId);
  }

  function openEdit(teamId: number, wodId: number) {
    if (!canEdit) return;
    const existing = getResult(teamId, wodId);
    setEditing({ teamId, wodId, existingId: existing?.id });
    setEditTime(existing ? formatTime(existing.time_seconds) : "");
    setEditReps(existing?.reps != null ? String(existing.reps) : "");
    setEditNotes(existing?.notes ?? "");
  }

  function closeEdit() {
    setEditing(null);
    setEditTime("");
    setEditReps("");
    setEditNotes("");
  }

  async function handleSave() {
    if (!editing) return;
    const time_seconds = parseTimeInput(editTime);
    const reps = editReps.trim() ? parseInt(editReps) : null;
    if (time_seconds === null && reps === null) {
      setError("Informe pelo menos o tempo ou as repetições");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: WodResultUpsert = {
        wod_id: editing.wodId,
        team_id: editing.teamId,
        time_seconds,
        reps,
        notes: editNotes.trim() || null,
      };
      await wodResultsApi.upsert(id, payload);
      await loadData();
      closeEdit();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao salvar resultado");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!editing?.existingId) return;
    setSaving(true);
    setError(null);
    try {
      await wodResultsApi.delete(id, editing.existingId);
      await loadData();
      closeEdit();
    } catch {
      setError("Erro ao remover resultado");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  if (!data) return null;

  if (data.wods.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Resultados</h1>
        <p className="text-sm text-gray-500">
          Nenhum WOD cadastrado. Adicione WODs na etapa de configuração da competição.
        </p>
      </div>
    );
  }

  if (data.teams.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Resultados</h1>
        <p className="text-sm text-gray-500">Nenhuma equipe cadastrada.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Resultados</h1>
        {canEdit && (
          <p className="text-sm text-gray-400">Clique em uma célula para inserir resultado</p>
        )}
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500 w-40">
                Equipe
              </th>
              {data.wods.map((wod) => (
                <th
                  key={wod.id}
                  className="px-4 py-3 text-center text-xs font-medium uppercase text-gray-500"
                >
                  <div>{wod.name}</div>
                  <div className="text-gray-400 normal-case font-normal">
                    {wod.wod_type === "for_time"
                      ? "Tempo"
                      : wod.wod_type === "amrap"
                      ? "AMRAP"
                      : wod.wod_type === "emom"
                      ? "EMOM"
                      : "Carga"}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {data.teams.map((team) => (
              <tr key={team.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">{team.name}</td>
                {data.wods.map((wod) => {
                  const result = getResult(team.id, wod.id);
                  const isEditing =
                    editing?.teamId === team.id && editing?.wodId === wod.id;

                  if (isEditing) {
                    return (
                      <td key={wod.id} className="px-2 py-2">
                        <div className="space-y-1 min-w-[160px]">
                          <input
                            type="text"
                            placeholder="mm:ss"
                            value={editTime}
                            onChange={(e) => setEditTime(e.target.value)}
                            className="block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-primary-500 focus:outline-none"
                          />
                          <input
                            type="number"
                            placeholder="Reps"
                            value={editReps}
                            onChange={(e) => setEditReps(e.target.value)}
                            className="block w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-primary-500 focus:outline-none"
                          />
                          <div className="flex gap-1">
                            <button
                              onClick={handleSave}
                              disabled={saving}
                              className="flex-1 rounded bg-primary-600 px-2 py-1 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                            >
                              {saving ? "…" : "Salvar"}
                            </button>
                            {editing.existingId && (
                              <button
                                onClick={handleDelete}
                                disabled={saving}
                                className="rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-200 disabled:opacity-50"
                              >
                                ×
                              </button>
                            )}
                            <button
                              onClick={closeEdit}
                              className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-200"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      </td>
                    );
                  }

                  return (
                    <td
                      key={wod.id}
                      onClick={() => openEdit(team.id, wod.id)}
                      className={`px-4 py-3 text-center text-sm ${
                        canEdit
                          ? "cursor-pointer hover:bg-primary-50"
                          : ""
                      }`}
                    >
                      {result ? (
                        <div className="space-y-0.5">
                          {result.time_seconds != null && (
                            <div className="font-mono text-gray-900">
                              {formatTime(result.time_seconds)}
                            </div>
                          )}
                          {result.reps != null && (
                            <div className="text-xs text-gray-500">{result.reps} reps</div>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-300">{canEdit ? "+" : "—"}</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Registrar rota em `App.tsx`**

Em `frontend/src/App.tsx`, adicionar o import:

```typescript
import ResultsPage from "./pages/dashboard/ResultsPage";
```

E dentro do bloco do `CompetitionDashboardLayout`, adicionar após `<Route path="baterias" element={<HeatsPage />} />`:

```typescript
<Route path="resultados" element={<ResultsPage />} />
```

O bloco deve ficar:

```typescript
<Route
  path="/competitions/:competitionId/dashboard"
  element={<CompetitionDashboardLayout />}
>
  <Route index element={<DashboardOverviewPage />} />
  <Route path="equipes" element={<TeamsPage />} />
  <Route path="atletas" element={<AthletesPage />} />
  <Route path="baterias" element={<HeatsPage />} />
  <Route path="resultados" element={<ResultsPage />} />
</Route>
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/wod_results.ts frontend/src/api/client.ts frontend/src/pages/dashboard/ResultsPage.tsx frontend/src/App.tsx
git commit -m "feat(results): ResultsPage com tabela de entrada de resultados por WOD"
```

---

## Task 5: Frontend — Seção WOD Leaderboard na RankingPage

**Files:**
- Modify: `frontend/src/pages/RankingPage.tsx`

**Interfaces:**
- Consumes: `wodResultsApi.getLeaderboard`, `WodLeaderboard`, `WodLeaderboardEntry` (Task 4)
- Produces: seção "Leaderboard WODs" renderizada acima do ranking de timers quando `entries.length > 0`

- [ ] **Step 1: Adicionar estado e fetch do leaderboard WOD em `RankingPage.tsx`**

Localizar o bloco de `useEffect` que faz o load inicial em `RankingPage.tsx` (onde `competitionsApi.getById` e `rankingApi.get` são chamados). Adicionar ao início do arquivo o import:

```typescript
import { wodResultsApi } from "../api/wod_results";
import type { WodLeaderboard } from "../types";
```

Adicionar estado após `const [ranking, setRanking] = useState<RankingEntry[]>([])`:

```typescript
const [wodLeaderboard, setWodLeaderboard] = useState<WodLeaderboard | null>(null);
```

No `useEffect` de load inicial, adicionar a chamada paralela ao leaderboard. Localizar:

```typescript
const [comp, cats] = await Promise.all([
  competitionsApi.getById(id),
  categoriesApi.list(id, true),
]);
setCompetition(comp);
setCategories(cats);
const rankData = await rankingApi.get(id);
setRanking(rankData);
```

Substituir por:

```typescript
const [comp, cats] = await Promise.all([
  competitionsApi.getById(id),
  categoriesApi.list(id, true),
]);
setCompetition(comp);
setCategories(cats);
const [rankData, leaderboard] = await Promise.all([
  rankingApi.get(id),
  wodResultsApi.getLeaderboard(id).catch(() => null),
]);
setRanking(rankData);
if (leaderboard && leaderboard.entries.length > 0) {
  setWodLeaderboard(leaderboard);
}
```

- [ ] **Step 2: Adicionar funções de formatação no topo do componente**

Logo após as declarações de estado, adicionar:

```typescript
function formatSeconds(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
```

- [ ] **Step 3: Adicionar a seção de WOD Leaderboard no JSX**

Localizar o bloco que renderiza o ranking de timers (onde há `{ranking.length === 0 ? ...}`). Adicionar **antes** desse bloco:

```tsx
{wodLeaderboard && wodLeaderboard.entries.length > 0 && (
  <div className="mb-10">
    <h2 className="mb-4 text-xl font-bold text-white">
      Leaderboard WODs
    </h2>
    <div className="overflow-x-auto rounded-xl border border-white/10">
      <table className="min-w-full divide-y divide-white/10">
        <thead className="bg-white/5">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400 w-8">#</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-400">Equipe</th>
            {wodLeaderboard.entries[0]?.wod_entries.map((we) => (
              <th
                key={we.wod_id}
                className="px-4 py-3 text-center text-xs font-medium uppercase text-gray-400"
              >
                {we.wod_name}
              </th>
            ))}
            <th className="px-4 py-3 text-center text-xs font-medium uppercase text-gray-400">
              Total
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {wodLeaderboard.entries.map((entry) => (
            <tr key={entry.team_id} className="hover:bg-white/5">
              <td className="px-4 py-3 text-sm font-bold text-primary-400">
                {entry.position}º
              </td>
              <td className="px-4 py-3 text-sm font-medium text-white">
                {entry.team_name}
              </td>
              {entry.wod_entries.map((we) => (
                <td key={we.wod_id} className="px-4 py-3 text-center text-sm text-gray-300">
                  {wodLeaderboard.scoring_model === "lowest_time" ? (
                    we.time_seconds != null ? formatSeconds(we.time_seconds) : "—"
                  ) : (
                    we.rank != null ? (
                      <span title={`${we.points} pts`}>
                        {we.rank}º ({we.points}pts)
                      </span>
                    ) : "—"
                  )}
                </td>
              ))}
              <td className="px-4 py-3 text-center text-sm font-bold text-white">
                {wodLeaderboard.scoring_model === "lowest_time"
                  ? formatSeconds(entry.total_points)
                  : `${entry.total_points} pts`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
)}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/RankingPage.tsx
git commit -m "feat(results): seção de leaderboard WOD na página pública de ranking"
```

---

## Self-Review do Plano

**Cobertura da spec:**
- ✅ Modelo `wod_results` com todos os campos e restrição única
- ✅ Scoring `most_points`: pontos por rank por WOD, soma total
- ✅ Scoring `lowest_time`: soma de tempos, incompletos ao fim
- ✅ `null` scoring_model: leaderboard retorna entries mas sem ordem calculada (retorna entries com 0 pontos)
- ✅ Endpoints GET/POST/DELETE wod-results + GET wod-leaderboard (público)
- ✅ Validação: pelo menos time_seconds ou reps
- ✅ Validação: wod_id e team_id pertencem à competition
- ✅ ResultsPage: tabela pivô equipes × WODs com inline edit
- ✅ RankingPage: seção WOD leaderboard acima do timer ranking
- ✅ Testes unitários para leaderboard (8 casos)
- ✅ Testes de integração (11 casos)
- ✅ PUBLIC_PATHS atualizado para `/wod-leaderboard`

**Tipos consistentes entre tarefas:**
- `WodResultService.compute_leaderboard` → `WodLeaderboard` ✅
- `WodResultService.upsert` → `WodResult` (model), serializado para `WodResultResponse` no router ✅
- `wodResultsApi.getLeaderboard` → `WodLeaderboard` (type) ✅
- `WodLeaderboardEntry.total_points` usado tanto para pontos quanto para segundos dependendo de `scoring_model` — frontend usa `scoring_model` para formatar ✅
