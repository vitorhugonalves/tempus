"""Exclusividade de equipe entre baterias — regra válida apenas para Hyrox.

Em Hyrox cada equipe corre uma única vez, então não pode estar em duas
baterias da mesma competição. Em CrossFit a mesma equipe participa de várias
baterias (uma por WOD), então a regra não se aplica.
"""

from httpx import AsyncClient

from app.models.heat import Heat, HeatTeam

# ── Helpers ─────────────────────────────────────────────────────────────────


async def _create_competition(client: AsyncClient, token: str, event_type: str) -> int:
    r = await client.post(
        "/api/v1/competitions",
        json={"name": f"Copa {event_type}", "event_type": event_type},
        cookies={"session_id": token},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_team(client: AsyncClient, token: str, competition_id: int) -> int:
    r = await client.post(
        f"/api/v1/competitions/{competition_id}/categories",
        json={"name": "Dupla", "category_type": "team", "max_team_size": 2},
        cookies={"session_id": token},
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        f"/api/v1/competitions/{competition_id}/teams",
        json={"name": "Equipe Alpha", "category_id": r.json()["id"]},
        cookies={"session_id": token},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _create_heat(
    client: AsyncClient, token: str, competition_id: int, name: str
) -> int:
    r = await client.post(
        f"/api/v1/competitions/{competition_id}/heats",
        json={"name": name},
        cookies={"session_id": token},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_team(
    client: AsyncClient, token: str, competition_id: int, heat_id: int, team_id: int
):
    return await client.post(
        f"/api/v1/competitions/{competition_id}/heats/{heat_id}/teams",
        json={"team_id": team_id},
        cookies={"session_id": token},
    )


# ── Vínculo manual (POST /heats/{id}/teams) ─────────────────────────────────


async def test_add_team_hyrox_team_already_in_other_heat_returns_409(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "hyrox")
    team_id = await _create_team(client, admin_token, comp_id)
    heat_1 = await _create_heat(client, admin_token, comp_id, "Bateria 1")
    heat_2 = await _create_heat(client, admin_token, comp_id, "Bateria 2")

    first = await _add_team(client, admin_token, comp_id, heat_1, team_id)
    assert first.status_code == 201, first.text

    second = await _add_team(client, admin_token, comp_id, heat_2, team_id)
    assert second.status_code == 409
    assert "Bateria 1" in second.json()["detail"]


async def test_add_team_hyrox_after_removed_from_other_heat_returns_201(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "hyrox")
    team_id = await _create_team(client, admin_token, comp_id)
    heat_1 = await _create_heat(client, admin_token, comp_id, "Bateria 1")
    heat_2 = await _create_heat(client, admin_token, comp_id, "Bateria 2")

    await _add_team(client, admin_token, comp_id, heat_1, team_id)
    removed = await client.delete(
        f"/api/v1/competitions/{comp_id}/heats/{heat_1}/teams/{team_id}",
        cookies={"session_id": admin_token},
    )
    assert removed.status_code == 204

    moved = await _add_team(client, admin_token, comp_id, heat_2, team_id)
    assert moved.status_code == 201, moved.text


async def test_add_team_crossfit_team_already_in_other_heat_returns_201(
    client: AsyncClient, admin_token: str
):
    comp_id = await _create_competition(client, admin_token, "crossfit")
    team_id = await _create_team(client, admin_token, comp_id)
    heat_1 = await _create_heat(client, admin_token, comp_id, "WOD 1 - Bateria 1")
    heat_2 = await _create_heat(client, admin_token, comp_id, "WOD 2 - Bateria 1")

    await _add_team(client, admin_token, comp_id, heat_1, team_id)
    second = await _add_team(client, admin_token, comp_id, heat_2, team_id)
    assert second.status_code == 201, second.text


# ── Importação em lote (POST /admin/bulk/heats) ─────────────────────────────


async def test_bulk_import_heats_hyrox_team_already_in_other_heat_adds_error(
    client: AsyncClient, admin_token: str, db
):
    from sqlalchemy import select

    comp_id = await _create_competition(client, admin_token, "hyrox")
    team_id = await _create_team(client, admin_token, comp_id)
    heat_1 = await _create_heat(client, admin_token, comp_id, "Bateria 1")
    await _add_team(client, admin_token, comp_id, heat_1, team_id)

    csv_content = f"{comp_id};Bateria 2;;Equipe Alpha".encode()
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "Bateria 1" in data["errors"][0]["reason"]

    # A bateria não deve ser criada pela metade (sem a equipe)
    result = await db.execute(select(Heat).where(Heat.name == "Bateria 2"))
    assert result.scalar_one_or_none() is None


async def test_bulk_import_heats_crossfit_team_already_in_other_heat_links_it(
    client: AsyncClient, admin_token: str, db
):
    from sqlalchemy import select

    comp_id = await _create_competition(client, admin_token, "crossfit")
    team_id = await _create_team(client, admin_token, comp_id)
    heat_1 = await _create_heat(client, admin_token, comp_id, "WOD 1")
    await _add_team(client, admin_token, comp_id, heat_1, team_id)

    csv_content = f"{comp_id};WOD 2;;Equipe Alpha".encode()
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.json()["created_count"] == 1

    result = await db.execute(select(HeatTeam).where(HeatTeam.team_id == team_id))
    assert len(result.scalars().all()) == 2
