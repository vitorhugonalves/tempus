# ADR-013 — Lock entre processos para `alembic upgrade head`

**Status:** Aceito
**Data:** 2026-10-22

---

## Contexto

O container do backend roda `alembic upgrade head` a cada start
(`docker/Dockerfile.backend`). O Alembic não tem lock próprio: quando uma segunda
execução acontece ao mesmo tempo (execução manual durante o restart, ou réplicas
subindo juntas), as duas leem a mesma revisão e aplicam o mesmo DDL.

Incidentes em produção:

- **2026-09-11:** `DeadlockDetectedError` no backfill de `20260909_athlete_team_required`.
- **2026-10-22:** `UniqueViolationError` em `pg_class_relname_nsp_index`
  (`report_issuances_id_seq`) ao criar `report_issuances`.

Nos dois casos, o DDL transacional do Postgres desfez a execução perdedora sem deixar
dado parcial. O deploy, porém, falhava de forma intermitente.

## Decisão

`app/db/migration_lock.py::acquire_migration_lock` executa
`SELECT pg_advisory_xact_lock(MIGRATION_ADVISORY_LOCK_KEY)` no Postgres, dentro da
transação das migrations e **antes** de `context.run_migrations()`
(`app/db/migrations/env.py`).

```mermaid
sequenceDiagram
    participant A as Processo A
    participant B as Processo B
    participant PG as Postgres
    A->>PG: BEGIN; pg_advisory_xact_lock(k)
    B->>PG: BEGIN; pg_advisory_xact_lock(k) (espera)
    A->>PG: lê revisão, aplica migrations, COMMIT (libera o lock)
    PG-->>B: lock concedido
    B->>PG: lê revisão (já na head), nada a aplicar, COMMIT
```

- **Lock de transação, não de sessão:** é liberado sozinho no commit ou no rollback,
  então nunca fica preso se o processo morrer.
- **Adquirido antes de ler a revisão:** quem esperou enxerga a head atualizada e não
  reaplica nada.
- **SQLite (testes e dev):** a função não faz nada, porque não há concorrência a tratar.

## Verificação

Testei com um Postgres 16 descartável e 4 `alembic upgrade head` simultâneos por rodada,
partindo de um banco vazio:

- **sem o lock:** 9 de 12 execuções falharam com o mesmo `UniqueViolationError`;
- **com o lock:** 0 de 20 falharam, e o banco terminou na head.

## Consequências

- Uma execução concorrente espera a outra terminar, em vez de falhar. Uma migration
  longa atrasa o start das outras réplicas pelo mesmo tempo.
- Toda execução de migration do Tempus precisa passar pelo `env.py` para usar a mesma
  chave (`MIGRATION_ADVISORY_LOCK_KEY` em `app/core/constants.py`).
