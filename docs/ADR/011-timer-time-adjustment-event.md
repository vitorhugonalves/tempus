# ADR-011 — Ajuste manual de tempo: evento `adjusted` append-only + `audit_logs`

**Status:** Aceito
**Data:** 2026-10-19

---

## Contexto

Em 2026-10-18 um timer (competição 7) foi finalizado por engano com 33 s,
quando a equipe correu 1h18. Não havia como corrigir pelo sistema: o tipo de
evento `adjusted` existia no enum desde o timer v2 (e `_compute_accumulated_ms`
já o tratava), mas nenhuma rota ou service o criava. A correção foi feita por
SQL direto em produção.

O tempo de um timer não fica numa coluna: ele é **derivado do evento de estado
mais recente** (`paused`, `finished`, `reset`, `cancelled` ou `adjusted`, por
maior `id`). O resultado oficial (`official_results.final_time_ms`) guarda uma
cópia do tempo no momento do `finish`.

## Decisão

`POST /api/v1/timers/{id}/adjust`, **somente admin**, com justificativa
obrigatória. O ajuste:

1. **Insere** um evento `adjusted` com o novo tempo, o admin
   (`triggered_by_id`) e a justificativa (`note`). Nada é apagado ou editado:
   os eventos `paused`/`finished` originais continuam no histórico.
2. Atualiza `official_results.final_time_ms` (cria o registro se o timer for
   anterior ao timer v2 e não tiver um).
3. Grava uma linha em `audit_logs` (`action = "timer.adjusted"`) com o tempo
   anterior e o novo. É o primeiro uso da tabela, que existia sem uso.
4. Publica o evento no canal Redis da competição, para ranking e telas ao vivo.

Só vale para timers `finished`. Ajustar timer pausado/rodando exigiria mexer no
estado quente do Redis e no cálculo do `resume`, e não há caso real que peça isso.

```mermaid
sequenceDiagram
    participant A as Admin (TimersPage)
    participant API as POST /timers/{id}/adjust
    participant S as TimerService.adjust
    participant DB as PostgreSQL
    participant R as Redis pub/sub
    A->>API: final_time_ms + justificativa
    API->>API: require_roles("admin") + validação Pydantic (422)
    API->>S: adjust()
    S->>S: timer_lock; 404 se não existe; 409 se não finished
    S->>DB: INSERT timer_events (adjusted)
    S->>DB: UPDATE official_results.final_time_ms
    S->>DB: INSERT audit_logs (antes/depois)
    S->>R: publish {event_type: adjusted, accumulated_ms}
    R-->>A: WS atualiza card / ranking
```

### Regras de entrada

| Campo | Regra | Constante (`core/constants.py`) |
|---|---|---|
| `final_time_ms` | `> 0` e `<= 24h` | `MAX_ADJUSTED_TIME_MS` |
| `justification` | 10–500 caracteres, sem contar espaços das pontas | `MIN_/MAX_ADJUST_JUSTIFICATION_CHARS` |

O tempo informado é **sem penalidades**; elas continuam somadas à parte no
ranking (`final_seconds = elapsed_seconds + penalidades`).

## Alternativas descartadas

- **Editar o `accumulated_ms` do evento `finished`:** apaga a evidência do
  tempo original e de quem o registrou.
- **Coluna "tempo corrigido" no timer:** cria uma segunda fonte de verdade em
  paralelo à derivação por eventos, que ranking, CSV e PDF teriam que conhecer.

## Consequências

- Ajustes repetidos são permitidos; vale o mais recente (maior `id`).
- **Ordem por `id` é crítica:** se a sequência de `timer_events` ficar
  atrasada (ex.: dados importados com `id` explícito), um evento novo pode
  receber `id` menor e ser ignorado. Na operação normal isso não ocorre.
- `audit_logs` ainda não tem tela de consulta. Por enquanto, consulta via SQL.
