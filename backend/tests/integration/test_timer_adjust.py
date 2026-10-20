"""Ajuste manual de tempo de timer finalizado (só admin, justificativa obrigatória)."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timer import AuditLog, OfficialResult, TimerEvent, TimerEventType

ONE_HOUR_EIGHTEEN_MS = 78 * 60 * 1000
JUSTIFICATION = "Timer finalizado por engano; tempo conferido no cronômetro manual"


async def _create_finished_timer(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
) -> int:
    """Cria competição ativa e um timer já iniciado e finalizado.

    Função (não fixture) de propósito: fixtures async rodam no loop da sessão e
    prenderiam a conexão do fakeredis a ele; o publish do teste rodaria em outro loop.
    """
    comp = (
        await client.post(
            "/api/v1/competitions",
            json={"name": "Comp Ajuste"},
            cookies={"session_id": admin_token},
        )
    ).json()
    await client.patch(
        f"/api/v1/competitions/{comp['id']}",
        json={"status": "active"},
        cookies={"session_id": admin_token},
    )
    timer_id = (
        await client.post(
            "/api/v1/timers",
            json={"competition_id": comp["id"], "user_id": competitor_user.id},
            cookies={"session_id": admin_token},
        )
    ).json()["id"]
    for action in ("start", "finish"):
        r = await client.post(
            f"/api/v1/timers/{timer_id}/{action}",
            json={},
            cookies={"session_id": judge_token},
        )
        assert r.status_code == 200, r.text
    return timer_id


async def _adjust(
    client: AsyncClient,
    token: str,
    timer_id: int,
    final_time_ms: int = ONE_HOUR_EIGHTEEN_MS,
    justification: str = JUSTIFICATION,
):
    return await client.post(
        f"/api/v1/timers/{timer_id}/adjust",
        json={"final_time_ms": final_time_ms, "justification": justification},
        cookies={"session_id": token},
    )


# ── Caminho feliz ───────────────────────────────────────────────────────────


async def test_adjust_finished_timer_as_admin_returns_new_time(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    response = await _adjust(client, admin_token, finished_timer_id)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "finished"
    assert data["accumulated_ms"] == ONE_HOUR_EIGHTEEN_MS


async def test_adjust_finished_timer_updates_official_result_and_event(
    client: AsyncClient,
    admin_token: str,
    judge_token: str,
    competitor_user,
    db: AsyncSession,
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    await _adjust(client, admin_token, finished_timer_id)

    result = (
        await db.execute(
            select(OfficialResult).where(OfficialResult.timer_id == finished_timer_id)
        )
    ).scalar_one()
    assert result.final_time_ms == ONE_HOUR_EIGHTEEN_MS

    last_event = (
        await db.execute(
            select(TimerEvent)
            .where(TimerEvent.timer_id == finished_timer_id)
            .order_by(TimerEvent.id.desc())
            .limit(1)
        )
    ).scalar_one()
    assert last_event.event_type == TimerEventType.adjusted
    assert last_event.accumulated_ms == ONE_HOUR_EIGHTEEN_MS
    assert last_event.note == JUSTIFICATION


async def test_adjust_finished_timer_writes_audit_log(
    client: AsyncClient,
    admin_token: str,
    admin_user,
    judge_token: str,
    competitor_user,
    db: AsyncSession,
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    previous_ms = (
        await db.execute(
            select(OfficialResult.final_time_ms).where(
                OfficialResult.timer_id == finished_timer_id
            )
        )
    ).scalar_one()

    await _adjust(client, admin_token, finished_timer_id)

    log = (
        await db.execute(
            select(AuditLog).where(AuditLog.resource_id == finished_timer_id)
        )
    ).scalar_one()
    assert log.action == "timer.adjusted"
    assert log.resource_type == "timer"
    assert log.actor_user_id == admin_user.id
    assert json.loads(log.before_json) == {"final_time_ms": previous_ms}
    assert json.loads(log.after_json) == {
        "final_time_ms": ONE_HOUR_EIGHTEEN_MS,
        "justification": JUSTIFICATION,
    }


async def test_adjust_finished_timer_reflects_in_ranking(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    timer = (
        await client.get(
            f"/api/v1/timers/{finished_timer_id}", cookies={"session_id": admin_token}
        )
    ).json()

    await _adjust(client, admin_token, finished_timer_id)

    ranking = (
        await client.get(f"/api/v1/competitions/{timer['competition_id']}/ranking")
    ).json()
    entry = next(e for e in ranking if e["timer_id"] == finished_timer_id)
    assert entry["accumulated_ms"] == ONE_HOUR_EIGHTEEN_MS
    assert entry["elapsed_seconds"] == ONE_HOUR_EIGHTEEN_MS // 1000


async def test_adjust_twice_latest_adjustment_wins(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    await _adjust(client, admin_token, finished_timer_id, final_time_ms=5_580_000)
    response = await _adjust(client, admin_token, finished_timer_id)

    assert response.status_code == 200
    assert response.json()["accumulated_ms"] == ONE_HOUR_EIGHTEEN_MS


# ── Autorização ─────────────────────────────────────────────────────────────


async def test_adjust_as_judge_returns_403(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    response = await _adjust(client, judge_token, finished_timer_id)
    assert response.status_code == 403


async def test_adjust_as_operator_returns_403(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
    judge_token: str,
    competitor_user,
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    response = await _adjust(client, operator_token, finished_timer_id)
    assert response.status_code == 403


async def test_adjust_as_competitor_returns_403(
    client: AsyncClient,
    admin_token: str,
    competitor_token: str,
    judge_token: str,
    competitor_user,
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    response = await _adjust(client, competitor_token, finished_timer_id)
    assert response.status_code == 403


async def test_adjust_without_session_returns_401(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    # As fixtures de login deixam o cookie no jar do client; limpa para simular anônimo
    client.cookies.clear()
    response = await client.post(
        f"/api/v1/timers/{finished_timer_id}/adjust",
        json={"final_time_ms": ONE_HOUR_EIGHTEEN_MS, "justification": JUSTIFICATION},
    )
    assert response.status_code == 401


# ── Regras de estado ────────────────────────────────────────────────────────


async def test_adjust_running_timer_returns_409(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    comp = (
        await client.post(
            "/api/v1/competitions",
            json={"name": "Comp Rodando"},
            cookies={"session_id": admin_token},
        )
    ).json()
    await client.patch(
        f"/api/v1/competitions/{comp['id']}",
        json={"status": "active"},
        cookies={"session_id": admin_token},
    )
    timer_id = (
        await client.post(
            "/api/v1/timers",
            json={"competition_id": comp["id"], "user_id": competitor_user.id},
            cookies={"session_id": admin_token},
        )
    ).json()["id"]
    await client.post(
        f"/api/v1/timers/{timer_id}/start", json={}, cookies={"session_id": judge_token}
    )

    response = await _adjust(client, admin_token, timer_id)
    assert response.status_code == 409


async def test_adjust_unknown_timer_returns_404(client: AsyncClient, admin_token: str):
    response = await _adjust(client, admin_token, 999_999)
    assert response.status_code == 404


# ── Validação de entrada ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "justification",
    ["", "          ", "curta", "   abc   "],
    ids=["vazia", "so-espacos", "curta", "curta-com-espacos"],
)
async def test_adjust_with_invalid_justification_returns_422(
    client: AsyncClient,
    admin_token: str,
    judge_token: str,
    competitor_user,
    justification: str,
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    response = await _adjust(
        client, admin_token, finished_timer_id, justification=justification
    )
    assert response.status_code == 422


async def test_adjust_with_too_long_justification_returns_422(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    response = await _adjust(
        client, admin_token, finished_timer_id, justification="x" * 501
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "final_time_ms",
    [0, -1, 24 * 60 * 60 * 1000 + 1],
    ids=["zero", "negativo", "acima-de-24h"],
)
async def test_adjust_with_invalid_time_returns_422(
    client: AsyncClient,
    admin_token: str,
    judge_token: str,
    competitor_user,
    final_time_ms: int,
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    response = await _adjust(
        client, admin_token, finished_timer_id, final_time_ms=final_time_ms
    )
    assert response.status_code == 422


async def test_adjust_invalid_input_does_not_change_result(
    client: AsyncClient,
    admin_token: str,
    judge_token: str,
    competitor_user,
    db: AsyncSession,
):
    finished_timer_id = await _create_finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    before = (
        await db.execute(
            select(OfficialResult.final_time_ms).where(
                OfficialResult.timer_id == finished_timer_id
            )
        )
    ).scalar_one()

    await _adjust(client, admin_token, finished_timer_id, justification="")

    db.expire_all()
    after = (
        await db.execute(
            select(OfficialResult.final_time_ms).where(
                OfficialResult.timer_id == finished_timer_id
            )
        )
    ).scalar_one()
    assert after == before
