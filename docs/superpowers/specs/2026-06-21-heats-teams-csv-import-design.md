# Design: Bug Baterias + Melhorias CSV de Atletas e Equipes

**Data:** 2026-06-21  
**Status:** Aprovado

---

## Escopo

Três itens independentes:

1. **Bug** — Não é possível adicionar equipes a uma bateria (falta UI)
2. **Melhoria** — Disclaimer + suporte à coluna `equipe` no CSV de atletas
3. **Melhoria** — Importação CSV de equipes na página de Equipes

---

## 1. Bug: Adicionar equipes a baterias

### Causa raiz

`HeatsPage.tsx` exibe `team_count` mas não tem UI para adicionar/remover equipes. O backend (`HeatService.add_team`, `HeatService.remove_team`) e a camada de API do frontend (`heatsApi.addTeam`, `heatsApi.removeTeam`) já estão completos.

### Solução: painel expansível no card

- Botão **"Gerenciar Equipes"** visível apenas quando `heat.status === "pending"`
- Ao clicar, o card expande exibindo:
  1. **Equipes vinculadas** — chips com nome + botão `×` para desvincular
  2. **Adicionar equipe** — `<select>` com equipes da competição **não vinculadas** + botão "Adicionar"
- Estado:
  - `expandedHeatId: number | null`
  - `allTeams: Team[]` — carregado junto com `heats` no `useEffect` inicial
- Ao adicionar/remover: chama `heatsApi.addTeam`/`removeTeam`; atualiza o item correspondente em `heats` com a resposta do backend

**Nenhuma mudança de backend.**

---

## 2. Melhoria: CSV de atletas — disclaimer + coluna `equipe`

### Frontend

Abaixo do botão "Importar CSV" na `AthletesPage.tsx`, exibir bloco informativo fixo:

> `Formato: nome;categoria;equipe — separador ponto-e-vírgula (;). A coluna equipe é opcional; se informada, a equipe será criada automaticamente caso não exista.`

### Backend — `AthleteService.import_csv`

| Campo | Antes | Depois |
|---|---|---|
| Separador | `,` | `;` |
| Colunas obrigatórias | `nome` | `nome` |
| Colunas opcionais | `email, documento, telefone, categoria, tamanho_camiseta` | `categoria, equipe, email, documento, telefone, tamanho_camiseta` |

**Lógica da coluna `equipe`:**
1. Ler campo `equipe` da linha do CSV
2. Se vazio: `athlete.team_id = None`
3. Se preenchido: buscar `Team` por `name` (case-insensitive) + `competition_id`
4. Se não encontrar: criar `Team(name=equipe, competition_id=competition_id, category_id=athlete.category_id)`
5. Setar `athlete.team_id = team.id`

**Nota:** A mudança de separador de `,` para `;` quebra CSVs existentes com vírgula. Aceito pois o formato anterior não tinha disclaimer e era pouco utilizado.

---

## 3. Melhoria: Importação CSV de equipes

### Backend — novo endpoint

```
POST /competitions/{competition_id}/teams/import
```

- Roles: `operator`, `admin`
- Limite: 1 MB
- Separador: `;`
- Formato: `nome_equipe;categoria`
- Lógica por linha:
  - Resolver categoria por nome (case-insensitive); se não encontrar → erro na linha
  - Verificar se equipe com mesmo nome já existe na competição; se sim → pular (sem erro)
  - Criar `Team(name, competition_id, category_id)`
- Resposta: `TeamBulkResult { created: int, errors: [{ row, name, error }] }`

Localização: `backend/app/api/v1/teams.py` (endpoint novo no router existente)  
Service: `TeamService.import_csv` (novo método)

### Frontend — `TeamsPage.tsx`

- Adicionar botão "Importar CSV" (mesmo padrão do `AthletesPage`: `<label>` + `<input type="file" sr-only>`)
- Bloco informativo: `Formato: nome_equipe;categoria — separador ponto-e-vírgula (;)`
- Após importação: exibir resultado e recarregar lista de equipes

### Tipos — `types/index.ts`

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

### API — `api/teams.ts`

Novo método:
```typescript
importCsv: (competitionId: number, file: File) => Promise<TeamBulkResult>
```

---

## Arquivos afetados

### Backend
- `app/services/athlete.py` — mudar separador + lógica da coluna `equipe`
- `app/services/team.py` — novo método `import_csv`
- `app/api/v1/teams.py` — novo endpoint `POST /competitions/{id}/teams/import`
- `app/schemas/team.py` — novo schema `TeamBulkResult` + `TeamBulkError`
- Testes: `tests/integration/test_athletes.py`, novo `tests/integration/test_teams_import.py`

### Frontend
- `src/pages/dashboard/HeatsPage.tsx` — painel expansível + lógica addTeam/removeTeam
- `src/pages/dashboard/AthletesPage.tsx` — disclaimer
- `src/pages/dashboard/TeamsPage.tsx` — botão importar + disclaimer + lógica
- `src/api/teams.ts` — método `importCsv`
- `src/types/index.ts` — `TeamBulkResult`, `TeamBulkError`

---

## Fora do escopo

- Criação de `TeamMember` (usuário com conta) via CSV de atletas — atleta usa `team_id` direto, não `TeamMember`
- Edição de equipes existentes via CSV
- Paginação nos resultados de importação
