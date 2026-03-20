# ADR-009 — Correção: double-counting em `accumulated_ms` no `TimerResponse`

**Status:** Aceito
**Data:** 2026-03-20

---

## Contexto

Timers em andamento apresentavam dois sintomas:

1. **Sincronismo divergente ao recarregar a página** — o contador avançava para um valor incorreto (frequentemente o dobro do esperado) a cada reload.
2. **Valor salvo ao finalizar divergia do display em tempo real** — o `final_time_ms` gravado em `official_results` era muito menor que o tempo exibido no frontend no momento em que o juiz clicava em "Finalizar".

## Causa Raiz

O método `TimerResponse.from_orm()` (`app/schemas/timer.py`) calculava `accumulated_ms` de forma incorreta para timers em execução:

```python
# ANTES — ERRADO
if redis_state and t.status == TimerStatus.running:
    accumulated_ms = _compute_accumulated_ms_from_redis(redis_state)
    # = redis_state["accumulated_ms"] + (T_servidor_resposta - T_start)
    started_at_ms = redis_state.get("started_at_ms")  # = T_start (âncora original)
```

Isso resultava em `accumulated_ms` que **já incluía** o tempo decorrido desde o início do segmento atual (`T_start`) até o momento da resposta do servidor (`T_servidor_resposta`).

O frontend, ao receber esses valores, calculava:

```ts
display = accumulated_ms + (Date.now() - started_at_ms)
        = [base + (T_servidor - T_start)] + (T_cliente - T_start)
        //                                   ↑ double-counting desde T_start
```

O intervalo `(T_servidor_resposta − T_start)` era somado duas vezes — uma vez no `accumulated_ms` já calculado no servidor, e outra vez pelo loop `requestAnimationFrame` do frontend com base no mesmo `started_at_ms` original.

### Por que os eventos WebSocket não tinham o bug?

Os eventos `started`/`resumed` publicados no Redis Pub/Sub enviavam corretamente o **baseline** separado da **âncora**:

```python
await publish_timer_event(redis, ..., {
    "event_type": "started",
    "accumulated_ms": accumulated_ms,  # baseline (tempo antes do start atual)
    "started_at_ms": now_ms,           # âncora = momento do start
})
```

O frontend aplicava: `display = baseline + (Date.now() - âncora)` — correto.

O problema ocorria somente nos caminhos REST (`GET /timers`, `GET /timers/{id}`) e na mensagem `init` do WebSocket (que também chama `TimerResponse.from_orm()`), ou seja, em qualquer snapshot carregado após a conexão inicial.

## Decisão

Alterar `TimerResponse.from_orm()` para retornar o **baseline bruto** do Redis em vez do total pré-computado:

```python
# DEPOIS — CORRETO
if redis_state and t.status == TimerStatus.running:
    accumulated_ms = redis_state["accumulated_ms"]        # baseline
    started_at_ms  = redis_state.get("started_at_ms")    # âncora
```

O frontend continua usando a mesma fórmula `accumulated_ms + (Date.now() - started_at_ms)`, que agora é matematicamente consistente com os eventos WebSocket.

```
display = baseline + (Date.now() - âncora)
        = base + (T_cliente_agora - T_start)   ✓ correto
```

## Consequências

- `elapsed_seconds` na resposta REST passa a refletir apenas o baseline (não o tempo vivo). Isso é aceitável pois o frontend usa `displayMs` derivado de `accumulated_ms + (Date.now() - started_at_ms)` para o display; `elapsed_seconds` só é usado como snapshot estático.
- A divergência ao finalizar reduz para `(T_servidor_finish − T_cliente_click)` ≈ latência de rede (tipicamente < 200 ms em produção), imperceptível em um cronômetro de precisão de segundos.
- Nenhum dado histórico é afetado — `official_results` e `timer_events` já eram calculados corretamente no servidor com `time.time()`.
- 208 testes passando após a correção.

## Diagrama

```
ANTES (bugado — reload após 60 s de timer)
─────────────────────────────────────────────────────
   T_start        T_server_resp     T_client_now
     │                 │                 │
─────┼─────────────────┼─────────────────┼──────► tempo
     ←──── 60 s ───────►                 │
     ←─────────────── 60 s ──────────────►
     ↑ somados pelo frontend: display = 120 s ❌

DEPOIS (correto)
─────────────────────────────────────────────────────
   T_start                          T_client_now
     │                                   │
─────┼───────────────────────────────────┼──────► tempo
     ←──────────────── 60 s ─────────────►
     ↑ display = 60 s ✓
```
