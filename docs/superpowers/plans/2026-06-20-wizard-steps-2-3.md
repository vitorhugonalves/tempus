# Wizard de Competição — Etapas 2 e 3: Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar Etapa 2 (Divulgação: descrição, redes sociais, upload de logo/banner) e Etapa 3 (WODs para CrossFit) no `CompetitionWizardPage`, com backend completo e testes de integração.

**Architecture:** Backend segue o padrão existente `api → service → repository → model`. Novos campos de divulgação são adicionados ao modelo `Competition`. Um novo modelo `Wod` com relacionamento FK é criado para WODs de CrossFit. Upload de logo e banner segue o padrão binário do `BoxSettings`. Etapa 3 do wizard é pulada automaticamente para eventos Hyrox.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.x async + Alembic + PostgreSQL | React 18 + TypeScript + TailwindCSS + axios

## Global Constraints

- `flush()` em repositories, nunca `commit()` — commit pertence exclusivamente ao `get_db`
- Type hints obrigatórios em todas as funções públicas
- Docstrings Google Style obrigatórias em services e repositories
- `async def` em todas as rotas e funções de I/O
- Testes usam SQLite `:memory:` — nunca banco de produção
- ENUMs PostgreSQL em `op.create_table`: deixar o SQLAlchemy criar automaticamente (não usar `op.execute("CREATE TYPE ...")`)
- ENUMs PostgreSQL em `batch_alter_table`: criar manualmente com `op.execute("CREATE TYPE ...")` antes do bloco
- Convenção de commits: `<tipo>(<escopo>): <descrição em português>`
- Rotas protegidas usam `require_roles("operator", "admin")` como `Depends`

## Mapa de Arquivos

| Arquivo | Ação |
|---|---|
| `backend/app/models/competition.py` | Modificar — 9 campos novos + `wods` relationship |
| `backend/app/models/wod.py` | Criar — modelo `Wod` + enum `WodType` |
| `backend/app/models/__init__.py` | Modificar — exportar `Wod`, `WodType` |
| `backend/app/schemas/competition.py` | Modificar — campos novos em Create/Update/Response |
| `backend/app/schemas/wod.py` | Criar — `WodCreate`, `WodResponse` |
| `backend/app/repositories/wod.py` | Criar — `WodRepository` |
| `backend/app/services/wod.py` | Criar — `WodService` |
| `backend/app/api/v1/competitions.py` | Modificar — endpoints logo, banner, wods |
| `backend/app/db/migrations/versions/20260620_competition_divulgacao_wods.py` | Criar — migration |
| `backend/tests/integration/test_wods.py` | Criar — testes de integração |
| `frontend/src/types/index.ts` | Modificar — `WodType`, `Wod` interface |
| `frontend/src/api/competitions.ts` | Modificar — funções de upload e WODs |
| `frontend/src/pages/CompetitionWizardPage.tsx` | Modificar — Etapas 2 e 3 + Resumo |

---

## Task 1: Migration + Modelos

**Files:**
- Modify: `backend/app/models/competition.py`
- Create: `backend/app/models/wod.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/db/migrations/versions/20260620_competition_divulgacao_wods.py`

**Interfaces:**
- Produces: `Wod` (ORM model), `WodType` (enum) — consumidos pelas Tasks 2, 3, 4

- [ ] **Step 1: Adicionar campos ao modelo Competition**

Editar `backend/app/models/competition.py`. Adicionar `LargeBinary` e `Text` nos imports de `sqlalchemy`, adicionar os 9 novos campos e o relacionamento com `Wod`:

```python
import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompetitionStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    finished = "finished"


class EventType(str, enum.Enum):
    hyrox = "hyrox"
    crossfit = "crossfit"


class ScoringModel(str, enum.Enum):
    lowest_time = "lowest_time"
    most_points = "most_points"


class TiebreakCriterion(str, enum.Enum):
    last_checkpoint = "last_checkpoint"
    registration_date = "registration_date"
    alphabetical = "alphabetical"


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_type: Mapped[EventType | None] = mapped_column(Enum(EventType), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scoring_model: Mapped[ScoringModel | None] = mapped_column(Enum(ScoringModel), nullable=True)
    tiebreak_criterion: Mapped[TiebreakCriterion | None] = mapped_column(
        Enum(TiebreakCriterion), nullable=True
    )
    status: Mapped[CompetitionStatus] = mapped_column(
        Enum(CompetitionStatus), nullable=False, default=CompetitionStatus.draft
    )
    # Divulgação
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    regulations_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registration_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    whatsapp_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    banner_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    banner_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    categories: Mapped[list["Category"]] = relationship(  # noqa: F821
        "Category", back_populates="competition", cascade="all, delete-orphan"
    )
    registrations: Mapped[list["CompetitorRegistration"]] = relationship(  # noqa: F821
        "CompetitorRegistration", back_populates="competition", cascade="all, delete-orphan"
    )
    teams: Mapped[list["Team"]] = relationship(  # noqa: F821
        "Team", back_populates="competition", cascade="all, delete-orphan"
    )
    heats: Mapped[list["Heat"]] = relationship(  # noqa: F821
        "Heat", back_populates="competition", cascade="all, delete-orphan"
    )
    timers: Mapped[list["Timer"]] = relationship(  # noqa: F821
        "Timer", back_populates="competition", cascade="all, delete-orphan"
    )
    penalty_types: Mapped[list["PenaltyType"]] = relationship(  # noqa: F821
        "PenaltyType", back_populates="competition", cascade="all, delete-orphan"
    )
    athletes: Mapped[list["Athlete"]] = relationship(  # noqa: F821
        "Athlete", back_populates="competition", cascade="all, delete-orphan"
    )
    wods: Mapped[list["Wod"]] = relationship(  # noqa: F821
        "Wod", back_populates="competition", cascade="all, delete-orphan", order_by="Wod.order"
    )
```

- [ ] **Step 2: Criar modelo Wod**

Criar `backend/app/models/wod.py`:

```python
import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WodType(str, enum.Enum):
    amrap = "amrap"
    for_time = "for_time"
    emom = "emom"
    max_load = "max_load"


class Wod(Base):
    """WOD (Workout of the Day) vinculado a uma competição CrossFit."""

    __tablename__ = "wods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    wod_type: Mapped[WodType] = mapped_column(Enum(WodType), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="wods"
    )
```

- [ ] **Step 3: Registrar Wod no __init__.py dos models**

Editar `backend/app/models/__init__.py`:

```python
from app.models.category import Category, CategoryType
from app.models.competitor import CompetitorRegistration
from app.models.competition import Competition, CompetitionStatus
from app.models.heat import Heat, HeatStatus, HeatTeam
from app.models.modality import Modality
from app.models.session import Session
from app.models.team import Team, TeamMember
from app.models.timer import Penalty, PenaltyType, Timer, TimerEvent, TimerStatus
from app.models.token import InviteToken, PasswordResetToken
from app.models.user import User, UserRole
from app.models.wod import Wod, WodType

__all__ = [
    "Category",
    "CategoryType",
    "Competition",
    "CompetitionStatus",
    "CompetitorRegistration",
    "Heat",
    "HeatStatus",
    "HeatTeam",
    "InviteToken",
    "Modality",
    "Penalty",
    "PenaltyType",
    "PasswordResetToken",
    "Session",
    "Team",
    "TeamMember",
    "Timer",
    "TimerEvent",
    "TimerStatus",
    "User",
    "UserRole",
    "Wod",
    "WodType",
]
```

- [ ] **Step 4: Criar migration**

Criar `backend/app/db/migrations/versions/20260620_competition_divulgacao_wods.py`:

```python
"""competition_divulgacao_wods

Revision ID: 20260620_competition_divulgacao_wods
Revises: 20260615_athletes_table
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from alembic import op

revision = "20260620_competition_divulgacao_wods"
down_revision = "20260615_athletes_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Campos de divulgação na tabela competitions
    with op.batch_alter_table("competitions") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("regulations_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("registration_url", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("instagram_url", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("whatsapp_url", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("logo_data", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("logo_mime_type", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("banner_data", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("banner_mime_type", sa.String(50), nullable=True))

    # 2. Tabela wods — SQLAlchemy cria o ENUM wodtype automaticamente via create_table
    op.create_table(
        "wods",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "wod_type",
            sa.Enum("amrap", "for_time", "emom", "max_load", name="wodtype"),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("wods")
    op.execute("DROP TYPE IF EXISTS wodtype")

    with op.batch_alter_table("competitions") as batch_op:
        batch_op.drop_column("banner_mime_type")
        batch_op.drop_column("banner_data")
        batch_op.drop_column("logo_mime_type")
        batch_op.drop_column("logo_data")
        batch_op.drop_column("whatsapp_url")
        batch_op.drop_column("instagram_url")
        batch_op.drop_column("registration_url")
        batch_op.drop_column("regulations_url")
        batch_op.drop_column("description")
```

- [ ] **Step 5: Aplicar migration no ambiente de desenvolvimento**

```bash
docker compose -f docker/docker-compose.yml exec backend alembic upgrade head
```

Resultado esperado:
```
INFO  [alembic.runtime.migration] Running upgrade 20260615_athletes_table -> 20260620_competition_divulgacao_wods, competition_divulgacao_wods
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/competition.py backend/app/models/wod.py backend/app/models/__init__.py backend/app/db/migrations/versions/20260620_competition_divulgacao_wods.py
git commit -m "db(competitions): adiciona campos de divulgação e modelo Wod"
```

---

## Task 2: Schemas Pydantic

**Files:**
- Modify: `backend/app/schemas/competition.py`
- Create: `backend/app/schemas/wod.py`

**Interfaces:**
- Consumes: `WodType` de `app.models.wod`
- Produces:
  - `CompetitionCreate`, `CompetitionUpdate`, `CompetitionResponse` (atualizados) — consumidos pela Task 4
  - `WodCreate`, `WodResponse` — consumidos pelas Tasks 3 e 4

- [ ] **Step 1: Escrever teste de validação dos schemas**

Criar `backend/tests/unit/test_wod_schemas.py`:

```python
import pytest
from app.schemas.wod import WodCreate, WodResponse
from app.models.wod import WodType
from datetime import datetime


def test_wod_create_valida_campos_obrigatorios():
    wod = WodCreate(name="Grace", wod_type=WodType.for_time)
    assert wod.name == "Grace"
    assert wod.wod_type == WodType.for_time
    assert wod.duration_minutes is None
    assert wod.description is None
    assert wod.order == 0


def test_wod_create_com_todos_campos():
    wod = WodCreate(
        name="Fran",
        wod_type=WodType.for_time,
        duration_minutes=7,
        description="21-15-9 Thrusters + Pull-ups",
        order=1,
    )
    assert wod.duration_minutes == 7
    assert wod.description == "21-15-9 Thrusters + Pull-ups"


def test_wod_response_from_attributes():
    class FakeWod:
        id = 1
        competition_id = 42
        name = "Grace"
        wod_type = WodType.for_time
        duration_minutes = 10
        description = "30 Clean and Jerk"
        order = 0
        created_at = datetime(2026, 6, 20)
        updated_at = datetime(2026, 6, 20)

    resp = WodResponse.model_validate(FakeWod())
    assert resp.id == 1
    assert resp.competition_id == 42
    assert resp.wod_type == WodType.for_time
```

- [ ] **Step 2: Rodar o teste — deve falhar**

```bash
cd backend && pytest tests/unit/test_wod_schemas.py -v
```

Esperado: `FAILED` — `ModuleNotFoundError: No module named 'app.schemas.wod'`

- [ ] **Step 3: Criar app/schemas/wod.py**

```python
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

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Atualizar app/schemas/competition.py**

Adicionar os novos campos em `CompetitionCreate`, `CompetitionUpdate` e `CompetitionResponse`:

```python
from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models.competition import (
    CompetitionStatus,
    EventType,
    ScoringModel,
    TiebreakCriterion,
)


class CompetitionCreate(BaseModel):
    name: str
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    event_type: EventType | None = None
    is_public: bool = False
    scoring_model: ScoringModel | None = None
    tiebreak_criterion: TiebreakCriterion | None = None
    description: str | None = None
    regulations_url: str | None = None
    registration_url: str | None = None
    instagram_url: str | None = None
    whatsapp_url: str | None = None

    @field_validator("start_date")
    @classmethod
    def start_date_not_in_past(cls, v: date | None) -> date | None:
        """Rejeita datas de início no passado."""
        if v is not None and v < date.today():
            raise ValueError("A data de início não pode ser no passado")
        return v


class CompetitionUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    event_type: EventType | None = None
    is_public: bool | None = None
    scoring_model: ScoringModel | None = None
    tiebreak_criterion: TiebreakCriterion | None = None
    status: CompetitionStatus | None = None
    description: str | None = None
    regulations_url: str | None = None
    registration_url: str | None = None
    instagram_url: str | None = None
    whatsapp_url: str | None = None

    @field_validator("start_date")
    @classmethod
    def start_date_not_in_past(cls, v: date | None) -> date | None:
        """Rejeita datas de início no passado."""
        if v is not None and v < date.today():
            raise ValueError("A data de início não pode ser no passado")
        return v


class CompetitionResponse(BaseModel):
    id: int
    name: str
    location: str | None
    start_date: date | None
    end_date: date | None
    event_type: EventType | None
    is_public: bool
    scoring_model: ScoringModel | None
    tiebreak_criterion: TiebreakCriterion | None
    status: CompetitionStatus
    description: str | None
    regulations_url: str | None
    registration_url: str | None
    instagram_url: str | None
    whatsapp_url: str | None
    has_logo: bool = False
    has_banner: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

> **Nota sobre `has_logo`/`has_banner`:** Esses campos serão populados manualmente no router (Task 4), pois o dado binário não deve ser incluído na resposta JSON. Todos os outros `CompetitionResponse.model_validate(c)` no router precisarão ser substituídos por um helper `_to_response(c)`.

- [ ] **Step 5: Rodar os testes — devem passar**

```bash
cd backend && pytest tests/unit/test_wod_schemas.py -v
```

Esperado: `3 passed`

- [ ] **Step 6: Garantir que os testes existentes ainda passam**

```bash
cd backend && pytest tests/ -v --ignore=tests/integration
```

Esperado: todos passando (os schemas existentes só ganharam campos opcionais).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/competition.py backend/app/schemas/wod.py backend/tests/unit/test_wod_schemas.py
git commit -m "feat(schemas): adiciona campos de divulgação e schema WOD"
```

---

## Task 3: Repository e Service de WODs

**Files:**
- Create: `backend/app/repositories/wod.py`
- Create: `backend/app/services/wod.py`

**Interfaces:**
- Consumes: `Wod` (model), `WodCreate` (schema), `AsyncSession` (db)
- Produces:
  - `WodRepository.create(db, wod) -> Wod`
  - `WodRepository.list_by_competition(db, competition_id) -> list[Wod]`
  - `WodRepository.delete(db, wod) -> None`
  - `WodRepository.get_by_id(db, wod_id) -> Wod | None`
  - `WodService.create_wod(db, competition_id, payload) -> Wod`
  - `WodService.list_wods(db, competition_id) -> list[Wod]`
  - `WodService.delete_wod(db, competition_id, wod_id) -> None`

- [ ] **Step 1: Criar app/repositories/wod.py**

```python
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wod import Wod

logger = logging.getLogger(__name__)


class WodRepository:
    """Repositório de acesso ao banco para a entidade Wod."""

    @staticmethod
    async def get_by_id(db: AsyncSession, wod_id: int) -> Wod | None:
        """Busca um WOD pelo ID.

        Args:
            db: Sessão assíncrona do banco de dados.
            wod_id: Identificador único do WOD.

        Returns:
            Objeto Wod ou None se não encontrado.
        """
        result = await db.execute(select(Wod).where(Wod.id == wod_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_competition(db: AsyncSession, competition_id: int) -> list[Wod]:
        """Lista todos os WODs de uma competição ordenados por `order`.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição.

        Returns:
            Lista de objetos Wod.
        """
        result = await db.execute(
            select(Wod)
            .where(Wod.competition_id == competition_id)
            .order_by(Wod.order)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, wod: Wod) -> Wod:
        """Persiste um novo WOD no banco de dados.

        Args:
            db: Sessão assíncrona do banco de dados.
            wod: Objeto Wod a ser criado.

        Returns:
            Objeto Wod com ID populado.
        """
        db.add(wod)
        await db.flush()
        await db.refresh(wod)
        logger.info("WOD criado: id=%s competition_id=%s", wod.id, wod.competition_id)
        return wod

    @staticmethod
    async def delete(db: AsyncSession, wod: Wod) -> None:
        """Remove um WOD do banco de dados.

        Args:
            db: Sessão assíncrona do banco de dados.
            wod: Objeto Wod a ser removido.
        """
        await db.delete(wod)
        await db.flush()
        logger.info("WOD removido: id=%s", wod.id)
```

- [ ] **Step 2: Criar app/services/wod.py**

```python
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wod import Wod
from app.repositories.competition import CompetitionRepository
from app.repositories.wod import WodRepository
from app.schemas.wod import WodCreate

logger = logging.getLogger(__name__)


class WodService:
    """Serviço de regras de negócio para WODs."""

    @staticmethod
    async def create_wod(db: AsyncSession, competition_id: int, payload: WodCreate) -> Wod:
        """Cria um novo WOD vinculado a uma competição.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição pai.
            payload: Dados do WOD a ser criado.

        Returns:
            Objeto Wod criado.

        Raises:
            HTTPException 404: Se a competição não existir.
        """
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if competition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competição não encontrada",
            )
        wod = Wod(competition_id=competition_id, **payload.model_dump())
        return await WodRepository.create(db, wod)

    @staticmethod
    async def list_wods(db: AsyncSession, competition_id: int) -> list[Wod]:
        """Lista WODs de uma competição ordenados por order.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição.

        Returns:
            Lista de WODs.
        """
        return await WodRepository.list_by_competition(db, competition_id)

    @staticmethod
    async def delete_wod(db: AsyncSession, competition_id: int, wod_id: int) -> None:
        """Remove um WOD, verificando que pertence à competição informada.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: ID da competição.
            wod_id: ID do WOD a ser removido.

        Raises:
            HTTPException 404: Se o WOD não existir ou não pertencer à competição.
        """
        wod = await WodRepository.get_by_id(db, wod_id)
        if wod is None or wod.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="WOD não encontrado",
            )
        await WodRepository.delete(db, wod)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/repositories/wod.py backend/app/services/wod.py
git commit -m "feat(wods): adiciona repository e service de WODs"
```

---

## Task 4: Endpoints de API (logo, banner, WODs) + Testes de integração

**Files:**
- Modify: `backend/app/api/v1/competitions.py`
- Create: `backend/tests/integration/test_wods.py`

**Interfaces:**
- Consumes: `WodService`, `WodCreate`, `WodResponse`, `CompetitionRepository`
- Produces: endpoints REST que serão consumidos pelo frontend (Task 5)

- [ ] **Step 1: Escrever testes de integração**

Criar `backend/tests/integration/test_wods.py`:

```python
import pytest
from httpx import AsyncClient


# ── Fixtures helpers ──────────────────────────────────────────────────────────


async def _criar_competicao_crossfit(client: AsyncClient, admin_token: str) -> int:
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": "CrossFit Open 2026", "event_type": "crossfit"},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── WODs ──────────────────────────────────────────────────────────────────────


async def test_listar_wods_competicao_vazia_retorna_lista_vazia(
    client: AsyncClient, admin_token: str
):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.get(f"/api/v1/competitions/{comp_id}/wods")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_criar_wod_como_admin_retorna_201(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/wods",
        json={"name": "Fran", "wod_type": "for_time", "duration_minutes": 7},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Fran"
    assert data["wod_type"] == "for_time"
    assert data["competition_id"] == comp_id


async def test_criar_wod_como_competidor_retorna_403(
    client: AsyncClient, competitor_token: str, admin_token: str
):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/wods",
        json={"name": "Grace", "wod_type": "for_time"},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403


async def test_criar_wod_competicao_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/api/v1/competitions/99999/wods",
        json={"name": "Grace", "wod_type": "for_time"},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 404


async def test_deletar_wod_retorna_204(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    criar = await client.post(
        f"/api/v1/competitions/{comp_id}/wods",
        json={"name": "Cindy", "wod_type": "amrap", "duration_minutes": 20},
        cookies={"session_id": admin_token},
    )
    wod_id = criar.json()["id"]

    resp = await client.delete(
        f"/api/v1/competitions/{comp_id}/wods/{wod_id}",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 204

    lista = await client.get(f"/api/v1/competitions/{comp_id}/wods")
    assert lista.json() == []


async def test_deletar_wod_inexistente_retorna_404(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.delete(
        f"/api/v1/competitions/{comp_id}/wods/99999",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 404


async def test_listar_wods_ordenados_por_order(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    for name, order in [("WOD C", 2), ("WOD A", 0), ("WOD B", 1)]:
        await client.post(
            f"/api/v1/competitions/{comp_id}/wods",
            json={"name": name, "wod_type": "amrap", "order": order},
            cookies={"session_id": admin_token},
        )
    resp = await client.get(f"/api/v1/competitions/{comp_id}/wods")
    nomes = [w["name"] for w in resp.json()]
    assert nomes == ["WOD A", "WOD B", "WOD C"]


# ── Campos de divulgação ──────────────────────────────────────────────────────


async def test_atualizar_campos_divulgacao_retorna_200(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.patch(
        f"/api/v1/competitions/{comp_id}",
        json={
            "description": "Maior evento CrossFit do Brasil",
            "instagram_url": "https://instagram.com/tempus",
            "whatsapp_url": "https://wa.me/5511999999999",
            "is_public": True,
        },
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Maior evento CrossFit do Brasil"
    assert data["instagram_url"] == "https://instagram.com/tempus"
    assert data["is_public"] is True


async def test_logo_inexistente_retorna_404(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.get(f"/api/v1/competitions/{comp_id}/logo")
    assert resp.status_code == 404


async def test_upload_logo_invalido_retorna_422(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/logo",
        files={"file": ("test.txt", b"not an image", "text/plain")},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Rodar os testes — devem falhar**

```bash
cd backend && pytest tests/integration/test_wods.py -v
```

Esperado: `FAILED` — `404 Not Found` nos endpoints de WODs (ainda não existem).

- [ ] **Step 3: Adicionar helper _to_response e endpoints ao router de competições**

Editar `backend/app/api/v1/competitions.py`. Adicionar ao topo dos imports:

```python
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
```

Adicionar logo após os imports existentes (antes da definição do `router`):

```python
from app.models.wod import Wod
from app.repositories.wod import WodRepository
from app.schemas.wod import WodCreate, WodResponse
from app.services.wod import WodService
```

Adicionar constantes de upload (logo após os imports):

```python
_ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
_EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _resolve_image_mime(file: UploadFile) -> str | None:
    """Retorna MIME type do arquivo, inferindo pela extensão quando necessário."""
    ct = (file.content_type or "").lower()
    if ct in _ALLOWED_IMAGE_MIME:
        return ct
    if file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext in _EXT_TO_MIME:
            return _EXT_TO_MIME[ext]
    return None


def _to_response(c: Competition) -> CompetitionResponse:
    """Constrói CompetitionResponse com flags has_logo e has_banner."""
    resp = CompetitionResponse.model_validate(c)
    resp.has_logo = c.logo_data is not None
    resp.has_banner = c.banner_data is not None
    return resp
```

Substituir TODAS as ocorrências de `CompetitionResponse.model_validate(c)` no router pelo helper `_to_response(c)`. Há 4 pontos: `list_competitions`, `create_competition`, `get_competition`, `update_competition`.

Adicionar os novos endpoints ao final do arquivo (antes dos endpoints de baterias/equipes, ou em seção separada):

```python
# ── Logo e Banner da competição ───────────────────────────────────────────────


@router.post(
    "/competitions/{competition_id}/logo",
    response_model=CompetitionResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_competition_logo(
    competition_id: int,
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Faz upload do logotipo de uma competição (Operador/Admin).

    Formatos aceitos: PNG, JPEG, GIF, WebP. Tamanho máximo: 5 MB.
    """
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")

    mime_type = _resolve_image_mime(file)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato não suportado. Aceitos: PNG, JPEG, GIF, WebP",
        )
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Imagem muito grande. Máximo: 5 MB",
        )
    competition.logo_data = data
    competition.logo_mime_type = mime_type
    updated = await CompetitionRepository.update(db, competition)
    return _to_response(updated)


@router.get("/competitions/{competition_id}/logo")
async def get_competition_logo(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Retorna o logotipo da competição como imagem binária (público)."""
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None or not competition.logo_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo não encontrado")
    return Response(content=competition.logo_data, media_type=competition.logo_mime_type or "image/png")


@router.post(
    "/competitions/{competition_id}/banner",
    response_model=CompetitionResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_competition_banner(
    competition_id: int,
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Faz upload do banner de uma competição (Operador/Admin).

    Formatos aceitos: PNG, JPEG, GIF, WebP. Tamanho máximo: 5 MB.
    """
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")

    mime_type = _resolve_image_mime(file)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Formato não suportado. Aceitos: PNG, JPEG, GIF, WebP",
        )
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Imagem muito grande. Máximo: 5 MB",
        )
    competition.banner_data = data
    competition.banner_mime_type = mime_type
    updated = await CompetitionRepository.update(db, competition)
    return _to_response(updated)


@router.get("/competitions/{competition_id}/banner")
async def get_competition_banner(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Retorna o banner da competição como imagem binária (público)."""
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None or not competition.banner_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner não encontrado")
    return Response(content=competition.banner_data, media_type=competition.banner_mime_type or "image/png")


# ── WODs ─────────────────────────────────────────────────────────────────────


@router.get("/competitions/{competition_id}/wods", response_model=list[WodResponse])
async def list_wods(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[WodResponse]:
    """Lista WODs de uma competição ordenados por order (público)."""
    wods = await WodService.list_wods(db, competition_id)
    return [WodResponse.model_validate(w) for w in wods]


@router.post(
    "/competitions/{competition_id}/wods",
    response_model=WodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_wod(
    competition_id: int,
    payload: WodCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> WodResponse:
    """Cria um WOD vinculado à competição (Operador/Admin)."""
    wod = await WodService.create_wod(db, competition_id, payload)
    return WodResponse.model_validate(wod)


@router.delete(
    "/competitions/{competition_id}/wods/{wod_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wod(
    competition_id: int,
    wod_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove um WOD (Operador/Admin)."""
    await WodService.delete_wod(db, competition_id, wod_id)
```

- [ ] **Step 4: Rodar os testes de integração**

```bash
cd backend && pytest tests/integration/test_wods.py -v
```

Esperado: todos os testes passando.

- [ ] **Step 5: Rodar toda a suite de testes**

```bash
cd backend && pytest tests/ -v
```

Esperado: todos os testes passando.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/competitions.py backend/app/repositories/wod.py backend/app/services/wod.py backend/tests/integration/test_wods.py
git commit -m "feat(api): adiciona endpoints de logo, banner e WODs em competitions"
```

---

## Task 5: Frontend — Tipos e API Client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/competitions.ts`

**Interfaces:**
- Produces:
  - `WodType` (union type), `Wod` (interface) — consumidos pela Task 6
  - `competitionsApi.uploadLogo`, `uploadBanner`, `listWods`, `createWod`, `deleteWod` — consumidos pela Task 6

- [ ] **Step 1: Adicionar tipos Wod em frontend/src/types/index.ts**

Localizar o final do arquivo e adicionar:

```typescript
export type WodType = "amrap" | "for_time" | "emom" | "max_load";

export interface Wod {
  id: number;
  competition_id: number;
  name: string;
  wod_type: WodType;
  duration_minutes: number | null;
  description: string | null;
  order: number;
  created_at: string;
  updated_at: string;
}
```

Também atualizar a interface `Competition` (se existir em `types/index.ts`) para incluir os campos novos:

```typescript
// Adicionar estes campos na interface Competition existente:
description?: string | null;
regulations_url?: string | null;
registration_url?: string | null;
instagram_url?: string | null;
whatsapp_url?: string | null;
has_logo?: boolean;
has_banner?: boolean;
```

- [ ] **Step 2: Adicionar funções na API client de competições**

Editar `frontend/src/api/competitions.ts`. Adicionar ao objeto `competitionsApi`:

```typescript
// Upload de logo
uploadLogo: (id: number, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient.post(`/api/v1/competitions/${id}/logo`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
},

// Upload de banner
uploadBanner: (id: number, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient.post(`/api/v1/competitions/${id}/banner`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
},

// WODs
listWods: (competitionId: number) =>
  apiClient.get<Wod[]>(`/api/v1/competitions/${competitionId}/wods`),

createWod: (competitionId: number, data: WodCreate) =>
  apiClient.post<Wod>(`/api/v1/competitions/${competitionId}/wods`, data),

deleteWod: (competitionId: number, wodId: number) =>
  apiClient.delete(`/api/v1/competitions/${competitionId}/wods/${wodId}`),
```

Adicionar os tipos de request de WOD no topo do arquivo (após os imports):

```typescript
export interface WodCreate {
  name: string;
  wod_type: WodType;
  duration_minutes?: number | null;
  description?: string | null;
  order?: number;
}
```

E adicionar o import de `Wod` e `WodType`:

```typescript
import type { Competition, EventType, RankingEntry, ScoringModel, TiebreakCriterion, Wod, WodType } from "../types";
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/competitions.ts
git commit -m "feat(frontend): adiciona tipos Wod e funções de API para WODs e imagens"
```

---

## Task 6: Frontend — Wizard Etapas 2, 3 e Resumo

**Files:**
- Modify: `frontend/src/pages/CompetitionWizardPage.tsx`

**Interfaces:**
- Consumes: `competitionsApi.uploadLogo`, `uploadBanner`, `listWods`, `createWod`, `deleteWod`; `Wod`, `WodCreate`, `WodType`

- [ ] **Step 1: Adicionar interfaces e estado do wizard**

Primeiro, atualizar os imports no topo de `CompetitionWizardPage.tsx`:

```typescript
// Atualizar import de types — adicionar Wod e WodType
import type { EventType, ScoringModel, TiebreakCriterion, Wod, WodType } from "../types";

// Atualizar import da API — adicionar WodCreate
import { competitionsApi, type CompetitionCreate, type WodCreate } from "../api/competitions";
```

Em seguida, após as interfaces existentes (`WizardStep1`, `WizardStep4`), adicionar:

```typescript
interface WizardStep2 {
  is_public: boolean;
  description: string;
  regulations_url: string;
  registration_url: string;
  instagram_url: string;
  whatsapp_url: string;
}

interface WizardStep3 {
  wods: Wod[];
}
```

Atualizar `WizardState` para incluir as novas etapas:

```typescript
interface WizardState {
  step1: WizardStep1;
  step2: WizardStep2;
  step3: WizardStep3;
  step4: WizardStep4;
}
```

Atualizar `INITIAL_STATE`:

```typescript
const INITIAL_STATE: WizardState = {
  step1: {
    name: "",
    start_date: "",
    end_date: "",
    cep: "",
    logradouro: "",
    bairro: "",
    cidade: "",
    uf: "",
    numero: "",
    complemento: "",
    event_type: "",
  },
  step2: {
    is_public: false,
    description: "",
    regulations_url: "",
    registration_url: "",
    instagram_url: "",
    whatsapp_url: "",
  },
  step3: { wods: [] },
  step4: { scoring_model: "", tiebreak_criterion: "" },
};
```

- [ ] **Step 2: Adicionar estados de upload e WOD**

Após os estados existentes (dentro do componente), adicionar:

```typescript
const [logoUploading, setLogoUploading] = useState(false);
const [bannerUploading, setBannerUploading] = useState(false);
const [createdCompId, setCreatedCompId] = useState<number | null>(id ? Number(id) : null);
const [wodAdding, setWodAdding] = useState(false);
const [wodForm, setWodForm] = useState<WodCreate>({
  name: "",
  wod_type: "amrap",
  duration_minutes: undefined,
  description: "",
  order: 0,
});
```

- [ ] **Step 3: Carregar WODs em modo edição**

No `useEffect` que carrega a competição (já existente), adicionar após `setState(...)`:

```typescript
if (c.event_type === "crossfit") {
  const wodsResp = await competitionsApi.listWods(Number(id));
  const wods = (wodsResp.data ?? wodsResp) as Wod[];
  setState((prev) => ({ ...prev, step3: { wods } }));
}
// Campos de divulgação
setState((prev) => ({
  ...prev,
  step2: {
    is_public: c.is_public ?? false,
    description: c.description ?? "",
    regulations_url: c.regulations_url ?? "",
    registration_url: c.registration_url ?? "",
    instagram_url: c.instagram_url ?? "",
    whatsapp_url: c.whatsapp_url ?? "",
  },
}));
```

- [ ] **Step 4: Lógica de navegação com skip do Step 3 para Hyrox**

Atualizar `handleNext` para pular a Etapa 3 quando o tipo for Hyrox:

```typescript
function handleNext() {
  setError(null);
  if (currentStep === 1) {
    const err = validateStep1();
    if (err) { setError(err); return; }
  }
  if (currentStep === 4) {
    const err = validateStep4();
    if (err) { setError(err); return; }
  }
  // Pular Etapa 3 (WODs) para eventos Hyrox
  if (currentStep === 2 && state.step1.event_type === "hyrox") {
    setCurrentStep(4);
    return;
  }
  setCurrentStep((s) => Math.min(s + 1, 5));
}

function handleBack() {
  setError(null);
  // Pular Etapa 3 (WODs) ao voltar para Hyrox
  if (currentStep === 4 && state.step1.event_type === "hyrox") {
    setCurrentStep(2);
    return;
  }
  setCurrentStep((s) => Math.max(s - 1, 1));
}
```

- [ ] **Step 5: Atualizar handleSubmit para incluir campos de divulgação e registrar o ID criado**

```typescript
async function handleSubmit() {
  setSubmitting(true);
  setError(null);
  const locationParts = [
    state.step1.logradouro,
    state.step1.numero,
    state.step1.bairro,
    state.step1.cidade,
    state.step1.uf,
  ].filter(Boolean);

  const payload: CompetitionCreate = {
    name: state.step1.name,
    location: locationParts.join(", ") || undefined,
    start_date: state.step1.start_date || undefined,
    end_date: state.step1.end_date || undefined,
    event_type: (state.step1.event_type as EventType) || undefined,
    scoring_model: (state.step4.scoring_model as ScoringModel) || undefined,
    tiebreak_criterion: (state.step4.tiebreak_criterion as TiebreakCriterion) || undefined,
    is_public: state.step2.is_public,
    description: state.step2.description || undefined,
    regulations_url: state.step2.regulations_url || undefined,
    registration_url: state.step2.registration_url || undefined,
    instagram_url: state.step2.instagram_url || undefined,
    whatsapp_url: state.step2.whatsapp_url || undefined,
  };

  try {
    let result: any;
    if (isEdit && id) {
      result = await competitionsApi.update(Number(id), payload);
    } else {
      result = await competitionsApi.create(payload);
    }
    const comp = result.data ?? result;
    setCreatedCompId(comp.id);
    navigate(`/competitions/${comp.id}/dashboard`);
  } catch (e: any) {
    setError(e?.response?.data?.detail ?? "Erro ao salvar campeonato");
  } finally {
    setSubmitting(false);
  }
}
```

- [ ] **Step 6: Adicionar handlers de upload e WOD**

```typescript
async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
  const file = e.target.files?.[0];
  if (!file || !createdCompId) return;
  setLogoUploading(true);
  try {
    await competitionsApi.uploadLogo(createdCompId, file);
  } catch {
    setError("Erro ao fazer upload do logotipo.");
  } finally {
    setLogoUploading(false);
  }
}

async function handleBannerUpload(e: React.ChangeEvent<HTMLInputElement>) {
  const file = e.target.files?.[0];
  if (!file || !createdCompId) return;
  setBannerUploading(true);
  try {
    await competitionsApi.uploadBanner(createdCompId, file);
  } catch {
    setError("Erro ao fazer upload do banner.");
  } finally {
    setBannerUploading(false);
  }
}

async function handleAddWod() {
  if (!wodForm.name.trim() || !createdCompId) return;
  setWodAdding(true);
  try {
    const resp = await competitionsApi.createWod(createdCompId, {
      ...wodForm,
      order: state.step3.wods.length,
    });
    const newWod = (resp.data ?? resp) as Wod;
    setState((p) => ({ ...p, step3: { wods: [...p.step3.wods, newWod] } }));
    setWodForm({ name: "", wod_type: "amrap", duration_minutes: undefined, description: "", order: 0 });
  } catch {
    setError("Erro ao adicionar WOD.");
  } finally {
    setWodAdding(false);
  }
}

async function handleDeleteWod(wodId: number) {
  if (!createdCompId) return;
  try {
    await competitionsApi.deleteWod(createdCompId, wodId);
    setState((p) => ({
      ...p,
      step3: { wods: p.step3.wods.filter((w) => w.id !== wodId) },
    }));
  } catch {
    setError("Erro ao remover WOD.");
  }
}
```

- [ ] **Step 7: Renderizar Etapa 2 (Divulgação)**

Substituir o bloco placeholder da Etapa 2:

```typescript
{currentStep === 2 && (
  <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
    <h2 className="text-lg font-semibold text-gray-900">Divulgação</h2>

    {/* Visibilidade */}
    <div className="flex items-center gap-3">
      <input
        id="is_public"
        type="checkbox"
        checked={state.step2.is_public}
        onChange={(e) =>
          setState((p) => ({ ...p, step2: { ...p.step2, is_public: e.target.checked } }))
        }
        className="h-4 w-4 rounded border-gray-300 text-primary-600"
      />
      <label htmlFor="is_public" className="text-sm font-medium text-gray-700">
        Tornar esta competição pública (visível na página de ranking e inscrição)
      </label>
    </div>

    {/* Descrição */}
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">Descrição</label>
      <textarea
        rows={4}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        placeholder="Descreva o evento, formato, local e demais informações relevantes..."
        value={state.step2.description}
        onChange={(e) =>
          setState((p) => ({ ...p, step2: { ...p.step2, description: e.target.value } }))
        }
      />
    </div>

    {/* Links */}
    <div className="space-y-4 border-t pt-4">
      <h3 className="font-medium text-gray-700">Links</h3>
      <Input
        label="Regulamento (URL)"
        placeholder="https://..."
        value={state.step2.regulations_url}
        onChange={(e) =>
          setState((p) => ({ ...p, step2: { ...p.step2, regulations_url: e.target.value } }))
        }
      />
      <Input
        label="Inscrições externas (URL)"
        placeholder="https://..."
        value={state.step2.registration_url}
        onChange={(e) =>
          setState((p) => ({ ...p, step2: { ...p.step2, registration_url: e.target.value } }))
        }
      />
    </div>

    {/* Redes sociais */}
    <div className="space-y-4 border-t pt-4">
      <h3 className="font-medium text-gray-700">Redes sociais</h3>
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Instagram"
          placeholder="https://instagram.com/..."
          value={state.step2.instagram_url}
          onChange={(e) =>
            setState((p) => ({ ...p, step2: { ...p.step2, instagram_url: e.target.value } }))
          }
        />
        <Input
          label="WhatsApp"
          placeholder="https://wa.me/55..."
          value={state.step2.whatsapp_url}
          onChange={(e) =>
            setState((p) => ({ ...p, step2: { ...p.step2, whatsapp_url: e.target.value } }))
          }
        />
      </div>
    </div>

    {/* Upload de imagens */}
    <div className="space-y-4 border-t pt-4">
      <h3 className="font-medium text-gray-700">Imagens</h3>
      {!createdCompId && (
        <p className="text-sm text-amber-700 bg-amber-50 rounded-md p-3 border border-amber-200">
          Upload disponível após criar a competição (Etapa 5).
        </p>
      )}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Logotipo</label>
          {createdCompId && (
            <img
              src={`/api/v1/competitions/${createdCompId}/logo`}
              alt="Logo"
              className="h-16 w-auto rounded border border-gray-200 object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <input
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            disabled={!createdCompId || logoUploading}
            onChange={handleLogoUpload}
            className="block w-full text-sm text-gray-500 file:mr-3 file:rounded file:border-0 file:bg-primary-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-primary-700 disabled:opacity-50"
          />
          {logoUploading && <p className="text-xs text-gray-400">Enviando...</p>}
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Banner</label>
          {createdCompId && (
            <img
              src={`/api/v1/competitions/${createdCompId}/banner`}
              alt="Banner"
              className="h-16 w-auto rounded border border-gray-200 object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <input
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            disabled={!createdCompId || bannerUploading}
            onChange={handleBannerUpload}
            className="block w-full text-sm text-gray-500 file:mr-3 file:rounded file:border-0 file:bg-primary-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-primary-700 disabled:opacity-50"
          />
          {bannerUploading && <p className="text-xs text-amber-600">Enviando...</p>}
        </div>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 8: Renderizar Etapa 3 (WODs)**

Substituir o bloco placeholder da Etapa 3:

```typescript
{currentStep === 3 && (
  <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
    <h2 className="text-lg font-semibold text-gray-900">WODs</h2>

    {/* Lista de WODs existentes */}
    {state.step3.wods.length === 0 && (
      <p className="text-sm text-gray-500">Nenhum WOD cadastrado ainda.</p>
    )}
    {state.step3.wods.map((wod) => (
      <div key={wod.id} className="flex items-start justify-between rounded-md border border-gray-200 p-4">
        <div className="space-y-1">
          <p className="font-medium text-gray-900">{wod.name}</p>
          <p className="text-xs text-gray-500">
            {wod.wod_type.replace("_", " ").toUpperCase()}
            {wod.duration_minutes ? ` · ${wod.duration_minutes} min` : ""}
          </p>
          {wod.description && (
            <p className="text-sm text-gray-600">{wod.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => handleDeleteWod(wod.id)}
          className="ml-4 text-red-500 hover:text-red-700"
          title="Remover WOD"
        >
          🗑
        </button>
      </div>
    ))}

    {/* Formulário de novo WOD */}
    <div className="space-y-4 rounded-md border border-dashed border-gray-300 p-4">
      <h3 className="text-sm font-medium text-gray-700">Adicionar WOD</h3>
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Nome *"
          placeholder="Ex: Fran"
          value={wodForm.name}
          onChange={(e) => setWodForm((f) => ({ ...f, name: e.target.value }))}
        />
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">Tipo *</label>
          <select
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none"
            value={wodForm.wod_type}
            onChange={(e) => setWodForm((f) => ({ ...f, wod_type: e.target.value as WodType }))}
          >
            <option value="amrap">AMRAP</option>
            <option value="for_time">For Time</option>
            <option value="emom">EMOM</option>
            <option value="max_load">Max Load</option>
          </select>
        </div>
      </div>
      <Input
        label="Duração (minutos)"
        type="number"
        placeholder="Ex: 20"
        value={wodForm.duration_minutes ?? ""}
        onChange={(e) =>
          setWodForm((f) => ({
            ...f,
            duration_minutes: e.target.value ? Number(e.target.value) : undefined,
          }))
        }
      />
      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">Movimentos</label>
        <textarea
          rows={3}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          placeholder="Ex: 21-15-9 Thrusters (43 kg) + Pull-ups"
          value={wodForm.description ?? ""}
          onChange={(e) => setWodForm((f) => ({ ...f, description: e.target.value }))}
        />
      </div>
      <Button
        onClick={handleAddWod}
        disabled={!wodForm.name.trim() || wodAdding || !createdCompId}
        variant="secondary"
      >
        {wodAdding ? "Adicionando..." : "+ Adicionar WOD"}
      </Button>
      {!createdCompId && (
        <p className="text-xs text-amber-600">
          WODs disponíveis após criar a competição (Etapa 5).
        </p>
      )}
    </div>
  </div>
)}
```

- [ ] **Step 9: Atualizar Resumo da Etapa 5**

No bloco de resumo (Etapa 5), adicionar dois cards novos ao grid:

```typescript
{/* Card: Visibilidade */}
<div className="rounded-md bg-gray-50 p-4">
  <p className="text-xs font-medium uppercase text-gray-500">Visibilidade</p>
  <p className="mt-1 font-medium text-gray-900">
    {state.step2.is_public ? "Pública" : "Privada"}
  </p>
</div>

{/* Card: WODs (só CrossFit) */}
{state.step1.event_type === "crossfit" && (
  <div className="rounded-md bg-gray-50 p-4">
    <p className="text-xs font-medium uppercase text-gray-500">WODs</p>
    <p className="mt-1 font-medium text-gray-900">
      {state.step3.wods.length > 0
        ? `${state.step3.wods.length} WOD(s) cadastrado(s)`
        : "Nenhum WOD"}
    </p>
  </div>
)}
```

- [ ] **Step 10: Verificar tipagem TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

Esperado: sem erros de tipo.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/pages/CompetitionWizardPage.tsx
git commit -m "feat(wizard): implementa etapas 2 (divulgação) e 3 (WODs)"
```

---

## Checklist de Conclusão

- [ ] Migration aplicada em produção: `docker compose exec backend alembic upgrade head`
- [ ] Todos os testes passando: `cd backend && pytest tests/ -v`
- [ ] TypeScript sem erros: `cd frontend && npx tsc --noEmit`
- [ ] Wizard testado manualmente: criar competição CrossFit passando por todas as 5 etapas
- [ ] Wizard testado manualmente: criar competição Hyrox confirmando que Etapa 3 é pulada
- [ ] Upload de logo e banner testado em modo edição
