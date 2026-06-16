# Tempus

**Gerenciador de timers e resultados para competições esportivas**

Tempus é uma plataforma web open-source voltada a organizadores de eventos esportivos cronometrados (Hyrox, CrossFit, funcionais em geral). Permite criar competições, gerenciar atletas e equipes, operar timers em tempo real e publicar rankings — tudo sem necessidade de infraestrutura complexa.

---

## Índice

- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Deploy com Docker (recomendado)](#deploy-com-docker-recomendado)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Primeiro Acesso](#primeiro-acesso)
- [Desenvolvimento Local](#desenvolvimento-local)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Contribuindo](#contribuindo)

---

## Funcionalidades

| Área | Destaques |
|---|---|
| **Competições** | Criação via wizard, suporte a múltiplos tipos de evento, categorias por gênero/idade/nível |
| **Atletas e Equipes** | Cadastro manual ou importação em massa via CSV, agrupamento em equipes, inscrição própria por link |
| **Baterias (Heats)** | Grupos de timers iniciados simultaneamente com sincronização exata |
| **Timers** | Iniciar, pausar, retomar, finalizar e reiniciar; estado quente em Redis; contador ao vivo via WebSocket |
| **Penalidades** | Tipos configuráveis por competição (acréscimo de tempo, parada obrigatória) com justificativa obrigatória |
| **Ranking** | Tempo real, ordenado por tempo final (cronometrado + penalidades), filtrável por categoria, acesso público sem login |
| **Relatórios** | Exportação de ranking em CSV e PDF, certificado individual em PDF, imagem para redes sociais |
| **Perfis de acesso** | `admin` · `operator` · `judge` · `competitor` — com permissões granulares por role |

---

## Arquitetura

```mermaid
graph TD
    Browser["Browser / Mobile"]
    FE["Frontend\nReact + Vite\n:5173 (dev) / :80 (prod)"]
    BE["Backend\nFastAPI + SQLAlchemy\n:8000"]
    PG["PostgreSQL 16\n:5432"]
    RD["Redis 7\n:6379"]

    Browser --> FE
    FE -->|"REST /api"| BE
    FE -->|"WebSocket /ws"| BE
    BE --> PG
    BE --> RD
```

**Stack:**

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic |
| Frontend | React 18 · TypeScript · Vite · TailwindCSS |
| Banco de dados | PostgreSQL 16 (produção) · SQLite (desenvolvimento leve) |
| Cache / Tempo real | Redis 7 · WebSocket nativo do FastAPI |
| Containers | Docker · Docker Compose v2 |

---

## Deploy com Docker (recomendado)

> **Pré-requisitos:** [Docker](https://docs.docker.com/get-docker/) >= 24 com Compose v2 (`docker compose version`).

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/tempus.git
cd tempus
```

### 2. Configure as variáveis de ambiente

```bash
# Arquivo de variáveis do backend
cp backend/.env.example backend/.env

# Arquivo de variáveis do Docker Compose
cp docker/.env.example docker/.env   # se existir; caso contrário, crie conforme seção abaixo
```

Edite `backend/.env` com os valores do seu ambiente. **No mínimo altere:**

```dotenv
SECRET_KEY=          # gere com: openssl rand -base64 32
POSTGRES_PASSWORD=   # senha do banco (qualquer string segura)
ADMIN_EMAIL=         # e-mail do usuário administrador inicial
ADMIN_FULL_NAME=     # nome do administrador
```

> Veja a seção [Variáveis de Ambiente](#variáveis-de-ambiente) para a lista completa.

### 3. Configure o SSL (produção)

O nginx de produção usa Let's Encrypt. Edite `docker/nginx.conf` e substitua o domínio:

```nginx
ssl_certificate     /etc/letsencrypt/live/SEU-DOMINIO/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/SEU-DOMINIO/privkey.pem;
```

Monte os certificados no serviço `frontend` em `docker/docker-compose.yml`:

```yaml
frontend:
  volumes:
    - /etc/letsencrypt:/etc/letsencrypt:ro
```

> **Sem SSL?** Para testes em rede local sem HTTPS, veja a seção [Desenvolvimento Local](#desenvolvimento-local) — ela usa Vite diretamente, sem nginx.

### 4. Suba os serviços

```bash
cd docker/
docker compose up --build -d
```

Aguarde todos os serviços ficarem saudáveis (leva cerca de 1–2 minutos na primeira vez):

```bash
docker compose ps
```

Na primeira inicialização, o backend executa automaticamente as migrations (`alembic upgrade head`) e cria o usuário administrador. As credenciais ficam salvas em `backend/.temp_cred`.

### 5. Acesse a aplicação

| Serviço | URL |
|---|---|
| Aplicação | `https://seu-dominio` ou `http://localhost` |
| API (Swagger) | `http://localhost:8000/docs` |
| API (Redoc) | `http://localhost:8000/redoc` |

---

## Variáveis de Ambiente

Todas as variáveis ficam em `backend/.env`. O arquivo `backend/.env.example` contém o template completo.

### Obrigatórias

| Variável | Descrição | Exemplo |
|---|---|---|
| `SECRET_KEY` | Chave para assinatura de cookies e tokens | `openssl rand -base64 32` |
| `DATABASE_URL` | URL de conexão com o banco | `postgresql+asyncpg://user:pass@host:5432/db` |
| `ADMIN_EMAIL` | E-mail do admin criado no seed | `admin@meuevento.com.br` |
| `ADMIN_FULL_NAME` | Nome do admin criado no seed | `João Silva` |

### Opcionais (com padrão)

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_ENV` | `development` | `development` ou `production` — controla cookie Secure e CORS |
| `SESSION_TTL_SECONDS` | `28800` | Tempo de vida da sessão (8 horas) |
| `REDIS_URL` | `redis://localhost:6379/0` | URL de conexão com o Redis |
| `REDIS_TIMER_TTL_SECONDS` | `86400` | TTL do estado do timer no Redis (24 horas) |
| `FRONTEND_URL` | `http://localhost:5173` | URL do frontend (usado em CORS e links de e-mail) |

### E-mail (SMTP)

Deixe em branco para desabilitar envio de e-mails (convites e recuperação de senha ainda funcionam via console).

| Variável | Descrição |
|---|---|
| `SMTP_HOST` | Servidor SMTP (ex: `smtp.gmail.com`) |
| `SMTP_PORT` | Porta SMTP (ex: `587`) |
| `SMTP_USER` | Usuário/e-mail de envio |
| `SMTP_PASSWORD` | Senha do SMTP (use aspas se tiver caracteres especiais) |

### PostgreSQL (Docker Compose)

Definidas no arquivo `docker/.env` (ou `docker/.env.dev` para desenvolvimento):

| Variável | Padrão | Descrição |
|---|---|---|
| `POSTGRES_DB` | `tempus` | Nome do banco |
| `POSTGRES_USER` | `tempus` | Usuário do banco |
| `POSTGRES_PASSWORD` | — | **Obrigatória.** Senha do banco |

---

## Primeiro Acesso

Após subir os serviços, localize as credenciais do administrador:

```bash
cat backend/.temp_cred
```

O arquivo contém o e-mail e a senha gerada automaticamente. Use-os para fazer login na aplicação.

> **Este arquivo nunca é versionado** (está no `.gitignore`). Guarde as credenciais em local seguro ou altere a senha pelo painel após o primeiro login.

### Passos iniciais recomendados

1. Faça login com as credenciais do admin
2. Acesse **Configurações** e altere a senha
3. Crie uma **Competição** pelo wizard (Nome, local, data, tipo de evento)
4. Adicione **Categorias** à competição
5. Importe **Atletas** via CSV ou cadastre manualmente
6. Crie **Baterias** e associe equipes
7. Inicie as baterias no dia do evento — os timers sobem automaticamente

---

## Desenvolvimento Local

Para contribuir com o projeto ou testar mudanças localmente com hot reload.

### Com Docker (recomendado para dev)

```bash
cd docker/
cp .env.dev.example .env.dev
# Edite .env.dev: altere SECRET_KEY e POSTGRES_PASSWORD
nano .env.dev

docker compose -f docker-compose.dev.yml up --build
```

| Serviço | URL |
|---|---|
| Frontend (Vite HMR) | http://localhost:5173 |
| Backend (uvicorn --reload) | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

O código-fonte é montado como volume — qualquer alteração em `backend/` ou `frontend/src/` reflete imediatamente sem rebuild.

### Sem Docker

**Pré-requisitos:** Python 3.12+, Node 20+, PostgreSQL 16+ (ou SQLite para desenvolvimento leve), Redis 7+.

**Backend:**

```bash
cd backend/

# Crie e ative o virtualenv
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# Instale as dependências
pip install -e ".[dev]"

# Configure o ambiente
cp .env.example .env
# Edite .env com sua DATABASE_URL e demais variáveis

# Rode as migrations e suba o servidor
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend/

# Instale as dependências
npm install

# Configure o proxy (crie frontend/.env se necessário)
# BACKEND_URL=http://127.0.0.1:8000

# Suba o servidor de desenvolvimento
npm run dev
```

---

## Estrutura do Projeto

```
tempus/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Routers FastAPI (auth, competitions, timers, athletes…)
│   │   ├── core/            # Config, segurança, sessão
│   │   ├── db/              # Engine SQLAlchemy, get_db, migrations (Alembic)
│   │   ├── models/          # Modelos ORM
│   │   ├── schemas/         # Schemas Pydantic (request/response)
│   │   ├── services/        # Regras de negócio
│   │   ├── repositories/    # Queries isoladas (acesso ao banco)
│   │   └── main.py          # App FastAPI + lifespan (Redis)
│   └── tests/
│       ├── unit/            # Testes de services e funções puras
│       └── integration/     # Testes de rotas com banco em memória
├── frontend/
│   └── src/
│       ├── api/             # Clientes HTTP por domínio
│       ├── components/ui/   # Componentes reutilizáveis (Button, Input, Badge…)
│       ├── pages/           # Páginas por rota
│       ├── store/           # Estado global (Zustand)
│       └── types/           # Tipos TypeScript
├── docker/
│   ├── docker-compose.yml       # Produção
│   ├── docker-compose.dev.yml   # Desenvolvimento local
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── nginx.conf               # Proxy reverso + SPA fallback (SSL)
└── docs/
    ├── dev-docker.md            # Guia detalhado do ambiente Docker dev
    └── ADR/                     # Architecture Decision Records
```

---

## Testes

```bash
cd backend/

# Todos os testes
pytest

# Com relatório de cobertura
pytest --cov=app --cov-report=html
# Relatório em htmlcov/index.html

# Apenas testes unitários
pytest tests/unit/

# Apenas testes de integração
pytest tests/integration/

# Linter
ruff check app/
ruff format --check app/
```

Meta mínima de cobertura: **80%**. O CI rejeita PRs abaixo desse limiar.

---

## Contribuindo

1. Faça um fork e crie um branch a partir de `develop`

   ```bash
   git checkout -b feat/minha-feature
   ```

2. Siga as convenções de código do projeto (ver `CLAUDE.md`)

3. Escreva testes para toda nova funcionalidade

4. Verifique linter e testes antes de abrir o PR:

   ```bash
   ruff check app/ && pytest
   ```

5. Abra o PR para o branch `develop` com descrição do que foi feito e como testar

---

## Licença

Este projeto é open-source. Consulte o arquivo `LICENSE` para os termos de uso.
