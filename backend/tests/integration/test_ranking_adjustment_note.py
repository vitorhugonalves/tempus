from httpx import AsyncClient


async def _finished_timer(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
) -> tuple[int, int]:
    """Competição ativa + timer finalizado.

    Função (não fixture) de propósito: fixtures async rodam no loop da sessão e
    prenderiam a conexão do fakeredis a ele.
    """
    comp = (
        await client.post(
            "/api/v1/competitions",
            json={"name": "Comp Justificativa"},
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
    return comp["id"], timer_id


async def _adjust(
    client: AsyncClient, admin_token: str, timer_id: int, justification: str
) -> None:
    r = await client.post(
        f"/api/v1/timers/{timer_id}/adjust",
        json={"final_time_ms": 4_680_000, "justification": justification},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200, r.text


async def test_ranking_entry_without_adjustment_has_null_note(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    comp_id, _ = await _finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    entry = (await client.get(f"/api/v1/competitions/{comp_id}/ranking")).json()[0]
    assert entry["adjustment_note"] is None
    assert entry["adjusted_at"] is None


async def test_ranking_entry_shows_last_adjustment_only(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    comp_id, timer_id = await _finished_timer(
        client, admin_token, judge_token, competitor_user
    )
    await _adjust(client, admin_token, timer_id, "Primeira correção do tempo")
    await _adjust(client, admin_token, timer_id, "Segunda correção — falha na largada")
    entry = (await client.get(f"/api/v1/competitions/{comp_id}/ranking")).json()[0]
    assert entry["adjustment_note"] == "Segunda correção — falha na largada"
    assert entry["adjusted_at"] is not None
