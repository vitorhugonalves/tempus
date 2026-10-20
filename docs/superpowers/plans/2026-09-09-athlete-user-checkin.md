# Unificação Atleta↔User via Check-in — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar a um operador de check-in presencial uma forma única de encontrar "a pessoa"
(seja ela um `Athlete` importado em massa ou um `User` auto-inscrito via
`CompetitorRegistration`) e garantir que sempre exista um registro `Athlete`
correspondente, pronto para receber uma pulseira RFID no dia do evento.

**Architecture:** Um serviço de busca que cruza `Athlete` e `CompetitorRegistration`/`User`
de uma competição, e uma operação idempotente "garantir atleta" que cria o `Athlete`
faltante (vinculado via novo `Athlete.user_id`) quando a pessoa só existe como inscrição
online. Nenhuma mudança nos fluxos de cadastro em massa ou auto-inscrição existentes —
isso é uma camada de reconciliação por cima dos dois.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, pytest + httpx.AsyncClient, React/TS.

**Spec:** `docs/superpowers/specs/2026-09-08-rfid-stations-design.md` (seção 3)

**Depends on:** `docs/superpowers/plans/2026-09-09-athlete-team-foundation.md` (todo
`Athlete` já tem `team_id` obrigatório antes deste plano rodar).

## Global Constraints

- `flush()` em repositories, nunca `commit()`.
- Toda alteração de schema via migration Alembic revisável, com `downgrade()`.
- Type hints obrigatórios; docstrings Google Style em services/repositories.
- Rodar `pytest` e `ruff check`/`ruff format` sem perguntar; parar e perguntar se algo falhar.
- Commits atômicos, mensagem `módulo: o que foi feito`.

---

## Contexto para quem for implementar

Hoje existem dois jeitos de uma pessoa "existir" numa competição, sem relação entre si:

1. **`Athlete`** (`app/models/athlete.py`) — importado em massa via CSV ou cadastrado à
   mão, sem login. Depois do plano de fundação, sempre tem `team_id`.
2. **`User` + `CompetitorRegistration` + `TeamMember`** — auto-inscrição online
   (`app/services/registration.py::RegistrationService.register`), com conta e senha.

Este plano adiciona `Athlete.user_id` (nullable) como ponte: quando alguém se auto-inscreve
e chega no check-in presencial, o operador busca pelo nome/e-mail, e se só existir o
`CompetitorRegistration` (sem `Athlete` ainda), o sistema cria o `Athlete` na hora,
reaproveitando a equipe (`Team`) que a auto-inscrição já criou via `TeamMember`.

Isso NÃO cria uma segunda equipe — o `Athlete` novo aponta pro mesmo `team_id` que o
`User` já tem via `TeamMember.team_id`.

---

## File Structure

- Create: `backend/app/db/migrations/versions/20260909_athlete_user_link.py`
- Modify: `backend/app/models/athlete.py` — campo `user_id`
- Create: `backend/app/repositories/competitor_registration.py`
- Create: `backend/app/schemas/checkin.py`
- Create: `backend/app/services/checkin.py`
- Create: `backend/app/api/v1/checkin.py`
- Modify: `backend/app/main.py` — registrar o novo router
- Create: `backend/tests/integration/test_checkin.py`
- Create: `frontend/src/api/checkin.ts`
- Create: `frontend/src/pages/dashboard/CheckinPage.tsx`
- Modify: `frontend/src/pages/dashboard/CompetitionDashboardLayout.tsx` — link de navegação
- Modify: `frontend/src/App.tsx` — rota nova

---

## Task 1: `Athlete.user_id` — ponte opcional pra `User`

**Files:**
- Create: `backend/app/db/migrations/versions/20260909_athlete_user_link.py`
- Modify: `backend/app/models/athlete.py`

**Interfaces:**
- Produces: `Athlete.user_id: int | None`, relacionamento `Athlete.user`.

- [ ] **Step 1: Migration**

```python
# backend/app/db/migrations/versions/20260909_athlete_user_link.py
"""athlete user_id — bridge to self-registered User accounts

Revision ID: 20260909_athlete_user_link
Revises: 20260909_athlete_team_required
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "20260909_athlete_user_link"
down_revision = "20260909_athlete_team_required"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_athletes_user_id", ["user_id"])
        batch_op.create_unique_constraint(
            "uq_athlete_user_per_competition", ["competition_id", "user_id"]
        )
        batch_op.create_foreign_key(
            "fk_athletes_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.drop_constraint("fk_athletes_user_id", type_="foreignkey")
        batch_op.drop_constraint("uq_athlete_user_per_competition", type_="unique")
        batch_op.drop_index("ix_athletes_user_id")
        batch_op.drop_column("user_id")
```

> `UniqueConstraint(competition_id, user_id)` permite `user_id IS NULL` múltiplas vezes
> (SQL padrão trata NULL como distinto em constraints únicas) — só impede o mesmo `User`
> virar dois `Athlete` na mesma competição.

- [ ] **Step 2: Atualizar o modelo**

```python
# backend/app/models/athlete.py — adicionar após team_id (linha ~35)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
```

```python
# backend/app/models/athlete.py — adicionar aos relationships, junto com team/category
    user: Mapped["User | None"] = relationship("User")  # noqa: F821
```

Adicionar `UniqueConstraint("competition_id", "user_id", name="uq_athlete_user_per_competition")`
em `__table_args__` da classe `Athlete` (a classe hoje não tem `__table_args__` — criar).

- [ ] **Step 3: Rodar migration e verificar**

```bash
cd backend && .venv/bin/alembic upgrade head
sqlite3 tempus.db "SELECT sql FROM sqlite_master WHERE name='athletes';"
```

Esperado: coluna `user_id INTEGER` e constraint única aparecem na definição da tabela.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/migrations/versions/20260909_athlete_user_link.py backend/app/models/athlete.py
git commit -m "db(athletes): adiciona user_id como ponte opcional para User auto-inscrito"
```

---

## Task 2: Repositório de `CompetitorRegistration` (consulta pro check-in)

**Files:**
- Create: `backend/app/repositories/competitor_registration.py`
- Test: `backend/tests/integration/test_checkin.py` (via serviço na Task 3 — este repo não tem teste unitário isolado, é exercitado pelos testes de integração do check-in)

**Interfaces:**
- Produces: `CompetitorRegistrationRepository.search(db, competition_id, query) -> list[CompetitorRegistration]` (com `.user` carregado), `CompetitorRegistrationRepository.get_by_id(db, registration_id) -> CompetitorRegistration | None` (com `.user`, `.category`).

- [ ] **Step 1: Implementar**

```python
# backend/app/repositories/competitor_registration.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.competitor import CompetitorRegistration
from app.models.user import User


class CompetitorRegistrationRepository:
    """Acesso ao banco para inscrições de competidores autoinscritos."""

    @staticmethod
    async def search(
        db: AsyncSession, competition_id: int, query: str
    ) -> list[CompetitorRegistration]:
        """Busca inscrições de uma competição por nome ou e-mail do usuário.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            query: Termo de busca (case-insensitive, aplicado a nome e e-mail).

        Returns:
            Lista de CompetitorRegistration com `.user` carregado.
        """
        like = f"%{query.lower()}%"
        result = await db.execute(
            select(CompetitorRegistration)
            .join(User)
            .options(selectinload(CompetitorRegistration.user))
            .where(
                CompetitorRegistration.competition_id == competition_id,
                (User.full_name.ilike(like)) | (User.email.ilike(like)),
            )
            .order_by(User.full_name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, registration_id: int) -> CompetitorRegistration | None:
        """Busca uma inscrição pelo ID, com usuário carregado.

        Args:
            db: Sessão assíncrona.
            registration_id: ID da inscrição.

        Returns:
            CompetitorRegistration ou None.
        """
        result = await db.execute(
            select(CompetitorRegistration)
            .options(selectinload(CompetitorRegistration.user))
            .where(CompetitorRegistration.id == registration_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 2: Commit (junto com a Task 3, que é quem exercita este código pela primeira vez — não faça commit isolado aqui, siga direto pro próximo task)**

---

## Task 3: `CheckinService` — buscar e garantir atleta

**Files:**
- Create: `backend/app/schemas/checkin.py`
- Create: `backend/app/services/checkin.py`
- Test: `backend/tests/integration/test_checkin.py`

**Interfaces:**
- Consumes: `CompetitorRegistrationRepository.search`/`get_by_id` (Task 2), `AthleteRepository.list_by_competition`/`create` (`app/repositories/athlete.py`), `TeamRepository.get_member_in_competition` (`app/repositories/team.py:124`, reaproveitado pra achar o `team_id` do `TeamMember` do usuário).
- Produces: `CheckinService.search(db, competition_id, query) -> list[CheckinCandidate]`, `CheckinService.ensure_athlete(db, competition_id, candidate: CheckinEnsureRequest) -> Athlete`.

- [ ] **Step 1: Schemas**

```python
# backend/app/schemas/checkin.py
from pydantic import BaseModel, Field


class CheckinCandidate(BaseModel):
    """Um resultado de busca de check-in — já é Athlete, ou só CompetitorRegistration."""

    kind: str  # "athlete" | "registration"
    source_id: int  # athlete.id ou registration.id, conforme `kind`
    name: str
    email: str | None
    team_name: str | None
    has_athlete_record: bool


class CheckinEnsureRequest(BaseModel):
    kind: str = Field(..., pattern="^(athlete|registration)$")
    source_id: int
```

- [ ] **Step 2: Escrever o teste que falha — busca cruzada e garantia de atleta**

```python
# backend/tests/integration/test_checkin.py
"""Testes de integração para o fluxo de check-in (unificação Athlete/User)."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryType
from app.models.competition import Competition, CompetitionStatus


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Checkin", status=CompetitionStatus.active)
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id, name="Elite", category_type=CategoryType.individual
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def test_busca_encontra_atleta_importado_em_massa(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Carlos Bulk", "category_id": category.id},
        cookies={"session_id": admin_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search?q=Carlos",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["kind"] == "athlete"
    assert results[0]["has_athlete_record"] is True


async def test_busca_encontra_inscricao_online_sem_atleta_ainda(
    client: AsyncClient, admin_token: str, competitor_token: str,
    competition: Competition, category: Category,
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search?q=Competidor",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["kind"] == "registration"
    assert results[0]["has_athlete_record"] is False


async def test_ensure_athlete_cria_atleta_a_partir_de_inscricao_online(
    client: AsyncClient, admin_token: str, competitor_token: str,
    competition: Competition, category: Category, db: AsyncSession,
):
    from sqlalchemy import select
    from app.models.competitor import CompetitorRegistration

    reg_r = await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )
    team_id = reg_r.json()["team_id"]

    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.competition_id == competition.id
        )
    )
    registration = result.scalar_one()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["team_id"] == team_id
    assert data["name"] == "Competidor Teste"

    # Idempotente: chamar de novo não cria um segundo Athlete
    r2 = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]


async def test_ensure_athlete_com_kind_athlete_retorna_o_proprio(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Ja Existe", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "athlete", "source_id": athlete_id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json()["id"] == athlete_id
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
cd backend && .venv/bin/pytest tests/integration/test_checkin.py -v
```

Esperado: FAIL — `/checkin/search` e `/checkin/ensure` ainda não existem (404).

- [ ] **Step 4: Implementar `CheckinService`**

```python
# backend/app/services/checkin.py
"""Serviço de check-in — unifica Athlete (import em massa) e CompetitorRegistration
(auto-inscrição online) num único ponto de busca e garante que a pessoa tenha um
registro Athlete antes do credenciamento físico (pareamento de tag RFID)."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.repositories.athlete import AthleteRepository
from app.repositories.competitor_registration import CompetitorRegistrationRepository
from app.repositories.team import TeamRepository
from app.schemas.checkin import CheckinCandidate, CheckinEnsureRequest


class CheckinService:
    """Regras de negócio para o check-in presencial de atletas."""

    @staticmethod
    async def search(
        db: AsyncSession, competition_id: int, query: str
    ) -> list[CheckinCandidate]:
        """Busca candidatos ao check-in cruzando Athlete e CompetitorRegistration.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            query: Termo de busca (nome ou e-mail).

        Returns:
            Lista de CheckinCandidate — atletas já existentes e inscrições online
            sem Athlete correspondente ainda.
        """
        athletes = await AthleteRepository.list_by_competition(db, competition_id)
        matched_athletes = [
            a for a in athletes if query.lower() in a.name.lower()
            or (a.email and query.lower() in a.email.lower())
        ]
        linked_user_ids = {a.user_id for a in athletes if a.user_id is not None}

        registrations = await CompetitorRegistrationRepository.search(
            db, competition_id, query
        )

        candidates = [
            CheckinCandidate(
                kind="athlete",
                source_id=a.id,
                name=a.name,
                email=a.email,
                team_name=a.team.name if a.team else None,
                has_athlete_record=True,
            )
            for a in matched_athletes
        ]
        for reg in registrations:
            if reg.user_id in linked_user_ids:
                continue  # já tem Athlete vinculado — evita duplicar na lista
            candidates.append(
                CheckinCandidate(
                    kind="registration",
                    source_id=reg.id,
                    name=reg.user.full_name,
                    email=reg.user.email,
                    team_name=None,
                    has_athlete_record=False,
                )
            )
        return candidates

    @staticmethod
    async def ensure_athlete(
        db: AsyncSession, competition_id: int, data: CheckinEnsureRequest
    ) -> Athlete:
        """Garante que existe um Athlete para o candidato — cria se necessário.

        Idempotente: se o CompetitorRegistration já tiver um Athlete vinculado
        (mesmo user_id na competição), retorna o existente em vez de duplicar.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            data: kind ("athlete" ou "registration") + source_id.

        Returns:
            Athlete garantido (existente ou recém-criado).

        Raises:
            HTTPException 404: fonte não encontrada nesta competição.
            HTTPException 422: inscrição sem equipe (não deveria acontecer, dado que
                toda auto-inscrição cria equipe — guarda defensiva).
        """
        if data.kind == "athlete":
            athlete = await AthleteRepository.get_by_id(db, data.source_id)
            if not athlete or athlete.competition_id != competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Atleta não encontrado"
                )
            return athlete

        registration = await CompetitorRegistrationRepository.get_by_id(db, data.source_id)
        if not registration or registration.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Inscrição não encontrada"
            )

        existing = await AthleteRepository.list_by_competition(db, competition_id)
        already = next((a for a in existing if a.user_id == registration.user_id), None)
        if already:
            return already

        team_member = await TeamRepository.get_member_in_competition(
            db, competition_id, registration.user_id
        )
        if not team_member:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Inscrição sem equipe vinculada — não é possível criar o atleta",
            )

        new_athlete = Athlete(
            competition_id=competition_id,
            category_id=registration.category_id,
            team_id=team_member.team_id,
            user_id=registration.user_id,
            name=registration.user.full_name,
            email=registration.user.email,
            document=registration.document,
        )
        return await AthleteRepository.create(db, new_athlete)
```

- [ ] **Step 5: Rotas**

```python
# backend/app/api/v1/checkin.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.checkin import CheckinCandidate, CheckinEnsureRequest
from app.services.athlete import AthleteService
from app.services.checkin import CheckinService

router = APIRouter()


@router.get(
    "/competitions/{competition_id}/checkin/search",
    response_model=list[CheckinCandidate],
)
async def search_checkin_candidates(
    competition_id: int,
    q: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> list[CheckinCandidate]:
    """Busca candidatos ao check-in por nome/e-mail (Operador/Admin)."""
    return await CheckinService.search(db, competition_id, q)


@router.post(
    "/competitions/{competition_id}/checkin/ensure",
)
async def ensure_checkin_athlete(
    competition_id: int,
    payload: CheckinEnsureRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
):
    """Garante o registro Athlete do candidato, criando se necessário (Operador/Admin)."""
    from app.api.v1.athletes import _to_response

    athlete = await CheckinService.ensure_athlete(db, competition_id, payload)
    return _to_response(athlete)
```

> Reaproveita `_to_response` de `app/api/v1/athletes.py` (função módulo, já pública o
> suficiente dentro do pacote) em vez de duplicar a serialização — import local pra evitar
> dependência circular no topo do módulo.

- [ ] **Step 6: Registrar o router em `main.py`**

```python
# backend/app/main.py — junto aos outros app.include_router(...)
from app.api.v1 import checkin as checkin_router
app.include_router(checkin_router.router, prefix="/api/v1", tags=["checkin"])
```

(Ajuste o nome exato da variável/import pra combinar com o padrão dos outros routers já
registrados em `main.py` — copie a linha de import e include de `athletes` como modelo.)

- [ ] **Step 7: Rodar os testes**

```bash
cd backend && .venv/bin/pytest tests/integration/test_checkin.py -v
```

Esperado: todos passam.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/checkin.py backend/app/services/checkin.py \
        backend/app/repositories/competitor_registration.py backend/app/api/v1/checkin.py \
        backend/app/main.py backend/tests/integration/test_checkin.py
git commit -m "feat(checkin): unifica busca de Athlete e CompetitorRegistration"
```

---

## Task 4: Frontend — tela de check-in

**Files:**
- Create: `frontend/src/api/checkin.ts`
- Create: `frontend/src/pages/dashboard/CheckinPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/dashboard/CompetitionDashboardLayout.tsx`
- Modify: `frontend/src/types/index.ts`

**Interfaces:**
- Consumes: `GET /competitions/{id}/checkin/search?q=`, `POST /competitions/{id}/checkin/ensure` (Task 3).

- [ ] **Step 1: Tipos**

```typescript
// frontend/src/types/index.ts — adicionar

export interface CheckinCandidate {
  kind: "athlete" | "registration";
  source_id: number;
  name: string;
  email: string | null;
  team_name: string | null;
  has_athlete_record: boolean;
}
```

- [ ] **Step 2: Cliente de API**

```typescript
// frontend/src/api/checkin.ts
import apiClient from "./client";
import type { Athlete, CheckinCandidate } from "../types";

export const checkinApi = {
  search: (competitionId: number, q: string) =>
    apiClient
      .get<CheckinCandidate[]>(`/api/v1/competitions/${competitionId}/checkin/search`, {
        params: { q },
      })
      .then((r) => r.data),

  ensure: (competitionId: number, kind: "athlete" | "registration", sourceId: number) =>
    apiClient
      .post<Athlete>(`/api/v1/competitions/${competitionId}/checkin/ensure`, {
        kind,
        source_id: sourceId,
      })
      .then((r) => r.data),
};
```

- [ ] **Step 3: Página**

```tsx
// frontend/src/pages/dashboard/CheckinPage.tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { checkinApi } from "../../api/checkin";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import type { Athlete, CheckinCandidate } from "../../types";

export default function CheckinPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CheckinCandidate[]>([]);
  const [checkedIn, setCheckedIn] = useState<Athlete | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setError(null);
    setCheckedIn(null);
    setSearching(true);
    try {
      const data = await checkinApi.search(id, query.trim());
      setResults(data);
    } catch {
      setError("Erro ao buscar");
    } finally {
      setSearching(false);
    }
  }

  async function handleEnsure(candidate: CheckinCandidate) {
    setError(null);
    try {
      const athlete = await checkinApi.ensure(id, candidate.kind, candidate.source_id);
      setCheckedIn(athlete);
      setResults([]);
      setQuery("");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao confirmar check-in");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Check-in</h1>

      {error && <Alert variant="error">{error}</Alert>}
      {checkedIn && (
        <Alert variant="success">
          Check-in confirmado: <strong>{checkedIn.name}</strong> — equipe{" "}
          {checkedIn.team_name}. Prossiga para o pareamento de tag.
        </Alert>
      )}

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          placeholder="Buscar por nome ou e-mail..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" disabled={searching}>Buscar</Button>
      </form>

      <div className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
        {results.length === 0 ? (
          <p className="p-6 text-center text-sm text-gray-500">
            {searching ? "Buscando..." : "Nenhum resultado ainda."}
          </p>
        ) : (
          results.map((c) => (
            <div key={`${c.kind}-${c.source_id}`} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium text-gray-900">{c.name}</p>
                <p className="text-xs text-gray-500">
                  {c.email ?? "—"} ·{" "}
                  {c.kind === "athlete"
                    ? `Equipe ${c.team_name ?? "—"}`
                    : "Inscrito online — sem check-in ainda"}
                </p>
              </div>
              <Button onClick={() => handleEnsure(c)} className="text-sm">
                {c.has_athlete_record ? "Selecionar" : "Confirmar check-in"}
              </Button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

> O pareamento de tag em si (campo de `tag_code`) entra no plano de RFID (Task 17 daquele
> plano) — esta tela já fica pronta pra receber esse bloco extra sem reestruturação, dado
> que `checkedIn` guarda o `Athlete` resultante.

- [ ] **Step 4: Rota e navegação**

```tsx
// frontend/src/App.tsx — junto às outras rotas do dashboard de competição
import CheckinPage from "./pages/dashboard/CheckinPage";
// ...
<Route path="checkin" element={<CheckinPage />} />
```

```tsx
// frontend/src/pages/dashboard/CompetitionDashboardLayout.tsx — adicionar item de nav
// junto aos links existentes (Atletas, Equipes, Baterias, ...):
{ to: "checkin", label: "Check-in" },
```

(Ajuste a chave exata do array/objeto de navegação conforme a estrutura já usada no
arquivo — copie o padrão do item "Atletas" existente.)

- [ ] **Step 5: Testar manualmente**

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload &
cd frontend && npm run dev
```

Criar um atleta via import em massa e um competidor via auto-inscrição na mesma
competição; buscar cada um pelo nome na tela de Check-in; confirmar que o de import em
massa aparece como "Selecionar" (já tem registro) e o auto-inscrito aparece como
"Confirmar check-in" (cria o registro na hora).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/checkin.ts frontend/src/pages/dashboard/CheckinPage.tsx \
        frontend/src/App.tsx frontend/src/pages/dashboard/CompetitionDashboardLayout.tsx \
        frontend/src/types/index.ts
git commit -m "feat(checkin): tela de check-in unificando atleta e inscrição online"
```

---

## Self-Review

- **Cobertura do spec (seção 3):** busca cruzada ✓ (Task 3), criação lazy de `Athlete` a
  partir de `CompetitorRegistration` no check-in ✓ (Task 3), reaproveita `team_id` já
  existente do `TeamMember` em vez de criar equipe nova ✓ (Task 3 `ensure_athlete`).
- **Placeholders:** nenhum. O comentário sobre "pareamento de tag entra no plano de RFID"
  é uma nota de escopo, não um placeholder de código — nenhum código incompleto foi deixado.
- **Consistência de tipos:** `CheckinCandidate`/`CheckinEnsureRequest` definidos na Task 3
  e usados sem alteração de forma na Task 4 (frontend). `Athlete` retornado por
  `ensure_athlete` é o mesmo tipo ORM que `AthleteRepository.create` já retorna em outros
  fluxos — serializado pela mesma `_to_response` já testada em `test_athletes.py`.

## Execution Handoff

Plano completo e salvo em `docs/superpowers/plans/2026-09-09-athlete-user-checkin.md`.
