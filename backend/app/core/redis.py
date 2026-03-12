"""Gerenciamento da conexão Redis e utilitários de estado de timers.

Este módulo é o único ponto de acesso ao Redis no projeto.
Responsabilidades:
- Conexão async via redis-py
- Dependency `get_redis` para injeção nas rotas FastAPI
- Helpers para leitura/escrita do estado quente dos timers
- Lock distribuído para evitar race conditions em operações de timer
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from redis.asyncio import Redis, from_url
from redis.exceptions import LockError

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pool de conexão (singleton por processo)
# ---------------------------------------------------------------------------

_redis_pool: Redis | None = None


async def get_redis_pool() -> Redis:
    """Retorna (ou inicializa) o pool de conexão Redis."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis_pool() -> None:
    """Fecha o pool de conexão — chamado no shutdown da aplicação."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis pool encerrado.")


# ---------------------------------------------------------------------------
# Dependency FastAPI
# ---------------------------------------------------------------------------


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Dependency que injeta a conexão Redis em rotas FastAPI.

    Exemplo de uso:
        redis: Redis = Depends(get_redis)
    """
    pool = await get_redis_pool()
    yield pool


# ---------------------------------------------------------------------------
# Chaves Redis (prefixo por domínio)
# ---------------------------------------------------------------------------


def timer_key(timer_id: int) -> str:
    """Chave do estado ativo de um timer."""
    return f"tempus:timer:{timer_id}"


def timer_lock_key(timer_id: int) -> str:
    """Chave de lock distribuído para operações no timer."""
    return f"tempus:lock:timer:{timer_id}"


def heat_timers_key(heat_id: int) -> str:
    """Chave do set de timer_ids ativos em uma bateria."""
    return f"tempus:heat:{heat_id}:timers"


def competition_channel(competition_id: int) -> str:
    """Canal Redis Pub/Sub para eventos de uma competição."""
    return f"tempus:ws:channel:competition:{competition_id}"


# ---------------------------------------------------------------------------
# Estado do timer no Redis
# ---------------------------------------------------------------------------


async def set_timer_state(
    redis: Redis,
    timer_id: int,
    state: dict[str, Any],
    ttl: int | None = None,
) -> None:
    """Grava o estado completo de um timer no Redis.

    Args:
        redis: Conexão Redis.
        timer_id: ID do timer.
        state: Dicionário com o estado (status, accumulated_ms, etc.).
        ttl: Tempo de expiração em segundos. Usa REDIS_TIMER_TTL_SECONDS se None.
    """
    key = timer_key(timer_id)
    payload = json.dumps(state)
    await redis.set(key, payload, ex=ttl or settings.REDIS_TIMER_TTL_SECONDS)


async def get_timer_state(redis: Redis, timer_id: int) -> dict[str, Any] | None:
    """Lê o estado de um timer do Redis.

    Args:
        redis: Conexão Redis.
        timer_id: ID do timer.

    Returns:
        Dicionário com o estado ou None se não existir.
    """
    key = timer_key(timer_id)
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def delete_timer_state(redis: Redis, timer_id: int) -> None:
    """Remove o estado de um timer do Redis (ex: após cancelamento).

    Args:
        redis: Conexão Redis.
        timer_id: ID do timer.
    """
    await redis.delete(timer_key(timer_id))


# ---------------------------------------------------------------------------
# Lock distribuído
# ---------------------------------------------------------------------------

LOCK_TIMEOUT_SECONDS = 3.0   # TTL máximo do lock no Redis
LOCK_ACQUIRE_TIMEOUT = 2.0   # Tempo máximo esperando para adquirir o lock
LOCK_SLEEP_INTERVAL = 0.05   # Intervalo entre tentativas (50ms)


@asynccontextmanager
async def timer_lock(redis: Redis, timer_id: int):
    """Context manager de lock distribuído para operações em um timer.

    Garante que apenas uma operação simultânea altere o estado do timer,
    evitando race conditions (ex: dois operadores pressionando start ao mesmo tempo).
    Usa o Lock nativo do redis-py que implementa liberação atômica internamente.

    Args:
        redis: Conexão Redis.
        timer_id: ID do timer a ser bloqueado.

    Raises:
        LockError: Se não conseguir adquirir o lock dentro do timeout.

    Exemplo:
        async with timer_lock(redis, timer_id):
            state = await get_timer_state(redis, timer_id)
            ...
            await set_timer_state(redis, timer_id, new_state)
    """
    lock = redis.lock(
        timer_lock_key(timer_id),
        timeout=LOCK_TIMEOUT_SECONDS,
        blocking_timeout=LOCK_ACQUIRE_TIMEOUT,
        sleep=LOCK_SLEEP_INTERVAL,
    )

    acquired = await lock.acquire()
    if not acquired:
        raise LockError(f"Não foi possível adquirir lock para o timer {timer_id}.")

    try:
        yield
    finally:
        try:
            await lock.release()
        except LockError:
            # Lock expirou antes da liberação — não é erro crítico
            logger.warning("Lock do timer %d expirou antes da liberação.", timer_id)


# ---------------------------------------------------------------------------
# Pub/Sub — publicação de eventos de timer
# ---------------------------------------------------------------------------


async def publish_timer_event(
    redis: Redis,
    competition_id: int,
    event: dict[str, Any],
) -> None:
    """Publica um evento de timer no canal da competição.

    Os clientes WebSocket inscritos neste canal receberão o evento
    e atualizarão a interface em tempo real.

    Args:
        redis: Conexão Redis.
        competition_id: ID da competição (define o canal).
        event: Dicionário com o evento a ser publicado.
    """
    channel = competition_channel(competition_id)
    payload = json.dumps(event)
    await redis.publish(channel, payload)
    logger.debug(
        "Evento publicado no canal %s: %s",
        channel,
        event.get("event_type", "unknown"),
    )
