# Design: Página de Resultados WOD + Leaderboard Público

**Data:** 2026-06-21
**Status:** Aprovado

---

## Escopo

Dois itens interdependentes:

1. **Página de Resultados** (`/competitions/:id/dashboard/resultados`) — entrada de resultados por equipe por WOD
2. **Leaderboard WOD** (`RankingPage` pública) — posições calculadas a partir dos resultados cadastrados

---

## 1. Modelo de Dados

### Nova tabela `wod_results`

| Campo | Tipo | Restrições |
|---|---|---|
| `id` | int PK | autoincrement |
| `competition_id` | int | FK → competitions.id ON DELETE CASCADE, index |
| `wod_id` | int | FK → wods.id ON DELETE CASCADE, index |
| `team_id` | int | FK → teams.id ON DELETE CASCADE, index |
| `time_seconds` | int | nullable — tempo em segundos |
| `reps` | int | nullable — repetições ou carga |
| `notes` | str(500) | nullable |
| `created_at` | datetime | server_default=now() |
| `updated_at` | datetime | server_default=now(), onupdate=now() |

**Restrição única:** `(wod_id, team_id)` → nome `uq_wod_result`

Nenhuma alteração em modelos existentes (`Competition`, `Wod`, `Team`).

---

## 2. Lógica de Pontuação (Leaderboard)

O critério é definido por `competition.scoring_model`:

### `most_points` (padrão CrossFit)
- Para cada WOD, ranquear equipes com resultado:
  - `for_time` → por `time_seconds` **ASC** (menor = melhor)
  - `amrap` / `emom` / `max_load` → por `reps` **DESC** (maior = melhor)
- Pontos por WOD: 1º = N equipes, 2º = N-1, …, último com resultado = 1. Sem resultado = 0 pts.
- Posição final: **maior total de pontos** DESC.

### `lowest_time` (soma de tempos)
- Somar `time_seconds` de todos os WODs por equipe.
- WOD sem resultado para a equipe → soma não inclui (equipe enviada ao fim da tabela se houver WODs sem resultado).
- Posição final: **menor soma** de segundos ASC.

### `null` / não definido
- Resultados são exibidos na `ResultsPage` mas leaderboard de WODs não é calculado nem exibido.

### Critério de desempate (ambos os modelos)
- Equipes empatadas ficam com a mesma posição.
- Ordenação secundária: nome da equipe ASC (para exibição estável).

---

## 3. API

### Arquivos afetados (backend)

- **Criar:** `app/models/wod_result.py` — modelo `WodResult`
- **Criar:** `app/db/migrations/versions/20260621_wod_results.py`
- **Criar:** `app/schemas/wod_result.py` — schemas request/response
- **Criar:** `app/repositories/wod_result.py` — `WodResultRepository`
- **Criar:** `app/services/wod_result.py` — `WodResultService` (upsert, delete, leaderboard)
- **Modificar:** `app/api/v1/competitions.py` — novos endpoints
- **Criar:** `tests/integration/test_wod_results.py`

### Endpoints novos

```
GET /competitions/{competition_id}/wod-results
    Roles: judge / operator / admin
    Response: WodResultsData {
        wods: list[WodResponse],
        teams: list[TeamResponse],
        results: list[WodResultResponse]
    }

POST /competitions/{competition_id}/wod-results
    Roles: operator / admin
    Body: WodResultUpsert { wod_id, team_id, time_seconds?, reps?, notes? }
    Response: WodResultResponse
    Semântica: upsert — se (wod_id, team_id) já existe, atualiza; se não, cria.

DELETE /competitions/{competition_id}/wod-results/{result_id}
    Roles: operator / admin
    Response: 204

GET /competitions/{competition_id}/wod-leaderboard
    Roles: público (sem autenticação)
    Response: WodLeaderboard {
        scoring_model: str | null,
        entries: list[LeaderboardEntry]
    }
```

### Schemas

```python
# WodResultUpsert (request)
class WodResultUpsert(BaseModel):
    wod_id: int
    team_id: int
    time_seconds: int | None = None
    reps: int | None = None
    notes: str | None = Field(None, max_length=500)

# WodResultResponse (response)
class WodResultResponse(BaseModel):
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

# WodResultsData — retorno do GET /wod-results
class WodResultsData(BaseModel):
    wods: list[WodResponse]
    teams: list[TeamSimpleResponse]   # id, name, category_id
    results: list[WodResultResponse]

# LeaderboardWodEntry — resultado de uma equipe em um WOD
class LeaderboardWodEntry(BaseModel):
    wod_id: int
    wod_name: str
    time_seconds: int | None
    reps: int | None
    points: int         # 0 se sem resultado
    rank: int | None    # None se sem resultado

# LeaderboardEntry — linha do leaderboard por equipe
class LeaderboardEntry(BaseModel):
    position: int
    team_id: int
    team_name: str
    total_points: int   # ou total_seconds dependendo do scoring_model
    wod_entries: list[LeaderboardWodEntry]

# WodLeaderboard — retorno do GET /wod-leaderboard
class WodLeaderboard(BaseModel):
    scoring_model: str | None
    entries: list[LeaderboardEntry]
```

### Validações nos endpoints

- `wod_id` deve pertencer à `competition_id` informada → 404 se não encontrado
- `team_id` deve pertencer à `competition_id` informada → 404 se não encontrado
- `result_id` deve pertencer à `competition_id` informada → 404 se não encontrado
- Pelo menos um entre `time_seconds` e `reps` deve ser não-nulo → 422

---

## 4. Frontend

### Arquivos afetados (frontend)

- **Criar:** `src/pages/dashboard/ResultsPage.tsx`
- **Criar:** `src/api/wod_results.ts`
- **Modificar:** `src/App.tsx` — adicionar rota `resultados`
- **Modificar:** `src/types/index.ts` — novos tipos
- **Modificar:** `src/pages/RankingPage.tsx` — seção de leaderboard WOD

### Tipos TypeScript

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

### `ResultsPage.tsx`

**Estado:**
- `data: WodResultsData | null`
- `editingCell: { teamId: number; wodId: number } | null`
- `editForm: { time: string; reps: string; notes: string }`
- `saving: boolean`

**Layout:**

Tabela pivô (equipes nas linhas, WODs nas colunas):

```
| Equipe | WOD 1 | WOD 2 | WOD N |
|--------|-------|-------|-------|
| Alpha  | 12:30 |  45r  |   —   |
| Beta   |   —   | 08:15 |  120r |
```

- Cabeçalhos de WOD mostram nome e tipo (`for_time`, `amrap`, etc.)
- Célula com resultado: exibe tempo formatado (`mm:ss`) e/ou reps. Clique → abre inline edit.
- Célula sem resultado: exibe `—`. Clique → abre inline edit (criar novo).
- Inline edit: dois campos (`Tempo mm:ss` + `Reps`) + botão Salvar + botão Apagar (se resultado existe) + botão Cancelar.
- Só `operator`/`admin` podem clicar; `judge` lê somente.
- Após salvar/apagar: refaz `GET /wod-results` e atualiza estado.
- Sem WODs cadastrados: mensagem "Nenhum WOD cadastrado. Adicione WODs na etapa de configuração."
- Sem equipes: mensagem "Nenhuma equipe cadastrada."

### `RankingPage.tsx` — seção WOD

- Chamada paralela ao `GET /competitions/{id}/wod-leaderboard` junto com o ranking de timers.
- Se `entries.length > 0` → renderizar **"Leaderboard WODs"** acima do ranking de timers:

```
| # | Equipe | WOD 1 | WOD 2 | Total |
|---|--------|-------|-------|-------|
| 1 | Alpha  | 10pts |  8pts |  18   |
| 2 | Beta   |  8pts | 10pts |  18   |
```

  - Para `lowest_time`: coluna Total exibe tempo somado no formato `hh:mm:ss`.
  - Para `most_points`: coluna Total exibe pontos.
- Se `entries.length === 0` → seção não é renderizada.
- Sem autenticação necessária (endpoint público).

---

## 5. Testes

Arquivo: `tests/integration/test_wod_results.py`

- `test_listar_resultados_vazio` — GET retorna listas vazias
- `test_criar_resultado_for_time` — POST com time_seconds, verifica persistência
- `test_criar_resultado_amrap` — POST com reps
- `test_upsert_sobrescreve_resultado_existente` — segundo POST para mesmo (wod_id, team_id) atualiza
- `test_apagar_resultado` — DELETE retorna 204
- `test_wod_invalido_retorna_404` — wod_id de outra competição
- `test_team_invalido_retorna_404` — team_id de outra competição
- `test_sem_tempo_nem_reps_retorna_422` — validação de payload
- `test_leaderboard_most_points` — GET /wod-leaderboard com scoring_model=most_points
- `test_leaderboard_lowest_time` — GET /wod-leaderboard com scoring_model=lowest_time
- `test_leaderboard_publico_sem_autenticacao` — endpoint não exige login
- `test_acesso_negado_para_judge` — POST retorna 403

---

## Fora do Escopo

- WebSocket para push em tempo real (o leaderboard atualiza por polling/reload)
- Resultados individuais por atleta (apenas por equipe)
- Exportação CSV/PDF do leaderboard WOD
- Edição de WODs a partir da página de resultados
