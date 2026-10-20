# Wizard Step 5 — Categorias: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar o Step 5 "Categorias" ao CompetitionWizardPage, deslocando a Finalização para Step 6.

**Architecture:** Mudança exclusivamente em `frontend/src/pages/CompetitionWizardPage.tsx`. O backend já expõe todos os endpoints necessários (`GET/POST/PATCH /competitions/{id}/categories`). O `categoriesApi` e o tipo `Category` já existem no frontend.

**Tech Stack:** React 18, TypeScript strict, TailwindCSS, axios (`categoriesApi`)

## Global Constraints

- Apenas `frontend/src/pages/CompetitionWizardPage.tsx` é modificado — sem outros arquivos, sem backend.
- `CategoryType`: `"individual" | "team"` (de `src/types/index.ts`)
- `Gender`: `"male" | "female" | "mixed"` (de `src/types/index.ts`)
- `Category` interface: `id, competition_id, name, category_type, gender, age_restriction_enabled, age_min, age_max, max_team_size, is_active, created_at, updated_at`
- `categoriesApi.list(competitionId, onlyActive?)` — retorna `Promise<Category[]>`
- `categoriesApi.create(competitionId, data)` — retorna `Promise<Category>`
- `categoriesApi.update(competitionId, categoryId, data)` — retorna `Promise<Category>`
- `categoriesApi.deactivate(competitionId, categoryId)` — retorna `Promise<void>`
- Desativar (soft delete) em vez de deletar — `categoriesApi.deactivate` chama `PATCH { is_active: false }`
- Em modo criação (`createdCompId === null`): exibir aviso e formulário desabilitado
- Em modo edição (`createdCompId !== null`): CRUD completo disponível
- Edição inline: a linha da categoria se transforma em formulário, sem modal
- TypeScript: `npx tsc --noEmit` deve retornar zero erros
- `ruff check` não se aplica (arquivo TypeScript)
- Wizard tem 6 steps após a mudança: Informações, Divulgação, WODs, Pontuação, **Categorias**, Finalização
- Step 6 (ex-Step 5) tem `handleSubmit` — o número do step muda, a lógica não muda
- O skip de Hyrox (step 2 → step 4 e back step 4 → step 2) permanece inalterado

---

### Task 1: Wizard Step 5 — Categorias

**Files:**
- Modify: `frontend/src/pages/CompetitionWizardPage.tsx`

**Interfaces:**
- Consumes: `categoriesApi` de `../api/categories`; `Category`, `CategoryType`, `Gender` de `../types`
- Produces: wizard funcional com 6 steps

---

- [ ] **Step 1: Ler o arquivo completo antes de qualquer edição**

```bash
wc -l frontend/src/pages/CompetitionWizardPage.tsx
```

Leia o arquivo inteiro para entender o padrão atual (interfaces, state, handlers, render). Só então faça as edições abaixo na sequência correta.

---

- [ ] **Step 2: Atualizar imports**

Localizar a linha:
```typescript
import type { EventType, ScoringModel, TiebreakCriterion, Wod, WodType } from "../types";
```

Substituir por:
```typescript
import type { Category, CategoryType, EventType, Gender, ScoringModel, TiebreakCriterion, Wod, WodType } from "../types";
```

Localizar a linha:
```typescript
import { competitionsApi, type CompetitionCreate, type WodCreate } from "../api/competitions";
```

Adicionar o import do categoriesApi logo abaixo (nova linha):
```typescript
import { categoriesApi } from "../api/categories";
```

---

- [ ] **Step 3: Adicionar interface e tipo do formulário de categoria**

Após a interface `WizardStep4`, adicionar:

```typescript
interface CatForm {
  name: string;
  category_type: CategoryType;
  gender: Gender | "";
  age_restriction_enabled: boolean;
  age_min: number | undefined;
  age_max: number | undefined;
  max_team_size: number | undefined;
}

interface WizardStep5 {
  categories: Category[];
}
```

---

- [ ] **Step 4: Atualizar WizardState e INITIAL_STATE**

Localizar:
```typescript
interface WizardState {
  step1: WizardStep1;
  step2: WizardStep2;
  step3: WizardStep3;
  step4: WizardStep4;
}
```

Substituir por:
```typescript
interface WizardState {
  step1: WizardStep1;
  step2: WizardStep2;
  step3: WizardStep3;
  step4: WizardStep4;
  step5: WizardStep5;
}
```

Localizar `step4: { scoring_model: "", tiebreak_criterion: "" },` e adicionar depois:
```typescript
  step5: { categories: [] },
```

---

- [ ] **Step 5: Adicionar variáveis de estado para categoria**

Após a linha `const [wodForm, setWodForm] = useState<WodCreate>({...});`, adicionar:

```typescript
const INITIAL_CAT_FORM: CatForm = {
  name: "",
  category_type: "individual",
  gender: "",
  age_restriction_enabled: false,
  age_min: undefined,
  age_max: undefined,
  max_team_size: undefined,
};

const [catAdding, setCatAdding] = useState(false);
const [catSaving, setCatSaving] = useState(false);
const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
const [catForm, setCatForm] = useState<CatForm>(INITIAL_CAT_FORM);
const [editCatForm, setEditCatForm] = useState<CatForm>(INITIAL_CAT_FORM);
```

---

- [ ] **Step 6: Carregar categorias no useEffect**

Localizar dentro do `useEffect` (modo edição) o bloco que carrega `step2`:

```typescript
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

Adicionar logo após esse bloco (ainda dentro do `.then` e do `try` existente, antes do `}` que fecha o catch):

```typescript
      const catsResp = await categoriesApi.list(Number(id), true);
      setState((prev) => ({ ...prev, step5: { categories: catsResp } }));
```

**Atenção:** este código vai dentro do bloco `try { ... } catch { setError(...) }` que já envolve o `listWods`. Verifique que está dentro do try existente para que erros de rede sejam capturados.

O bloco try completo deve ficar assim:
```typescript
      try {
        if (c.event_type === "crossfit") {
          const wodsResp = await competitionsApi.listWods(Number(id));
          const wods = (wodsResp.data ?? wodsResp) as Wod[];
          setState((prev) => ({ ...prev, step3: { wods } }));
        }
        const catsResp = await categoriesApi.list(Number(id), true);
        setState((prev) => ({ ...prev, step5: { categories: catsResp } }));
      } catch {
        setError("Erro ao carregar dados. Tente recarregar a página.");
      }
```

(A mensagem do catch fica genérica para cobrir falhas de WODs ou categorias.)

---

- [ ] **Step 7: Adicionar handlers de categoria**

Após o handler `handleDeleteWod`, adicionar:

```typescript
  // ── Handlers de Categoria ──────────────────────────────────────────────────

  async function handleAddCategory() {
    if (!catForm.name.trim() || !createdCompId) return;
    setCatAdding(true);
    try {
      const payload: Record<string, unknown> = {
        name: catForm.name.trim(),
        category_type: catForm.category_type,
      };
      if (catForm.gender) payload.gender = catForm.gender;
      if (catForm.age_restriction_enabled) {
        payload.age_restriction_enabled = true;
        if (catForm.age_min !== undefined) payload.age_min = catForm.age_min;
        if (catForm.age_max !== undefined) payload.age_max = catForm.age_max;
      }
      if (catForm.category_type === "team" && catForm.max_team_size !== undefined) {
        payload.max_team_size = catForm.max_team_size;
      }
      const created = await categoriesApi.create(createdCompId, payload as any);
      setState((p) => ({ ...p, step5: { categories: [...p.step5.categories, created] } }));
      setCatForm(INITIAL_CAT_FORM);
    } catch {
      setError("Erro ao adicionar categoria.");
    } finally {
      setCatAdding(false);
    }
  }

  function handleStartEditCategory(cat: Category) {
    setEditingCategoryId(cat.id);
    setEditCatForm({
      name: cat.name,
      category_type: cat.category_type,
      gender: cat.gender ?? "",
      age_restriction_enabled: cat.age_restriction_enabled,
      age_min: cat.age_min ?? undefined,
      age_max: cat.age_max ?? undefined,
      max_team_size: cat.max_team_size ?? undefined,
    });
  }

  function handleCancelEditCategory() {
    setEditingCategoryId(null);
    setEditCatForm(INITIAL_CAT_FORM);
  }

  async function handleSaveCategory() {
    if (!editCatForm.name.trim() || !createdCompId || editingCategoryId === null) return;
    setCatSaving(true);
    try {
      const payload: Record<string, unknown> = {
        name: editCatForm.name.trim(),
        category_type: editCatForm.category_type,
        gender: editCatForm.gender || null,
        age_restriction_enabled: editCatForm.age_restriction_enabled,
        age_min: editCatForm.age_restriction_enabled ? (editCatForm.age_min ?? null) : null,
        age_max: editCatForm.age_restriction_enabled ? (editCatForm.age_max ?? null) : null,
        max_team_size: editCatForm.category_type === "team" ? (editCatForm.max_team_size ?? null) : null,
      };
      const updated = await categoriesApi.update(createdCompId, editingCategoryId, payload as any);
      setState((p) => ({
        ...p,
        step5: {
          categories: p.step5.categories.map((c) => (c.id === editingCategoryId ? updated : c)),
        },
      }));
      setEditingCategoryId(null);
      setEditCatForm(INITIAL_CAT_FORM);
    } catch {
      setError("Erro ao salvar categoria.");
    } finally {
      setCatSaving(false);
    }
  }

  async function handleDeactivateCategory(catId: number) {
    if (!createdCompId) return;
    try {
      await categoriesApi.deactivate(createdCompId, catId);
      setState((p) => ({
        ...p,
        step5: { categories: p.step5.categories.filter((c) => c.id !== catId) },
      }));
    } catch {
      setError("Erro ao desativar categoria.");
    }
  }
```

---

- [ ] **Step 8: Atualizar handleNext (max step 6)**

Localizar:
```typescript
    setCurrentStep((s) => Math.min(s + 1, 5));
```

Substituir por:
```typescript
    setCurrentStep((s) => Math.min(s + 1, 6));
```

---

- [ ] **Step 9: Atualizar STEPS e renderização da navegação**

Localizar:
```typescript
  const STEPS = ["Informações", "Divulgação", "WODs", "Pontuação", "Finalização"];
```

Substituir por:
```typescript
  const STEPS = ["Informações", "Divulgação", "WODs", "Pontuação", "Categorias", "Finalização"];
```

Localizar no bloco de navegação (perto do final do return):
```typescript
        {currentStep < 5 && (
          <Button onClick={handleNext}>
            {currentStep === 4 ? "Revisar" : "Avançar"}
          </Button>
        )}
```

Substituir por:
```typescript
        {currentStep < 6 && (
          <Button onClick={handleNext}>
            {currentStep === 5 ? "Revisar" : "Avançar"}
          </Button>
        )}
```

---

- [ ] **Step 10: Mover o bloco de Finalização de step 5 para step 6**

Localizar:
```typescript
      {/* Etapa 5: Resumo e criação */}
      {currentStep === 5 && (
```

Substituir por:
```typescript
      {/* Etapa 6: Resumo e criação */}
      {currentStep === 6 && (
```

Também adicionar o card de categorias no grid do resumo (após o card de WODs):

```typescript
            {/* Card: Categorias */}
            <div className="rounded-md bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase text-gray-500">Categorias</p>
              <p className="mt-1 font-medium text-gray-900">
                {state.step5.categories.length > 0
                  ? `${state.step5.categories.length} categoria(s) ativa(s)`
                  : "Nenhuma categoria"}
              </p>
            </div>
```

---

- [ ] **Step 11: Adicionar render do Step 5 (Categorias)**

Após o bloco `{/* Etapa 4: ... */}` e antes do bloco `{/* Etapa 6: ... */}`, inserir:

```tsx
      {/* Etapa 5: Categorias */}
      {currentStep === 5 && (
        <div className="space-y-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Categorias</h2>

          {!createdCompId ? (
            <p className="rounded-md bg-blue-50 px-4 py-3 text-sm text-blue-700">
              Categorias ficam disponíveis após criar a competição. Prossiga para a etapa de
              Finalização e volte para adicionar categorias.
            </p>
          ) : (
            <div className="space-y-6">
              {/* Lista de categorias */}
              {state.step5.categories.length === 0 ? (
                <p className="text-sm text-gray-500">Nenhuma categoria cadastrada ainda.</p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {state.step5.categories.map((cat) =>
                    editingCategoryId === cat.id ? (
                      /* Linha em modo edição inline */
                      <li key={cat.id} className="space-y-3 py-4">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-600">Nome *</label>
                            <input
                              type="text"
                              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                              value={editCatForm.name}
                              onChange={(e) => setEditCatForm((f) => ({ ...f, name: e.target.value }))}
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-600">Tipo *</label>
                            <select
                              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                              value={editCatForm.category_type}
                              onChange={(e) =>
                                setEditCatForm((f) => ({
                                  ...f,
                                  category_type: e.target.value as CategoryType,
                                  max_team_size: undefined,
                                }))
                              }
                            >
                              <option value="individual">Individual</option>
                              <option value="team">Equipe</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-600">Gênero</label>
                            <select
                              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                              value={editCatForm.gender}
                              onChange={(e) =>
                                setEditCatForm((f) => ({ ...f, gender: e.target.value as Gender | "" }))
                              }
                            >
                              <option value="">Sem restrição</option>
                              <option value="male">Masculino</option>
                              <option value="female">Feminino</option>
                              <option value="mixed">Misto</option>
                            </select>
                          </div>
                          {editCatForm.category_type === "team" && (
                            <div>
                              <label className="block text-xs font-medium text-gray-600">
                                Tamanho máx. equipe
                              </label>
                              <input
                                type="number"
                                min={2}
                                max={50}
                                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                                value={editCatForm.max_team_size ?? ""}
                                onChange={(e) =>
                                  setEditCatForm((f) => ({
                                    ...f,
                                    max_team_size: e.target.value ? Number(e.target.value) : undefined,
                                  }))
                                }
                              />
                            </div>
                          )}
                        </div>
                        <label className="flex items-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={editCatForm.age_restriction_enabled}
                            onChange={(e) =>
                              setEditCatForm((f) => ({
                                ...f,
                                age_restriction_enabled: e.target.checked,
                                age_min: undefined,
                                age_max: undefined,
                              }))
                            }
                            className="h-4 w-4 rounded border-gray-300"
                          />
                          Restringir por idade
                        </label>
                        {editCatForm.age_restriction_enabled && (
                          <div className="grid grid-cols-2 gap-3 pl-6">
                            <div>
                              <label className="block text-xs font-medium text-gray-600">Idade mínima</label>
                              <input
                                type="number"
                                min={0}
                                max={120}
                                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                                value={editCatForm.age_min ?? ""}
                                onChange={(e) =>
                                  setEditCatForm((f) => ({
                                    ...f,
                                    age_min: e.target.value ? Number(e.target.value) : undefined,
                                  }))
                                }
                              />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600">Idade máxima</label>
                              <input
                                type="number"
                                min={0}
                                max={120}
                                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                                value={editCatForm.age_max ?? ""}
                                onChange={(e) =>
                                  setEditCatForm((f) => ({
                                    ...f,
                                    age_max: e.target.value ? Number(e.target.value) : undefined,
                                  }))
                                }
                              />
                            </div>
                          </div>
                        )}
                        <div className="flex gap-2">
                          <button
                            onClick={handleSaveCategory}
                            disabled={catSaving}
                            className="rounded-md bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                          >
                            {catSaving ? "Salvando..." : "Salvar"}
                          </button>
                          <button
                            onClick={handleCancelEditCategory}
                            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                          >
                            Cancelar
                          </button>
                        </div>
                      </li>
                    ) : (
                      /* Linha em modo exibição */
                      <li key={cat.id} className="flex items-center justify-between py-3">
                        <div className="space-y-0.5">
                          <p className="text-sm font-medium text-gray-900">{cat.name}</p>
                          <div className="flex flex-wrap gap-1.5">
                            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                              {cat.category_type === "individual" ? "Individual" : "Equipe"}
                            </span>
                            {cat.gender && (
                              <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                                {cat.gender === "male"
                                  ? "Masculino"
                                  : cat.gender === "female"
                                  ? "Feminino"
                                  : "Misto"}
                              </span>
                            )}
                            {cat.age_restriction_enabled && (
                              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                                {cat.age_min ?? "?"} – {cat.age_max ?? "?"} anos
                              </span>
                            )}
                            {cat.category_type === "team" && cat.max_team_size && (
                              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                                Máx. {cat.max_team_size} membros
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleStartEditCategory(cat)}
                            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                            title="Editar"
                          >
                            ✏️
                          </button>
                          <button
                            onClick={() => handleDeactivateCategory(cat.id)}
                            className="rounded-md p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600"
                            title="Desativar"
                          >
                            &#128465;
                          </button>
                        </div>
                      </li>
                    )
                  )}
                </ul>
              )}

              {/* Formulário de criação */}
              <div className="space-y-4 border-t pt-4">
                <h3 className="text-sm font-medium text-gray-700">Adicionar categoria</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-gray-600">Nome *</label>
                    <input
                      type="text"
                      placeholder="Ex: Elite Masculino"
                      className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                      value={catForm.name}
                      onChange={(e) => setCatForm((f) => ({ ...f, name: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600">Tipo *</label>
                    <select
                      className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                      value={catForm.category_type}
                      onChange={(e) =>
                        setCatForm((f) => ({
                          ...f,
                          category_type: e.target.value as CategoryType,
                          max_team_size: undefined,
                        }))
                      }
                    >
                      <option value="individual">Individual</option>
                      <option value="team">Equipe</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600">Gênero</label>
                    <select
                      className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                      value={catForm.gender}
                      onChange={(e) =>
                        setCatForm((f) => ({ ...f, gender: e.target.value as Gender | "" }))
                      }
                    >
                      <option value="">Sem restrição</option>
                      <option value="male">Masculino</option>
                      <option value="female">Feminino</option>
                      <option value="mixed">Misto</option>
                    </select>
                  </div>
                  {catForm.category_type === "team" && (
                    <div>
                      <label className="block text-xs font-medium text-gray-600">
                        Tamanho máx. equipe
                      </label>
                      <input
                        type="number"
                        min={2}
                        max={50}
                        className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                        value={catForm.max_team_size ?? ""}
                        onChange={(e) =>
                          setCatForm((f) => ({
                            ...f,
                            max_team_size: e.target.value ? Number(e.target.value) : undefined,
                          }))
                        }
                      />
                    </div>
                  )}
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={catForm.age_restriction_enabled}
                    onChange={(e) =>
                      setCatForm((f) => ({
                        ...f,
                        age_restriction_enabled: e.target.checked,
                        age_min: undefined,
                        age_max: undefined,
                      }))
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  Restringir por idade
                </label>
                {catForm.age_restriction_enabled && (
                  <div className="grid grid-cols-2 gap-3 pl-6">
                    <div>
                      <label className="block text-xs font-medium text-gray-600">Idade mínima</label>
                      <input
                        type="number"
                        min={0}
                        max={120}
                        className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                        value={catForm.age_min ?? ""}
                        onChange={(e) =>
                          setCatForm((f) => ({
                            ...f,
                            age_min: e.target.value ? Number(e.target.value) : undefined,
                          }))
                        }
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600">Idade máxima</label>
                      <input
                        type="number"
                        min={0}
                        max={120}
                        className="mt-1 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                        value={catForm.age_max ?? ""}
                        onChange={(e) =>
                          setCatForm((f) => ({
                            ...f,
                            age_max: e.target.value ? Number(e.target.value) : undefined,
                          }))
                        }
                      />
                    </div>
                  </div>
                )}
                <button
                  onClick={handleAddCategory}
                  disabled={catAdding || !catForm.name.trim()}
                  className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {catAdding ? "Adicionando..." : "+ Adicionar Categoria"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
```

---

- [ ] **Step 12: Verificar TypeScript**

```bash
cd /home/vitoralves/projects/tempus/frontend && npx tsc --noEmit 2>&1 | head -40
```

Esperado: nenhuma saída (zero erros). Se houver erros, corrija-os antes de continuar.

---

- [ ] **Step 13: Commit**

```bash
cd /home/vitoralves/projects/tempus && git add frontend/src/pages/CompetitionWizardPage.tsx && git commit -m "feat(wizard): adiciona step 5 de categorias ao wizard de competição"
```

---
