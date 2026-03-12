"""Testes unitários para app/core/redis.py.

Estratégia:
- Testes de estado do timer usam fakeredis (sem infraestrutura externa).
- Testes de lock usam Redis real (localhost:6379), pois o Lock do redis-py
  usa scripts Lua (evalsha) que o fakeredis não suporta. Esses testes são
  pulados automaticamente se o Redis não estiver disponível.
- Testes de chave são puramente unitários (sem I/O).
"""

import json

import pytest
import pytest_asyncio
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio import from_url

try:
    import fakeredis.aioredis as fakeredis_async

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False

from app.core.redis import (
    competition_channel,
    delete_timer_state,
    get_timer_state,
    heat_timers_key,
    publish_timer_event,
    set_timer_state,
    timer_key,
    timer_lock,
    timer_lock_key,
)

# ---------------------------------------------------------------------------
# Helpers de chave (puramente unitários, sem I/O)
# ---------------------------------------------------------------------------


def test_timer_key_format():
    assert timer_key(42) == "tempus:timer:42"


def test_timer_lock_key_format():
    assert timer_lock_key(99) == "tempus:lock:timer:99"


def test_heat_timers_key_format():
    assert heat_timers_key(7) == "tempus:heat:7:timers"


def test_competition_channel_format():
    assert competition_channel(1) == "tempus:ws:channel:competition:1"


# ---------------------------------------------------------------------------
# Estado do timer — fakeredis (sem Redis real necessário)
# ---------------------------------------------------------------------------

if FAKEREDIS_AVAILABLE:

    @pytest_asyncio.fixture
    async def fake_redis():
        """Instância fakeredis isolada para cada teste."""
        r = fakeredis_async.FakeRedis(decode_responses=True)
        yield r
        await r.aclose()

    @pytest.mark.asyncio
    async def test_set_and_get_timer_state(fake_redis):
        state = {
            "timer_id": 1,
            "status": "running",
            "version": 1,
            "accumulated_ms": 0,
            "last_resumed_at_utc": "2026-03-11T14:00:00Z",
        }
        await set_timer_state(fake_redis, 1, state)
        result = await get_timer_state(fake_redis, 1)
        assert result == state

    @pytest.mark.asyncio
    async def test_get_timer_state_returns_none_for_missing(fake_redis):
        result = await get_timer_state(fake_redis, 999)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_timer_state(fake_redis):
        state = {"timer_id": 5, "status": "finished"}
        await set_timer_state(fake_redis, 5, state)
        await delete_timer_state(fake_redis, 5)
        result = await get_timer_state(fake_redis, 5)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_timer_state_overwrites_previous(fake_redis):
        await set_timer_state(fake_redis, 2, {"status": "created"})
        await set_timer_state(fake_redis, 2, {"status": "running", "version": 2})
        result = await get_timer_state(fake_redis, 2)
        assert result["status"] == "running"
        assert result["version"] == 2

    @pytest.mark.asyncio
    async def test_publish_timer_event_sends_to_channel(fake_redis):
        """Verifica que publish_timer_event publica no canal correto."""
        published = []
        original_publish = fake_redis.publish

        async def capture_publish(channel, message):
            published.append((channel, message))
            return await original_publish(channel, message)

        fake_redis.publish = capture_publish

        event = {"event_type": "started", "timer_id": 3}
        await publish_timer_event(fake_redis, competition_id=1, event=event)

        assert len(published) == 1
        channel, message = published[0]
        assert channel == "tempus:ws:channel:competition:1"
        assert json.loads(message) == event

else:

    def test_fakeredis_not_installed():
        pytest.skip("fakeredis não instalado — instale com: pip install fakeredis")


# ---------------------------------------------------------------------------
# Lock distribuído — Redis real (usa Lua/evalsha internamente)
# ---------------------------------------------------------------------------

REDIS_TEST_URL = "redis://localhost:6379/15"  # DB 15 dedicado para testes


@pytest_asyncio.fixture(loop_scope="function")
async def real_redis():
    """Conexão Redis real no DB 15 (isolado de produção).

    Cria a conexão dentro do event loop do teste (sem pré-verificação separada)
    para evitar conflito de loops com pytest-asyncio.
    Pulado automaticamente se Redis não estiver disponível.
    """
    r = from_url(REDIS_TEST_URL, decode_responses=True)
    try:
        await r.ping()
    except Exception:
        await r.aclose()
        pytest.skip("Redis não disponível em localhost:6379")

    await r.flushdb()
    yield r
    await r.flushdb()
    await r.aclose()


@pytest.mark.asyncio
async def test_timer_lock_acquires_and_releases(real_redis):
    """Lock deve ser adquirido dentro do bloco e liberado ao sair."""
    key = timer_lock_key(10)

    assert await real_redis.get(key) is None

    async with timer_lock(real_redis, 10):
        value = await real_redis.get(key)
        assert value is not None  # lock ativo

    value_after = await real_redis.get(key)
    assert value_after is None  # lock liberado


@pytest.mark.asyncio
async def test_timer_lock_raises_on_conflict(real_redis):
    """Tentar adquirir lock em timer já bloqueado deve levantar LockError."""
    from redis.exceptions import LockError

    first_lock = real_redis.lock(
        timer_lock_key(20),
        timeout=10.0,
        blocking_timeout=0.01,
    )
    await first_lock.acquire()

    try:
        with pytest.raises(LockError):
            async with timer_lock(real_redis, 20):
                pass
    finally:
        await first_lock.release()


@pytest.mark.asyncio
async def test_timer_lock_releases_on_exception(real_redis):
    """Lock deve ser liberado mesmo quando ocorre exceção no bloco."""
    key = timer_lock_key(30)

    with pytest.raises(ValueError):
        async with timer_lock(real_redis, 30):
            raise ValueError("erro simulado")

    # Lock deve ter sido liberado
    value_after = await real_redis.get(key)
    assert value_after is None
