"""Testes de integração para as configurações do Box (admin/settings)."""

import pytest
from httpx import AsyncClient

# PNG 1x1 pixel válido (usado para testes de upload de logotipo)
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_get_settings_as_admin_returns_200(client: AsyncClient, admin_token: str):
    """GET /admin/settings retorna 200 com has_logo=False em estado inicial."""
    response = await client.get(
        "/api/v1/admin/settings",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_logo"] is False
    assert "name" in data


@pytest.mark.asyncio
async def test_get_settings_as_non_admin_returns_403(client: AsyncClient, judge_token: str):
    """GET /admin/settings retorna 403 para roles não-admin."""
    response = await client.get(
        "/api/v1/admin/settings",
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_settings_as_admin_persists_data(client: AsyncClient, admin_token: str):
    """PUT /admin/settings persiste nome e dados de contato."""
    payload = {
        "name": "CrossFit Test",
        "address": "Rua Teste, 100",
        "website": "https://crossfittest.com",
        "instagram": "@crossfittest",
    }
    response = await client.put(
        "/api/v1/admin/settings",
        json=payload,
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CrossFit Test"
    assert data["address"] == "Rua Teste, 100"
    assert data["website"] == "https://crossfittest.com"
    assert data["instagram"] == "@crossfittest"


@pytest.mark.asyncio
async def test_update_settings_creates_if_not_exists(client: AsyncClient, admin_token: str):
    """PUT /admin/settings cria registro se não existir (200, não 404)."""
    response = await client.put(
        "/api/v1/admin/settings",
        json={"name": "Novo Box"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Novo Box"


@pytest.mark.asyncio
async def test_upload_logo_as_admin_returns_200(client: AsyncClient, admin_token: str):
    """POST /admin/settings/logo aceita imagem PNG válida."""
    response = await client.post(
        "/api/v1/admin/settings/logo",
        files={"file": ("logo.png", MINIMAL_PNG, "image/png")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_logo"] is True


@pytest.mark.asyncio
async def test_upload_logo_invalid_mime_type_returns_422(client: AsyncClient, admin_token: str):
    """POST /admin/settings/logo rejeita MIME type não-imagem."""
    response = await client.post(
        "/api/v1/admin/settings/logo",
        files={"file": ("arquivo.txt", b"conteudo texto", "text/plain")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_logo_returns_image_bytes(client: AsyncClient, admin_token: str):
    """GET /admin/settings/logo retorna bytes da imagem após upload."""
    # Primeiro faz upload
    await client.post(
        "/api/v1/admin/settings/logo",
        files={"file": ("logo.png", MINIMAL_PNG, "image/png")},
        cookies={"session_id": admin_token},
    )
    # Depois busca sem auth (endpoint público)
    response = await client.get("/api/v1/admin/settings/logo")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_get_logo_when_none_returns_404(client: AsyncClient):
    """GET /admin/settings/logo retorna 404 quando nenhum logotipo configurado."""
    response = await client.get("/api/v1/admin/settings/logo")
    assert response.status_code == 404
