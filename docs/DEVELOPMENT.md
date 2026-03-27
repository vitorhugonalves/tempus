# Guia de Desenvolvimento — Tempus

Este documento descreve como configurar o ambiente de desenvolvimento, executar os testes e realizar o deploy do projeto Tempus.

---

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Configuração do Ambiente](#2-configuração-do-ambiente)
3. [Executando os Testes](#3-executando-os-testes)
4. [Deploy em Desenvolvimento](#4-deploy-em-desenvolvimento)
5. [Deploy em Produção](#5-deploy-em-produção)
6. [Variáveis de Ambiente](#6-variáveis-de-ambiente)
7. [Migrações de Banco de Dados](#7-migrações-de-banco-de-dados)

---

## 1. Pré-requisitos

| Ferramenta | Versão mínima | Observação |
|---|---|---|
| Python | 3.12 | Recomendado: 3.14 |
| Node.js | 18 | Recomendado: 20+ |
| npm | 9+ | |
| Git | qualquer | |
| Docker + Docker Compose | 24+ | Necessário para PostgreSQL e Redis via containers |

---

## 2. Configuração do Ambiente

### Backend

```bash
# 1. Entre no diretório do backend
cd backend/

# 2. Crie o ambiente virtual
python -m venv .venv

# 3. Ative o ambiente virtual
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 4. Instale as dependências
pip install -e ".[dev]"

# 5. Copie e edite as variáveis de ambiente
cp .env.example .env
# Edite .env conforme sua necessidade

# 6. Execute as migrações
alembic upgrade head

# 7. Inicie o servidor de desenvolvimento
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API estará disponível em `http://localhost:8000`.
Documentação interativa: `http://localhost:8000/docs`

### Frontend

```bash
# 1. Entre no diretório do frontend
cd frontend/

# 2. Instale as dependências
npm install

# 3. Inicie o servidor de desenvolvimento (com proxy para o backend)
npm run dev
```

O frontend estará disponível em `http://localhost:5173`.

> **Proxy:** O Vite está configurado para encaminhar `/api/*` para `http://localhost:8000`, portanto o backend deve estar rodando.

---

## 3. Executando os Testes

### Testes do Backend

O backend usa `pytest` com `pytest-asyncio`. O banco de dados de teste é SQLite em memória — nenhuma configuração adicional é necessária.

```bash
cd backend/
source .venv/bin/activate

# Executar todos os testes
pytest

# Com saída detalhada
pytest -v

# Apenas testes de integração
pytest tests/integration/ -v

# Apenas testes unitários
pytest tests/unit/ -v

# Com relatório de cobertura (HTML)
pytest --cov=app --cov-report=html
# Relatório em: htmlcov/index.html

# Com relatório de cobertura no terminal
pytest --cov=app --cov-report=term-missing

# Parar ao primeiro erro
pytest -x

# Executar teste específico
pytest tests/integration/test_auth.py::test_login_com_credenciais_validas -v
```

**Meta de cobertura:** ≥ 80%

#### Organização dos testes

```
tests/
├── unit/                   # Testa funções puras e serviços (sem DB, sem HTTP)
│   └── test_security.py
└── integration/            # Testa rotas com banco em memória
    ├── test_auth.py
    ├── test_auth_tokens.py  # Recuperação de senha e convites
    ├── test_categories.py
    ├── test_certificates.py # Certificados PDF e imagens sociais
    ├── test_competitions.py
    ├── test_timers.py
    └── test_users.py
```

### Testes do Frontend

O frontend usa **Vitest** com **React Testing Library**.

```bash
cd frontend/

# Executar todos os testes
npm test

# Modo watch (re-executa ao salvar arquivos)
npm run test:watch

# Com cobertura
npm run test:coverage

# Interface gráfica (Vitest UI)
npm run test:ui
```

> **Nota:** Os testes do frontend verificam componentes individuais e hooks. Testes end-to-end (E2E) com Playwright/Cypress não estão incluídos nesta versão.

### Verificação de qualidade de código (Backend)

```bash
cd backend/
source .venv/bin/activate

# Verificar e corrigir estilo automaticamente
ruff format .

# Verificar regras de linting
ruff check .

# Corrigir problemas automaticamente (quando possível)
ruff check --fix .
```

### Verificação de qualidade de código (Frontend)

```bash
cd frontend/

# Verificar TypeScript
npx tsc --noEmit

# Verificar lint
npm run lint

# Build de produção (também valida TypeScript)
npm run build
```

---

## 4. Deploy em Desenvolvimento

O modo desenvolvimento usa o Vite Dev Server (frontend) e o Uvicorn com `--reload` (backend), cada um rodando em terminais separados.

### Opção A: Processos separados (recomendado para desenvolvimento ativo)

**Terminal 1 — Backend:**
```bash
cd backend/
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend/
npm run dev
```

Acesse: `http://localhost:5173`

### Opção B: Docker Compose (desenvolvimento com containers)

```bash
# Na raiz do projeto

# 1. Configure as variáveis obrigatórias (pode ser em docker/.env ou exportando no shell)
cp docker/.env.example docker/.env
# Edite docker/.env com a senha do PostgreSQL

# 2. Suba todos os serviços (PostgreSQL, Redis, backend, frontend)
docker compose -f docker/docker-compose.yml up --build -d

# 3. Aguarde o backend ficar healthy e aplique as migrações
docker compose -f docker/docker-compose.yml exec backend alembic upgrade head

# 4. Verifique os logs
docker compose -f docker/docker-compose.yml logs -f backend
```

Acesse: `http://localhost` (frontend via Nginx) e `http://localhost:8000` (API)

---

## 5. Deploy em Produção

### Pré-requisitos de produção

- Domínio configurado com HTTPS (obrigatório para cookies `Secure`)
- Variáveis de ambiente configuradas com valores seguros (veja seção 6)
- Banco de dados PostgreSQL (recomendado para produção)

### Opção A: Docker Compose (recomendado)

```bash
# 1. Clone o repositório no servidor
git clone <repo-url> tempus
cd tempus

# 2. Configure as variáveis de ambiente da aplicação
cp backend/.env.example backend/.env
# Edite backend/.env com os valores de produção (SECRET_KEY, SMTP, etc.)

# 3. Configure as variáveis do Docker Compose (PostgreSQL)
cp docker/.env.example docker/.env
# Edite docker/.env — defina POSTGRES_PASSWORD com uma senha forte

# 4. Build e deploy
docker compose -f docker/docker-compose.yml up -d --build

# 5. Execute as migrações (aguarde o backend estar healthy)
docker compose -f docker/docker-compose.yml exec backend alembic upgrade head

# 6. Verifique os logs
docker compose -f docker/docker-compose.yml logs -f
```

> **Nota:** O `DATABASE_URL` no `.env` do backend é **ignorado quando rodando via Docker Compose**, pois o compose injeta a variável `DATABASE_URL` diretamente no container apontando para o serviço `tempus-postgres`. Para desenvolvimento local sem Docker, configure `DATABASE_URL` no `backend/.env` normalmente.

### Opção B: Deploy manual (bare metal)

#### Backend (FastAPI com Uvicorn + Gunicorn)

```bash
cd backend/
source .venv/bin/activate

# Instale apenas dependências de produção
pip install -e .

# Execute as migrações
alembic upgrade head

# Inicie com Gunicorn + workers Uvicorn
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000
```

Para gerenciamento do processo, use **systemd** ou **supervisor**. Exemplo de unit systemd:

```ini
# /etc/systemd/system/tempus-backend.service
[Unit]
Description=Tempus Backend
After=network.target

[Service]
User=tempus
WorkingDirectory=/opt/tempus/backend
Environment="PATH=/opt/tempus/backend/.venv/bin"
ExecStart=/opt/tempus/backend/.venv/bin/gunicorn app.main:app \
  -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable tempus-backend
systemctl start tempus-backend
```

#### Frontend (build estático com Nginx)

```bash
cd frontend/

# Defina a URL da API de produção
echo "VITE_API_BASE_URL=https://api.seudominio.com" > .env.production

# Gere o build de produção
npm run build
# Arquivos em: dist/

# Copie para o diretório do Nginx
cp -r dist/* /var/www/tempus/
```

Configuração Nginx (`/etc/nginx/sites-available/tempus`):

```nginx
server {
    listen 443 ssl http2;
    server_name seudominio.com;

    ssl_certificate     /etc/letsencrypt/live/seudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seudominio.com/privkey.pem;

    root /var/www/tempus;
    index index.html;

    # Frontend (SPA — todas as rotas retornam index.html)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API (proxy reverso para o backend)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redireciona HTTP para HTTPS
server {
    listen 80;
    server_name seudominio.com;
    return 301 https://$host$request_uri;
}
```

---

## 6. Variáveis de Ambiente

Copie `backend/.env.example` para `backend/.env` e ajuste os valores:

### `backend/.env` — Variáveis da aplicação

| Variável | Obrigatória | Exemplo | Descrição |
|---|---|---|---|
| `APP_ENV` | Sim | `production` | `development` ou `production` |
| `SECRET_KEY` | Sim | `<string aleatória longa>` | Chave de assinatura de cookies — gere com `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Sim* | `postgresql+asyncpg://user:pass@host/db` | *Ignorada pelo Docker Compose (sobrescrita pelo compose). Necessária para execução local sem Docker. |
| `SESSION_TTL_SECONDS` | Não | `28800` | Duração da sessão (padrão: 8 horas) |
| `SMTP_HOST` | Não | `smtp.gmail.com` | Servidor SMTP para envio de e-mails |
| `SMTP_PORT` | Não | `587` | Porta SMTP (padrão: 587 com STARTTLS) |
| `SMTP_USER` | Não | `noreply@seudominio.com` | Usuário SMTP |
| `SMTP_PASSWORD` | Não | `senha-app` | Senha SMTP |
| `FRONTEND_URL` | Sim | `https://seudominio.com` | URL base do frontend (usada no backend para gerar links de e-mail) |
| `ADMIN_EMAIL` | Sim | `admin@seudominio.com` | E-mail do administrador inicial (seed) |
| `ADMIN_FULL_NAME` | Não | `Administrador` | Nome do administrador inicial |

### `docker/.env` — Variáveis do Docker Compose (PostgreSQL)

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `POSTGRES_DB` | Não | `tempus` | Nome do banco de dados PostgreSQL |
| `POSTGRES_USER` | Não | `tempus` | Usuário do banco de dados |
| `POSTGRES_PASSWORD` | **Sim** | — | Senha do banco — **nunca use valores fracos em produção** |

> **Segurança:** Nunca comite o arquivo `.env`. Ele já está no `.gitignore`.

### Gerando SECRET_KEY segura

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 7. Migrações de Banco de Dados

O projeto usa **Alembic** para gerenciar o schema do banco de dados.

```bash
cd backend/
source .venv/bin/activate

# Aplicar todas as migrações pendentes
alembic upgrade head

# Ver status atual
alembic current

# Ver histórico de migrações
alembic history --verbose

# Criar nova migração (após alterar modelos SQLAlchemy)
alembic revision --autogenerate -m "descricao_da_mudanca"

# Reverter última migração
alembic downgrade -1

# Reverter para versão específica
alembic downgrade <revision_id>
```

> **Regra:** Toda alteração de schema deve ser feita via migration — nunca altere o banco diretamente. Revise o arquivo gerado pelo `--autogenerate` antes de aplicar.

---

## Estrutura de Logs

Em produção, os logs são gravados em `backend/logs/`:

| Arquivo | Conteúdo |
|---|---|
| `access.log` | Todas as requisições HTTP (formato: `IP - status - método - rota - tempo`) |
| `app.log` | Logs da aplicação (DEBUG, INFO, WARNING, ERROR) |

Para visualizar em tempo real:

```bash
tail -f backend/logs/access.log
tail -f backend/logs/app.log
```
