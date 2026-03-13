import pytest
from httpx import AsyncClient


# ── Signup (cadastro aberto) ──────────────────────────────────────────────────


async def test_signup_com_dados_validos_retorna_201_e_seta_cookie(client: AsyncClient):
    """Cadastro aberto com dados válidos cria conta, inicia sessão e retorna 201."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Novo Competidor",
            "email": "novo@example.com",
            "password": "senha-nova-123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "novo@example.com"
    assert data["full_name"] == "Novo Competidor"
    assert data["role"] == "competitor"
    assert "session_id" in response.cookies


async def test_signup_sempre_atribui_role_competitor(client: AsyncClient):
    """Signup aberto deve sempre criar o usuário com role competitor."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Tentativa Admin",
            "email": "tentativa@example.com",
            "password": "senha-tentativa-123",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "competitor"


async def test_signup_com_email_duplicado_retorna_409(
    client: AsyncClient, competitor_user
):
    """Cadastro com e-mail já existente deve retornar 409."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Outro Nome",
            "email": "competidor@example.com",
            "password": "outra-senha-123",
        },
    )
    assert response.status_code == 409
    assert "e-mail" in response.json()["detail"].lower()


async def test_signup_com_senha_curta_retorna_422(client: AsyncClient):
    """Senha com menos de 8 caracteres deve retornar 422 (validação Pydantic)."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Usuário Novo",
            "email": "curta@example.com",
            "password": "curta",
        },
    )
    assert response.status_code == 422


# ── Login e demais rotas de auth ──────────────────────────────────────────────


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
