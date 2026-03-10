"""Testes de integração para recuperação de senha e convite (RF-05, RF-06, RF-13, RNF-07)."""

import pytest
from httpx import AsyncClient


# ── Recuperação de senha (RF-05) ──────────────────────────────────────────────


async def test_forgot_password_email_inexistente_retorna_204(client: AsyncClient):
    """Não revela se o e-mail existe (sempre retorna 204)."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "naoexiste@example.com"},
    )
    assert response.status_code == 204


async def test_forgot_password_email_existente_retorna_204(
    client: AsyncClient, admin_user
):
    """E-mail válido também retorna 204 (não vaza informação)."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "admin@example.com"},
    )
    assert response.status_code == 204


async def test_reset_password_token_invalido_retorna_400(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "token-inexistente", "new_password": "nova-senha-123"},
    )
    assert response.status_code == 400


async def test_reset_password_fluxo_completo(
    client: AsyncClient, admin_user, db
):
    """Cria token via serviço e redefine a senha com sucesso."""
    from app.services.auth_tokens import PasswordResetService

    # Gera token diretamente via service
    token_obj = await PasswordResetService.create_token(db, "admin@example.com")
    await db.commit()
    assert token_obj is not None

    # Consome o token e redefine a senha
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token_obj.token, "new_password": "nova-senha-forte-456"},
    )
    assert response.status_code == 204

    # Login com nova senha deve funcionar
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "nova-senha-forte-456"},
    )
    assert login_resp.status_code == 200


async def test_reset_password_token_reutilizado_retorna_400(
    client: AsyncClient, admin_user, db
):
    """Token de uso único — segunda tentativa falha."""
    from app.services.auth_tokens import PasswordResetService

    token_obj = await PasswordResetService.create_token(db, "admin@example.com")
    await db.commit()

    payload = {"token": token_obj.token, "new_password": "senha-nova-999"}

    r1 = await client.post("/api/v1/auth/reset-password", json=payload)
    assert r1.status_code == 204

    r2 = await client.post("/api/v1/auth/reset-password", json=payload)
    assert r2.status_code == 400


# ── Convite e auto-cadastro (RF-06, RF-13, RN-07) ────────────────────────────


async def test_criar_convite_como_admin_retorna_201(
    client: AsyncClient, admin_token
):
    response = await client.post(
        "/api/v1/auth/invite",
        json={"email": "novato@example.com"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert "invite_link" in data
    assert data["email"] == "novato@example.com"


async def test_criar_convite_como_competidor_retorna_403(
    client: AsyncClient, competitor_token
):
    response = await client.post(
        "/api/v1/auth/invite",
        json={"email": "outro@example.com"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_criar_convite_email_existente_retorna_409(
    client: AsyncClient, admin_token, admin_user
):
    """Não pode convidar alguém que já tem conta."""
    response = await client.post(
        "/api/v1/auth/invite",
        json={"email": "admin@example.com"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409


async def test_register_via_invite_fluxo_completo(
    client: AsyncClient, admin_token, db
):
    """Convite criado → competidor se registra → login automático."""
    # Cria convite
    invite_resp = await client.post(
        "/api/v1/auth/invite",
        json={"email": "competidor.novo@example.com"},
        cookies={"session_id": admin_token},
    )
    assert invite_resp.status_code == 201

    # Extrai token do link de convite
    invite_link = invite_resp.json()["invite_link"]
    token = invite_link.split("token=")[1]

    # Competidor se registra
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "token": token,
            "full_name": "Competidor Novo",
            "email": "competidor.novo@example.com",
            "password": "senha-forte-123",
        },
    )
    assert reg_resp.status_code == 201
    assert "session_id" in reg_resp.cookies

    # Dados do usuário retornados
    data = reg_resp.json()
    assert data["email"] == "competidor.novo@example.com"
    assert data["role"] == "competitor"


async def test_register_via_invite_email_diferente_retorna_400(
    client: AsyncClient, admin_token
):
    """RN-07: convite é pessoal — e-mail deve coincidir."""
    invite_resp = await client.post(
        "/api/v1/auth/invite",
        json={"email": "correto@example.com"},
        cookies={"session_id": admin_token},
    )
    assert invite_resp.status_code == 201
    token = invite_resp.json()["invite_link"].split("token=")[1]

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "token": token,
            "full_name": "Fraudador",
            "email": "errado@example.com",
            "password": "senha-forte-123",
        },
    )
    assert response.status_code == 400


async def test_register_via_invite_token_invalido_retorna_400(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "token": "token-falso",
            "full_name": "Qualquer Um",
            "email": "qualquer@example.com",
            "password": "senha-forte-123",
        },
    )
    assert response.status_code == 400


async def test_register_via_invite_sem_autenticacao(
    client: AsyncClient, admin_token
):
    """Rota de registro não requer autenticação (é pública)."""
    invite_resp = await client.post(
        "/api/v1/auth/invite",
        json={"email": "publico@example.com"},
        cookies={"session_id": admin_token},
    )
    token = invite_resp.json()["invite_link"].split("token=")[1]

    # Sem cookies de sessão
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "token": token,
            "full_name": "Usuário Público",
            "email": "publico@example.com",
            "password": "senha-forte-123",
        },
    )
    assert reg_resp.status_code == 201
