import pytest
from httpx import AsyncClient


# ── GET /users/me ──────────────────────────────────────────────────────────────


async def test_get_me_autenticado_retorna_200_com_dados_do_usuario(
    client: AsyncClient, competitor_token: str, competitor_user
):
    """GET /users/me retorna os dados do usuário autenticado com status 200."""
    response = await client.get(
        "/api/v1/users/me",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == competitor_user.email
    assert data["full_name"] == competitor_user.full_name
    assert data["role"] == "competitor"
    assert "id" in data


async def test_get_me_sem_autenticacao_retorna_401(client: AsyncClient):
    """GET /users/me sem sessão deve retornar 401."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


# ── PATCH /users/me ───────────────────────────────────────────────────────────


async def test_update_me_atualiza_nome_retorna_200(
    client: AsyncClient, competitor_token: str
):
    """PATCH /users/me com nome válido atualiza e retorna 200."""
    response = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "Nome Atualizado"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Nome Atualizado"


async def test_update_me_atualiza_email_retorna_200(
    client: AsyncClient, competitor_token: str
):
    """PATCH /users/me com novo e-mail válido atualiza e retorna 200."""
    response = await client.patch(
        "/api/v1/users/me",
        json={"email": "novo-email@example.com"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "novo-email@example.com"


async def test_update_me_email_duplicado_retorna_409(
    client: AsyncClient, competitor_token: str, admin_user
):
    """PATCH /users/me com e-mail já em uso por outro usuário deve retornar 409."""
    response = await client.patch(
        "/api/v1/users/me",
        json={"email": "admin@example.com"},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 409
    assert "e-mail" in response.json()["detail"].lower()


async def test_update_me_sem_autenticacao_retorna_401(client: AsyncClient):
    """PATCH /users/me sem sessão deve retornar 401."""
    response = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "Fantasma"},
    )
    assert response.status_code == 401


# ── DELETE /users/me ──────────────────────────────────────────────────────────


async def test_delete_me_remove_conta_e_retorna_204(
    client: AsyncClient, competitor_token: str
):
    """DELETE /users/me remove a conta do usuário autenticado e retorna 204."""
    response = await client.delete(
        "/api/v1/users/me",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 204


async def test_delete_me_invalida_sessao_apos_exclusao(
    client: AsyncClient, competitor_token: str
):
    """Após DELETE /users/me a sessão anterior deve ser inválida (401 no /users/me)."""
    delete_resp = await client.delete(
        "/api/v1/users/me",
        cookies={"session_id": competitor_token},
    )
    assert delete_resp.status_code == 204

    me_resp = await client.get(
        "/api/v1/users/me",
        cookies={"session_id": competitor_token},
    )
    assert me_resp.status_code == 401


async def test_delete_me_como_admin_retorna_409(
    client: AsyncClient, admin_token: str
):
    """Admin não pode remover a própria conta."""
    response = await client.delete(
        "/api/v1/users/me",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409
    assert "administrador" in response.json()["detail"].lower()


async def test_delete_me_sem_autenticacao_retorna_401(client: AsyncClient):
    """DELETE /users/me sem sessão deve retornar 401."""
    response = await client.delete("/api/v1/users/me")
    assert response.status_code == 401


# ── Listagem e CRUD de usuários (Admin/Operator) ──────────────────────────────


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


async def test_excluir_usuario_admin_retorna_409(
    client: AsyncClient, admin_token: str, db
):
    """Usuário com role admin não pode ser excluído por outro admin."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    # Cria um segundo admin diretamente no banco
    second_admin = User(
        full_name="Segundo Admin",
        email="second_admin@example.com",
        hashed_password=hash_password("admin-senha-123"),
        role=UserRole.admin,
    )
    db.add(second_admin)
    await db.commit()
    await db.refresh(second_admin)

    response = await client.delete(
        f"/api/v1/users/{second_admin.id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 409
    assert "administrador" in response.json()["detail"].lower()


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
