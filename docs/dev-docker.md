# Ambiente de Desenvolvimento com Docker

Este guia descreve como subir o ambiente de desenvolvimento local do Tempus usando Docker Compose, com PostgreSQL como banco de dados.

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) >= 24
- [Docker Compose](https://docs.docker.com/compose/install/) v2 (já incluso no Docker Desktop)

## Serviços

| Serviço    | Imagem             | Porta local |
|------------|--------------------|-------------|
| `postgres`  | postgres:16-alpine | 5432        |
| `redis`     | redis:7-alpine     | 6379        |
| `backend`   | Dockerfile.backend | 8000        |
| `frontend`  | node:20-alpine     | 5173        |

## Configuração inicial (primeira vez)

```bash
# 1. Vá para o diretório docker/
cd docker/

# 2. Copie o arquivo de variáveis de ambiente
cp .env.dev.example .env.dev

# 3. Edite os valores sensíveis
#    No mínimo, altere SECRET_KEY e POSTGRES_PASSWORD
nano .env.dev   # ou vim, code, etc.
```

> **Importante:** `DATABASE_URL` e `REDIS_URL` são injetados automaticamente pelo
> `docker-compose.dev.yml` — não é necessário defini-los no `.env.dev`.

## Subindo o ambiente

```bash
# Dentro de docker/
docker compose -f docker-compose.dev.yml up --build
```

Na primeira execução:

1. As imagens são baixadas e construídas
2. O PostgreSQL sobe e aguarda estar saudável
3. O backend executa `alembic upgrade head` — cria todas as tabelas e roda o seed
4. O seed cria o usuário admin e salva as credenciais em `backend/.temp_cred`
5. O Vite inicia em modo desenvolvimento com hot reload

Para rodar em background:

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

## Primeiro acesso

```bash
# Encontre as credenciais do admin geradas pelo seed
cat ../backend/.temp_cred
```

Acesse o frontend em: **http://localhost:5173**

A API está disponível em: **http://localhost:8000**

Documentação interativa da API: **http://localhost:8000/docs**

## Hot reload

- **Backend:** qualquer alteração em `backend/` é detectada automaticamente pelo uvicorn `--reload`
- **Frontend:** o Vite HMR funciona normalmente — alterações em `frontend/src/` aparecem instantaneamente no browser

## Comandos úteis

```bash
# Ver logs de um serviço específico
docker compose -f docker-compose.dev.yml logs -f backend
docker compose -f docker-compose.dev.yml logs -f frontend

# Parar tudo
docker compose -f docker-compose.dev.yml down

# Parar e remover volumes (reset completo, inclusive o banco)
docker compose -f docker-compose.dev.yml down -v

# Executar uma migration manualmente
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head

# Abrir um shell no backend
docker compose -f docker-compose.dev.yml exec backend bash

# Instalar dependências Python adicionais (reflita no pyproject.toml depois)
docker compose -f docker-compose.dev.yml exec backend pip install <pacote>

# Rodar os testes
docker compose -f docker-compose.dev.yml exec backend pytest

# Rodar o linter
docker compose -f docker-compose.dev.yml exec backend ruff check app/
```

## Acesso direto ao PostgreSQL

```bash
# psql via docker
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U tempus -d tempus
```

Ou use qualquer cliente SQL externo (DBeaver, TablePlus, etc.) apontando para:

- **Host:** `localhost`
- **Porta:** `5432`
- **Banco:** `tempus`
- **Usuário/Senha:** conforme definido em `.env.dev`

## Estrutura dos arquivos

```
docker/
├── docker-compose.yml          # Produção (nginx + SSL)
├── docker-compose.dev.yml      # Desenvolvimento local (este guia)
├── .env.dev.example            # Template de variáveis para dev
├── Dockerfile.backend          # Imagem compartilhada prod/dev
├── Dockerfile.frontend         # Prod apenas (multi-stage + nginx)
└── nginx.conf                  # Prod apenas (SSL/Let's Encrypt)
```

## Diferenças entre dev e produção

| Aspecto          | Dev (`docker-compose.dev.yml`) | Prod (`docker-compose.yml`) |
|------------------|-------------------------------|----------------------------|
| Frontend         | Vite dev server (HMR)         | nginx servindo `/dist`     |
| Código-fonte     | Montado como volume           | Copiado na imagem          |
| Hot reload       | Sim (backend + frontend)      | Não                        |
| SSL/HTTPS        | Não                           | Sim (Let's Encrypt)        |
| Migrations       | Automáticas no boot           | Manual ou CI               |
| Banco de dados   | PostgreSQL local              | PostgreSQL local           |

## Troubleshooting

### `alembic upgrade head` falha na inicialização

O banco pode ainda não estar pronto. Suba apenas o postgres primeiro e aguarde:

```bash
docker compose -f docker-compose.dev.yml up postgres redis -d
# aguarde os healthchecks passarem
docker compose -f docker-compose.dev.yml up backend frontend
```

### Porta já em uso

Se `5173`, `8000`, `5432` ou `6379` já estiverem ocupadas, edite as portas no
`docker-compose.dev.yml` (seção `ports:` de cada serviço).

### `node_modules` corrompidos ou desatualizados

O volume `frontend-node-modules` isola os módulos do SO do host. Se houver problemas:

```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up --build
```

### Alterações no `pyproject.toml` não refletem

O volume monta o código, mas as dependências Python são instaladas no build. Após adicionar
uma dependência, reconstrua a imagem do backend:

```bash
docker compose -f docker-compose.dev.yml up --build backend
```
