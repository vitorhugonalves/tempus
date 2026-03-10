import pytest
from httpx import AsyncClient


async def test_login_com_credenciais_validas_retorna_200(client: AsyncClient, admin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "senha-admin-123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@example.com"
    assert data["role"] == "admin"
    assert "session_id" in response.cookies


async def test_login_com_senha_errada_retorna_401(client: AsyncClient, admin_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "senha-errada"},
    )
    assert response.status_code == 401


async def test_login_com_email_inexistente_retorna_401(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "naoexiste@example.com", "password": "qualquer"},
    )
    assert response.status_code == 401


async def test_me_com_sessao_valida_retorna_dados_do_usuario(
    client: AsyncClient, admin_token: str
):
    response = await client.get(
        "/api/v1/auth/me",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


async def test_me_sem_sessao_retorna_401(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_logout_invalida_sessao(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/api/v1/auth/logout",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204

    # Sessão deve ser inválida após logout
    me_response = await client.get(
        "/api/v1/auth/me",
        cookies={"session_id": admin_token},
    )
    assert me_response.status_code == 401
