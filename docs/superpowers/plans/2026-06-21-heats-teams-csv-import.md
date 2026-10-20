# Baterias-Equipes + CSV Atletas e Equipes — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir o bug de adicionar equipes a baterias e implementar duas melhorias de importação CSV (atletas e equipes).

**Architecture:** Três áreas independentes: (1) UI frontend para vincular equipes a baterias usando endpoints já existentes no backend; (2) mudança de separador e nova coluna `equipe` no CSV de atletas (backend + frontend); (3) novo endpoint de importação CSV de equipes com botão na TeamsPage.

**Tech Stack:** FastAPI (Python 3.12), SQLAlchemy 2.x async, Pydantic v2, React 18 + TypeScript, TailwindCSS

## Global Constraints

- Separador de CSV: ponto-e-vírgula (`;`) para todos os CSVs neste escopo
- `flush()` em repositories — nunca `commit()` dentro de services/repositories de request
- Roles backend: `operator` e `admin` para endpoints de escrita; `judge` pode listar
- Testes backend: pytest + pytest-asyncio, SQLite :memory:, httpx.AsyncClient com `cookies={"session_id": admin_token}`
- Sem CSS-in-JS: apenas TailwindCSS
- Pydantic v2: usar `model_config = {"from_attributes": True}` em schemas de resposta

---

## File Map

| Arquivo | Ação |
|---|---|
| `frontend/src/pages/dashboard/HeatsPage.tsx` | Modificar — painel expansível + add/remove teams |
| `frontend/src/pages/dashboard/AthletesPage.tsx` | Modificar — disclaimer CSV |
| `frontend/src/pages/dashboard/TeamsPage.tsx` | Modificar — botão CSV + disclaimer |
| `frontend/src/api/teams.ts` | Modificar — adicionar `importCsv` |
| `frontend/src/types/index.ts` | Modificar — adicionar `TeamBulkResult`, `TeamBulkError` |
| `backend/app/services/athlete.py` | Modificar — separador `;` + coluna `equipe` |
| `backend/app/schemas/team.py` | Modificar — adicionar `TeamBulkResult`, `TeamBulkError` |
| `backend/app/services/team.py` | Modificar — adicionar `import_csv` |
| `backend/app/api/v1/competitions.py` | Modificar — novo endpoint `POST /teams/import` |
| `backend/tests/integration/test_athletes.py` | Modificar — atualizar testes para novo separador + testar coluna `equipe` |
| `backend/tests/integration/test_teams_import.py` | Criar — testes para importação CSV de equipes |

---

### Task 1: HeatsPage — painel expansível para gerenciar equipes

**Files:**
- Modify: `frontend/src/pages/dashboard/HeatsPage.tsx`

**Interfaces:**
- Consumes: `heatsApi.addTeam(competitionId, heatId, teamId): Promise<Heat>` (já existe em `api/heats.ts:37`), `heatsApi.removeTeam(competitionId, heatId, teamId)` (já existe em `api/heats.ts:45`), `teamsApi.list(competitionId): Promise<Team[]>` (já existe em `api/teams.ts:16`)
- Produces: UI funcional — clicar em "Gerenciar Equipes" expande o card, exibe equipes vinculadas com botão de remoção e select para adicionar novas

- [ ] **Step 1: Substituir o conteúdo de `frontend/src/pages/dashboard/HeatsPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { PlusIcon } from "@heroicons/react/24/outline";
import { heatsApi, type HeatCreate } from "../../api/heats";
import { teamsApi } from "../../api/teams";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import Badge from "../../components/ui/Badge";
import type { Competition, Heat, Team } from "../../types";

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
  useOutletContext<OutletCtx>();
  const id = Number(competitionId);

  const [heats, setHeats] = useState<Heat[]>([]);
  const [allTeams, setAllTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newHeatName, setNewHeatName] = useState("");
  const [expandedHeatId, setExpandedHeatId] = useState<number | null>(null);
  const [selectedTeam, setSelectedTeam] = useState<Record<number, string>>({});

  useEffect(() => {
    Promise.all([heatsApi.list(id), teamsApi.list(id)])
      .then(([h, t]) => {
        setHeats(h);
        setAllTeams(t);
      })
      .catch(() => setError("Erro ao carregar dados"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const payload: HeatCreate = { name: newHeatName };
      const heat = await heatsApi.create(id, payload);
      setHeats((p) => [...p, heat]);
      setNewHeatName("");
      setShowForm(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao criar bateria");
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
      const updated = await heatsApi.start(id, heatId);
      setHeats((p) => p.map((h) => (h.id === heatId ? updated : h)));
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao iniciar bateria");
    }
  }

  async function handleAddTeam(heatId: number) {
    const teamId = Number(selectedTeam[heatId]);
    if (!teamId) return;
    setError(null);
    try {
      const updated = await heatsApi.addTeam(id, heatId, teamId);
      setHeats((p) => p.map((h) => (h.id === heatId ? updated : h)));
      setSelectedTeam((p) => ({ ...p, [heatId]: "" }));
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao adicionar equipe");
    }
  }

  async function handleRemoveTeam(heatId: number, teamId: number) {
    setError(null);
    try {
      await heatsApi.removeTeam(id, heatId, teamId);
      setHeats((p) =>
        p.map((h) =>
          h.id === heatId
            ? { ...h, teams: h.teams.filter((t) => t.team_id !== teamId), team_count: h.team_count - 1 }
            : h
        )
      );
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao remover equipe");
    }
  }

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Baterias</h1>
        <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
          <PlusIcon className="h-4 w-4" /> Nova Bateria
        </Button>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

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
            <Button variant="secondary" type="button" onClick={() => setShowForm(false)}>
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
            const isExpanded = expandedHeatId === heat.id;
            const availableTeams = allTeams.filter(
              (t) => !heat.teams.some((ht) => ht.team_id === t.id)
            );
            return (
              <div key={heat.id} className="rounded-lg border border-gray-200 bg-white p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-gray-900">{heat.name}</p>
                    <p className="text-xs text-gray-500">
                      {heat.team_count} equipe(s) · {heat.timer_count} timer(s)
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                    {heat.status === "pending" && (
                      <button
                        onClick={() =>
                          setExpandedHeatId((prev) => (prev === heat.id ? null : heat.id))
                        }
                        className="text-sm font-medium text-primary-600 hover:text-primary-800"
                      >
                        {isExpanded ? "Fechar" : "Gerenciar Equipes"}
                      </button>
                    )}
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

                {isExpanded && (
                  <div className="mt-4 space-y-3 border-t border-gray-100 pt-4">
                    <p className="text-xs font-medium uppercase text-gray-500">
                      Equipes na bateria
                    </p>
                    {heat.teams.length === 0 ? (
                      <p className="text-sm text-gray-400">Nenhuma equipe vinculada.</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {heat.teams.map((ht) => (
                          <span
                            key={ht.team_id}
                            className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-3 py-1 text-sm font-medium text-primary-700"
                          >
                            {ht.team_name}
                            <button
                              onClick={() => handleRemoveTeam(heat.id, ht.team_id)}
                              className="ml-1 text-primary-400 hover:text-red-500"
                              title="Remover equipe da bateria"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2 items-center pt-1">
                      <select
                        className="flex-1 rounded-md border-gray-300 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
                        value={selectedTeam[heat.id] ?? ""}
                        onChange={(e) =>
                          setSelectedTeam((p) => ({ ...p, [heat.id]: e.target.value }))
                        }
                      >
                        <option value="">Selecione uma equipe...</option>
                        {availableTeams.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                      <Button
                        onClick={() => handleAddTeam(heat.id)}
                        disabled={!selectedTeam[heat.id]}
                        className="text-sm"
                      >
                        Adicionar
                      </Button>
                    </div>
                    {availableTeams.length === 0 && (
                      <p className="text-xs text-gray-400">
                        Todas as equipes já estão nesta bateria.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verificar que o TypeScript compila sem erros**

```bash
cd /home/vitoralves/projects/tempus/frontend && npx tsc --noEmit 2>&1 | head -30
```

Esperado: nenhuma saída (sem erros de tipo).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/dashboard/HeatsPage.tsx
git commit -m "fix(heats): adicionar painel expansível para gerenciar equipes em baterias"
```

---

### Task 2: Backend — CSV de atletas: separador `;` + coluna `equipe`

**Files:**
- Modify: `backend/app/services/athlete.py`
- Modify: `backend/tests/integration/test_athletes.py`

**Interfaces:**
- Consumes: `TeamRepository.get_by_competition(db, competition_id): list[Team]` (já existe em `repositories/team.py:30`), `Category` list passada pelo caller
- Produces: `AthleteService.import_csv(db, competition_id, content, categories)` com novo separador `;`, nova coluna `equipe` com auto-criação de equipe

- [ ] **Step 1: Atualizar testes existentes para usar o novo separador `;`**

Em `backend/tests/integration/test_athletes.py`, localizar a função `test_importar_atletas_csv_retorna_200` (linha ~162) e substituir:

```python
async def test_importar_atletas_csv_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome;email;documento;telefone;categoria;tamanho_camiseta\n"
        f"Pedro Alves;pedro@example.com;123.456.789-00;(11)91111-2222;{category.name};M\n"
        "Rita Souza;;;;;"
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
```

E substituir `test_importar_atletas_csv_sem_nome_gera_erro`:

```python
async def test_importar_atletas_csv_sem_nome_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition
):
    csv_content = b"nome;email\n;pedro@example.com"

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

- [ ] **Step 2: Adicionar novos testes para a coluna `equipe`**

Ao final de `backend/tests/integration/test_athletes.py`, adicionar:

```python
async def test_importar_atletas_csv_cria_equipe_automaticamente(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome;categoria;equipe\n"
        f"Carlos Silva;{category.name};Equipe Alpha\n"
        f"Ana Souza;{category.name};Equipe Alpha\n"
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

    # Verifica que apenas UMA equipe foi criada (reutilizada na segunda linha)
    teams_r = await client.get(
        f"/api/v1/competitions/{competition.id}/teams",
        cookies={"session_id": admin_token},
    )
    teams = teams_r.json()
    assert len([t for t in teams if t["name"] == "Equipe Alpha"]) == 1


async def test_importar_atletas_csv_equipe_sem_categoria_nao_cria_equipe(
    client: AsyncClient, admin_token: str, competition: Competition
):
    """Equipe não é criada se categoria está ausente; atleta é criado sem equipe."""
    csv_content = b"nome;categoria;equipe\nJoao Lima;;Orfaos FC"

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1  # atleta criado
    assert len(data["errors"]) == 1  # erro de equipe sem categoria
    assert "equipe" in data["errors"][0]["error"].lower()


async def test_importar_atletas_csv_vincula_equipe_existente(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category,
    db: AsyncSession
):
    """Se a equipe já existe, o atleta é vinculado sem criar duplicata."""
    from app.models.team import Team as TeamModel

    existing_team = TeamModel(
        competition_id=competition.id,
        name="Time Beta",
        category_id=category.id,
    )
    db.add(existing_team)
    await db.commit()
    await db.refresh(existing_team)

    csv_content = (
        f"nome;categoria;equipe\nMaria Nunes;{category.name};Time Beta\n"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1
    assert data["errors"] == []

    # Verifica que nenhuma equipe duplicada foi criada
    teams_r = await client.get(
        f"/api/v1/competitions/{competition.id}/teams",
        cookies={"session_id": admin_token},
    )
    assert len([t for t in teams_r.json() if t["name"] == "Time Beta"]) == 1
```

- [ ] **Step 3: Rodar testes para confirmar que falham**

```bash
cd /home/vitoralves/projects/tempus/backend && python -m pytest tests/integration/test_athletes.py -v 2>&1 | tail -20
```

Esperado: `test_importar_atletas_csv_retorna_200` FAIL (separador errado), `test_importar_atletas_csv_sem_nome_gera_erro` FAIL, novos testes FAIL.

- [ ] **Step 4: Atualizar `backend/app/services/athlete.py`**

Substituir o método `import_csv` completo:

```python
@staticmethod
async def import_csv(
    db: AsyncSession, competition_id: int, content: bytes, categories: list[Category]
) -> AthleteBulkResult:
    """Importa atletas de um arquivo CSV.

    Colunas (separador ponto-e-vírgula):
        nome;categoria;equipe;email;documento;telefone;tamanho_camiseta

    Apenas 'nome' é obrigatório. Se 'equipe' for informada e a equipe não existir,
    ela será criada automaticamente usando a mesma categoria do atleta.

    Args:
        db: Sessão assíncrona.
        competition_id: ID da competição.
        content: Conteúdo do CSV em bytes.
        categories: Categorias da competição para resolução de nomes.

    Returns:
        AthleteBulkResult com contagens e erros por linha.
    """
    from app.models.team import Team
    from app.repositories.team import TeamRepository

    category_by_name = {c.name.lower(): c for c in categories}

    existing_teams = await TeamRepository.get_by_competition(db, competition_id)
    teams_by_name: dict[str, Team] = {t.name.lower(): t for t in existing_teams}

    created_count = 0
    errors: list[AthleteBulkError] = []

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    for row_num, row in enumerate(reader, start=1):
        name = (row.get("nome") or "").strip()
        if not name:
            errors.append(
                AthleteBulkError(row=row_num, name="", error="Campo 'nome' obrigatório")
            )
            continue

        cat_name = (row.get("categoria") or "").strip().lower()
        category = category_by_name.get(cat_name) if cat_name else None
        category_id = category.id if category else None

        raw_size = (row.get("tamanho_camiseta") or "").strip().upper()
        tshirt_size = TshirtSize(raw_size) if raw_size in _TSHIRT_SIZES else None

        team_name = (row.get("equipe") or "").strip()
        team_id: int | None = None
        if team_name:
            team_key = team_name.lower()
            if team_key in teams_by_name:
                team_id = teams_by_name[team_key].id
            elif category_id is None:
                errors.append(
                    AthleteBulkError(
                        row=row_num,
                        name=name,
                        error=f"Equipe '{team_name}' não pode ser criada sem categoria válida",
                    )
                )
            else:
                new_team = Team(
                    competition_id=competition_id,
                    name=team_name,
                    category_id=category_id,
                )
                db.add(new_team)
                await db.flush()
                await db.refresh(new_team)
                teams_by_name[team_key] = new_team
                team_id = new_team.id

        athlete = Athlete(
            competition_id=competition_id,
            name=name,
            email=(row.get("email") or "").strip() or None,
            document=(row.get("documento") or "").strip() or None,
            phone=(row.get("telefone") or "").strip() or None,
            category_id=category_id,
            tshirt_size=tshirt_size,
            team_id=team_id,
        )
        db.add(athlete)
        created_count += 1

    if created_count:
        await db.flush()

    return AthleteBulkResult(created=created_count, errors=errors)
```

- [ ] **Step 5: Rodar testes para confirmar que passam**

```bash
cd /home/vitoralves/projects/tempus/backend && python -m pytest tests/integration/test_athletes.py -v 2>&1 | tail -20
```

Esperado: todos os testes PASS.

- [ ] **Step 6: Rodar suite completa para verificar regressões**

```bash
cd /home/vitoralves/projects/tempus/backend && python -m pytest -x -q 2>&1 | tail -20
```

Esperado: 0 failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/athlete.py backend/tests/integration/test_athletes.py
git commit -m "feat(athletes): separador ponto-e-vírgula e coluna equipe no CSV de importação"
```

---

### Task 3: Frontend — AthletesPage: disclaimer CSV

**Files:**
- Modify: `frontend/src/pages/dashboard/AthletesPage.tsx`

**Interfaces:**
- Produces: bloco informativo fixo abaixo do botão "Importar CSV"

- [ ] **Step 1: Adicionar bloco informativo em `AthletesPage.tsx`**

Localizar o bloco do botão "Importar CSV" (linhas ~97-108). Substituir:

```tsx
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
```

Por:

```tsx
          <div className="flex flex-col items-end gap-1">
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
            <p className="text-xs text-gray-400">
              Formato: <code className="font-mono">nome;categoria;equipe</code> — separador{" "}
              <code className="font-mono">;</code>. Equipe criada automaticamente se não existir.
            </p>
          </div>
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /home/vitoralves/projects/tempus/frontend && npx tsc --noEmit 2>&1 | head -20
```

Esperado: sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/dashboard/AthletesPage.tsx
git commit -m "feat(athletes): adicionar disclaimer de formato CSV na página de importação"
```

---

### Task 4: Backend — Importação CSV de equipes (schema + service + endpoint + testes)

**Files:**
- Modify: `backend/app/schemas/team.py`
- Modify: `backend/app/services/team.py`
- Modify: `backend/app/api/v1/competitions.py`
- Create: `backend/tests/integration/test_teams_import.py`

**Interfaces:**
- Consumes: `CategoryService.list_by_competition(db, competition_id): list[Category]` (já existe), `TeamRepository.get_by_competition(db, competition_id): list[Team]` (já existe)
- Produces:
  - `TeamBulkError` (schema): `{ row: int, name: str, error: str }`
  - `TeamBulkResult` (schema): `{ created: int, errors: list[TeamBulkError] }`
  - `TeamService.import_csv(db, competition_id, content, categories) -> TeamBulkResult`
  - `POST /api/v1/competitions/{competition_id}/teams/import` → `200 TeamBulkResult`

- [ ] **Step 1: Criar arquivo de testes `backend/tests/integration/test_teams_import.py`**

```python
"""Testes de integração para importação CSV de equipes."""
import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.category import Category, CategoryType


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Equipes CSV", status=CompetitionStatus.active)
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Masters",
        category_type=CategoryType.team,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def test_importar_equipes_csv_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome_equipe;categoria\n"
        f"Thunder Force;{category.name}\n"
        f"Iron Squad;{category.name}\n"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []


async def test_importar_equipes_csv_categoria_invalida_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome_equipe;categoria\n"
        "Equipe Valida;{}\n".format(category.name) +
        "Equipe Invalida;CategoriaInexistente\n"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 2


async def test_importar_equipes_csv_nome_vazio_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome_equipe;categoria\n"
        f";{category.name}\n"
    ).encode("utf-8")

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1


async def test_importar_equipes_csv_duplicata_ignorada(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    """Equipe com mesmo nome já existente é pulada silenciosamente."""
    from app.models.team import Team as TeamModel

    # importar duas vezes o mesmo CSV
    csv_content = (
        "nome_equipe;categoria\n"
        f"Única Equipe;{category.name}\n"
    ).encode("utf-8")

    await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    r2 = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    data = r2.json()
    assert data["created"] == 0  # já existia, pulada
    assert data["errors"] == []


async def test_importar_equipes_csv_requer_autenticacao(
    client: AsyncClient, competition: Competition
):
    csv_content = b"nome_equipe;categoria\nTime X;Elite\n"
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert r.status_code == 401


async def test_importar_equipes_csv_competidor_retorna_403(
    client: AsyncClient, competitor_token: str, competition: Competition
):
    csv_content = b"nome_equipe;categoria\nTime X;Elite\n"
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/teams/import",
        files={"file": ("equipes.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Rodar testes para confirmar que falham (endpoint inexistente)**

```bash
cd /home/vitoralves/projects/tempus/backend && python -m pytest tests/integration/test_teams_import.py -v 2>&1 | tail -15
```

Esperado: todos falham com `404 Not Found` (endpoint não existe ainda).

- [ ] **Step 3: Adicionar `TeamBulkError` e `TeamBulkResult` em `backend/app/schemas/team.py`**

Ao final do arquivo, adicionar:

```python
class TeamBulkError(BaseModel):
    row: int
    name: str
    error: str


class TeamBulkResult(BaseModel):
    created: int
    errors: list[TeamBulkError]
```

- [ ] **Step 4: Adicionar `import_csv` em `backend/app/services/team.py`**

No topo do arquivo, inserir `import csv` e `import io` antes da linha `from fastapi import ...`:

```python
import csv
import io
```

(`Category`, `Team` e `TeamRepository` já estão importados — não duplicar.)

Ao final da classe `TeamService`, adicionar:

```python
    @staticmethod
    async def import_csv(
        db: AsyncSession,
        competition_id: int,
        content: bytes,
        categories: list[Category],
    ) -> "TeamBulkResult":
        """Importa equipes de um arquivo CSV.

        Colunas (separador ponto-e-vírgula):
            nome_equipe;categoria

        Equipes com nome já existente na competição são puladas silenciosamente.
        Linhas com categoria inválida geram erro e não são criadas.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            content: Conteúdo do CSV em bytes.
            categories: Categorias da competição para resolução de nomes.

        Returns:
            TeamBulkResult com contagem de criadas e erros por linha.
        """
        from app.schemas.team import TeamBulkError, TeamBulkResult

        category_by_name = {c.name.lower(): c for c in categories}
        existing = await TeamRepository.get_by_competition(db, competition_id)
        existing_names = {t.name.lower() for t in existing}

        created_count = 0
        errors: list[TeamBulkError] = []

        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        for row_num, row in enumerate(reader, start=1):
            name = (row.get("nome_equipe") or "").strip()
            if not name:
                errors.append(
                    TeamBulkError(row=row_num, name="", error="Campo 'nome_equipe' obrigatório")
                )
                continue

            if name.lower() in existing_names:
                continue

            cat_name = (row.get("categoria") or "").strip().lower()
            category = category_by_name.get(cat_name)
            if not category:
                errors.append(
                    TeamBulkError(
                        row=row_num,
                        name=name,
                        error=f"Categoria '{cat_name}' não encontrada na competição",
                    )
                )
                continue

            team = Team(
                competition_id=competition_id,
                name=name,
                category_id=category.id,
            )
            db.add(team)
            existing_names.add(name.lower())
            created_count += 1

        if created_count:
            await db.flush()

        return TeamBulkResult(created=created_count, errors=errors)
```

- [ ] **Step 5: Adicionar endpoint em `backend/app/api/v1/competitions.py`**

No bloco de imports `from app.schemas.team import (...)` (linha ~37), adicionar `TeamBulkResult`:

```python
from app.schemas.team import (
    TeamBulkResult,
    TeamCreate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)
```

Localizar o endpoint `delete_team` (linha ~457). Após o bloco `delete_team`, inserir o novo endpoint:

```python
@router.post(
    "/competitions/{competition_id}/teams/import",
    response_model=TeamBulkResult,
    status_code=status.HTTP_200_OK,
)
async def import_teams_csv(
    competition_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles("operator", "admin")),
) -> TeamBulkResult:
    """Importa equipes de arquivo CSV (Operador/Admin). Máximo 1 MB.

    Formato: nome_equipe;categoria (separador ponto-e-vírgula).
    """
    _max_csv_bytes = 1 * 1024 * 1024
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
        )
    content = await file.read()
    if len(content) > _max_csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo CSV excede o tamanho máximo de 1 MB",
        )
    categories = await CategoryService.list_by_competition(db, competition_id)
    result = await TeamService.import_csv(db, competition_id, content, categories)
    logger.info(
        "Import CSV equipes: competition_id=%s created=%s errors=%s",
        competition_id,
        result.created,
        len(result.errors),
    )
    return result
```

- [ ] **Step 6: Rodar testes para confirmar que passam**

```bash
cd /home/vitoralves/projects/tempus/backend && python -m pytest tests/integration/test_teams_import.py -v 2>&1 | tail -20
```

Esperado: todos os 6 testes PASS.

- [ ] **Step 7: Rodar suite completa**

```bash
cd /home/vitoralves/projects/tempus/backend && python -m pytest -x -q 2>&1 | tail -10
```

Esperado: 0 failures.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/team.py backend/app/services/team.py backend/app/api/v1/competitions.py backend/tests/integration/test_teams_import.py
git commit -m "feat(teams): endpoint de importação CSV de equipes por competição"
```

---

### Task 5: Frontend — TeamsPage: botão importar CSV + disclaimer

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/teams.ts`
- Modify: `frontend/src/pages/dashboard/TeamsPage.tsx`

**Interfaces:**
- Consumes: `POST /api/v1/competitions/{id}/teams/import` (criado na Task 4)
- Produces: `teamsApi.importCsv(competitionId, file): Promise<TeamBulkResult>`, botão na TeamsPage com disclaimer

- [ ] **Step 1: Adicionar tipos em `frontend/src/types/index.ts`**

Localizar a interface `Team` (linha ~134). Logo após o bloco da interface `Team`, adicionar:

```typescript
export interface TeamBulkError {
  row: number;
  name: string;
  error: string;
}

export interface TeamBulkResult {
  created: number;
  errors: TeamBulkError[];
}
```

- [ ] **Step 2: Adicionar `importCsv` em `frontend/src/api/teams.ts`**

Adicionar o import do tipo:

```typescript
import type { Team, TeamMember, TeamBulkResult } from "../types";
```

(Substitui a linha de import existente que importa `Team` e `TeamMember`.)

Ao final do objeto `teamsApi`, antes do fechamento `};`, adicionar:

```typescript
  importCsv: (competitionId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<TeamBulkResult>(
        `/api/v1/competitions/${competitionId}/teams/import`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      )
      .then((r) => r.data);
  },
```

- [ ] **Step 3: Atualizar `frontend/src/pages/dashboard/TeamsPage.tsx`**

Substituir o conteúdo completo do arquivo:

```tsx
import { useEffect, useRef, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { PlusIcon, ArrowUpTrayIcon } from "@heroicons/react/24/outline";
import { teamsApi, type TeamCreate } from "../../api/teams";
import { categoriesApi } from "../../api/categories";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import type { Category, Competition, Team, TeamBulkResult } from "../../types";

interface OutletCtx {
  competition: Competition;
}

export default function TeamsPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  useOutletContext<OutletCtx>();
  const id = Number(competitionId);
  const fileRef = useRef<HTMLInputElement>(null);

  const [teams, setTeams] = useState<Team[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [filterCat, setFilterCat] = useState<string>("");
  const [search, setSearch] = useState("");

  const [form, setForm] = useState<{ name: string; category_id?: number }>({
    name: "",
    category_id: undefined,
  });

  useEffect(() => {
    Promise.all([
      teamsApi.list(id),
      categoriesApi.list(id),
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
      const payload: TeamCreate = {
        name: form.name,
        category_id: form.category_id ?? 0,
      };
      const team = await teamsApi.create(id, payload);
      setTeams((p) => [...p, team]);
      setForm({ name: "", category_id: undefined });
      setShowForm(false);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao criar equipe");
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

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setImportResult(null);
    try {
      const data: TeamBulkResult = await teamsApi.importCsv(id, file);
      setImportResult(
        `${data.created} equipe(s) importada(s) com sucesso.${
          data.errors.length ? ` ${data.errors.length} erro(s).` : ""
        }`
      );
      const updated = await teamsApi.list(id);
      setTeams(updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro na importação");
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Equipes</h1>
        <div className="flex items-start gap-3">
          <div className="flex flex-col items-end gap-1">
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
            <p className="text-xs text-gray-400">
              Formato: <code className="font-mono">nome_equipe;categoria</code>
            </p>
          </div>
          <Button onClick={() => setShowForm((s) => !s)} className="flex items-center gap-2">
            <PlusIcon className="h-4 w-4" /> Nova Equipe
          </Button>
        </div>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {importResult && <Alert variant="success">{importResult}</Alert>}

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
            <Button variant="secondary" type="button" onClick={() => setShowForm(false)}>
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

- [ ] **Step 4: Verificar TypeScript**

```bash
cd /home/vitoralves/projects/tempus/frontend && npx tsc --noEmit 2>&1 | head -20
```

Esperado: sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/teams.ts frontend/src/pages/dashboard/TeamsPage.tsx
git commit -m "feat(teams): importação CSV de equipes com botão e disclaimer na TeamsPage"
```

---

## Verificação Final

- [ ] Rodar suite completa do backend

```bash
cd /home/vitoralves/projects/tempus/backend && python -m pytest -q 2>&1 | tail -5
```

Esperado: 0 failures.

- [ ] Rodar TypeScript check do frontend

```bash
cd /home/vitoralves/projects/tempus/frontend && npx tsc --noEmit 2>&1 | head -10
```

Esperado: sem erros.
