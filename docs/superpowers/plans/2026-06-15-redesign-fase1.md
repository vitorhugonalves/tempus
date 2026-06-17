# Redesenho Tempus — Fase 1 (Core Redesign) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar os modelos Competition e Category, criar o modelo Athlete com CRUD completo, adicionar proxy CEP, e redesenhar o frontend com wizard de criação e dashboard por campeonato (sidebar escura).

**Architecture:** Monolito modular FastAPI + React. Backend segue a cadeia api → services → repositories → models. Frontend usa React Router nested routes para o dashboard. Migrações via Alembic com batch_alter_table para compatibilidade SQLite.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.x async + Alembic + React 18 + Vite + TailwindCSS + React Router v6 + Zustand

---

## Contexto Geral

O projeto tem testes com SQLite `:memory:` que usam `Base.metadata.create_all` — **migrações Alembic não rodam nos testes**. Os modelos ORM determinam o schema de teste. A migration Alembic só é necessária para o banco real (produção/desenvolvimento).

**Campos que serão removidos de `Competition`:** `modality_id`, `modality_rel`, `duration_seconds`, `max_athletes`, `rules`

**Campos renomeados:** `event_date` → `start_date`

**Campos adicionados à Competition:** `end_date`, `event_type`, `is_public`, `scoring_model`, `tiebreak_criterion`

**Campos adicionados à Category:** `gender`, `age_restriction_enabled`, `age_min`, `age_max`

**Novo modelo:** `Athlete`

---

## Estrutura de Arquivos

### Backend — Criados
- `backend/app/models/athlete.py` — modelo ORM Athlete
- `backend/app/schemas/athlete.py` — Pydantic schemas
- `backend/app/repositories/athlete.py` — queries SQLAlchemy
- `backend/app/services/athlete.py` — lógica de negócio + CSV import
- `backend/app/api/v1/athletes.py` — router FastAPI
- `backend/app/api/v1/cep.py` — proxy ViaCEP
- `backend/app/db/migrations/versions/20260615_competition_core_fields.py`
- `backend/app/db/migrations/versions/20260615_category_gender_age.py`
- `backend/app/db/migrations/versions/20260615_athletes_table.py`
- `backend/tests/integration/test_athletes.py`
- `backend/tests/integration/test_cep.py`

### Backend — Modificados
- `backend/app/models/competition.py` — novos enums + campos, remoção de campos
- `backend/app/models/modality.py` — remove back_populates (evita broken relationship)
- `backend/app/models/category.py` — novos enums + campos
- `backend/app/models/competitor.py` — se referencia `max_athletes` em validação
- `backend/app/schemas/competition.py` — schemas novos
- `backend/app/schemas/category.py` — schemas atualizados
- `backend/app/repositories/competition.py` — remove selectinload de modality_rel
- `backend/app/api/v1/competitions.py` — remove lógica de modality; simplifica clone
- `backend/app/main.py` — registra athletes.router e cep.router; remove modalities.router
- `backend/tests/integration/test_competitions.py` — remove `max_athletes`
- `backend/tests/integration/test_categories.py` — remove `max_athletes`
- `backend/tests/integration/test_competition_fixes.py` — reescreve testes de modality
- `backend/tests/integration/test_timers.py` — remove `max_athletes`
- `backend/tests/integration/test_registration.py` — remove `max_athletes`
- `backend/tests/integration/test_bulk_teams.py` — remove `max_athletes`
- `backend/tests/integration/test_registration_box.py` — remove `max_athletes`
- `backend/tests/integration/test_bulk_heats.py` — remove `max_athletes`

### Frontend — Criados
- `frontend/src/api/athletes.ts`
- `frontend/src/api/cep.ts`
- `frontend/src/pages/CompetitionsListPage.tsx` — substitui CompetitionsPage
- `frontend/src/pages/CompetitionWizardPage.tsx` — wizard 5 etapas (fase 1: etapas 1, 4, 5)
- `frontend/src/pages/dashboard/CompetitionDashboardLayout.tsx` — sidebar escura
- `frontend/src/pages/dashboard/DashboardOverviewPage.tsx`
- `frontend/src/pages/dashboard/TeamsPage.tsx`
- `frontend/src/pages/dashboard/AthletesPage.tsx`
- `frontend/src/pages/dashboard/HeatsPage.tsx` — migrado de TimersPage

### Frontend — Modificados
- `frontend/src/types/index.ts` — adiciona Competition campos novos + Athlete
- `frontend/src/api/competitions.ts` — usa novos campos
- `frontend/src/App.tsx` — novas rotas + nested routes do dashboard
- `frontend/src/components/layouts/MainLayout.tsx` — ajusta nav links

---

## Task 1: Atualizar modelo Competition + Modality

**Files:**
- Modify: `backend/app/models/competition.py`
- Modify: `backend/app/models/modality.py`

- [ ] **Step 1: Escrever testes que validam os novos campos da Competition**

```python
# backend/tests/integration/test_competitions.py — adicionar ao final do arquivo existente
async def test_criar_competicao_com_event_type_retorna_201(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/competitions",
        json={"name": "Hyrox SP 2026", "event_type": "hyrox"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "hyrox"
    assert data["is_public"] is False
    assert "start_date" in data
    assert "end_date" in data
    # campos removidos não devem existir na resposta
    assert "max_athletes" not in data
    assert "modality_id" not in data
    assert "rules" not in data


async def test_criar_competicao_crossfit_retorna_201(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/competitions",
        json={"name": "CrossFit Open 2026", "event_type": "crossfit", "scoring_model": "most_points"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["event_type"] == "crossfit"
    assert data["scoring_model"] == "most_points"
```

- [ ] **Step 2: Executar testes — confirmar FAIL (campos ainda não existem)**

```bash
cd backend && python -m pytest tests/integration/test_competitions.py::test_criar_competicao_com_event_type_retorna_201 -v
```
Esperado: `FAILED` — `422 Unprocessable Entity` (campo `event_type` rejeitado ou ausente da response)

- [ ] **Step 3: Atualizar `app/models/competition.py`**

Substituir o arquivo inteiro:

```python
import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text, func
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
```

- [ ] **Step 4: Remover `competitions` backref do `app/models/modality.py`**

O campo `competitions` aponta para `back_populates="modality_rel"`, que não existe mais.
Substituir o arquivo inteiro:

```python
from datetime import datetime

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Modality(Base):
    """Modalidade esportiva — mantida por compatibilidade mas sem FK de Competition."""

    __tablename__ = "modalities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 5: Commit parcial**

```bash
cd backend && git add app/models/competition.py app/models/modality.py
git commit -m "feat(competition): atualiza modelo com event_type, scoring_model, start_date; remove modality FK"
```

---

## Task 2: Atualizar schemas e repositório de Competition

**Files:**
- Modify: `backend/app/schemas/competition.py`
- Modify: `backend/app/repositories/competition.py`
- Modify: `backend/app/api/v1/competitions.py`

- [ ] **Step 1: Substituir `app/schemas/competition.py`**

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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Substituir `app/repositories/competition.py`**

Remove `selectinload(Competition.modality_rel)`:

```python
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition

logger = logging.getLogger(__name__)


class CompetitionRepository:
    """Repositório responsável pelo acesso ao banco de dados para a entidade Competition."""

    @staticmethod
    async def get_by_id(db: AsyncSession, competition_id: int) -> Competition | None:
        """Busca uma competição pelo ID.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition_id: Identificador único da competição.

        Returns:
            Objeto Competition ou None se não encontrado.
        """
        result = await db.execute(
            select(Competition)
            .where(Competition.id == competition_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(
        db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[Competition]:
        """Retorna uma lista paginada de competições.

        Args:
            db: Sessão assíncrona do banco de dados.
            skip: Número de registros a pular.
            limit: Número máximo de registros a retornar.

        Returns:
            Lista de objetos Competition.
        """
        result = await db.execute(
            select(Competition)
            .offset(skip)
            .limit(limit)
            .order_by(Competition.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, competition: Competition) -> Competition:
        """Persiste uma nova competição no banco de dados.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition: Objeto Competition a ser criado.

        Returns:
            Objeto Competition com ID populado.
        """
        db.add(competition)
        await db.flush()
        logger.info("Competição criada: id=%s, nome=%s", competition.id, competition.name)
        return await CompetitionRepository.get_by_id(db, competition.id)  # type: ignore[return-value]

    @staticmethod
    async def update(db: AsyncSession, competition: Competition) -> Competition:
        """Persiste alterações em uma competição existente.

        Args:
            db: Sessão assíncrona do banco de dados.
            competition: Objeto Competition com dados atualizados.

        Returns:
            Objeto Competition atualizado.
        """
        await db.flush()
        return await CompetitionRepository.get_by_id(db, competition.id)  # type: ignore[return-value]
```

- [ ] **Step 3: Atualizar `app/api/v1/competitions.py`**

Remover: import `ModalityRepository`, lógica de modality no create, campos antigos no clone.

Substituir apenas as partes afetadas:

**Remover do bloco de imports:**
```python
from app.repositories.modality import ModalityRepository
```

**Substituir a função `create_competition` (linhas ~105-129):**
```python
@router.post(
    "/competitions", response_model=CompetitionResponse, status_code=status.HTTP_201_CREATED
)
async def create_competition(
    payload: CompetitionCreate,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Cria nova competição (Operador/Admin)."""
    competition = Competition(**payload.model_dump())
    created = await CompetitionRepository.create(db, competition)
    logger.info("Competição criada: id=%s nome=%s", created.id, created.name)
    return CompetitionResponse.model_validate(created)
```

**Substituir `list_competitions` para usar `model_validate`:**
```python
@router.get("/competitions", response_model=list[CompetitionResponse])
async def list_competitions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[CompetitionResponse]:
    """Lista todas as competições (acesso público)."""
    competitions = await CompetitionRepository.get_all(db, skip=skip, limit=limit)
    return [CompetitionResponse.model_validate(c) for c in competitions]
```

**Substituir `get_competition`:**
```python
@router.get("/competitions/{competition_id}", response_model=CompetitionResponse)
async def get_competition(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Retorna uma competição pelo ID (acesso público)."""
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )
    return CompetitionResponse.model_validate(competition)
```

**Substituir `update_competition`:**
```python
@router.patch("/competitions/{competition_id}", response_model=CompetitionResponse)
async def update_competition(
    competition_id: int,
    payload: CompetitionUpdate,
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Atualiza dados de uma competição (Operador/Admin).

    Regra RN-05: apenas Admin pode reabrir competição encerrada.
    """
    competition = await CompetitionRepository.get_by_id(db, competition_id)
    if competition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    if (
        competition.status == CompetitionStatus.finished
        and payload.status is not None
        and payload.status != CompetitionStatus.finished
        and current_user.role.value != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas o Administrador pode reabrir uma competição encerrada",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(competition, field, value)

    updated = await CompetitionRepository.update(db, competition)
    logger.info("Competição atualizada: id=%s status=%s", updated.id, updated.status)
    return CompetitionResponse.model_validate(updated)
```

**Substituir `clone_competition` (remover campos antigos):**
```python
@router.post(
    "/competitions/{competition_id}/clone",
    response_model=CompetitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_competition(
    competition_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> CompetitionResponse:
    """Clona uma competição como template (RF-19)."""
    from app.models.category import Category

    source = await CompetitionRepository.get_by_id(db, competition_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )

    clone = Competition(
        name=f"{source.name} (cópia)",
        location=source.location,
        event_type=source.event_type,
        scoring_model=source.scoring_model,
        tiebreak_criterion=source.tiebreak_criterion,
        status=CompetitionStatus.draft,
    )
    db.add(clone)
    await db.flush()

    source_categories = await CategoryService.list_by_competition(db, competition_id)
    for cat in source_categories:
        db.add(Category(
            competition_id=clone.id,
            name=cat.name,
            category_type=cat.category_type,
            max_team_size=cat.max_team_size,
        ))

    await db.flush()
    await db.refresh(clone)
    logger.info("Competição clonada: source=%s clone=%s", competition_id, clone.id)
    return CompetitionResponse.model_validate(clone)
```

- [ ] **Step 4: Executar os novos testes**

```bash
cd backend && python -m pytest tests/integration/test_competitions.py -v
```
Esperado: `test_criar_competicao_com_event_type_retorna_201` PASS, `test_criar_competicao_crossfit_retorna_201` PASS.

Alguns testes antigos vão falhar porque ainda passam `max_athletes` — isso é corrigido na Task 3.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/competition.py app/repositories/competition.py app/api/v1/competitions.py
git commit -m "feat(competition): atualiza schemas, repositório e router para novos campos"
```

---

## Task 3: Corrigir testes quebrados pela remoção de campos da Competition

**Files:**
- Modify: `backend/tests/integration/test_competitions.py`
- Modify: `backend/tests/integration/test_competition_fixes.py`
- Modify: `backend/tests/integration/test_categories.py`
- Modify: `backend/tests/integration/test_timers.py`
- Modify: `backend/tests/integration/test_registration.py`
- Modify: `backend/tests/integration/test_bulk_teams.py`
- Modify: `backend/tests/integration/test_registration_box.py`
- Modify: `backend/tests/integration/test_bulk_heats.py`
- Modify: `backend/tests/integration/test_modalities.py`

- [ ] **Step 1: Corrigir `test_competitions.py`**

Remover `max_athletes` do payload (linha ~20):
```python
# DE:
json={
    "name": "Hyrox São Paulo 2026",
    "location": "São Paulo, SP",
    "modality": "Hyrox",
    "max_athletes": 200,
},
# PARA:
json={
    "name": "Hyrox São Paulo 2026",
    "location": "São Paulo, SP",
    "event_type": "hyrox",
},
```

- [ ] **Step 2: Corrigir `test_competition_fixes.py`**

A função `_create_modality` pode ficar (o endpoint `/api/v1/modalities` ainda existe), mas os testes que verificam `modality_id` e `modality_name` nos campos de Competition devem ser atualizados.

Substituir `_create_competition` (remove `max_athletes` e `modality_id`):
```python
async def _create_competition(
    client: AsyncClient, admin_token: str
) -> dict:
    payload = {
        "name": "Competição Teste",
        "location": "Porto Alegre",
        "event_type": "hyrox",
    }
    r = await client.post(
        "/api/v1/competitions",
        json=payload,
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201, r.text
    return r.json()
```

Substituir o bloco `# ── Bug 2` (linhas ~95-155) pelos novos testes que fazem sentido após o redesenho:
```python
# ── Competição básica retorna campos corretos ──────────────────────────────────


async def test_criar_competicao_retorna_campos_corretos(
    client: AsyncClient, admin_token: str
):
    r = await client.post(
        "/api/v1/competitions",
        json={"name": "Hyrox RS 2026", "event_type": "hyrox", "location": "Porto Alegre"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Hyrox RS 2026"
    assert data["event_type"] == "hyrox"
    assert data["location"] == "Porto Alegre"
    assert data["status"] == "draft"
    assert data["is_public"] is False
```

- [ ] **Step 3: Corrigir `test_categories.py`**

Remover `max_athletes` do `json` de criação de competição:
```python
# DE:
json={"name": "Competição Teste", "max_athletes": 50},
# PARA:
json={"name": "Competição Teste"},
```

- [ ] **Step 4: Corrigir `test_timers.py`**

Remover `max_athletes` nos dois locais (~linha 12 e ~linha 29):
```python
# DE:
json={"name": "Comp Ativa", "max_athletes": 10},
# PARA:
json={"name": "Comp Ativa"},
```
```python
# DE:
json={"name": "Comp Rascunho", "max_athletes": 10},
# PARA:
json={"name": "Comp Rascunho"},
```

- [ ] **Step 5: Corrigir `test_registration.py`**

Remover `max_athletes` nos dois locais (~linhas 18 e 36):
```python
json={"name": "Copa Teste"},
```
```python
json={"name": "Copa Rascunho"},
```

- [ ] **Step 6: Corrigir `test_bulk_teams.py`, `test_registration_box.py`, `test_bulk_heats.py`**

Cada um tem `Competition(... max_athletes=100 ...)` em fixture. Remover `max_athletes=100`:

Em `test_bulk_teams.py` (~linha 24-28):
```python
comp = Competition(
    name="Competição Batch",
    status=CompetitionStatus.active,
)
```

Em `test_registration_box.py` (~linha 17-21): idem, remover `max_athletes=100`.

Em `test_bulk_heats.py` (~linha 24-28): idem.

- [ ] **Step 7: Corrigir `test_modalities.py`**

Remover o teste (ou ajustar) que tenta passar `modality_id` na criação de competição (~linha 135):
```python
# DE:
json={"name": "Copa Luta Livre", "modality_id": mod_id},
# PARA:
json={"name": "Copa Luta Livre"},
```
O teste que verifica que a competição foi criada ainda passa — apenas sem o `modality_id`.

- [ ] **Step 8: Executar toda a suite de testes**

```bash
cd backend && python -m pytest -v
```
Esperado: todos passando (ou próximo disso — qualquer falha remanescente deve ser investigada antes de continuar).

- [ ] **Step 9: Commit**

```bash
git add tests/
git commit -m "test(competition): remove campos antigos (max_athletes, modality_id) dos testes"
```

---

## Task 4: Atualizar modelo e schema de Category

**Files:**
- Modify: `backend/app/models/category.py`
- Modify: `backend/app/schemas/category.py`

- [ ] **Step 1: Escrever testes para novos campos de Category**

Adicionar ao final de `tests/integration/test_categories.py`:

```python
async def test_criar_categoria_com_genero_retorna_201(
    client: AsyncClient, admin_token: str
):
    comp_r = await client.post(
        "/api/v1/competitions",
        json={"name": "Comp Gênero"},
        cookies={"session_id": admin_token},
    )
    comp_id = comp_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{comp_id}/categories",
        json={
            "name": "Elite Feminino",
            "category_type": "individual",
            "gender": "female",
        },
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["gender"] == "female"
    assert data["age_restriction_enabled"] is False
    assert data["age_min"] is None


async def test_criar_categoria_com_restricao_etaria(
    client: AsyncClient, admin_token: str
):
    comp_r = await client.post(
        "/api/v1/competitions",
        json={"name": "Comp Etária"},
        cookies={"session_id": admin_token},
    )
    comp_id = comp_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{comp_id}/categories",
        json={
            "name": "Master 40+",
            "category_type": "individual",
            "age_restriction_enabled": True,
            "age_min": 40,
        },
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["age_restriction_enabled"] is True
    assert data["age_min"] == 40
    assert data["age_max"] is None
```

- [ ] **Step 2: Confirmar FAIL**

```bash
cd backend && python -m pytest tests/integration/test_categories.py::test_criar_categoria_com_genero_retorna_201 -v
```
Esperado: `FAILED` — campo `gender` rejeitado ou ausente.

- [ ] **Step 3: Substituir `app/models/category.py`**

```python
import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CategoryType(str, enum.Enum):
    individual = "individual"
    team = "team"


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    mixed = "mixed"


class Category(Base):
    """Categoria de participação dentro de uma competição.

    Exemplos: Elite Masculino, Master 40+, Equipe Mista.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType), nullable=False, default=CategoryType.individual
    )
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender), nullable=True)
    age_restriction_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="categories"
    )
    registrations: Mapped[list["CompetitorRegistration"]] = relationship(  # noqa: F821
        "CompetitorRegistration", back_populates="category", cascade="all, delete-orphan"
    )
    teams: Mapped[list["Team"]] = relationship(  # noqa: F821
        "Team", back_populates="category", cascade="all, delete-orphan"
    )
    timers: Mapped[list["Timer"]] = relationship(  # noqa: F821
        "Timer", back_populates="category"
    )
    athletes: Mapped[list["Athlete"]] = relationship(  # noqa: F821
        "Athlete", back_populates="category"
    )
```

- [ ] **Step 4: Atualizar `app/schemas/category.py`**

```python
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
```

- [ ] **Step 5: Verificar testes passando**

```bash
cd backend && python -m pytest tests/integration/test_categories.py -v
```
Esperado: todos PASS incluindo os novos.

- [ ] **Step 6: Commit**

```bash
git add app/models/category.py app/schemas/category.py tests/integration/test_categories.py
git commit -m "feat(category): adiciona gender, age_restriction, age_min, age_max"
```

---

## Task 5: Criar modelo Athlete + repository + service + router

**Files:**
- Create: `backend/app/models/athlete.py`
- Create: `backend/app/schemas/athlete.py`
- Create: `backend/app/repositories/athlete.py`
- Create: `backend/app/services/athlete.py`
- Create: `backend/app/api/v1/athletes.py`
- Create: `backend/tests/integration/test_athletes.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Escrever testes de athletes**

Criar `backend/tests/integration/test_athletes.py`:

```python
"""Testes de integração para CRUD de atletas."""
import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.category import Category, CategoryType


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Atletas", status=CompetitionStatus.active)
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Elite",
        category_type=CategoryType.individual,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


# ── Testes CRUD ───────────────────────────────────────────────────────────────


async def test_listar_atletas_vazio_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_criar_atleta_retorna_201(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={
            "name": "Carlos Mendes",
            "email": "carlos@example.com",
            "category_id": category.id,
        },
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Carlos Mendes"
    assert data["email"] == "carlos@example.com"
    assert data["competition_id"] == competition.id
    assert data["category_id"] == category.id


async def test_criar_atleta_campos_minimos(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Ana Lima"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Ana Lima"


async def test_editar_atleta_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "João Silva"},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"name": "João P. Silva", "phone": "(11)99999-0000"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "João P. Silva"
    assert data["phone"] == "(11)99999-0000"


async def test_remover_atleta_retorna_204(
    client: AsyncClient, admin_token: str, competition: Competition
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Maria Costa"},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 204

    # Confirmar remoção
    list_r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    assert all(a["id"] != athlete_id for a in list_r.json())


async def test_competidor_nao_pode_criar_atleta(
    client: AsyncClient, competitor_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Intruso"},
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403


async def test_listar_atletas_filtra_por_categoria(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    # Cria atleta com categoria
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Com Categoria", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    # Cria atleta sem categoria
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Sem Categoria"},
        cookies={"session_id": admin_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes?category_id={category.id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Com Categoria"


async def test_importar_atletas_csv_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome,email,documento,telefone,categoria,tamanho_camiseta\n"
        f"Pedro Alves,pedro@example.com,123.456.789-00,(11)91111-2222,{category.name},M\n"
        "Rita Souza,,,,,"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []


async def test_importar_atletas_csv_sem_nome_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition
):
    csv_content = b"nome,email\n,pedro@example.com"

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 1
```

- [ ] **Step 2: Confirmar FAIL**

```bash
cd backend && python -m pytest tests/integration/test_athletes.py -v 2>&1 | head -20
```
Esperado: `FAILED` — `ImportError` ou `404` pois o router não existe ainda.

- [ ] **Step 3: Criar `app/models/athlete.py`**

```python
import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TshirtSize(str, enum.Enum):
    P = "P"
    M = "M"
    G = "G"
    GG = "GG"
    XG = "XG"


class Athlete(Base):
    """Atleta participante de uma competição.

    Registro independente — não requer conta de sistema.
    """

    __tablename__ = "athletes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    document: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tshirt_size: Mapped[TshirtSize | None] = mapped_column(Enum(TshirtSize), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="athletes"
    )
    category: Mapped["Category | None"] = relationship(  # noqa: F821
        "Category", back_populates="athletes"
    )
    team: Mapped["Team | None"] = relationship(  # noqa: F821
        "Team", back_populates="athletes"
    )
```

- [ ] **Step 4: Adicionar `athletes` relationship no modelo Team**

Abrir `backend/app/models/team.py` e adicionar dentro da classe `Team`:
```python
athletes: Mapped[list["Athlete"]] = relationship(  # noqa: F821
    "Athlete", back_populates="team"
)
```

- [ ] **Step 5: Criar `app/schemas/athlete.py`**

```python
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.athlete import TshirtSize


class AthleteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str | None = Field(None, max_length=200)
    document: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=30)
    category_id: int | None = None
    team_id: int | None = None
    tshirt_size: TshirtSize | None = None


class AthleteUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    email: str | None = Field(None, max_length=200)
    document: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=30)
    category_id: int | None = None
    team_id: int | None = None
    tshirt_size: TshirtSize | None = None


class AthleteResponse(BaseModel):
    id: int
    competition_id: int
    category_id: int | None
    team_id: int | None
    name: str
    email: str | None
    document: str | None
    phone: str | None
    tshirt_size: TshirtSize | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AthleteBulkError(BaseModel):
    row: int
    name: str
    error: str


class AthleteBulkResult(BaseModel):
    created: int
    errors: list[AthleteBulkError]
```

- [ ] **Step 6: Criar `app/repositories/athlete.py`**

```python
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete

logger = logging.getLogger(__name__)


class AthleteRepository:
    """Repositório para a entidade Athlete."""

    @staticmethod
    async def get_by_id(db: AsyncSession, athlete_id: int) -> Athlete | None:
        """Busca atleta pelo ID.

        Args:
            db: Sessão assíncrona.
            athlete_id: ID do atleta.

        Returns:
            Objeto Athlete ou None.
        """
        result = await db.execute(
            select(Athlete).where(Athlete.id == athlete_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_competition(
        db: AsyncSession,
        competition_id: int,
        category_id: int | None = None,
        team_id: int | None = None,
    ) -> list[Athlete]:
        """Lista atletas de uma competição com filtros opcionais.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro opcional por categoria.
            team_id: Filtro opcional por equipe.

        Returns:
            Lista de atletas.
        """
        stmt = select(Athlete).where(Athlete.competition_id == competition_id)
        if category_id is not None:
            stmt = stmt.where(Athlete.category_id == category_id)
        if team_id is not None:
            stmt = stmt.where(Athlete.team_id == team_id)
        stmt = stmt.order_by(Athlete.name)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, athlete: Athlete) -> Athlete:
        """Persiste um novo atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a criar.

        Returns:
            Athlete com ID populado.
        """
        db.add(athlete)
        await db.flush()
        await db.refresh(athlete)
        return athlete

    @staticmethod
    async def update(db: AsyncSession, athlete: Athlete) -> Athlete:
        """Persiste alterações em um atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete com dados atualizados.

        Returns:
            Athlete atualizado.
        """
        await db.flush()
        await db.refresh(athlete)
        return athlete

    @staticmethod
    async def delete(db: AsyncSession, athlete: Athlete) -> None:
        """Remove um atleta do banco.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a remover.
        """
        await db.delete(athlete)
        await db.flush()
```

- [ ] **Step 7: Criar `app/services/athlete.py`**

```python
"""Serviço de atletas — CRUD e importação CSV."""
import csv
import io
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete, TshirtSize
from app.models.category import Category
from app.repositories.athlete import AthleteRepository
from app.schemas.athlete import (
    AthleteBulkError,
    AthleteBulkResult,
    AthleteCreate,
    AthleteUpdate,
)

logger = logging.getLogger(__name__)

_TSHIRT_SIZES = {s.value for s in TshirtSize}
_CSV_REQUIRED = {"nome"}


class AthleteService:
    """Lógica de negócio para atletas."""

    @staticmethod
    async def list_by_competition(
        db: AsyncSession,
        competition_id: int,
        category_id: int | None = None,
        team_id: int | None = None,
    ) -> list[Athlete]:
        """Lista atletas de uma competição com filtros opcionais.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro por categoria (opcional).
            team_id: Filtro por equipe (opcional).

        Returns:
            Lista de atletas.
        """
        return await AthleteRepository.list_by_competition(
            db, competition_id, category_id=category_id, team_id=team_id
        )

    @staticmethod
    async def get_or_404(db: AsyncSession, athlete_id: int) -> Athlete:
        """Busca atleta ou lança 404.

        Args:
            db: Sessão assíncrona.
            athlete_id: ID do atleta.

        Returns:
            Objeto Athlete.

        Raises:
            HTTPException 404: se não encontrado.
        """
        athlete = await AthleteRepository.get_by_id(db, athlete_id)
        if athlete is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado"
            )
        return athlete

    @staticmethod
    async def create(
        db: AsyncSession, competition_id: int, data: AthleteCreate
    ) -> Athlete:
        """Cria um novo atleta.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição à qual o atleta pertence.
            data: Dados do atleta.

        Returns:
            Objeto Athlete criado.
        """
        athlete = Athlete(competition_id=competition_id, **data.model_dump())
        return await AthleteRepository.create(db, athlete)

    @staticmethod
    async def update(db: AsyncSession, athlete: Athlete, data: AthleteUpdate) -> Athlete:
        """Atualiza dados de um atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a atualizar.
            data: Dados de atualização (parcial).

        Returns:
            Objeto Athlete atualizado.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(athlete, field, value)
        return await AthleteRepository.update(db, athlete)

    @staticmethod
    async def delete(db: AsyncSession, athlete: Athlete) -> None:
        """Remove um atleta.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a remover.
        """
        await AthleteRepository.delete(db, athlete)

    @staticmethod
    async def import_csv(
        db: AsyncSession, competition_id: int, content: bytes, categories: list[Category]
    ) -> AthleteBulkResult:
        """Importa atletas de um arquivo CSV.

        Colunas esperadas (separador vírgula):
            nome, email, documento, telefone, categoria, tamanho_camiseta

        Apenas 'nome' é obrigatório. Categorias são resolvidas por nome (case-insensitive).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            content: Conteúdo do CSV em bytes.
            categories: Categorias da competição para resolução de nomes.

        Returns:
            AthleteBulkResult com contagens e erros por linha.
        """
        category_by_name = {c.name.lower(): c for c in categories}
        created_count = 0
        errors: list[AthleteBulkError] = []

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        for row_num, row in enumerate(reader, start=1):
            name = (row.get("nome") or "").strip()
            if not name:
                errors.append(AthleteBulkError(row=row_num, name="", error="Campo 'nome' obrigatório"))
                continue

            cat_name = (row.get("categoria") or "").strip().lower()
            category_id = category_by_name[cat_name].id if cat_name in category_by_name else None

            raw_size = (row.get("tamanho_camiseta") or "").strip().upper()
            tshirt_size = TshirtSize(raw_size) if raw_size in _TSHIRT_SIZES else None

            athlete = Athlete(
                competition_id=competition_id,
                name=name,
                email=(row.get("email") or "").strip() or None,
                document=(row.get("documento") or "").strip() or None,
                phone=(row.get("telefone") or "").strip() or None,
                category_id=category_id,
                tshirt_size=tshirt_size,
            )
            db.add(athlete)
            created_count += 1

        if created_count:
            await db.flush()

        return AthleteBulkResult(created=created_count, errors=errors)
```

- [ ] **Step 8: Criar `app/api/v1/athletes.py`**

```python
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.schemas.athlete import AthleteBulkResult, AthleteCreate, AthleteResponse, AthleteUpdate
from app.services.athlete import AthleteService
from app.services.category import CategoryService

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_CSV_BYTES = 1 * 1024 * 1024  # 1 MB


def _competition_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")


@router.get(
    "/competitions/{competition_id}/athletes",
    response_model=list[AthleteResponse],
)
async def list_athletes(
    competition_id: int,
    category_id: int | None = None,
    team_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("judge", "operator", "admin")),
) -> list[AthleteResponse]:
    """Lista atletas de uma competição com filtros opcionais."""
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()
    athletes = await AthleteService.list_by_competition(
        db, competition_id, category_id=category_id, team_id=team_id
    )
    return [AthleteResponse.model_validate(a) for a in athletes]


@router.post(
    "/competitions/{competition_id}/athletes",
    response_model=AthleteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_athlete(
    competition_id: int,
    payload: AthleteCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> AthleteResponse:
    """Cria um atleta em uma competição (Operador/Admin)."""
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()
    athlete = await AthleteService.create(db, competition_id, payload)
    logger.info("Atleta criado: id=%s competition_id=%s", athlete.id, competition_id)
    return AthleteResponse.model_validate(athlete)


@router.put(
    "/competitions/{competition_id}/athletes/{athlete_id}",
    response_model=AthleteResponse,
)
async def update_athlete(
    competition_id: int,
    athlete_id: int,
    payload: AthleteUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> AthleteResponse:
    """Atualiza dados de um atleta (Operador/Admin)."""
    athlete = await AthleteService.get_or_404(db, athlete_id)
    if athlete.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado")
    updated = await AthleteService.update(db, athlete, payload)
    return AthleteResponse.model_validate(updated)


@router.delete(
    "/competitions/{competition_id}/athletes/{athlete_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_athlete(
    competition_id: int,
    athlete_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> None:
    """Remove um atleta (Operador/Admin)."""
    athlete = await AthleteService.get_or_404(db, athlete_id)
    if athlete.competition_id != competition_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado")
    await AthleteService.delete(db, athlete)
    logger.info("Atleta removido: id=%s", athlete_id)


@router.post(
    "/competitions/{competition_id}/athletes/import",
    response_model=AthleteBulkResult,
)
async def import_athletes_csv(
    competition_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> AthleteBulkResult:
    """Importa atletas de arquivo CSV (Operador/Admin). Máximo 1 MB."""
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()

    content = await file.read()
    if len(content) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo CSV excede o tamanho máximo de 1 MB",
        )

    categories = await CategoryService.list_by_competition(db, competition_id)
    result = await AthleteService.import_csv(db, competition_id, content, categories)
    logger.info(
        "Import CSV atletas: competition_id=%s created=%s errors=%s",
        competition_id, result.created, len(result.errors),
    )
    return result
```

- [ ] **Step 9: Registrar router em `app/main.py`**

Adicionar após o import de `bulk`:
```python
from app.api.v1 import athletes, cep  # cep será criado na Task 6
```

Após `app.include_router(bulk.router ...)`:
```python
app.include_router(athletes.router, prefix="/api/v1", tags=["athletes"])
```

Por ora, adicionar só o athletes — cep será adicionado na Task 6.

- [ ] **Step 10: Executar testes de atletas**

```bash
cd backend && python -m pytest tests/integration/test_athletes.py -v
```
Esperado: todos PASS.

- [ ] **Step 11: Executar suite completa**

```bash
cd backend && python -m pytest -v
```
Esperado: todos passando.

- [ ] **Step 12: Commit**

```bash
git add app/models/athlete.py app/schemas/athlete.py app/repositories/athlete.py \
        app/services/athlete.py app/api/v1/athletes.py app/main.py \
        app/models/team.py tests/integration/test_athletes.py
git commit -m "feat(athletes): adiciona CRUD e importação CSV de atletas"
```

---

## Task 6: Endpoint CEP proxy

**Files:**
- Create: `backend/app/api/v1/cep.py`
- Create: `backend/tests/integration/test_cep.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Escrever testes CEP**

Criar `backend/tests/integration/test_cep.py`:

```python
"""Testes de integração para o proxy CEP."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


async def test_cep_valido_retorna_dados(client: AsyncClient):
    mock_response = {
        "cep": "01310-100",
        "logradouro": "Avenida Paulista",
        "bairro": "Bela Vista",
        "localidade": "São Paulo",
        "uf": "SP",
    }
    with patch("app.api.v1.cep.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_http
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_http.get.return_value = mock_response_obj

        r = await client.get("/api/v1/cep/01310100")
    assert r.status_code == 200
    data = r.json()
    assert data["logradouro"] == "Avenida Paulista"
    assert data["uf"] == "SP"


async def test_cep_invalido_retorna_404(client: AsyncClient):
    with patch("app.api.v1.cep.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_http
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = {"erro": True}
        mock_http.get.return_value = mock_response_obj

        r = await client.get("/api/v1/cep/00000000")
    assert r.status_code == 404


async def test_cep_formato_incorreto_retorna_422(client: AsyncClient):
    # CEP com menos de 8 dígitos
    r = await client.get("/api/v1/cep/0131")
    assert r.status_code == 422
```

- [ ] **Step 2: Confirmar FAIL**

```bash
cd backend && python -m pytest tests/integration/test_cep.py -v 2>&1 | head -10
```
Esperado: `FAILED` — 404 pois rota não existe.

- [ ] **Step 3: Criar `app/api/v1/cep.py`**

```python
"""Proxy para ViaCEP — evita CORS do frontend."""
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException, Path, status

logger = logging.getLogger(__name__)

router = APIRouter()

_CEP_PATTERN = re.compile(r"^\d{8}$")
_VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"


@router.get("/cep/{cep}")
async def lookup_cep(
    cep: str = Path(..., description="CEP sem traço (8 dígitos)"),
) -> dict:
    """Consulta dados de endereço via ViaCEP.

    Args:
        cep: CEP sem traço, exatamente 8 dígitos.

    Returns:
        Dicionário com logradouro, bairro, localidade, uf.

    Raises:
        HTTPException 422: CEP com formato inválido.
        HTTPException 404: CEP não encontrado.
        HTTPException 502: ViaCEP indisponível.
    """
    if not _CEP_PATTERN.match(cep):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CEP deve ter exatamente 8 dígitos numéricos",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(_VIACEP_URL.format(cep=cep))
    except httpx.RequestError as exc:
        logger.warning("ViaCEP indisponível: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Serviço de CEP temporariamente indisponível",
        ) from exc

    data = response.json()
    if data.get("erro"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="CEP não encontrado"
        )

    return {
        "cep": data.get("cep"),
        "logradouro": data.get("logradouro"),
        "complemento": data.get("complemento"),
        "bairro": data.get("bairro"),
        "localidade": data.get("localidade"),
        "uf": data.get("uf"),
    }
```

- [ ] **Step 4: Registrar `cep.router` em `app/main.py`**

O import já foi adicionado na Task 5 Step 9. Adicionar após `athletes.router`:
```python
app.include_router(cep.router, prefix="/api/v1", tags=["cep"])
```

- [ ] **Step 5: Verificar que `httpx` está nas dependências**

```bash
cd backend && grep httpx pyproject.toml
```
Se não estiver: `pip install httpx` e adicionar em `pyproject.toml` nas `dependencies`.

- [ ] **Step 6: Executar testes CEP**

```bash
cd backend && python -m pytest tests/integration/test_cep.py -v
```
Esperado: todos PASS.

- [ ] **Step 7: Executar suite completa**

```bash
cd backend && python -m pytest -v
```
Esperado: todos PASS.

- [ ] **Step 8: Commit**

```bash
git add app/api/v1/cep.py app/main.py tests/integration/test_cep.py
git commit -m "feat(cep): adiciona proxy ViaCEP para lookup de endereço"
```

---

## Task 7: Criar migrations Alembic

**Files:**
- Create: `backend/app/db/migrations/versions/20260615_competition_core_fields.py`
- Create: `backend/app/db/migrations/versions/20260615_category_gender_age.py`
- Create: `backend/app/db/migrations/versions/20260615_athletes_table.py`

> ⚠️ Migrações não afetam os testes (que usam SQLite :memory: com `create_all`). São necessárias apenas para o banco real.

- [ ] **Step 1: Criar `20260615_competition_core_fields.py`**

```python
"""competition_core_fields

Revision ID: 20260615_competition_core_fields
Revises: 20260328_add_sort_order_to_heats
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260615_competition_core_fields"
down_revision = "20260328_add_sort_order_to_heats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("competitions") as batch_op:
        # Renomeia event_date → start_date
        batch_op.alter_column(
            "event_date",
            new_column_name="start_date",
            existing_type=sa.Date(),
            nullable=True,
        )
        # Adiciona novos campos
        batch_op.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "event_type",
                sa.Enum("hyrox", "crossfit", name="eventtype"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "scoring_model",
                sa.Enum("lowest_time", "most_points", name="scoringmodel"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "tiebreak_criterion",
                sa.Enum(
                    "last_checkpoint",
                    "registration_date",
                    "alphabetical",
                    name="tiebreakcriterion",
                ),
                nullable=True,
            )
        )
        # Remove campos antigos
        batch_op.drop_index("ix_competitions_modality_id")
        batch_op.drop_constraint("fk_competitions_modality_id", type_="foreignkey")
        batch_op.drop_column("modality_id")
        batch_op.drop_column("duration_seconds")
        batch_op.drop_column("max_athletes")
        batch_op.drop_column("rules")


def downgrade() -> None:
    with op.batch_alter_table("competitions") as batch_op:
        batch_op.add_column(sa.Column("rules", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("max_athletes", sa.Integer(), nullable=False, server_default="300")
        )
        batch_op.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("modality_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_competitions_modality_id", "modalities", ["modality_id"], ["id"]
        )
        batch_op.create_index("ix_competitions_modality_id", ["modality_id"], unique=False)
        batch_op.drop_column("tiebreak_criterion")
        batch_op.drop_column("scoring_model")
        batch_op.drop_column("is_public")
        batch_op.drop_column("event_type")
        batch_op.drop_column("end_date")
        batch_op.alter_column(
            "start_date", new_column_name="event_date", existing_type=sa.Date(), nullable=True
        )
```

- [ ] **Step 2: Criar `20260615_category_gender_age.py`**

```python
"""category_gender_age

Revision ID: 20260615_category_gender_age
Revises: 20260615_competition_core_fields
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260615_category_gender_age"
down_revision = "20260615_competition_core_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(
            sa.Column(
                "gender",
                sa.Enum("male", "female", "mixed", name="gender"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "age_restriction_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("age_min", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("age_max", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_column("age_max")
        batch_op.drop_column("age_min")
        batch_op.drop_column("age_restriction_enabled")
        batch_op.drop_column("gender")
```

- [ ] **Step 3: Criar `20260615_athletes_table.py`**

```python
"""athletes_table

Revision ID: 20260615_athletes_table
Revises: 20260615_category_gender_age
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260615_athletes_table"
down_revision = "20260615_category_gender_age"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athletes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("document", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column(
            "tshirt_size",
            sa.Enum("P", "M", "G", "GG", "XG", name="tshirtsize"),
            nullable=True,
        ),
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
    )


def downgrade() -> None:
    op.drop_table("athletes")
```

- [ ] **Step 4: Verificar encadeamento correto das migrations**

```bash
cd backend && python -m alembic history --verbose 2>&1 | tail -20
```
Verificar que a chain está correta: `...20260328... → 20260615_competition_core_fields → 20260615_category_gender_age → 20260615_athletes_table`

- [ ] **Step 5: Commit**

```bash
git add app/db/migrations/versions/20260615_*.py
git commit -m "db(migrations): fase 1 — competition core fields, category gender/age, athletes table"
```

---

## Task 8: Frontend — Atualizar tipos e clientes de API

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/competitions.ts`
- Create: `frontend/src/api/athletes.ts`
- Create: `frontend/src/api/cep.ts`

- [ ] **Step 1: Atualizar `src/types/index.ts`**

Adicionar os novos tipos (manter os existentes que ainda são válidos):

```typescript
// Adicionar novos tipos de Competition
export type EventType = "hyrox" | "crossfit";
export type ScoringModel = "lowest_time" | "most_points";
export type TiebreakCriterion = "last_checkpoint" | "registration_date" | "alphabetical";
export type Gender = "male" | "female" | "mixed";
export type TshirtSize = "P" | "M" | "G" | "GG" | "XG";

// Atualizar interface Competition (substituir a existente)
export interface Competition {
  id: number;
  name: string;
  location: string | null;
  start_date: string | null;   // era event_date
  end_date: string | null;
  event_type: EventType | null;
  is_public: boolean;
  scoring_model: ScoringModel | null;
  tiebreak_criterion: TiebreakCriterion | null;
  status: "draft" | "active" | "finished";
  created_at: string;
  updated_at: string;
}

// Atualizar interface Category (adicionar novos campos)
export interface Category {
  id: number;
  competition_id: number;
  name: string;
  category_type: "individual" | "team";
  gender: Gender | null;
  age_restriction_enabled: boolean;
  age_min: number | null;
  age_max: number | null;
  max_team_size: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Novo tipo Athlete
export interface Athlete {
  id: number;
  competition_id: number;
  category_id: number | null;
  team_id: number | null;
  name: string;
  email: string | null;
  document: string | null;
  phone: string | null;
  tshirt_size: TshirtSize | null;
  created_at: string;
  updated_at: string;
}

export interface AthleteCreate {
  name: string;
  email?: string;
  document?: string;
  phone?: string;
  category_id?: number;
  team_id?: number;
  tshirt_size?: TshirtSize;
}

export interface AthleteBulkResult {
  created: number;
  errors: Array<{ row: number; name: string; error: string }>;
}

// Tipo para lookup CEP
export interface CepResult {
  cep: string | null;
  logradouro: string | null;
  complemento: string | null;
  bairro: string | null;
  localidade: string | null;
  uf: string | null;
}
```

- [ ] **Step 2: Atualizar `src/api/competitions.ts`**

Substituir `CompetitionCreate` e `CompetitionUpdate` para usar os novos campos:

```typescript
import { apiClient } from "./client";
import type { Competition, EventType, ScoringModel, TiebreakCriterion } from "../types";

export interface CompetitionCreate {
  name: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  event_type?: EventType;
  is_public?: boolean;
  scoring_model?: ScoringModel;
  tiebreak_criterion?: TiebreakCriterion;
}

export interface CompetitionUpdate extends Partial<CompetitionCreate> {
  status?: "draft" | "active" | "finished";
}

export const competitionsApi = {
  list: () => apiClient.get<Competition[]>("/competitions"),
  get: (id: number) => apiClient.get<Competition>(`/competitions/${id}`),
  create: (data: CompetitionCreate) => apiClient.post<Competition>("/competitions", data),
  update: (id: number, data: CompetitionUpdate) =>
    apiClient.patch<Competition>(`/competitions/${id}`, data),
  delete: (id: number) => apiClient.delete(`/competitions/${id}`),
  clone: (id: number) => apiClient.post<Competition>(`/competitions/${id}/clone`),
};
```

> Nota: `apiClient.get<T>(path)` e demais métodos devem retornar `Promise<T>` — ajustar conforme o padrão existente em `src/api/client.ts`. Se `apiClient` retorna `AxiosResponse<T>`, usar `.then(r => r.data)` nos componentes.

- [ ] **Step 3: Criar `src/api/athletes.ts`**

```typescript
import { apiClient } from "./client";
import type { Athlete, AthleteCreate, AthleteBulkResult } from "../types";

export const athletesApi = {
  list: (competitionId: number, params?: { category_id?: number; team_id?: number }) =>
    apiClient.get<Athlete[]>(`/competitions/${competitionId}/athletes`, { params }),

  create: (competitionId: number, data: AthleteCreate) =>
    apiClient.post<Athlete>(`/competitions/${competitionId}/athletes`, data),

  update: (competitionId: number, athleteId: number, data: Partial<AthleteCreate>) =>
    apiClient.put<Athlete>(`/competitions/${competitionId}/athletes/${athleteId}`, data),

  delete: (competitionId: number, athleteId: number) =>
    apiClient.delete(`/competitions/${competitionId}/athletes/${athleteId}`),

  importCsv: (competitionId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<AthleteBulkResult>(
      `/competitions/${competitionId}/athletes/import`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
  },
};
```

- [ ] **Step 4: Criar `src/api/cep.ts`**

```typescript
import { apiClient } from "./client";
import type { CepResult } from "../types";

export const cepApi = {
  lookup: (cep: string) =>
    apiClient.get<CepResult>(`/cep/${cep.replace(/\D/g, "")}`),
};
```

- [ ] **Step 5: Verificar build TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Esperado: sem erros de tipo nos arquivos novos/modificados.

- [ ] **Step 6: Commit**

```bash
git add src/types/index.ts src/api/competitions.ts src/api/athletes.ts src/api/cep.ts
git commit -m "feat(frontend): atualiza tipos e clientes de API para redesenho fase 1"
```

---

## Task 9: CompetitionsListPage

**Files:**
- Create: `frontend/src/pages/CompetitionsListPage.tsx`
- Modify: `frontend/src/App.tsx` (parcial — só a rota /competitions)

A página atual (`CompetitionsPage.tsx`) tem tudo inline. A nova é uma tabela limpa com ações por linha.

- [ ] **Step 1: Criar `src/pages/CompetitionsListPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PlusIcon } from "@heroicons/react/24/outline";
import { competitionsApi } from "../api/competitions";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Alert from "../components/ui/Alert";
import type { Competition } from "../types";

const STATUS_LABEL: Record<string, { label: string; variant: "gray" | "green" | "red" }> = {
  draft: { label: "Rascunho", variant: "gray" },
  active: { label: "Ativa", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

const EVENT_TYPE_LABEL: Record<string, string> = {
  hyrox: "Hyrox",
  crossfit: "CrossFit",
};

function formatDateRange(start: string | null, end: string | null): string {
  if (!start) return "—";
  const fmt = (d: string) =>
    new Date(d + "T00:00:00").toLocaleDateString("pt-BR");
  return end ? `${fmt(start)} → ${fmt(end)}` : fmt(start);
}

export default function CompetitionsListPage() {
  const navigate = useNavigate();
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  useEffect(() => {
    competitionsApi
      .list()
      .then((data) => setCompetitions(Array.isArray(data) ? data : (data as any).data))
      .catch(() => setError("Erro ao carregar campeonatos"))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(id: number) {
    if (!window.confirm("Remover este campeonato? Esta ação não pode ser desfeita.")) return;
    try {
      await competitionsApi.delete(id);
      setCompetitions((prev) => prev.filter((c) => c.id !== id));
    } catch {
      setError("Erro ao remover campeonato");
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Campeonatos</h1>
          <p className="mt-1 text-sm text-gray-500">
            {competitions.length} campeonato{competitions.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Button
          onClick={() => navigate("/competitions/new")}
          className="flex items-center gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          Novo Campeonato
        </Button>
      </div>

      {error && <Alert variant="error" message={error} onClose={() => setError(null)} />}

      {competitions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center">
          <p className="text-gray-500">Nenhum campeonato cadastrado.</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => navigate("/competitions/new")}
          >
            Criar primeiro campeonato
          </Button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Nome
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Data
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Tipo
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {competitions.map((comp) => {
                const statusInfo = STATUS_LABEL[comp.status] ?? { label: comp.status, variant: "gray" as const };
                return (
                  <tr key={comp.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <span className="font-medium text-gray-900">{comp.name}</span>
                      {comp.location && (
                        <p className="text-xs text-gray-500">{comp.location}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">
                      {formatDateRange(comp.start_date, comp.end_date)}
                    </td>
                    <td className="px-6 py-4">
                      {comp.event_type ? (
                        <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                          {EVENT_TYPE_LABEL[comp.event_type] ?? comp.event_type}
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => navigate(`/competitions/${comp.id}/dashboard`)}
                          className="text-sm font-medium text-primary-600 hover:text-primary-800"
                        >
                          Dashboard
                        </button>
                        <button
                          onClick={() => navigate(`/competitions/${comp.id}/edit`)}
                          className="text-sm font-medium text-gray-600 hover:text-gray-800"
                        >
                          Editar
                        </button>
                        {comp.status === "draft" && (
                          <button
                            onClick={() => handleDelete(comp.id)}
                            className="text-sm font-medium text-red-600 hover:text-red-800"
                          >
                            Remover
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/CompetitionsListPage.tsx
git commit -m "feat(frontend): CompetitionsListPage com tabela limpa e ações por linha"
```

---

## Task 10: CompetitionWizardPage (etapas 1, 4, 5)

**Files:**
- Create: `frontend/src/pages/CompetitionWizardPage.tsx`

O wizard armazena todo o estado local até a Etapa 5. Em modo edição (`/competitions/:id/edit`), carrega os dados da competição existente no estado.

- [ ] **Step 1: Criar `src/pages/CompetitionWizardPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { competitionsApi, type CompetitionCreate } from "../api/competitions";
import { categoriesApi } from "../api/categories";
import { cepApi } from "../api/cep";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import type { Category, EventType, ScoringModel, TiebreakCriterion } from "../types";

// ── Tipos do estado local ─────────────────────────────────────────────────────

interface WizardStep1 {
  name: string;
  start_date: string;
  end_date: string;
  cep: string;
  logradouro: string;
  bairro: string;
  cidade: string;
  uf: string;
  numero: string;
  complemento: string;
  event_type: EventType | "";
}

interface WizardStep4 {
  scoring_model: ScoringModel | "";
  tiebreak_criterion: TiebreakCriterion | "";
}

interface WizardState {
  step1: WizardStep1;
  step4: WizardStep4;
  categories: Pick<Category, "name" | "category_type" | "gender" | "max_team_size">[];
}

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
  step4: { scoring_model: "", tiebreak_criterion: "" },
  categories: [],
};

// ── Componente principal ──────────────────────────────────────────────────────

export default function CompetitionWizardPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [currentStep, setCurrentStep] = useState(1);
  const [state, setState] = useState<WizardState>(INITIAL_STATE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [cepLoading, setCepLoading] = useState(false);

  // Em modo edição, carrega dados existentes
  useEffect(() => {
    if (!id) return;
    competitionsApi.get(Number(id)).then((comp: any) => {
      const c = comp.data ?? comp;
      setState((prev) => ({
        ...prev,
        step1: {
          name: c.name ?? "",
          start_date: c.start_date ?? "",
          end_date: c.end_date ?? "",
          cep: "",
          logradouro: c.location ?? "",
          bairro: "",
          cidade: "",
          uf: "",
          numero: "",
          complemento: "",
          event_type: c.event_type ?? "",
        },
        step4: {
          scoring_model: c.scoring_model ?? "",
          tiebreak_criterion: c.tiebreak_criterion ?? "",
        },
      }));
    });
  }, [id]);

  // ── CEP lookup ─────────────────────────────────────────────────────────────

  async function handleCepBlur() {
    const digits = state.step1.cep.replace(/\D/g, "");
    if (digits.length !== 8) return;
    setCepLoading(true);
    try {
      const result: any = await cepApi.lookup(digits);
      const d = result.data ?? result;
      setState((prev) => ({
        ...prev,
        step1: {
          ...prev.step1,
          logradouro: d.logradouro ?? "",
          bairro: d.bairro ?? "",
          cidade: d.localidade ?? "",
          uf: d.uf ?? "",
        },
      }));
    } catch {
      // CEP inválido — não exibir erro, usuário preenche manualmente
    } finally {
      setCepLoading(false);
    }
  }

  // ── Validação por etapa ────────────────────────────────────────────────────

  function validateStep1(): string | null {
    if (!state.step1.name.trim()) return "Nome do campeonato é obrigatório";
    if (!state.step1.event_type) return "Selecione o tipo de evento (Hyrox ou CrossFit)";
    return null;
  }

  function validateStep4(): string | null {
    if (!state.step4.scoring_model) return "Selecione o modelo de pontuação";
    return null;
  }

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
    setCurrentStep((s) => Math.min(s + 1, 5));
  }

  function handleBack() {
    setError(null);
    setCurrentStep((s) => Math.max(s - 1, 1));
  }

  // ── Submissão final ────────────────────────────────────────────────────────

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
    };

    try {
      let competition: any;
      if (isEdit && id) {
        competition = await competitionsApi.update(Number(id), payload);
      } else {
        competition = await competitionsApi.create(payload);
      }
      const comp = competition.data ?? competition;
      navigate(`/competitions/${comp.id}/dashboard`);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro ao salvar campeonato");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Render por etapa ───────────────────────────────────────────────────────

  const STEPS = ["Informações", "Divulgação", "WODs", "Pontuação", "Finalização"];

  return (
    <div className="mx-auto max-w-3xl space-y-8 py-8">
      {/* Breadcrumb de etapas */}
      <nav className="flex gap-2">
        {STEPS.map((label, i) => {
          const step = i + 1;
          const done = step < currentStep;
          const active = step === currentStep;
          return (
            <div key={step} className="flex items-center gap-2">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  done
                    ? "bg-primary-600 text-white"
                    : active
                    ? "border-2 border-primary-600 text-primary-600"
                    : "border-2 border-gray-300 text-gray-400"
                }`}
              >
                {step}
              </div>
              <span
                className={`text-sm ${active ? "font-medium text-gray-900" : "text-gray-400"}`}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && (
                <div className="h-px w-6 bg-gray-300" />
              )}
            </div>
          );
        })}
      </nav>

      {error && <Alert variant="error" message={error} onClose={() => setError(null)} />}

      {/* Etapa 1: Informações Gerais */}
      {currentStep === 1 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Informações Gerais</h2>

          {/* 1.1 Dados básicos */}
          <div className="space-y-4">
            <Input
              label="Nome do campeonato *"
              value={state.step1.name}
              onChange={(e) =>
                setState((p) => ({ ...p, step1: { ...p.step1, name: e.target.value } }))
              }
            />
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Data de início"
                type="date"
                value={state.step1.start_date}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, start_date: e.target.value } }))
                }
              />
              <Input
                label="Data de término"
                type="date"
                value={state.step1.end_date}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, end_date: e.target.value } }))
                }
              />
            </div>
          </div>

          {/* 1.1 Local / CEP */}
          <div className="space-y-4 border-t pt-4">
            <h3 className="font-medium text-gray-700">Local do evento</h3>
            <div className="grid grid-cols-3 gap-4">
              <Input
                label="CEP"
                value={state.step1.cep}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, cep: e.target.value } }))
                }
                onBlur={handleCepBlur}
                placeholder="00000-000"
              />
              {cepLoading && (
                <div className="flex items-end pb-2">
                  <span className="text-sm text-gray-400">Buscando...</span>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Logradouro"
                value={state.step1.logradouro}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, logradouro: e.target.value } }))
                }
              />
              <Input
                label="Número"
                value={state.step1.numero}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, numero: e.target.value } }))
                }
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Input
                label="Bairro"
                value={state.step1.bairro}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, bairro: e.target.value } }))
                }
              />
              <Input
                label="Cidade"
                value={state.step1.cidade}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, cidade: e.target.value } }))
                }
              />
              <Input
                label="UF"
                value={state.step1.uf}
                maxLength={2}
                onChange={(e) =>
                  setState((p) => ({ ...p, step1: { ...p.step1, uf: e.target.value.toUpperCase() } }))
                }
              />
            </div>
          </div>

          {/* 1.2 Tipo do evento */}
          <div className="space-y-3 border-t pt-4">
            <h3 className="font-medium text-gray-700">Tipo de evento *</h3>
            <div className="grid grid-cols-2 gap-4">
              {(["hyrox", "crossfit"] as EventType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() =>
                    setState((p) => ({ ...p, step1: { ...p.step1, event_type: type } }))
                  }
                  className={`rounded-lg border-2 p-4 text-left transition-colors ${
                    state.step1.event_type === type
                      ? "border-primary-600 bg-primary-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <p className="font-semibold text-gray-900 capitalize">{type}</p>
                  <p className="text-sm text-gray-500">
                    {type === "hyrox"
                      ? "Corrida + Estações de Funcional"
                      : "WODs com pontuação por posição"}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* 1.3 Categorias — placeholder para esta fase */}
          <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
            Categorias podem ser adicionadas após a criação no dashboard do campeonato.
          </div>
        </div>
      )}

      {/* Etapas 2 e 3 — implementadas na Fase 2 e 3 */}
      {(currentStep === 2 || currentStep === 3) && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-12 text-center">
          <p className="text-gray-500">
            {currentStep === 2
              ? "Etapa 2 (Divulgação) — disponível na Fase 2 do redesenho."
              : "Etapa 3 (WODs) — disponível na Fase 3 do redesenho (somente CrossFit)."}
          </p>
        </div>
      )}

      {/* Etapa 4: Pontuação */}
      {currentStep === 4 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Modelo de Pontuação</h2>

          <div className="grid grid-cols-2 gap-4">
            {(
              [
                {
                  value: "lowest_time" as ScoringModel,
                  label: "Menor Tempo",
                  desc: "Vence quem terminar mais rápido",
                },
                {
                  value: "most_points" as ScoringModel,
                  label: "Mais Pontos",
                  desc: "Vence quem acumular mais pontos",
                },
              ] as const
            ).map(({ value, label, desc }) => (
              <button
                key={value}
                type="button"
                onClick={() =>
                  setState((p) => ({ ...p, step4: { ...p.step4, scoring_model: value } }))
                }
                className={`rounded-lg border-2 p-4 text-left transition-colors ${
                  state.step4.scoring_model === value
                    ? "border-primary-600 bg-primary-50"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <p className="font-semibold text-gray-900">{label}</p>
                <p className="text-sm text-gray-500">{desc}</p>
              </button>
            ))}
          </div>

          <div className="space-y-3 border-t pt-4">
            <h3 className="font-medium text-gray-700">Critério de desempate</h3>
            {(
              [
                { value: "last_checkpoint" as TiebreakCriterion, label: "Último checkpoint" },
                { value: "registration_date" as TiebreakCriterion, label: "Data de inscrição" },
                { value: "alphabetical" as TiebreakCriterion, label: "Ordem alfabética" },
              ] as const
            ).map(({ value, label }) => (
              <label key={value} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="tiebreak"
                  value={value}
                  checked={state.step4.tiebreak_criterion === value}
                  onChange={() =>
                    setState((p) => ({
                      ...p,
                      step4: { ...p.step4, tiebreak_criterion: value },
                    }))
                  }
                  className="h-4 w-4 text-primary-600"
                />
                <span className="text-sm text-gray-700">{label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Etapa 5: Resumo e criação */}
      {currentStep === 5 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Resumo</h2>

          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Nome</p>
              <p className="mt-1 font-medium text-gray-900">{state.step1.name || "—"}</p>
            </div>
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Tipo</p>
              <p className="mt-1 font-medium text-gray-900 capitalize">
                {state.step1.event_type || "—"}
              </p>
            </div>
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Data</p>
              <p className="mt-1 font-medium text-gray-900">
                {state.step1.start_date || "—"}
                {state.step1.end_date ? ` → ${state.step1.end_date}` : ""}
              </p>
            </div>
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Pontuação</p>
              <p className="mt-1 font-medium text-gray-900">
                {state.step4.scoring_model === "lowest_time" ? "Menor Tempo" : state.step4.scoring_model === "most_points" ? "Mais Pontos" : "—"}
              </p>
            </div>
          </div>

          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full justify-center"
          >
            {submitting
              ? "Salvando..."
              : isEdit
              ? "Salvar Alterações"
              : "Criar Campeonato"}
          </Button>
        </div>
      )}

      {/* Navegação */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={currentStep === 1}
        >
          Voltar
        </Button>
        {currentStep < 5 && (
          <Button onClick={handleNext}>
            {currentStep === 4 ? "Revisar" : "Avançar"}
          </Button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/CompetitionWizardPage.tsx
git commit -m "feat(frontend): CompetitionWizardPage com etapas 1 (informações+tipo), 4 (pontuação), 5 (resumo)"
```

---

## Task 11: CompetitionDashboardLayout + DashboardOverviewPage

**Files:**
- Create: `frontend/src/pages/dashboard/CompetitionDashboardLayout.tsx`
- Create: `frontend/src/pages/dashboard/DashboardOverviewPage.tsx`

- [ ] **Step 1: Criar `src/pages/dashboard/CompetitionDashboardLayout.tsx`**

```tsx
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import {
  ChartBarIcon,
  UserGroupIcon,
  PlayIcon,
  TrophyIcon,
  ArrowLeftIcon,
} from "@heroicons/react/24/outline";
import { competitionsApi } from "../../api/competitions";
import Badge from "../../components/ui/Badge";
import type { Competition } from "../../types";

const STATUS_VARIANT: Record<string, "gray" | "green" | "red"> = {
  draft: "gray",
  active: "green",
  finished: "red",
};
const STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho",
  active: "Ativa",
  finished: "Encerrada",
};

const NAV_ITEMS = [
  { to: "", label: "Visão Geral", icon: ChartBarIcon, end: true },
  { to: "equipes", label: "Equipes", icon: UserGroupIcon, end: false },
  { to: "atletas", label: "Atletas", icon: UserGroupIcon, end: false },
  { to: "baterias", label: "Baterias", icon: PlayIcon, end: false },
  { to: "resultados", label: "Resultados", icon: TrophyIcon, end: false },
];

export default function CompetitionDashboardLayout() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const navigate = useNavigate();
  const [competition, setCompetition] = useState<Competition | null>(null);

  useEffect(() => {
    if (!competitionId) return;
    competitionsApi.get(Number(competitionId)).then((data: any) => {
      setCompetition(data.data ?? data);
    });
  }, [competitionId]);

  return (
    <div className="flex min-h-screen">
      {/* Sidebar escura */}
      <aside className="flex w-52 flex-col bg-slate-900 text-white">
        {/* Voltar + nome */}
        <div className="border-b border-slate-700 p-4">
          <button
            onClick={() => navigate("/competitions")}
            className="mb-3 flex items-center gap-1 text-xs text-slate-400 hover:text-white"
          >
            <ArrowLeftIcon className="h-3 w-3" /> Campeonatos
          </button>
          {competition ? (
            <>
              <p className="text-sm font-semibold leading-tight">{competition.name}</p>
              <div className="mt-1">
                <Badge variant={STATUS_VARIANT[competition.status]}>
                  {STATUS_LABEL[competition.status]}
                </Badge>
              </div>
            </>
          ) : (
            <div className="h-4 w-32 animate-pulse rounded bg-slate-700" />
          )}
        </div>

        {/* Navegação */}
        <nav className="flex-1 space-y-0.5 p-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-slate-700 text-white"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Leaderboard público */}
        <div className="border-t border-slate-700 p-3">
          <a
            href={`/competitions/${competitionId}/leaderboard`}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-md px-3 py-2 text-xs text-slate-400 hover:text-white"
          >
            🔗 Leaderboard público
          </a>
        </div>
      </aside>

      {/* Conteúdo */}
      <main className="flex-1 overflow-auto bg-gray-50 p-8">
        {competition ? (
          <Outlet context={{ competition }} />
        ) : (
          <div className="flex justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
          </div>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Criar `src/pages/dashboard/DashboardOverviewPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { teamsApi } from "../../api/teams";
import { categoriesApi } from "../../api/categories";
import { athletesApi } from "../../api/athletes";
import type { Competition } from "../../types";

interface OutletCtx {
  competition: Competition;
}

function daysUntil(dateStr: string | null): string {
  if (!dateStr) return "—";
  const diff = Math.ceil(
    (new Date(dateStr + "T00:00:00").getTime() - Date.now()) / 86400000
  );
  if (diff < 0) return "Encerrado";
  if (diff === 0) return "Hoje";
  return `${diff} dia${diff !== 1 ? "s" : ""}`;
}

export default function DashboardOverviewPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const { competition } = useOutletContext<OutletCtx>();
  const [teamCount, setTeamCount] = useState<number | null>(null);
  const [athleteCount, setAthleteCount] = useState<number | null>(null);
  const [categoryCount, setCategoryCount] = useState<number | null>(null);

  useEffect(() => {
    const id = Number(competitionId);
    teamsApi.list(id).then((d: any) => setTeamCount((d.data ?? d).length));
    athletesApi.list(id).then((d: any) => setAthleteCount((d.data ?? d).length));
    categoriesApi.list(id).then((d: any) => setCategoryCount((d.data ?? d).length));
  }, [competitionId]);

  const EVENT_LABEL: Record<string, string> = { hyrox: "Hyrox", crossfit: "CrossFit" };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{competition.name}</h1>
        {competition.location && (
          <p className="mt-1 text-sm text-gray-500">{competition.location}</p>
        )}
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Dias para início", value: daysUntil(competition.start_date) },
          { label: "Equipes", value: teamCount ?? "…" },
          { label: "Atletas", value: athleteCount ?? "…" },
          { label: "Categorias", value: categoryCount ?? "…" },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg border border-gray-200 bg-white p-5">
            <p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p>
            <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Informações do evento */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 font-semibold text-gray-900">Informações do Evento</h2>
        <dl className="grid grid-cols-2 gap-4">
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Tipo</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {competition.event_type
                ? EVENT_LABEL[competition.event_type] ?? competition.event_type
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Pontuação</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {competition.scoring_model === "lowest_time"
                ? "Menor Tempo"
                : competition.scoring_model === "most_points"
                ? "Mais Pontos"
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Inscrições</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {competition.is_public ? "Públicas" : "Fechadas"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Desempate</dt>
            <dd className="mt-1 text-sm text-gray-900 capitalize">
              {competition.tiebreak_criterion?.replace(/_/g, " ") ?? "—"}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add src/pages/dashboard/
git commit -m "feat(frontend): CompetitionDashboardLayout (sidebar escura) + DashboardOverviewPage"
```

---

## Task 12: TeamsPage no dashboard

**Files:**
- Create: `frontend/src/pages/dashboard/TeamsPage.tsx`

Mesma funcionalidade de gerenciar equipes, mas dentro do dashboard. Usa `competitionId` do `useParams`.

- [ ] **Step 1: Criar `src/pages/dashboard/TeamsPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { PlusIcon } from "@heroicons/react/24/outline";
import { teamsApi, type TeamCreate } from "../../api/teams";
import { categoriesApi } from "../../api/categories";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import type { Category, Competition, Team } from "../../types";

interface OutletCtx {
  competition: Competition;
}

export default function TeamsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const { competition } = useOutletContext<OutletCtx>();
  const id = Number(competitionId);

  const [teams, setTeams] = useState<Team[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [filterCat, setFilterCat] = useState<string>("");
  const [search, setSearch] = useState("");

  // Form state
  const [form, setForm] = useState<TeamCreate & { category_id?: number }>({
    name: "",
    category_id: undefined,
  });

  useEffect(() => {
    Promise.all([
      teamsApi.list(id).then((d: any) => d.data ?? d),
      categoriesApi.list(id).then((d: any) => d.data ?? d),
    ])
      .then(([t, c]) => { setTeams(t); setCategories(c); })
      .catch(() => setError("Erro ao carregar dados"))
      .finally(() => setLoading(false));
  }, [id]);

  const filtered = teams.filter((t) => {
    if (filterCat && String(t.category_id) !== filterCat) return false;
    if (search && !t.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const created: any = await teamsApi.create(id, form);
      const team = created.data ?? created;
      setTeams((p) => [...p, team]);
      setForm({ name: "", category_id: undefined });
      setShowForm(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro ao criar equipe");
    }
  }

  async function handleDelete(teamId: number) {
    if (!window.confirm("Remover esta equipe?")) return;
    try {
      await teamsApi.delete(id, teamId);
      setTeams((p) => p.filter((t) => t.id !== teamId));
    } catch {
      setError("Erro ao remover equipe");
    }
  }

  if (loading) return <div className="flex justify-center py-20"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Equipes</h1>
        <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
          <PlusIcon className="h-4 w-4" /> Nova Equipe
        </Button>
      </div>

      {error && <Alert variant="error" message={error} onClose={() => setError(null)} />}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-4"
        >
          <h3 className="font-medium">Nova Equipe</h3>
          <Input
            label="Nome *"
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            required
          />
          <div>
            <label className="block text-sm font-medium text-gray-700">Categoria</label>
            <select
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              value={form.category_id ?? ""}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  category_id: e.target.value ? Number(e.target.value) : undefined,
                }))
              }
            >
              <option value="">Sem categoria</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <Button type="submit">Salvar</Button>
            <Button variant="outline" type="button" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {/* Filtros */}
      <div className="flex gap-3">
        <Input
          placeholder="Buscar por nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          className="rounded-md border-gray-300 text-sm shadow-sm"
          value={filterCat}
          onChange={(e) => setFilterCat(e.target.value)}
        >
          <option value="">Todas as categorias</option>
          {categories.map((c) => (
            <option key={c.id} value={String(c.id)}>{c.name}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Nome</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Categoria</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Membros</th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase text-gray-500">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">
                  Nenhuma equipe encontrada
                </td>
              </tr>
            ) : (
              filtered.map((team) => {
                const cat = categories.find((c) => c.id === team.category_id);
                return (
                  <tr key={team.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 font-medium text-gray-900">{team.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{cat?.name ?? "—"}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{team.member_count}</td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(team.id)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Remover
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

> Nota: `teamsApi.list(id)` e `teamsApi.create(id, form)` e `teamsApi.delete(id, teamId)` devem existir em `src/api/teams.ts`. Verificar assinatura atual e ajustar se necessário.

- [ ] **Step 2: Commit**

```bash
git add src/pages/dashboard/TeamsPage.tsx
git commit -m "feat(frontend): TeamsPage dentro do dashboard (filtros + criar + remover)"
```

---

## Task 13: AthletesPage no dashboard

**Files:**
- Create: `frontend/src/pages/dashboard/AthletesPage.tsx`

- [ ] **Step 1: Criar `src/pages/dashboard/AthletesPage.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { PlusIcon, ArrowUpTrayIcon } from "@heroicons/react/24/outline";
import { athletesApi } from "../../api/athletes";
import { categoriesApi } from "../../api/categories";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import type { Athlete, AthleteCreate, Category, TshirtSize } from "../../types";

const TSHIRT_SIZES: TshirtSize[] = ["P", "M", "G", "GG", "XG"];

export default function AthletesPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);

  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [filterCat, setFilterCat] = useState<string>("");
  const [search, setSearch] = useState("");
  const [editId, setEditId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState<AthleteCreate>({ name: "" });

  useEffect(() => {
    Promise.all([
      athletesApi.list(id).then((d: any) => d.data ?? d),
      categoriesApi.list(id).then((d: any) => d.data ?? d),
    ])
      .then(([a, c]) => { setAthletes(a); setCategories(c); })
      .catch(() => setError("Erro ao carregar dados"))
      .finally(() => setLoading(false));
  }, [id]);

  const filtered = athletes.filter((a) => {
    if (filterCat && String(a.category_id) !== filterCat) return false;
    if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res: any = await athletesApi.create(id, form);
      setAthletes((p) => [...p, res.data ?? res]);
      setForm({ name: "" });
      setShowForm(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro ao criar atleta");
    }
  }

  async function handleDelete(athleteId: number) {
    if (!window.confirm("Remover este atleta?")) return;
    try {
      await athletesApi.delete(id, athleteId);
      setAthletes((p) => p.filter((a) => a.id !== athleteId));
    } catch {
      setError("Erro ao remover atleta");
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setImportResult(null);
    try {
      const res: any = await athletesApi.importCsv(id, file);
      const data = res.data ?? res;
      setImportResult(`${data.created} atleta(s) importado(s) com sucesso.${data.errors.length ? ` ${data.errors.length} erro(s).` : ""}`);
      // Recarrega lista
      const updated: any = await athletesApi.list(id);
      setAthletes(updated.data ?? updated);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro na importação");
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  if (loading) return <div className="flex justify-center py-20"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Atletas</h1>
        <div className="flex gap-2">
          <label className="flex cursor-pointer items-center gap-2 rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            <ArrowUpTrayIcon className="h-4 w-4" />
            Importar CSV
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="sr-only"
              onChange={handleImport}
            />
          </label>
          <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
            <PlusIcon className="h-4 w-4" /> Novo Atleta
          </Button>
        </div>
      </div>

      {error && <Alert variant="error" message={error} onClose={() => setError(null)} />}
      {importResult && (
        <Alert variant="success" message={importResult} onClose={() => setImportResult(null)} />
      )}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-4"
        >
          <h3 className="font-medium">Novo Atleta</h3>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Nome *"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              required
            />
            <Input
              label="Email"
              type="email"
              value={form.email ?? ""}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value || undefined }))}
            />
            <Input
              label="Documento (CPF)"
              value={form.document ?? ""}
              onChange={(e) => setForm((p) => ({ ...p, document: e.target.value || undefined }))}
            />
            <Input
              label="Telefone"
              value={form.phone ?? ""}
              onChange={(e) => setForm((p) => ({ ...p, phone: e.target.value || undefined }))}
            />
            <div>
              <label className="block text-sm font-medium text-gray-700">Categoria</label>
              <select
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                value={form.category_id ?? ""}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    category_id: e.target.value ? Number(e.target.value) : undefined,
                  }))
                }
              >
                <option value="">Sem categoria</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Tamanho de Camiseta</label>
              <select
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                value={form.tshirt_size ?? ""}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    tshirt_size: (e.target.value as TshirtSize) || undefined,
                  }))
                }
              >
                <option value="">—</option>
                {TSHIRT_SIZES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="submit">Salvar</Button>
            <Button variant="outline" type="button" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {/* Filtros */}
      <div className="flex gap-3">
        <Input
          placeholder="Buscar por nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <select
          className="rounded-md border-gray-300 text-sm shadow-sm"
          value={filterCat}
          onChange={(e) => setFilterCat(e.target.value)}
        >
          <option value="">Todas as categorias</option>
          {categories.map((c) => (
            <option key={c.id} value={String(c.id)}>{c.name}</option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Nome</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Email</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Documento</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Categoria</th>
              <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500">
                  Nenhum atleta encontrado
                </td>
              </tr>
            ) : (
              filtered.map((athlete) => {
                const cat = categories.find((c) => c.id === athlete.category_id);
                return (
                  <tr key={athlete.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{athlete.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{athlete.email ?? "—"}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{athlete.document ?? "—"}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{cat?.name ?? "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(athlete.id)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Remover
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/dashboard/AthletesPage.tsx
git commit -m "feat(frontend): AthletesPage com CRUD e importação CSV dentro do dashboard"
```

---

## Task 14: HeatsPage migrada para o dashboard

**Files:**
- Create: `frontend/src/pages/dashboard/HeatsPage.tsx`

A `TimersPage.tsx` atual tem funcionalidade de baterias. Criar uma versão simplificada para o dashboard, mantendo a funcionalidade de baterias existente.

- [ ] **Step 1: Criar `src/pages/dashboard/HeatsPage.tsx`**

Esta página deve:
1. Importar e reusar a lógica de baterias existente (heatsApi, timersApi)
2. Não exibir seletor de competição (já está no contexto do dashboard)
3. Exibir cards de bateria com status e controles

```tsx
import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { PlusIcon } from "@heroicons/react/24/outline";
import { heatsApi, type HeatCreate } from "../../api/heats";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import Badge from "../../components/ui/Badge";
import type { Competition, Heat } from "../../types";

interface OutletCtx {
  competition: Competition;
}

const HEAT_STATUS_BADGE: Record<string, { label: string; variant: "gray" | "green" | "red" }> = {
  pending: { label: "Aguardando", variant: "gray" },
  running: { label: "Em andamento", variant: "green" },
  finished: { label: "Encerrada", variant: "red" },
};

export default function HeatsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const { competition } = useOutletContext<OutletCtx>();
  const id = Number(competitionId);

  const [heats, setHeats] = useState<Heat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newHeatName, setNewHeatName] = useState("");

  useEffect(() => {
    heatsApi
      .list(id)
      .then((d: any) => setHeats(d.data ?? d))
      .catch(() => setError("Erro ao carregar baterias"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const payload: HeatCreate = { name: newHeatName, competition_id: id };
      const res: any = await heatsApi.create(id, payload);
      setHeats((p) => [...p, res.data ?? res]);
      setNewHeatName("");
      setShowForm(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro ao criar bateria");
    }
  }

  async function handleDelete(heatId: number) {
    if (!window.confirm("Remover esta bateria?")) return;
    try {
      await heatsApi.delete(id, heatId);
      setHeats((p) => p.filter((h) => h.id !== heatId));
    } catch {
      setError("Erro ao remover bateria");
    }
  }

  async function handleStart(heatId: number) {
    setError(null);
    try {
      const res: any = await heatsApi.start(id, heatId);
      const updated = res.data ?? res;
      setHeats((p) => p.map((h) => (h.id === heatId ? updated : h)));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Erro ao iniciar bateria");
    }
  }

  if (loading) return <div className="flex justify-center py-20"><div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Baterias</h1>
        <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
          <PlusIcon className="h-4 w-4" /> Nova Bateria
        </Button>
      </div>

      {error && <Alert variant="error" message={error} onClose={() => setError(null)} />}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="flex gap-3 rounded-lg border border-gray-200 bg-white p-4"
        >
          <Input
            label="Nome da bateria *"
            value={newHeatName}
            onChange={(e) => setNewHeatName(e.target.value)}
            required
            className="flex-1"
          />
          <div className="flex items-end gap-2">
            <Button type="submit">Criar</Button>
            <Button variant="outline" type="button" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}

      {heats.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <p className="text-gray-500">Nenhuma bateria cadastrada.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {heats.map((heat) => {
            const statusInfo = HEAT_STATUS_BADGE[heat.status] ?? { label: heat.status, variant: "gray" as const };
            return (
              <div key={heat.id} className="rounded-lg border border-gray-200 bg-white p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-gray-900">{heat.name}</p>
                    <p className="text-xs text-gray-500">{heat.team_count} equipe(s) · {heat.timer_count} timer(s)</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                    {heat.status === "pending" && (
                      <Button onClick={() => handleStart(heat.id)} className="text-sm">
                        ▶ Iniciar
                      </Button>
                    )}
                    {heat.status === "pending" && (
                      <button
                        onClick={() => handleDelete(heat.id)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Remover
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

> Nota: Verificar que `heatsApi.list(id)`, `heatsApi.create(id, payload)`, `heatsApi.delete(id, heatId)` e `heatsApi.start(id, heatId)` existem em `src/api/heats.ts`. Ajustar assinaturas conforme necessário.

- [ ] **Step 2: Commit**

```bash
git add src/pages/dashboard/HeatsPage.tsx
git commit -m "feat(frontend): HeatsPage integrada ao dashboard por competição"
```

---

## Task 15: Atualizar App.tsx com novas rotas

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layouts/MainLayout.tsx` (ajustar nav link Campeonatos)

- [ ] **Step 1: Substituir `src/App.tsx`**

```tsx
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/auth";
import { ToastProvider } from "./components/ui/ToastContext";

import AuthLayout from "./components/layouts/AuthLayout";
import MainLayout from "./components/layouts/MainLayout";
import ProtectedRoute from "./components/ProtectedRoute";

import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import DashboardPage from "./pages/DashboardPage";
import CompetitionsListPage from "./pages/CompetitionsListPage";
import CompetitionWizardPage from "./pages/CompetitionWizardPage";
import CompetitionDashboardLayout from "./pages/dashboard/CompetitionDashboardLayout";
import DashboardOverviewPage from "./pages/dashboard/DashboardOverviewPage";
import TeamsPage from "./pages/dashboard/TeamsPage";
import AthletesPage from "./pages/dashboard/AthletesPage";
import HeatsPage from "./pages/dashboard/HeatsPage";
import UsersPage from "./pages/UsersPage";
import TimersPage from "./pages/TimersPage";
import LivePage from "./pages/LivePage";
import RankingPage from "./pages/RankingPage";
import RegistrationPage from "./pages/RegistrationPage";
import NotFoundPage from "./pages/NotFoundPage";
import ProfilePage from "./pages/ProfilePage";
import AdminPage from "./pages/AdminPage";
import BulkActionsPage from "./pages/BulkActionsPage";

function AppLoader() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <svg
          className="h-8 w-8 animate-spin text-primary-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <p className="text-sm text-gray-400">Carregando...</p>
      </div>
    </div>
  );
}

export default function App() {
  const { initialize, isInitialized } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (!isInitialized) return <AppLoader />;

  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Rotas públicas */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
          </Route>

          {/* Ranking público */}
          <Route path="/ranking/:competitionId" element={<RankingPage />} />
          <Route path="/competitions/:competitionId/ranking" element={<RankingPage />} />

          {/* Dashboard do campeonato — layout próprio com sidebar */}
          <Route element={<ProtectedRoute allowedRoles={["judge", "operator", "admin"]} />}>
            <Route
              path="/competitions/:competitionId/dashboard"
              element={<CompetitionDashboardLayout />}
            >
              <Route index element={<DashboardOverviewPage />} />
              <Route path="equipes" element={<TeamsPage />} />
              <Route path="atletas" element={<AthletesPage />} />
              <Route path="baterias" element={<HeatsPage />} />
              {/* resultados virá na Fase 3 */}
            </Route>
          </Route>

          {/* Rotas protegidas com MainLayout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/ranking" element={<RankingPage />} />
              <Route path="/inscricao" element={<RegistrationPage />} />
              <Route path="/competitions/:competitionId/inscricao" element={<RegistrationPage />} />
              <Route path="/profile" element={<ProfilePage />} />

              {/* Timers legado */}
              <Route element={<ProtectedRoute allowedRoles={["judge", "operator", "admin"]} />}>
                <Route path="/timers" element={<TimersPage />} />
                <Route path="/competitions/:competitionId/timers" element={<TimersPage />} />
                <Route path="/competitions/:competitionId/live" element={<LivePage />} />
              </Route>

              {/* Gestão */}
              <Route element={<ProtectedRoute allowedRoles={["operator", "admin"]} />}>
                <Route path="/competitions" element={<CompetitionsListPage />} />
                <Route path="/competitions/new" element={<CompetitionWizardPage />} />
                <Route path="/competitions/:id/edit" element={<CompetitionWizardPage />} />
                <Route path="/users" element={<UsersPage />} />
              </Route>

              {/* Administração */}
              <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/admin/bulk" element={<BulkActionsPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
```

> **Atenção:** A rota `/competitions/new` deve ser registrada ANTES de `/competitions/:id/edit` no ProtectedRoute de operator/admin. O React Router v6 resolve por ordem de declaração dentro de `<Routes>` — verificar que "new" não é interpretado como `:id`.
> 
> Se houver conflito, mover `/competitions/new` e `/competitions/:id/edit` para fora do `ProtectedRoute allowedRoles` wrapper mas ainda dentro do `ProtectedRoute` base (todos os roles), já que o backend protege as APIs.

- [ ] **Step 2: Verificar build**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```
Corrigir quaisquer erros de tipo antes de continuar.

- [ ] **Step 3: Iniciar o servidor e testar**

```bash
# Terminal 1 — backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Testar fluxo completo:
1. Login como admin → `/competitions` → tabela aparece
2. Clicar "+ Novo Campeonato" → wizard abre
3. Preencher Etapa 1 (nome "Hyrox Teste", tipo "Hyrox"), avançar → Etapa 2 (placeholder), avançar → Etapa 3 (placeholder), avançar → Etapa 4 (Menor Tempo), avançar → Etapa 5 (resumo)
4. Clicar "Criar Campeonato" → redireciona para `/competitions/{id}/dashboard`
5. Dashboard abre com sidebar escura: visão geral com métricas
6. Clicar "Equipes" na sidebar → TeamsPage carrega
7. Clicar "Atletas" na sidebar → AthletesPage carrega
8. Clicar "Baterias" na sidebar → HeatsPage carrega
9. Clicar "← Campeonatos" → volta para CompetitionsListPage

- [ ] **Step 4: Commit final**

```bash
git add src/App.tsx
git commit -m "feat(frontend): conecta rotas do dashboard, wizard e lista de campeonatos"
```

---

## Task 16: Executar suite de testes completa e ajustar navegação

- [ ] **Step 1: Executar backend completo**

```bash
cd backend && python -m pytest -v --tb=short 2>&1 | tail -30
```
Esperado: todos PASS. Qualquer falha deve ser investigada antes de continuar.

- [ ] **Step 2: Verificar cobertura**

```bash
cd backend && python -m pytest --cov=app --cov-report=term-missing 2>&1 | tail -20
```
Esperado: cobertura ≥ 80%.

- [ ] **Step 3: Remover `modalities` do `main.py` se não há mais uso ativo**

> Opcional: o router de modalidades ainda funciona mas não tem UI ativa. Pode ser mantido para não quebrar histórico de endpoints, ou removido se Vitor confirmar que não é mais necessário.

- [ ] **Step 4: Commit de fechamento da Fase 1**

```bash
git add -A
git commit -m "feat: redesenho fase 1 — competition + category refactor, athletes CRUD, CEP proxy, wizard + dashboard frontend"
```

---

## Self-Review — Cobertura da Spec

| Requisito da Spec | Task Correspondente | Status |
|---|---|---|
| Competition: rename event_date → start_date | Task 1-2 | ✅ |
| Competition: add end_date, event_type, is_public, scoring_model, tiebreak_criterion | Task 1-2 | ✅ |
| Competition: remove modality_id, duration_seconds, max_athletes, rules | Task 1-2 | ✅ |
| Category: add gender, age_restriction_enabled, age_min, age_max | Task 4 | ✅ |
| Athlete: novo modelo com CRUD | Task 5 | ✅ |
| Athletes: CSV import | Task 5 | ✅ |
| Athletes: filtro por category_id, team_id | Task 5 | ✅ |
| CEP proxy endpoint | Task 6 | ✅ |
| Migration competition_core_fields | Task 7 | ✅ |
| Migration category_gender_age | Task 7 | ✅ |
| Migration athletes_table | Task 7 | ✅ |
| Frontend: CompetitionsListPage (tabela + dropdown ações) | Task 9 | ✅ |
| Frontend: CompetitionWizardPage etapas 1, 4, 5 | Task 10 | ✅ |
| Frontend: CEP lookup com auto-preenchimento | Task 10 | ✅ |
| Frontend: CompetitionDashboardLayout sidebar escura | Task 11 | ✅ |
| Frontend: DashboardOverviewPage (métricas) | Task 11 | ✅ |
| Frontend: TeamsPage no dashboard | Task 12 | ✅ |
| Frontend: AthletesPage (novo) | Task 13 | ✅ |
| Frontend: HeatsPage migrado para dashboard | Task 14 | ✅ |
| Frontend: atualização de rotas | Task 15 | ✅ |
| Segurança: athletes CRUD requer operator/admin | Task 5 | ✅ |
| Segurança: leaderboard público (não afetado nesta fase) | N/A | — |

**Gaps identificados:**
- Leaderboard público: Fase 3
- Wizard etapa 2 (Divulgação/PDFs): Fase 2
- Wizard etapa 3 (WODs): Fase 3
- ResultsPage: Fase 3

**Fases futuras:**
- `docs/superpowers/plans/2026-06-15-redesign-fase2.md` — PDF upload, organizer, divulgação
- `docs/superpowers/plans/2026-06-15-redesign-fase3.md` — WODs, pontuação CrossFit, leaderboard público

---

## Notas Críticas para o Executor

1. **Ordem das Tasks:** Tasks 1–4 (backend) devem ser concluídas antes das Tasks 8–15 (frontend) para garantir que os endpoints novos existem quando o frontend é testado.

2. **Testes com SQLite :memory:** A `Base.metadata.create_all` cria o schema a partir dos modelos ORM atuais. Não é necessário rodar migrations para os testes passarem. Migrations são apenas para o banco real.

3. **`modality_rel` removido:** Qualquer import de `Competition.modality_rel` em outros arquivos quebrará. Buscar com `grep -r "modality_rel" backend/app/` após a Task 1 para confirmar que nenhum arquivo ficou referenciando o atributo removido.

4. **Relacionamento `Category.athletes`:** Adicionado na Task 4 Step 3. O `Team.athletes` é adicionado na Task 5 Step 4. Ambos devem ser adicionados antes de rodar os testes de atletas.

5. **Frontend rota `/competitions/new` vs `/:id/edit`:** O React Router v6 não distingue por pattern mais específico — resolve por ordem de declaração. `/competitions/new` declarado antes de `/competitions/:id/edit` garante que "new" não vira um `id`.

6. **`apiClient` pode retornar `AxiosResponse<T>` ou `T`:** Verificar `src/api/client.ts` para saber se os métodos retornam `AxiosResponse` (precisar de `.data`) ou diretamente os dados. O código dos componentes já usa `const d = res.data ?? res` para lidar com ambos.
