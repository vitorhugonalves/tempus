# CLAUDE.md — Tempus

Arquivo de contexto do projeto para uso conjunto entre Vitor e Claude.
Versão do documento de referência: **v4.1 — Março 2026**

---

## Sobre este arquivo

Este arquivo é a fonte de verdade do projeto para o Claude. Toda vez que iniciarmos
uma sessão de trabalho, este arquivo deve estar em contexto. Ele contém arquitetura,
decisões técnicas, regras de trabalho e o estado atual do projeto.

**Quando houver dúvida sobre qualquer decisão de design, consulte este arquivo primeiro.**
Se a resposta não estiver aqui, pergunte antes de implementar.

---

## O que é o Tempus

**Tempus** é um gerenciador de timers online para competições esportivas (e.g., Hyrox, CrossFit).
Suporta até **300 atletas por evento**, com quatro perfis de acesso distintos e operação via web.

**Problema que resolve:** elimina a gestão manual de atletas, pontuações, ranking, geração de súmulas e timers.
---

## Regras de Trabalho

### Segurança em primeiro lugar

**Nunca implemente nada inseguro.** Se uma feature puder ser feita de forma segura ou
de forma rápida-mas-insegura, escolha sempre a segura. Se não souber como implementar
algo de forma segura, diga antes de escrever código.

Regras concretas:
- Senhas de usuário **nunca** reversíveis. Sempre bcrypt rounds=12 (hash unidirecional) + pepper.
- Tokens de resets de senhas são de **uso único**. Invalide imediatamente após uso.
- Inputs do usuário sempre validados e sanitizados antes de qualquer execução.

### Código mantido por humanos

Este código será lido, modificado e debugado por pessoas. Otimize para clareza, não para esperteza.

- **Funções pequenas com nomes descritivos.** Se o nome não explica o que faz, renomeie.
- **Um nível de abstração por função.** Não misture lógica de negócio com queryset com formatação de resposta.
- **Comentários explicam o porquê, não o quê.** O código já diz o quê.
- **Sem magic numbers ou magic strings.** Use constantes nomeadas em `core/constants.py`.
- **Erros explícitos.** Prefira `raise ValueError("credencial não encontrada para device_id=X")` a `return None` silencioso.

### Regras de UI/UX

- **Todo item permite edição.** Nem todo item permite deleção.
  - Sempre implemente botão/modal de edição para qualquer entidade cadastrada.
  - Deleção é opcional e depende da regra de negócio de cada entidade.
- **Frontend sempre incluso no escopo.** Toda feature nova deve contemplar o frontend na mesma sessão de desenvolvimento. Durante o brainstorming, incluir seção de frontend no design. No plano de implementação, incluir tasks de frontend para cada feature de backend.

### Como trabalhamos juntos

- Vitor toma as decisões de produto e arquitetura. Claude implementa e questiona quando necessário.
- Se Claude identificar um problema de segurança, **para tudo e reporta antes de continuar**.
- Se Claude identificar uma decisão de arquitetura que conflita com este arquivo, **aponta o conflito antes de implementar**.
- Mudanças de arquitetura relevantes são documentadas neste arquivo antes de ir para o código.
- Commits atômicos: uma coisa por commit, mensagem no formato `módulo: o que foi feito`.

### Manutenção da memória do projeto

**Ao concluir qualquer sessão de desenvolvimento — incluindo subagentes — o Claude DEVE atualizar a memória do projeto.**

O arquivo a manter é:
`~/.claude/projects/-home-vitoralves-projects-seumikrotik/memory/project_state.md`

Regras:
- Qualquer módulo novo implementado deve ser adicionado à lista de módulos implementados.
- Qualquer decisão arquitetural nova deve ser registrada.
- Pendências resolvidas devem ser removidas da seção de pendências.
- Pendências novas descobertas durante a implementação devem ser adicionadas.
- O `MEMORY.md` (`~/.claude/projects/-home-vitoralves-projects-seumikrotik/memory/MEMORY.md`) deve refletir o índice atualizado.

**Esta atualização é obrigatória, não opcional. Não conclua uma sessão sem atualizar a memória.**

---

## Decisões Arquiteturais (não reverter sem discussão)

| Decisão | Escolha | Motivo |
|---|---|---|
| Arquitetura | Monolito Modular (Majestic Monolith) | Projeto simples e sem grande escala |
| Backend | Python 3.12 + FastAPI | Stack conhecida, ecossistema rico para rede/infra |
| Hash de senhas de usuário | bcrypt (rounds=12) + pepper | Hash unidirecional. Nunca armazenar senha em texto plano ou hash fraco |

---

## Estrutura do Projeto Django

```
tempus/
├── backend/
│   ├── app/
│   │   ├── api/                  # Routers FastAPI (um arquivo por domínio)
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── users.py
│   │   │   │   ├── competitions.py
│   │   │   │   ├── timers.py
│   │   │   │   ├── judges.py
│   │   │   │   └── reports.py
│   │   │   └── deps.py           # Dependências compartilhadas (get_session, get_current_user)
│   │   ├── core/
│   │   │   ├── config.py         # Settings via pydantic-settings
│   │   │   ├── security.py       # Hash de senha, geração de token de sessão
│   │   │   └── session.py        # Gerenciamento de sessão server-side
│   │   ├── db/
│   │   │   ├── base.py           # Base declarativa SQLAlchemy
│   │   │   ├── session.py        # Engine + SessionLocal
│   │   │   └── migrations/       # Scripts Alembic
│   │   ├── models/               # Modelos ORM (SQLAlchemy)
│   │   ├── schemas/              # Schemas Pydantic (request/response)
│   │   ├── services/             # Lógica de negócio (sem acesso direto ao ORM)
│   │   ├── repositories/         # Acesso ao banco (queries isoladas)
│   │   └── main.py               # Criação da app FastAPI
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                  # Chamadas HTTP (axios / fetch)
│   │   ├── components/           # Componentes reutilizáveis
│   │   ├── pages/                # Páginas por rota
│   │   ├── hooks/                # Custom hooks
│   │   ├── store/                # Estado global (Zustand ou Context)
│   │   ├── types/                # Tipos TypeScript
│   │   └── utils/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── docs/
│   ├── REQUIREMENTS.md
│   ├── ADR/                      # Architecture Decision Records
│   └── api/                      # Especificação OpenAPI exportada
├── CLAUDE.md                     # Este arquivo
└── README.md
└── .gitignore                    # Especificações de arquivos que não devem ser enviados para o Git.
```

**Regra:** módulos se comunicam apenas por `services.py` ou `selectors.py` internos.
Nunca importe um `Model` de outro módulo diretamente. Se precisar de dado de outro módulo,
crie uma função de serviço explícita.

---

### Princípios Arquiteturais

- **Testes são a esseência do projeto:** todas regras de negócio devem ser validadas por testes. Nenhum commit ou versão nova, poderá seguir sem passar em todos os testes.
- **Segurança no DNA:** Mesmo sendo um projeto "simples", a segurança deve estar enraizada nos códigos gerados. 
- **Separação de camadas:** `api` → `services` → `repositories` → `models`. Nunca pule camadas.
- **Services são o coração:** toda regra de negócio vive nos services. Routers apenas delegam.
- **Repositories isolam o ORM:** queries ficam em repositories, não em services ou routers.
- **Schemas Pydantic** são usados exclusivamente para entrada/saída da API. Modelos ORM nunca vazam para o cliente.

---

## 3. Convenções de Código e Estilo

### Python (Backend)

- **Formatador:** `ruff format` (substitui Black)
- **Linter:** `ruff check` com regras: `E, W, F, I, B, UP, N`
- **Type hints:** obrigatórios em todas as funções públicas
- **Docstrings:** obrigatórias em services e repositories (formato Google Style)
- **Async:** usar `async def` em todas as rotas e funções de I/O
- **Variáveis de ambiente:** sempre via `app/core/config.py` (pydantic-settings), nunca `os.environ` diretamente

```python
# ✅ Correto
async def get_competition(competition_id: int, db: AsyncSession) -> Competition:
    """Busca uma competição pelo ID.

    Args:
        competition_id: Identificador único da competição.
        db: Sessão assíncrona do banco de dados.

    Returns:
        Objeto Competition ou lança HTTPException 404.
    """
    ...

# ❌ Errado — sem type hints, sem async, sem docstring
def get_competition(id, db):
    ...
```

- **Nomes:** `snake_case` para variáveis/funções, `PascalCase` para classes, `UPPER_SNAKE_CASE` para constantes
- **Imports:** agrupados na ordem: stdlib → third-party → local, separados por linha em branco

### TypeScript / React (Frontend)

- **Formatador:** Prettier
- **Linter:** ESLint (airbnb-typescript ou eslint-config-react-app)
- **Componentes:** sempre funcionais com hooks; proibido class components
- **Nomenclatura:** componentes em `PascalCase`, hooks em `useCamelCase`, utilitários em `camelCase`
- **Props:** tipar com `interface` (preferível a `type` para props de componentes)
- **Estilo:** TailwindCSS ou CSS Modules — sem CSS-in-JS inline extenso

---

## 4. Banco de Dados e Migrações

### ORM e Engine

- Usar **SQLAlchemy 2.x** com sintaxe assíncrona (`AsyncSession`, `async_scoped_session`)
- Abstração de banco via variável de ambiente `DATABASE_URL`:
  - SQLite: `sqlite+aiosqlite:///./tempus.db`
  - PostgreSQL: `postgresql+asyncpg://user:pass@host/db`

### Modelos

- Toda tabela deve ter: `id` (PK inteiro autoincrement), `created_at` e `updated_at` (via `server_default` + `onupdate`)
- Usar `Mapped` e `mapped_column` (SQLAlchemy 2.x declarativo)
- Relacionamentos: sempre declarar `back_populates` explicitamente

```python
class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

### Padrão de Persistência — Unit of Work via `get_db`

**Regra central:** `get_db` é o único responsável pelo `commit` da transação. Repositories e services **nunca** chamam `db.commit()` — apenas `db.flush()` para materializar IDs e disparar constraints dentro da transação aberta.

```python
# app/db/session.py — get_db faz commit ao final da requisição
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()   # ← único commit do ciclo de request
        except Exception:
            await session.rollback()
            raise
```

```python
# ✅ Repository correto — só flush, nunca commit
@staticmethod
async def create(db: AsyncSession, obj: Model) -> Model:
    db.add(obj)
    await db.flush()    # materializa o ID; commit fica com get_db
    await db.refresh(obj)
    return obj

# ❌ Errado — commit dentro do repository quebra o Unit of Work
@staticmethod
async def create(db: AsyncSession, obj: Model) -> Model:
    db.add(obj)
    await db.commit()   # NÃO FAÇA ISSO em repositories/services de request
    await db.refresh(obj)
    return obj
```

**Exceção permitida:** funções utilitárias chamadas **fora do ciclo de request** (jobs, scripts, tarefas agendadas) podem gerenciar seu próprio `commit`, pois não passam pelo `get_db`.

> **Histórico:** a ausência de `commit()` no `get_db` fez com que operações que usavam apenas `flush()` (categorias, timers, penalidades) retornassem 201 mas não persistissem os dados no banco. O bug foi silencioso porque a resposta da API era construída a partir dos objetos em memória (ainda válidos na sessão), não de uma releitura do banco.

### Migrations (Alembic)

- **Toda** alteração de schema deve ser feita via migration Alembic — nunca altere o banco manualmente
- Nomear migrations descritivamente: `alembic revision --autogenerate -m "add_penalty_column_to_results"`
- Revisar o arquivo gerado antes de aplicar (`alembic upgrade head`)
- Migrations devem ser reversíveis: implementar sempre `downgrade()`
- Commits de migration sempre acompanham o código que os utiliza

---

## 5. Autenticação e Sessão

- Autenticação via **sessão server-side** com cookie `HttpOnly; Secure; SameSite=Lax`
- ID de sessão gerado com `secrets.token_urlsafe(32)`
- Sessões armazenadas no banco (tabela `sessions`) ou em Redis (configurável)
- Expiração padrão: **8 horas** (configurável por `SESSION_TTL_SECONDS`)
- Dependência FastAPI `get_current_user` injeta o usuário autenticado em todas as rotas protegidas
- Perfis de acesso (roles): `competitor`, `judge`, `operator`, `admin`
- Decorator de autorização: `require_roles(*roles)` aplicado como dependência FastAPI

```python
@router.post("/timers/{timer_id}/start")
async def start_timer(
    timer_id: int,
    current_user: User = Depends(require_roles("judge", "operator", "admin")),
    db: AsyncSession = Depends(get_db),
):
    ...
```

---

## 6. Testes

### Estrutura

```
tests/
├── unit/           # Testa services e funções puras (sem DB, sem HTTP)
├── integration/    # Testa rotas com DB em memória (SQLite)
└── conftest.py     # Fixtures: app, client, db, usuários por role
```

### Ferramentas

- **Framework:** `pytest` + `pytest-asyncio`
- **HTTP Client:** `httpx.AsyncClient` com `ASGITransport`
- **Banco de testes:** SQLite em memória (`:memory:`) — nunca o banco de produção
- **Cobertura:** `pytest-cov` — meta mínima de **80%** de cobertura

### Convenções

- Nome dos testes: `test_<ação>_<contexto>_<resultado_esperado>`
- Cada teste deve ser independente (sem dependência de ordem de execução)
- Fixtures de usuário para cada role devem estar no `conftest.py` global
- Mocks via `unittest.mock` ou `pytest-mock` — nunca alterar estado global

```python
# ✅ Exemplo de teste de integração
async def test_start_timer_as_judge_returns_200(client, judge_token):
    response = await client.post(
        "/api/v1/timers/1/start",
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 200

async def test_start_timer_as_competitor_returns_403(client, competitor_token):
    response = await client.post(
        "/api/v1/timers/1/start",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403
```

### Executando

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=app --cov-report=html

# Apenas unit
pytest tests/unit/

# Verbose
pytest -v
```

---

## 7. Fluxo de Git e PRs

### Branches

| Tipo | Padrão | Exemplo |
|------|--------|---------|
| Feature | `feat/<descricao-curta>` | `feat/timer-controls` |
| Bugfix | `fix/<descricao-curta>` | `fix/session-expiry` |
| Hotfix | `hotfix/<descricao-curta>` | `hotfix/crash-on-start` |
| Migration | `db/<descricao-curta>` | `db/add-penalty-table` |
| Docs | `docs/<descricao-curta>` | `docs/update-readme` |

- Branch principal: `main` (produção)
- Branch de desenvolvimento: `develop`
- PRs sempre saem de feature branches para `develop`
- `develop` → `main` apenas via release PR revisado

### Commits (Conventional Commits)

```
<tipo>(<escopo>): <descrição curta em português>

[corpo opcional]

[rodapé opcional: BREAKING CHANGE, closes #issue]
```

**Tipos:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `db`

```bash
# Exemplos
feat(timer): adicionar endpoint de início de timer
fix(auth): corrigir expiração de sessão para usuários inativos
db(migrations): adicionar coluna penalty_seconds em results
test(judge): adicionar testes de autorização para controle de timer
```

### Checklist de PR

Antes de abrir um PR, verificar:
- [ ] `ruff check` e `ruff format` sem erros
- [ ] Testes passando (`pytest`)
- [ ] Cobertura não reduziu abaixo de 80%
- [ ] Migration acompanha o código (se houver mudança de schema)
- [ ] `REQUIREMENTS.md` atualizado se houver nova feature
- [ ] Sem secrets ou credenciais no código

---

## 8. Variáveis de Ambiente

Sempre usar `.env` local (nunca commitar). Copiar de `.env.example`:

```dotenv
# App
APP_ENV=development          # development | production
SECRET_KEY=troque-isso       # usado para assinar cookies
SESSION_TTL_SECONDS=28800    # 8 horas

# Banco de dados
DATABASE_URL=sqlite+aiosqlite:///./tempus.db

# Email (para convite de competidores)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

---

## 9. Regras Gerais para o Assistente (Claude)

1. **`flush()` em repositories, nunca `commit()`** — o commit pertence exclusivamente ao `get_db`. Ver seção 4 "Padrão de Persistência".
2. **Sempre pergunte** antes de refatorar código existente não relacionado à tarefa
2. **Nunca altere migrações já aplicadas** — crie uma nova se necessário
3. **Siga a estrutura de pastas** definida na seção 2 — não crie arquivos fora do padrão sem justificativa
4. **Testes são obrigatórios** para toda nova funcionalidade implementada
5. **Não use `print()` para logging** — use `logging` ou `structlog`
6. **Documente decisões arquiteturais** relevantes em `docs/ADR/`
7. **Priorize legibilidade** sobre cleverness — código será mantido por humanos
8. **Em caso de dúvida sobre regra de negócio**, interrompa e pergunte antes de implementar
9. **Documentação sempre atualizada** - sempre que houverem mudanças na arquitetura do projeto e/ou no banco de dados documente. Caso ainda não tenha realizado nenhuma documentação, faça-a. Procure sempre realizar a documentação, adicionando topologias com o Mermaid.
10. **Sempre execute os testes** sem perguntar. Caso tenha algum erro nos testes, pergunte antes de ajustar.

---

*Atualizado em: Março 2026 — Vitor + Claude*

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
