from httpx import AsyncClient

# ── Fixtures helpers ──────────────────────────────────────────────────────────


async def _criar_competicao_crossfit(client: AsyncClient, admin_token: str) -> int:
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": "CrossFit Open 2026", "event_type": "crossfit"},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── WODs ──────────────────────────────────────────────────────────────────────


async def test_listar_wods_competicao_vazia_retorna_lista_vazia(
    client: AsyncClient, admin_token: str
):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.get(f"/api/v1/competitions/{comp_id}/wods")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_criar_wod_como_admin_retorna_201(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/wods",
        json={"name": "Fran", "wod_type": "for_time", "duration_minutes": 7},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Fran"
    assert data["wod_type"] == "for_time"
    assert data["competition_id"] == comp_id


async def test_criar_wod_como_competidor_retorna_403(
    client: AsyncClient, competitor_token: str, admin_token: str
):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/wods",
        json={"name": "Grace", "wod_type": "for_time"},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403


async def test_criar_wod_competicao_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/api/v1/competitions/99999/wods",
        json={"name": "Grace", "wod_type": "for_time"},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 404


async def test_deletar_wod_retorna_204(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    criar = await client.post(
        f"/api/v1/competitions/{comp_id}/wods",
        json={"name": "Cindy", "wod_type": "amrap", "duration_minutes": 20},
        cookies={"session_id": admin_token},
    )
    wod_id = criar.json()["id"]

    resp = await client.delete(
        f"/api/v1/competitions/{comp_id}/wods/{wod_id}",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 204

    lista = await client.get(f"/api/v1/competitions/{comp_id}/wods")
    assert lista.json() == []


async def test_deletar_wod_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.delete(
        f"/api/v1/competitions/{comp_id}/wods/99999",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 404


async def test_listar_wods_ordenados_por_order(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    for name, order in [("WOD C", 2), ("WOD A", 0), ("WOD B", 1)]:
        await client.post(
            f"/api/v1/competitions/{comp_id}/wods",
            json={"name": name, "wod_type": "amrap", "order": order},
            cookies={"session_id": admin_token},
        )
    resp = await client.get(f"/api/v1/competitions/{comp_id}/wods")
    nomes = [w["name"] for w in resp.json()]
    assert nomes == ["WOD A", "WOD B", "WOD C"]


# ── Campos de divulgação ──────────────────────────────────────────────────────


async def test_atualizar_campos_divulgacao_retorna_200(
    client: AsyncClient, admin_token: str
):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.patch(
        f"/api/v1/competitions/{comp_id}",
        json={
            "description": "Maior evento CrossFit do Brasil",
            "instagram_url": "https://instagram.com/tempus",
            "whatsapp_url": "https://wa.me/5511999999999",
            "is_public": True,
        },
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Maior evento CrossFit do Brasil"
    assert data["instagram_url"] == "https://instagram.com/tempus"
    assert data["is_public"] is True


async def test_logo_inexistente_retorna_404(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.get(f"/api/v1/competitions/{comp_id}/logo")
    assert resp.status_code == 404


async def test_upload_logo_invalido_retorna_422(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/logo",
        files={"file": ("test.txt", b"not an image", "text/plain")},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 422


async def test_banner_inexistente_retorna_404(client: AsyncClient, admin_token: str):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    resp = await client.get(f"/api/v1/competitions/{comp_id}/banner")
    assert resp.status_code == 404


async def test_upload_banner_invalido_retorna_422(
    client: AsyncClient, admin_token: str
):
    comp_id = await _criar_competicao_crossfit(client, admin_token)
    fake_pdf = b"%PDF-1.4"
    files = {"file": ("test.pdf", fake_pdf, "application/pdf")}
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/banner",
        files=files,
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 422


async def test_listar_wods_competicao_inexistente_retorna_404(client: AsyncClient):
    resp = await client.get("/api/v1/competitions/9999/wods")
    assert resp.status_code == 404
