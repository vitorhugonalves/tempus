# Design — Wizard de Competição: Step 5 Categorias

**Data:** 2026-06-21
**Status:** Aprovado

---

## Contexto

O `CompetitionWizardPage.tsx` passa a ter 6 etapas. A Etapa 5 (Categorias) é inserida entre Pontuação (ex-Step 4) e Finalização (ex-Step 5, agora Step 6).

Todo o backend necessário já existe: modelo `Category`, endpoints CRUD em `/competitions/{id}/categories`, `categoriesApi` no frontend e tipo `Category` em `src/types/index.ts`.

---

## Estrutura do Wizard (após a mudança)

| Step | Label | Visibilidade |
|------|-------|-------------|
| 1 | Informações | Sempre |
| 2 | Divulgação | Sempre |
| 3 | WODs | Apenas CrossFit |
| 4 | Pontuação | Sempre |
| 5 | Categorias | Sempre |
| 6 | Finalização | Sempre |

O skip do Hyrox (step 2 → step 4 e 4 → 2) não é alterado. Categorias são válidas para ambos os tipos de evento.

---

## Comportamento por Modo

### Modo criação (`isEdit === false`)

A etapa exibe um banner de aviso:

> "Categorias ficam disponíveis após criar a competição."

Formulário de adição desabilitado. Lista vazia. Comportamento idêntico ao dos uploads de logo/banner.

### Modo edição (`isEdit === true`)

CRUD completo disponível. A lista é carregada via `categoriesApi.list(id)` no `useEffect` existente.

---

## UI da Etapa 5

### Lista de categorias

Uma linha por categoria com:
- Nome
- Badge de tipo: `Individual` / `Equipe`
- Badge de gênero: `Masculino` / `Feminino` / `Misto` (omitido se nulo)
- Faixa etária: `18–40` (exibida somente se `age_restriction_enabled`)
- Botão ✏️ Editar
- Botão 🗑 Desativar

Estado vazio: "Nenhuma categoria cadastrada ainda."

### Edição inline

Ao clicar em Editar, a linha se transforma em formulário com os campos pré-preenchidos:
- Mesmos campos do formulário de criação (ver abaixo)
- Botão "Salvar" → `PATCH /competitions/{id}/categories/{categoryId}` → atualiza linha na lista
- Botão "Cancelar" → restaura a linha sem chamar a API

### Formulário de criação (abaixo da lista)

Campos:

| Campo | Tipo | Obrigatório | Condição |
|-------|------|------------|----------|
| Nome | text | sim | sempre |
| Tipo | select (individual / team) | sim | sempre |
| Gênero | select (null / male / female / mixed) | não | sempre |
| Restringir por idade | toggle | não | sempre |
| Idade mínima | number (0–120) | não | somente se toggle ativo |
| Idade máxima | number (0–120) | não | somente se toggle ativo |
| Tamanho máx. de equipe | number (2–50) | não | somente se tipo = team |

Botão "Adicionar Categoria":
- Valida que `name` não está vazio
- Chama `POST /competitions/{id}/categories`
- Acrescenta a categoria retornada à lista
- Limpa o formulário

### Desativar

Chama `PATCH /competitions/{id}/categories/{id}` com `{ is_active: false }` (não remove do banco — regra de negócio existente). A categoria desativada some da lista (filtra `is_active === true`).

---

## Estado Local Adicionado

```typescript
interface WizardStep5 {
  categories: Category[];
}
```

Adicionado ao `WizardState` e ao `INITIAL_STATE` (`step5: { categories: [] }`).

Carregado no `useEffect` existente junto com `step2` e `step3` (apenas em modo edição).

---

## Atualização do Resumo (Step 6)

Adiciona card ao lado dos cards existentes:

> **Categorias:** X ativas

Exibido sempre (não condicional ao tipo de evento).

---

## Camadas Afetadas

Apenas frontend — sem alterações de backend, sem migrations.

| Arquivo | Mudança |
|---------|---------|
| `frontend/src/pages/CompetitionWizardPage.tsx` | +WizardStep5, estado, useEffect, handlers, render Step 5, resumo Step 6, STEPS array |

---

## Decisões

- Desativar (soft delete) em vez de deletar — consistente com a API existente
- `only_active=true` no `categoriesApi.list` para omitir categorias desativadas da lista
- A lista exibe apenas categorias ativas (`is_active === true`)
- Formulário de criação limpo após cada adição bem-sucedida
- Edição inline sem modal — mais compacto para o contexto de wizard
