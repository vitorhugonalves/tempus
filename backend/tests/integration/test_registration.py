"""Testes de integração para auto-inscrição de competidores."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def active_competition(client: AsyncClient, admin_token: str) -> dict:
    """Cria uma competição ativa."""
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": "Copa Teste", "max_athletes": 50},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    comp = resp.json()
    await client.patch(
        f"/api/v1/competitions/{comp['id']}",
        json={"status": "active"},
        cookies={"session_id": admin_token},
    )
    return comp


@pytest.fixture
async def draft_competition(client: AsyncClient, admin_token: str) -> dict:
    """Cria uma competição em rascunho (não ativa)."""
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": "Copa Rascunho", "max_athletes": 50},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def individual_category(
    client: AsyncClient, active_competition: dict, admin_token: str
) -> dict:
    """Cria uma categoria individual na competição ativa."""
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/categories",
        json={"name": "Elite Masculino", "category_type": "individual"},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def team_category(
    client: AsyncClient, active_competition: dict, admin_token: str
) -> dict:
    """Cria uma categoria de equipe (dupla) na competição ativa."""
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/categories",
        json={"name": "Duplas", "category_type": "team", "max_team_size": 2},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def second_competitor(db: AsyncSession) -> dict:
    """Cria um segundo usuário competidor diretamente no banco de testes."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        full_name="Parceiro Teste",
        email="parceiro@example.com",
        hashed_password=hash_password("senha-parceiro-123"),
        role=UserRole.competitor,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "full_name": user.full_name}


# ── Inscrição individual ──────────────────────────────────────────────────────


async def test_inscricao_individual_retorna_201(
    client: AsyncClient,
    active_competition: dict,
    individual_category: dict,
    competitor_token: str,
):
    """Competidor se inscreve em categoria individual e recebe 201."""
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={"category_id": individual_category["id"]},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["registration_id"] > 0
    assert data["team_id"] > 0
    assert data["accounts_created"] == 0


async def test_inscricao_individual_com_documento(
    client: AsyncClient,
    active_competition: dict,
    individual_category: dict,
    competitor_token: str,
):
    """Competidor pode informar documento ao se inscrever."""
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={"category_id": individual_category["id"], "document": "123.456.789-00"},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 201


async def test_inscricao_duplicada_retorna_409(
    client: AsyncClient,
    active_competition: dict,
    individual_category: dict,
    competitor_token: str,
):
    """Segunda inscrição na mesma competição retorna 409."""
    payload = {"category_id": individual_category["id"]}
    r1 = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json=payload,
        cookies={"session_id": competitor_token},
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json=payload,
        cookies={"session_id": competitor_token},
    )
    assert r2.status_code == 409
    assert "já está inscrito" in r2.json()["detail"].lower()


async def test_inscricao_sem_autenticacao_retorna_401(
    client: AsyncClient,
):
    """Inscrição sem cookie de sessão retorna 401. Auth check ocorre antes do 404."""
    resp = await client.post(
        "/api/v1/competitions/999/register",
        json={"category_id": 1},
    )
    assert resp.status_code == 401


async def test_inscricao_em_competicao_inativa_retorna_409(
    client: AsyncClient,
    draft_competition: dict,
    admin_token: str,
    competitor_token: str,
):
    """Inscrição em competição não-ativa retorna 409."""
    cat_resp = await client.post(
        f"/api/v1/competitions/{draft_competition['id']}/categories",
        json={"name": "Individual", "category_type": "individual"},
        cookies={"session_id": admin_token},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/competitions/{draft_competition['id']}/register",
        json={"category_id": cat_id},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 409
    assert "ativas" in resp.json()["detail"].lower()


async def test_inscricao_categoria_invalida_retorna_404(
    client: AsyncClient,
    active_competition: dict,
    competitor_token: str,
):
    """Categoria inexistente retorna 404."""
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={"category_id": 9999},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 404


# ── Inscrição de equipe ───────────────────────────────────────────────────────


async def test_inscricao_equipe_sem_nome_retorna_422(
    client: AsyncClient,
    active_competition: dict,
    team_category: dict,
    competitor_token: str,
):
    """Inscrição de equipe sem team_name retorna 422."""
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={"category_id": team_category["id"]},
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 422
    assert "obrigatório" in resp.json()["detail"].lower()


async def test_inscricao_equipe_com_membro_existente_retorna_201(
    client: AsyncClient,
    active_competition: dict,
    team_category: dict,
    competitor_token: str,
    second_competitor: dict,
    monkeypatch,
):
    """Capitão + 1 membro existente (pelo email) → 201, accounts_created=0."""
    monkeypatch.setattr(
        "app.services.registration.send_registration_welcome", AsyncMock()
    )
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={
            "category_id": team_category["id"],
            "team_name": "Dupla dos Campeões",
            "additional_members": [
                {
                    "full_name": second_competitor["full_name"],
                    "email": second_competitor["email"],
                }
            ],
        },
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["team_name"] == "Dupla dos Campeões"
    assert data["accounts_created"] == 0


async def test_inscricao_equipe_cria_conta_novo_membro(
    client: AsyncClient,
    active_competition: dict,
    team_category: dict,
    competitor_token: str,
    monkeypatch,
):
    """Membro sem conta é criado automaticamente → accounts_created = 1."""
    monkeypatch.setattr(
        "app.services.registration.send_registration_welcome", AsyncMock()
    )
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={
            "category_id": team_category["id"],
            "team_name": "Dupla Nova",
            "additional_members": [
                {"full_name": "Novo Atleta", "email": "novoatleta@example.com"}
            ],
        },
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["accounts_created"] == 1


async def test_inscricao_equipe_acima_do_limite_retorna_409(
    client: AsyncClient,
    active_competition: dict,
    team_category: dict,
    competitor_token: str,
    monkeypatch,
):
    """Equipe com mais membros do que max_team_size retorna 409."""
    monkeypatch.setattr(
        "app.services.registration.send_registration_welcome", AsyncMock()
    )
    # max_team_size=2 → capitão + 2 adicionais = 3 > 2
    resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={
            "category_id": team_category["id"],
            "team_name": "Equipe Grande Demais",
            "additional_members": [
                {"full_name": "Membro 2", "email": "m2@example.com"},
                {"full_name": "Membro 3", "email": "m3@example.com"},
            ],
        },
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 409
    assert "máximo" in resp.json()["detail"].lower()


# ── Limite via endpoint de equipes (max_team_size) ────────────────────────────


async def test_add_member_acima_max_team_size_retorna_409(
    client: AsyncClient,
    active_competition: dict,
    team_category: dict,
    admin_token: str,
    competitor_user,
    second_competitor: dict,
    db: AsyncSession,
):
    """Operador não pode adicionar membro além do max_team_size."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    # Cria terceiro usuário
    u3 = User(
        full_name="Atleta3",
        email="atleta3@example.com",
        hashed_password=hash_password("senha123"),
        role=UserRole.competitor,
    )
    db.add(u3)
    await db.commit()
    await db.refresh(u3)
    u3_id = u3.id

    # Cria a equipe
    team_resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/teams",
        json={
            "name": "Dupla Teste",
            "category_id": team_category["id"],
            "captain_id": competitor_user.id,
        },
        cookies={"session_id": admin_token},
    )
    assert team_resp.status_code == 201
    team_id = team_resp.json()["id"]

    # 1° membro (competitor_user) → OK
    r1 = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/teams/{team_id}/members",
        json={"user_id": competitor_user.id},
        cookies={"session_id": admin_token},
    )
    assert r1.status_code == 201

    # 2° membro → OK (atingindo o limite = 2)
    r2 = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/teams/{team_id}/members",
        json={"user_id": second_competitor["id"]},
        cookies={"session_id": admin_token},
    )
    assert r2.status_code == 201

    # 3° membro → 409 (max_team_size = 2)
    r3 = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/teams/{team_id}/members",
        json={"user_id": u3_id},
        cookies={"session_id": admin_token},
    )
    assert r3.status_code == 409
    assert "limite" in r3.json()["detail"].lower()


# ── GET /competitions/{id}/my-registration ───────────────────────────────────


async def test_get_my_registration_nao_inscrito_retorna_is_registered_false(
    client: AsyncClient,
    active_competition: dict,
    competitor_token: str,
):
    """Competidor que não está inscrito deve receber is_registered=false."""
    resp = await client.get(
        f"/api/v1/competitions/{active_competition['id']}/my-registration",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_registered"] is False
    assert data["competition_id"] == active_competition["id"]


async def test_get_my_registration_inscrito_retorna_is_registered_true(
    client: AsyncClient,
    active_competition: dict,
    individual_category: dict,
    competitor_token: str,
):
    """Competidor já inscrito deve receber is_registered=true."""
    # Realiza inscrição primeiro
    register_resp = await client.post(
        f"/api/v1/competitions/{active_competition['id']}/register",
        json={"category_id": individual_category["id"]},
        cookies={"session_id": competitor_token},
    )
    assert register_resp.status_code == 201

    # Verifica status de inscrição
    resp = await client.get(
        f"/api/v1/competitions/{active_competition['id']}/my-registration",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_registered"] is True
    assert data["competition_id"] == active_competition["id"]


async def test_get_my_registration_sem_autenticacao_retorna_401(client: AsyncClient):
    """GET /my-registration sem sessão deve retornar 401. Auth check ocorre antes do 404."""
    resp = await client.get("/api/v1/competitions/999/my-registration")
    assert resp.status_code == 401
