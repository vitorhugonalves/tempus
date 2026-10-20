# Design — Wizard de Competição: Etapas 2 (Divulgação) e 3 (WODs)

**Data:** 2026-06-20
**Status:** Aprovado

---

## Contexto

O `CompetitionWizardPage.tsx` possui 5 etapas. As etapas 2 e 3 estavam como placeholder. Este spec cobre a implementação completa de ambas.

---

## Etapa 2 — Divulgação

### Campos adicionados ao modelo `Competition`

| Campo | Tipo SQL | Nullable |
|---|---|---|
| `description` | Text | sim |
| `regulations_url` | String(500) | sim |
| `registration_url` | String(500) | sim |
| `instagram_url` | String(200) | sim |
| `whatsapp_url` | String(200) | sim |
| `logo_data` | LargeBinary | sim |
| `logo_mime_type` | String(50) | sim |
| `banner_data` | LargeBinary | sim |
| `banner_mime_type` | String(50) | sim |

### Endpoints

| Método | Path | Descrição |
|---|---|---|
| `PATCH` | `/api/v1/competitions/{id}` | Já existe — receberá campos novos |
| `POST` | `/api/v1/competitions/{id}/logo` | Upload binário (PNG/JPEG/GIF/WebP, max 5 MB) |
| `GET` | `/api/v1/competitions/{id}/logo` | Serve imagem pública (sem auth) |
| `POST` | `/api/v1/competitions/{id}/banner` | Upload binário (PNG/JPEG/GIF/WebP, max 5 MB) |
| `GET` | `/api/v1/competitions/{id}/banner` | Serve imagem pública (sem auth) |

Upload segue o padrão de `POST /admin/settings/logo`: `UploadFile`, validação de MIME, limite de 5 MB, armazenamento binário no banco.

### Frontend — campos da Etapa 2

- Toggle `is_public` — "Tornar competição pública"
- Textarea `description` — descrição da competição
- Input `regulations_url` — URL do regulamento
- Input `registration_url` — URL de inscrições externas
- Input `instagram_url`
- Input `whatsapp_url`
- Upload de logo: botão + preview inline (via `GET /competitions/{id}/logo`)
- Upload de banner: idem

Upload de imagem no wizard: a competição só é persistida no banco ao clicar em "Criar Campeonato" (Etapa 5). Por isso:
- **Criação nova** (`isEdit === false`): campos de logo e banner aparecem desabilitados com tooltip "Disponível após criar a competição".
- **Edição** (`isEdit === true`): upload disponível imediatamente (competição já existe no banco).

---

## Etapa 3 — WODs

### Escopo

Só exibida quando `event_type === "crossfit"`. Quando `event_type === "hyrox"`, o wizard avança da Etapa 2 direto para a Etapa 4 (Pontuação), pulando a Etapa 3.

### Novo modelo `Wod`

Tabela: `wods`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK Integer | |
| `competition_id` | FK → competitions | cascade delete |
| `name` | String(200), not null | Ex: "WOD 1 — Grace" |
| `wod_type` | Enum | `amrap`, `for_time`, `emom`, `max_load` |
| `duration_minutes` | Integer, nullable | Duração em minutos (opcional para max_load) |
| `description` | Text, nullable | Movimentos livres em texto |
| `order` | Integer, default 0 | Ordem de exibição |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

Enum PostgreSQL: `CREATE TYPE wodtype AS ENUM ('amrap', 'for_time', 'emom', 'max_load')`

### Endpoints

| Método | Path | Auth | Descrição |
|---|---|---|---|
| `GET` | `/api/v1/competitions/{id}/wods` | público | Lista WODs ordenados por `order` |
| `POST` | `/api/v1/competitions/{id}/wods` | operator/admin | Cria WOD |
| `DELETE` | `/api/v1/competitions/{id}/wods/{wod_id}` | operator/admin | Remove WOD |

### Schemas Pydantic

```python
class WodCreate(BaseModel):
    name: str
    wod_type: WodType
    duration_minutes: int | None = None
    description: str | None = None
    order: int = 0

class WodResponse(BaseModel):
    id: int
    competition_id: int
    name: str
    wod_type: WodType
    duration_minutes: int | None
    description: str | None
    order: int
    created_at: datetime
    updated_at: datetime
```

### Frontend — campos da Etapa 3

- Botão "Adicionar WOD" — appenda novo WOD vazio à lista
- Cada WOD renderiza:
  - Input `name`
  - Select `wod_type` (AMRAP / For Time / EMOM / Max Load)
  - Input numérico `duration_minutes` (opcional)
  - Textarea `description`
  - Botão remover (ícone lixeira)
- WODs são criados via `POST` ao clicar em "Adicionar" e removidos via `DELETE` ao clicar na lixeira
- Ao carregar o wizard em modo edição, WODs são carregados via `GET /competitions/{id}/wods`

---

## Etapa 5 — Resumo (adições)

- Exibe se a competição é pública (`is_public`)
- Exibe contagem de WODs cadastrados (somente para CrossFit)

---

## Camadas afetadas

### Backend
1. `app/models/competition.py` — campos novos
2. `app/models/wod.py` — novo modelo
3. `app/schemas/competition.py` — campos novos em `CompetitionCreate`, `CompetitionUpdate`, `CompetitionResponse`
4. `app/schemas/wod.py` — novo schema
5. `app/repositories/competition.py` — nenhuma mudança esperada (campos novos são automáticos)
6. `app/repositories/wod.py` — novo repositório (`create`, `list_by_competition`, `delete`)
7. `app/services/competition.py` — nenhuma mudança (campos novos chegam via PATCH)
8. `app/services/wod.py` — novo service
9. `app/api/v1/competitions.py` — endpoints de logo, banner e WODs
10. Migration: `20260620_competition_divulgacao_wods.py`

### Frontend
1. `CompetitionWizardPage.tsx` — interfaces `WizardStep2`, `WizardStep3`; lógica de skip do step 3 para Hyrox
2. `src/api/competitions.ts` — funções `uploadLogo`, `uploadBanner`, `listWods`, `createWod`, `deleteWod`

---

## Decisões

- Upload de logo/banner só disponível após criação da competição — simplifica o fluxo sem perda funcional
- WODs persistidos imediatamente (não em buffer) — consistente com o padrão de outras entidades do sistema
- Hyrox pula Etapa 3 no wizard navegando de step 2 → step 4
- `order` dos WODs é definido pela sequência de criação (sem drag-and-drop nesta fase)
