# Fundação Atleta/Equipe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar `Athlete.team_id` obrigatório em todas as competições — todo atleta sempre
pertence a uma equipe (solo = equipe de 1) — com criação automática de equipe quando
necessário, tanto no cadastro individual quanto no import CSV.

**Architecture:** Extensão de schema (`athletes.team_id` NOT NULL) + um resolvedor de
equipe compartilhado entre `AthleteService.create` e `AthleteService.import_csv`, que
busca equipe existente por nome ou cria uma nova a partir de `category_id`. Sem novas
tabelas.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, pytest + httpx.AsyncClient, React/TS.

**Spec:** `docs/superpowers/specs/2026-09-08-rfid-stations-design.md` (seção 2)

## Global Constraints

- `flush()` em repositories, nunca `commit()` — commit é só do `get_db`.
- Toda alteração de schema via migration Alembic revisável, com `downgrade()`.
- Type hints obrigatórios; docstrings Google Style em services/repositories.
- Todo item cadastrado precisa de edição na UI (regra de UI/UX do projeto).
- Commits atômicos, mensagem `módulo: o que foi feito`.
- Rodar `pytest` e `ruff check`/`ruff format` sem perguntar; se algo falhar, parar e perguntar antes de ajustar.

---

## Contexto para quem for implementar

Hoje `backend/app/models/athlete.py::Athlete.team_id` é opcional
(`nullable=True`). Um atleta pode existir sem equipe. Isso muda: **toda competição**
(CrossFit incluído, não só Hyrox) passa a exigir que todo `Athlete` tenha uma equipe —
mesmo que seja uma equipe de uma pessoa só. O import CSV já sabe criar equipe
automaticamente quando falta (`app/services/athlete.py::AthleteService.import_csv`,
linhas 165-189) — vamos extrair essa lógica pra um método compartilhado e usá-la também
no `create()` individual, que hoje não faz isso.

`Team.category_id` é `NOT NULL` no schema (`app/models/team.py:21-23`) — por isso criar
equipe nova sempre exige `category_id` conhecido. Isso não muda; é a restrição que já
existe e orienta o design abaixo.

Banco local (`backend/tempus.db`) tem **0 atletas hoje** — confirmado por query direta
antes deste plano ser escrito. Ainda assim, a migration abaixo é escrita para ser segura
contra dados reais: ela nunca inventa uma categoria para um atleta órfão — aborta com uma
mensagem listando os IDs afetados.

---

## File Structure

- Modify: `backend/app/models/athlete.py` — `team_id` vira `nullable=False`
- Create: `backend/app/db/migrations/versions/20260909_athlete_team_required.py`
- Modify: `backend/app/schemas/athlete.py` — validação em `AthleteCreate`
- Modify: `backend/app/services/athlete.py` — resolvedor de equipe compartilhado
- Modify: `backend/tests/integration/test_athletes.py` — testes existentes ajustados + novos
- Modify: `frontend/src/pages/dashboard/AthletesPage.tsx` — form de criação exige equipe/categoria + modal de edição (nova capacidade)

---

## Task 1: Migration — `athletes.team_id` obrigatório

**Files:**
- Create: `backend/app/db/migrations/versions/20260909_athlete_team_required.py`
- Modify: `backend/app/models/athlete.py:33-35`

**Interfaces:**
- Produces: coluna `athletes.team_id` como `NOT NULL` no schema; nenhuma função nova.

- [ ] **Step 1: Escrever a migration com backfill defensivo**

```python
# backend/app/db/migrations/versions/20260909_athlete_team_required.py
"""athlete team_id required — backfill solo teams for orphan athletes

Revision ID: 20260909_athlete_team_required
Revises: 20260621_wod_walkover
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "20260909_athlete_team_required"
down_revision = "20260621_wod_walkover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    orphans = bind.execute(
        sa.text("SELECT id, name, category_id FROM athletes WHERE team_id IS NULL")
    ).fetchall()

    blocked = [row for row in orphans if row.category_id is None]
    if blocked:
        ids = ", ".join(str(row.id) for row in blocked)
        raise RuntimeError(
            "Não é possível tornar athletes.team_id obrigatório: os atletas com IDs "
            f"[{ids}] não têm equipe NEM categoria — não há como criar uma equipe solo "
            "automaticamente para eles. Atribua uma categoria (ou uma equipe) a esses "
            "atletas manualmente antes de rodar esta migration novamente."
        )

    for row in orphans:
        result = bind.execute(
            sa.text(
                "INSERT INTO teams (competition_id, name, category_id, created_at, updated_at) "
                "SELECT competition_id, :team_name, category_id, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM athletes WHERE id = :athlete_id"
            ),
            {"team_name": f"Equipe {row.name}", "athlete_id": row.id},
        )
        new_team_id = result.lastrowid
        bind.execute(
            sa.text("UPDATE athletes SET team_id = :team_id WHERE id = :athlete_id"),
            {"team_id": new_team_id, "athlete_id": row.id},
        )

    with op.batch_alter_table("athletes") as batch_op:
        batch_op.alter_column("team_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("athletes") as batch_op:
        batch_op.alter_column("team_id", existing_type=sa.Integer(), nullable=True)
```

- [ ] **Step 2: Atualizar o modelo ORM para refletir o schema**

```python
# backend/app/models/athlete.py — trocar a definição existente de team_id (linha ~33)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True
    )
```

> Nota: `ondelete` muda de `SET NULL` pra `RESTRICT` — não faz mais sentido "setar null"
> num campo obrigatório. Remover uma equipe com atletas vinculados agora falha por
> integridade referencial em vez de deixar atletas órfãos silenciosamente. Isso é
> intencional: force o operador a mover os atletas antes de apagar a equipe.

- [ ] **Step 3: Rodar a migration e verificar**

```bash
cd backend && .venv/bin/alembic upgrade head
sqlite3 tempus.db "SELECT sql FROM sqlite_master WHERE name='athletes';"
```

Esperado: a definição da tabela mostra `team_id INTEGER NOT NULL`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/migrations/versions/20260909_athlete_team_required.py backend/app/models/athlete.py
git commit -m "db(athletes): torna team_id obrigatório com backfill de equipe solo"
```

---

## Task 2: Resolvedor de equipe compartilhado no `AthleteService`

**Files:**
- Modify: `backend/app/services/athlete.py`
- Modify: `backend/app/schemas/athlete.py`
- Test: `backend/tests/integration/test_athletes.py`

**Interfaces:**
- Consumes: `CategoryRepository.get_by_id(db, category_id) -> Category | None` (`app/repositories/category.py:12`), `TeamRepository.get_by_name_in_competition(db, competition_id, name) -> Team | None` (`app/repositories/team.py:145`).
- Produces: `AthleteService._resolve_team(db, competition_id, *, team_id, team_name, category_id) -> int` (retorna `team_id` resolvido, ou levanta `HTTPException`). Task 3 (import CSV) reutiliza este método.

- [ ] **Step 1: Escrever o teste que falha — criar atleta sem equipe nem categoria retorna 422**

```python
# backend/tests/integration/test_athletes.py — adicionar ao final do arquivo

async def test_criar_atleta_sem_equipe_nem_categoria_retorna_422(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Sem Vinculo"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 422
    assert "equipe" in r.json()["detail"].lower()


async def test_criar_atleta_com_categoria_cria_equipe_solo_automaticamente(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Carlos Solo", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["team_id"] is not None
    assert data["team_name"] == "Equipe Carlos Solo"


async def test_criar_atleta_com_team_id_existente_usa_equipe_informada(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category,
    db: AsyncSession,
):
    from app.models.team import Team as TeamModel

    team = TeamModel(competition_id=competition.id, name="Equipe Existente", category_id=category.id)
    db.add(team)
    await db.commit()
    await db.refresh(team)

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Maria Vinculada", "team_id": team.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["team_id"] == team.id
```

- [ ] **Step 2: Rodar os testes novos e ver falhar**

```bash
cd backend && .venv/bin/pytest tests/integration/test_athletes.py -k "sem_equipe or solo_automaticamente or usa_equipe_informada" -v
```

Esperado: FAIL — `test_criar_atleta_sem_equipe_nem_categoria_retorna_422` recebe 201 hoje (comportamento antigo); os outros dois falham porque `team_id`/`team_name` não vêm preenchidos.

- [ ] **Step 3: Implementar o resolvedor em `AthleteService`**

```python
# backend/app/services/athlete.py — adicionar import e método novo

from app.models.team import Team
from app.repositories.category import CategoryRepository
from app.repositories.team import TeamRepository


class AthleteService:
    # ... métodos existentes ...

    @staticmethod
    async def _resolve_team(
        db: AsyncSession,
        competition_id: int,
        *,
        team_id: int | None,
        team_name: str | None,
        category_id: int | None,
    ) -> int:
        """Resolve o team_id de um atleta: usa o informado, busca por nome ou cria um novo.

        Todo atleta pertence a uma equipe (mesmo que solo). Se `team_id` for informado,
        é usado diretamente. Caso contrário, tenta localizar uma equipe existente pelo
        nome; se não encontrar, cria uma equipe nova — o que exige `category_id`.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            team_id: ID de equipe existente, se já escolhida explicitamente.
            team_name: Nome de equipe pra buscar/criar quando `team_id` não é informado.
            category_id: Categoria do atleta — obrigatória pra criar equipe nova.

        Returns:
            ID da equipe resolvida ou criada.

        Raises:
            HTTPException 404: `team_id` informado não existe na competição.
            HTTPException 422: Nenhuma equipe pôde ser resolvida (sem team_id, sem nome
                de equipe existente e sem categoria pra criar uma nova).
        """
        if team_id is not None:
            team = await TeamRepository.get_by_id(db, team_id)
            if not team or team.competition_id != competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Equipe não encontrada nesta competição",
                )
            return team_id

        if team_name:
            existing = await TeamRepository.get_by_name_in_competition(
                db, competition_id, team_name
            )
            if existing:
                return existing.id
            if category_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Equipe '{team_name}' não pode ser criada sem categoria válida",
                )
            category = await CategoryRepository.get_by_id(db, category_id)
            if not category or category.competition_id != competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Categoria não encontrada nesta competição",
                )
            new_team = Team(competition_id=competition_id, name=team_name, category_id=category_id)
            db.add(new_team)
            await db.flush()
            await db.refresh(new_team)
            return new_team.id

        # Sem team_id nem nome de equipe: cria equipe solo a partir da categoria
        if category_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Todo atleta precisa de uma equipe. Informe 'team_id' de uma equipe "
                    "existente ou 'category_id' para criar uma equipe solo automaticamente."
                ),
            )
        category = await CategoryRepository.get_by_id(db, category_id)
        if not category or category.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria não encontrada nesta competição",
            )
        return category_id  # placeholder substituído no Step 3b abaixo
```

> O último `return category_id` está errado de propósito — vai ser corrigido no próximo
> passo, junto com o nome da equipe solo (que depende do nome do atleta, não disponível
> dentro de `_resolve_team`). Ajuste:

- [ ] **Step 3b: Corrigir a assinatura para receber o nome do atleta (equipe solo usa `f"Equipe {nome}"`)**

Altere a assinatura de `_resolve_team` para aceitar `athlete_name: str` e troque o último
bloco (`# Sem team_id nem nome de equipe...`) por:

```python
        # Sem team_id nem nome de equipe: cria equipe solo a partir da categoria
        if category_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Todo atleta precisa de uma equipe. Informe 'team_id' de uma equipe "
                    "existente ou 'category_id' para criar uma equipe solo automaticamente."
                ),
            )
        category = await CategoryRepository.get_by_id(db, category_id)
        if not category or category.competition_id != competition_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria não encontrada nesta competição",
            )
        solo_team = Team(
            competition_id=competition_id,
            name=f"Equipe {athlete_name}",
            category_id=category_id,
        )
        db.add(solo_team)
        await db.flush()
        await db.refresh(solo_team)
        return solo_team.id
```

E a assinatura final do método:

```python
    @staticmethod
    async def _resolve_team(
        db: AsyncSession,
        competition_id: int,
        *,
        athlete_name: str,
        team_id: int | None,
        team_name: str | None,
        category_id: int | None,
    ) -> int:
```

- [ ] **Step 4: Usar o resolvedor em `AthleteService.create`**

```python
# backend/app/services/athlete.py — substituir o método create() existente

    @staticmethod
    async def create(db: AsyncSession, competition_id: int, data: AthleteCreate) -> Athlete:
        """Cria um novo atleta, resolvendo (ou criando) a equipe à qual ele pertence.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição à qual o atleta pertence.
            data: Dados do atleta.

        Returns:
            Objeto Athlete criado, sempre com team_id preenchido.
        """
        team_id = await AthleteService._resolve_team(
            db,
            competition_id,
            athlete_name=data.name,
            team_id=data.team_id,
            team_name=None,
            category_id=data.category_id,
        )
        payload = data.model_dump()
        payload["team_id"] = team_id
        athlete = Athlete(competition_id=competition_id, **payload)
        return await AthleteRepository.create(db, athlete)
```

- [ ] **Step 5: Rodar os testes e ver passar**

```bash
cd backend && .venv/bin/pytest tests/integration/test_athletes.py -k "sem_equipe or solo_automaticamente or usa_equipe_informada" -v
```

Esperado: PASS nos três.

- [ ] **Step 6: Ajustar os testes existentes que ficaram inválidos com a nova regra**

`test_criar_atleta_campos_minimos` cria atleta só com `{"name": ...}` — isso agora é 422.
Substitua por uma versão que informa categoria (continua sendo "campos mínimos" dado que
`team_id` nunca foi obrigatório *diretamente*, só via categoria):

```python
async def test_criar_atleta_campos_minimos(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Ana Lima", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Ana Lima"
    assert r.json()["team_id"] is not None
```

`test_listar_atletas_filtra_por_categoria` cria um segundo atleta "Sem Categoria" sem
`category_id` — isso também é 422 agora. Adicione uma segunda fixture de categoria e use-a:

```python
@pytest.fixture
async def outra_categoria(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Master",
        category_type=CategoryType.individual,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def test_listar_atletas_filtra_por_categoria(
    client: AsyncClient, admin_token: str, competition: Competition,
    category: Category, outra_categoria: Category,
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Com Categoria", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Outra Categoria", "category_id": outra_categoria.id},
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
```

- [ ] **Step 7: Rodar a suíte inteira de `test_athletes.py`**

```bash
cd backend && .venv/bin/pytest tests/integration/test_athletes.py -v
```

Esperado: todos os testes do arquivo passam (incluindo os ajustados no Step 6; os de CSV
serão ajustados na Task 3).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/athlete.py backend/tests/integration/test_athletes.py
git commit -m "feat(athletes): cria equipe automaticamente ao cadastrar atleta individual"
```

---

## Task 3: `import_csv` usa o mesmo resolvedor — remove o caminho "atleta sem equipe"

**Files:**
- Modify: `backend/app/services/athlete.py`
- Test: `backend/tests/integration/test_athletes.py`

**Interfaces:**
- Consumes: `AthleteService._resolve_team(...)` (Task 2).

- [ ] **Step 1: Atualizar o teste que hoje espera "atleta criado sem equipe"**

O teste `test_importar_atletas_csv_equipe_sem_categoria_nao_cria_equipe` hoje espera
`created == 1` (atleta criado sem equipe) com 1 erro. Isso não é mais válido — sem equipe
resolvível, a linha inteira falha. Substitua por:

```python
async def test_importar_atletas_csv_sem_equipe_nem_categoria_gera_erro_e_nao_cria(
    client: AsyncClient, admin_token: str, competition: Competition
):
    """Sem equipe existente, sem nome de equipe válido e sem categoria: linha inteira falha."""
    csv_content = b"nome;categoria;equipe\nJoao Lima;;Orfaos FC"

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1
    assert "equipe" in data["errors"][0]["error"].lower()


async def test_importar_atletas_csv_sem_coluna_equipe_cria_equipe_solo(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    """Sem coluna 'equipe' no CSV, mas com categoria: cria equipe solo por atleta."""
    csv_content = (
        f"nome;categoria\nPedro Alves;{category.name}\n"
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

    athletes_r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    athlete = athletes_r.json()[0]
    assert athlete["team_name"] == "Equipe Pedro Alves"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && .venv/bin/pytest tests/integration/test_athletes.py -k "sem_equipe_nem_categoria_gera_erro or sem_coluna_equipe_cria_equipe_solo" -v
```

Esperado: FAIL — comportamento atual ainda cria o atleta sem equipe / não cria equipe solo
quando falta a coluna `equipe`.

- [ ] **Step 3: Reescrever o corpo do loop de `import_csv` usando o resolvedor**

```python
# backend/app/services/athlete.py — dentro de import_csv, substituir todo o bloco
# "team_name = ... / if team_name: ... / athlete = Athlete(...)" por:

            team_name = (row.get("equipe") or "").strip() or None

            try:
                resolved_team_id = await AthleteService._resolve_team(
                    db,
                    competition_id,
                    athlete_name=name,
                    team_id=None,
                    team_name=team_name,
                    category_id=category_id,
                )
            except HTTPException as exc:
                errors.append(
                    AthleteBulkError(row=row_num, name=name, error=str(exc.detail))
                )
                continue

            athlete = Athlete(
                competition_id=competition_id,
                name=name,
                email=(row.get("email") or "").strip() or None,
                document=(row.get("documento") or "").strip() or None,
                phone=(row.get("telefone") or "").strip() or None,
                category_id=category_id,
                tshirt_size=tshirt_size,
                team_id=resolved_team_id,
            )
            db.add(athlete)
            created_count += 1
```

Remova o bloco antigo de resolução de `team_id` (linhas 165-189 do arquivo original) e o
`teams_by_name`/`existing_teams` que ele usava, já que `_resolve_team` já busca por nome
via `TeamRepository.get_by_name_in_competition` — não precisa mais do dicionário local.
Mantenha o `import` de `HTTPException` no topo do arquivo (já presente).

> Atenção de performance: `_resolve_team` agora faz uma query por linha do CSV pra checar
> equipe existente por nome, em vez de usar o dicionário `teams_by_name` pré-carregado.
> Para o volume desta feature (dezenas de atletas por importação, não milhares) isso é
> aceitável; não otimize prematuramente.

- [ ] **Step 4: Rodar os testes novos e os antigos de CSV**

```bash
cd backend && .venv/bin/pytest tests/integration/test_athletes.py -v
```

Esperado: todos passam, incluindo `test_importar_atletas_csv_cria_equipe_automaticamente`
e `test_importar_atletas_csv_vincula_equipe_existente` (não deveriam ter sido afetados,
mas confirme).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/athlete.py backend/tests/integration/test_athletes.py
git commit -m "fix(athletes): import CSV exige equipe resolvível, sem atleta órfão"
```

---

## Task 4: Reatribuir equipe de um atleta existente (edição)

**Files:**
- Modify: `backend/app/services/athlete.py`
- Test: `backend/tests/integration/test_athletes.py`

**Interfaces:**
- Consumes: `AthleteRepository.get_or_404` (já existe), `AthleteUpdate` schema (já tem `team_id: int | None`).
- Produces: `AthleteService.update` valida o novo `team_id` antes de aplicar (não aceita `team_id=None` explícito, já que o campo é obrigatório).

- [ ] **Step 1: Escrever o teste que falha**

```python
async def test_editar_atleta_reatribui_equipe(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category,
    db: AsyncSession,
):
    from app.models.team import Team as TeamModel

    nova_equipe = TeamModel(competition_id=competition.id, name="Nova Equipe", category_id=category.id)
    db.add(nova_equipe)
    await db.commit()
    await db.refresh(nova_equipe)

    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Reatribuido", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"team_id": nova_equipe.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json()["team_id"] == nova_equipe.id


async def test_editar_atleta_equipe_de_outra_competicao_retorna_404(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category,
    db: AsyncSession,
):
    from app.models.competition import Competition as CompModel, CompetitionStatus
    from app.models.team import Team as TeamModel

    outra_comp = CompModel(name="Outra Comp", status=CompetitionStatus.active)
    db.add(outra_comp)
    await db.commit()
    await db.refresh(outra_comp)
    equipe_alheia = TeamModel(competition_id=outra_comp.id, name="Alheia", category_id=category.id)
    db.add(equipe_alheia)
    await db.commit()
    await db.refresh(equipe_alheia)

    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Vitima", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"team_id": equipe_alheia.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd backend && .venv/bin/pytest tests/integration/test_athletes.py -k "reatribui_equipe or outra_competicao_retorna_404" -v
```

Esperado: FAIL no segundo teste (hoje `update()` aplica `team_id` sem validar a competição
— viraria 200 em vez de 404). O primeiro já deve passar hoje, mas escreva-o mesmo assim
como salvaguarda de regressão.

- [ ] **Step 3: Validar `team_id` em `AthleteService.update`**

```python
# backend/app/services/athlete.py — substituir o método update() existente

    @staticmethod
    async def update(db: AsyncSession, athlete: Athlete, data: AthleteUpdate) -> Athlete:
        """Atualiza dados de um atleta, validando reatribuição de equipe.

        Args:
            db: Sessão assíncrona.
            athlete: Objeto Athlete a atualizar.
            data: Dados de atualização (parcial).

        Returns:
            Objeto Athlete atualizado.

        Raises:
            HTTPException 404: `team_id` informado não pertence à mesma competição.
        """
        updates = data.model_dump(exclude_unset=True)
        if "team_id" in updates and updates["team_id"] is not None:
            team = await TeamRepository.get_by_id(db, updates["team_id"])
            if not team or team.competition_id != athlete.competition_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Equipe não encontrada nesta competição",
                )
        for field, value in updates.items():
            setattr(athlete, field, value)
        return await AthleteRepository.update(db, athlete)
```

- [ ] **Step 4: Rodar os testes**

```bash
cd backend && .venv/bin/pytest tests/integration/test_athletes.py -v
```

Esperado: todos passam.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/athlete.py backend/tests/integration/test_athletes.py
git commit -m "fix(athletes): valida equipe da mesma competição ao reatribuir no edit"
```

---

## Task 5: Frontend — exigir equipe/categoria no cadastro + modal de edição

**Files:**
- Modify: `frontend/src/pages/dashboard/AthletesPage.tsx`
- Modify: `frontend/src/api/athletes.ts`

**Interfaces:**
- Consumes: `athletesApi.update(competitionId, athleteId, data)` (já existe em `api/athletes.ts:11`), `teamsApi.list(competitionId)` (`api/teams.ts:16`).
- Produces: nenhuma interface nova consumida por outro código — é folha da árvore de dependências deste plano.

- [ ] **Step 1: Carregar equipes junto com atletas/categorias**

```tsx
// frontend/src/pages/dashboard/AthletesPage.tsx — imports e estado

import { teamsApi } from "../../api/teams";
import type { Athlete, AthleteCreate, Category, Team, TshirtSize } from "../../types";

// dentro do componente, junto aos outros useState:
const [teams, setTeams] = useState<Team[]>([]);
const [newTeamName, setNewTeamName] = useState("");
const [editingAthlete, setEditingAthlete] = useState<Athlete | null>(null);
const [editForm, setEditForm] = useState<AthleteCreate>({ name: "" });

// no useEffect de carga inicial, adicionar teamsApi.list(id) ao Promise.all
useEffect(() => {
  Promise.all([
    athletesApi.list(id).then((r: any) => r.data ?? r),
    categoriesApi.list(id),
    teamsApi.list(id),
  ])
    .then(([a, c, t]) => { setAthletes(a); setCategories(c); setTeams(t); })
    .catch(() => setError("Erro ao carregar dados"))
    .finally(() => setLoading(false));
}, [id]);
```

- [ ] **Step 2: Substituir o `<select>` de categoria por um bloco equipe+categoria no form de criação**

```tsx
// frontend/src/pages/dashboard/AthletesPage.tsx — dentro do form de criação,
// no lugar do bloco "Categoria" isolado, adicionar antes dele:

            <div>
              <label className="block text-sm font-medium text-gray-700">Equipe *</label>
              <select
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                value={form.team_id ?? ""}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    team_id: e.target.value ? Number(e.target.value) : undefined,
                  }))
                }
              >
                <option value="">Nova equipe (usa a categoria abaixo)</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              {!form.team_id && (
                <p className="mt-1 text-xs text-gray-400">
                  Sem selecionar uma equipe existente, é criada uma equipe solo com o
                  nome do atleta — exige categoria escolhida ao lado.
                </p>
              )}
            </div>
```

O `<select>` de Categoria existente permanece, mas seu rótulo passa a ser `"Categoria *"`
quando `form.team_id` não está setado (equipe nova depende dela). Não é necessário
validar no frontend além de deixar o campo condicionalmente obrigatório visualmente — a
API já retorna 422 com mensagem clara se faltar.

- [ ] **Step 3: Adicionar botão e modal de edição (capacidade que hoje não existe)**

```tsx
// frontend/src/pages/dashboard/AthletesPage.tsx — na célula de Ações, antes do botão Remover

                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => {
                          setEditingAthlete(athlete);
                          setEditForm({
                            name: athlete.name,
                            email: athlete.email ?? undefined,
                            document: athlete.document ?? undefined,
                            phone: athlete.phone ?? undefined,
                            category_id: athlete.category_id ?? undefined,
                            team_id: athlete.team_id,
                            tshirt_size: athlete.tshirt_size ?? undefined,
                          });
                        }}
                        className="mr-3 text-sm font-medium text-primary-600 hover:text-primary-800"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(athlete.id)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Remover
                      </button>
                    </td>
```

```tsx
// frontend/src/pages/dashboard/AthletesPage.tsx — handler + modal, antes do return final

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editingAthlete) return;
    setError(null);
    try {
      const res: any = await athletesApi.update(id, editingAthlete.id, editForm);
      const updated = res.data ?? res;
      setAthletes((p) => p.map((a) => (a.id === updated.id ? updated : a)));
      setEditingAthlete(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao editar atleta");
    }
  }
```

```tsx
      {editingAthlete && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/30">
          <form
            onSubmit={handleEditSave}
            className="w-full max-w-lg space-y-4 rounded-lg bg-white p-6 shadow-xl"
          >
            <h3 className="font-medium">Editar Atleta</h3>
            <Input
              label="Nome *"
              value={editForm.name}
              onChange={(e) => setEditForm((p) => ({ ...p, name: e.target.value }))}
              required
            />
            <div>
              <label className="block text-sm font-medium text-gray-700">Equipe *</label>
              <select
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-sm"
                value={editForm.team_id ?? ""}
                onChange={(e) =>
                  setEditForm((p) => ({ ...p, team_id: Number(e.target.value) }))
                }
                required
              >
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <Button type="submit">Salvar</Button>
              <Button variant="secondary" type="button" onClick={() => setEditingAthlete(null)}>
                Cancelar
              </Button>
            </div>
          </form>
        </div>
      )}
```

- [ ] **Step 4: Testar manualmente no navegador**

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload &
cd frontend && npm run dev
```

Abrir a página de Atletas de uma competição: criar um atleta sem escolher equipe (deve
pedir categoria e criar equipe solo), criar um segundo atleta escolhendo uma equipe
existente, e editar um atleta trocando sua equipe. Confirmar que a coluna "Equipe" reflete
a mudança sem precisar recarregar a página.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/dashboard/AthletesPage.tsx
git commit -m "feat(athletes): exige equipe no cadastro e adiciona edição de atleta"
```

---

## Self-Review

- **Cobertura do spec (seção 2):** `team_id` obrigatório ✓ (Task 1), resolução de equipe
  no create individual ✓ (Task 2), CSV sem caminho órfão ✓ (Task 3), migração com
  auditoria/abort explícito em vez de decisão silenciosa ✓ (Task 1), UI com equipe
  obrigatória + edição ✓ (Task 5). Reatribuição de equipe (Task 4) não estava explícita no
  spec mas é pré-requisito direto da regra global (única forma de corrigir um atleta
  órfão pós-migração sem recriar o registro) — incluída por necessidade da própria tarefa.
- **Placeholders:** nenhum "TBD"/"implementar depois" — todo passo tem código completo.
- **Consistência de tipos:** `_resolve_team` usado identicamente em `create` (Task 2) e
  `import_csv` (Task 3) com a mesma assinatura definida na Task 2, Step 3b.

## Execution Handoff

Plano completo e salvo em `docs/superpowers/plans/2026-09-09-athlete-team-foundation.md`.
