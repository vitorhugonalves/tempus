import pytest
from httpx import AsyncClient


async def test_listar_usuarios_como_admin_retorna_200(
    client: AsyncClient, admin_token: str
):
    response = await client.get(
        "/api/v1/users",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_listar_usuarios_como_competidor_retorna_403(
    client: AsyncClient, competitor_token: str
):
    response = await client.get(
        "/api/v1/users",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_listar_usuarios_sem_autenticacao_retorna_401(client: AsyncClient):
    response = await client.get("/api/v1/users")
    assert response.status_code == 401


async def test_criar_usuario_como_admin_retorna_201(
    client: AsyncClient, admin_token: str
):
    response = await client.post(
        "/api/v1/users",
        json={
            "full_name": "Novo Usuário",
            "email": "novo@example.com",
            "password": "senha-nova-123",
            "role": "judge",
        },
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "novo@example.com"
    assert data["role"] == "judge"


async def test_criar_usuario_com_email_duplicado_retorna_409(
    client: AsyncClient, admin_token: str, admin_user
):
    response = await client.post(
        "/api/v1/users",
        json={
            "full_name": "Duplicado",
            "email": "admin@example.com",
            "password": "senha-123",
            "role": "competitor",
        },
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409


# ── Exclusão de usuário ────────────────────────────────────────────────────────

async def test_excluir_usuario_como_admin_retorna_204(
    client: AsyncClient, admin_token: str, competitor_user
):
    response = await client.delete(
        f"/api/v1/users/{competitor_user.id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204


async def test_excluir_proprio_usuario_retorna_409(
    client: AsyncClient, admin_token: str, admin_user
):
    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409


async def test_excluir_usuario_como_judge_retorna_403(
    client: AsyncClient, judge_token: str, competitor_user
):
    response = await client.delete(
        f"/api/v1/users/{competitor_user.id}",
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 403


async def test_excluir_usuario_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    response = await client.delete(
        "/api/v1/users/9999",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 404


# ── Redefinição de senha ───────────────────────────────────────────────────────

async def test_redefinir_senha_proprio_usuario_retorna_204(
    client: AsyncClient, competitor_token: str, competitor_user
):
    response = await client.post(
        f"/api/v1/users/{competitor_user.id}/reset-password",
        json={"new_password": "nova-senha-456"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 204


async def test_redefinir_senha_como_admin_retorna_204(
    client: AsyncClient, admin_token: str, competitor_user
):
    response = await client.post(
        f"/api/v1/users/{competitor_user.id}/reset-password",
        json={"new_password": "nova-senha-admin-456"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 204


async def test_redefinir_senha_de_outro_usuario_como_competidor_retorna_403(
    client: AsyncClient, competitor_token: str, judge_user
):
    response = await client.post(
        f"/api/v1/users/{judge_user.id}/reset-password",
        json={"new_password": "nova-senha-456"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_redefinir_senha_muito_curta_retorna_422(
    client: AsyncClient, admin_token: str, competitor_user
):
    response = await client.post(
        f"/api/v1/users/{competitor_user.id}/reset-password",
        json={"new_password": "curta"},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 422
