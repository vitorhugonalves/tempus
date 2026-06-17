"""Testes de integração para importação em lote de equipes."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.category import Category, CategoryType
from app.models.competition import Competition, CompetitionStatus
from app.models.user import User, UserRole


def _csv(rows: list[str]) -> bytes:
    """Gera conteúdo CSV como bytes com separador ponto-e-vírgula."""
    return "\n".join(rows).encode("utf-8")


# ── Fixtures auxiliares ─────────────────────────────────────────────────────────


@pytest.fixture
async def active_competition(db: AsyncSession) -> Competition:
    """Cria competição ativa para uso nos testes de equipes em lote."""
    comp = Competition(
        name="Competição Batch",
        status=CompetitionStatus.active,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def team_category(db: AsyncSession, active_competition: Competition) -> Category:
    """Cria categoria de equipe (max_team_size=2) na competição ativa."""
    cat = Category(
        competition_id=active_competition.id,
        name="Dupla Mista",
        category_type=CategoryType.team,
        max_team_size=2,
        is_active=True,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@pytest.fixture
async def competitor_a(db: AsyncSession) -> User:
    """Usuário competidor A para testes."""
    user = User(
        full_name="Competidor A",
        email="comp_a@example.com",
        hashed_password=hash_password("senha123"),
        role=UserRole.competitor,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def competitor_b(db: AsyncSession) -> User:
    """Usuário competidor B para testes."""
    user = User(
        full_name="Competidor B",
        email="comp_b@example.com",
        hashed_password=hash_password("senha123"),
        role=UserRole.competitor,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── Testes ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_import_teams_valid_csv_creates_team(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
    competitor_a: User,
    competitor_b: User,
):
    """CSV válido com 2 competidores (max_team_size=2) cria 1 equipe."""
    csv_content = _csv([
        f"{active_competition.id};Dupla Mista;Equipe Alpha;comp_a@example.com;comp_b@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_bulk_import_teams_invalid_competition_id_adds_to_errors(
    client: AsyncClient, admin_token: str
):
    """ID de competição inexistente gera erro."""
    csv_content = _csv([
        "9999;Dupla Mista;Equipe X;a@example.com;b@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "9999" in data["errors"][0]["reason"]


@pytest.mark.asyncio
async def test_bulk_import_teams_invalid_category_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
    competitor_a: User,
    competitor_b: User,
):
    """Categoria inexistente na competição gera erro."""
    csv_content = _csv([
        f"{active_competition.id};Categoria Inexistente;Equipe Y;comp_a@example.com;comp_b@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "Categoria" in data["errors"][0]["reason"]


@pytest.mark.asyncio
async def test_bulk_import_teams_duplicate_team_name_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
    competitor_a: User,
    competitor_b: User,
):
    """Nome de equipe duplicado na mesma competição gera erro na segunda linha."""
    csv_content = _csv([
        f"{active_competition.id};Dupla Mista;Equipe Dup;comp_a@example.com;comp_b@example.com",
    ])
    # Primeira importação — deve criar
    r1 = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r1.json()["created_count"] == 1

    # Segunda importação com o mesmo nome — deve gerar erro
    r2 = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    data = r2.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "já existe" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_bulk_import_teams_unknown_user_email_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
):
    """E-mail de competidor não cadastrado gera erro."""
    csv_content = _csv([
        f"{active_competition.id};Dupla Mista;Equipe Z;naoexiste@example.com;tambemnao@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "não encontrado" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_bulk_import_teams_wrong_member_count_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
    competitor_a: User,
):
    """Quantidade de membros diferente de max_team_size=2 gera erro."""
    # Apenas 1 e-mail quando max_team_size=2
    csv_content = _csv([
        f"{active_competition.id};Dupla Mista;Equipe W;comp_a@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "tamanho" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_bulk_import_teams_with_box_name_persists_box(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
    competitor_a: User,
    competitor_b: User,
    db: AsyncSession,
):
    """CSV com box_name (formato novo) persiste o campo na equipe criada."""
    from sqlalchemy import select
    from app.models.team import Team

    csv_content = _csv([
        f"{active_competition.id};Dupla Mista;Equipe Box;CrossFit Downtown;comp_a@example.com;comp_b@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["errors"] == []

    result = await db.execute(select(Team).where(Team.name == "Equipe Box"))
    team = result.scalar_one()
    assert team.box_name == "CrossFit Downtown"


@pytest.mark.asyncio
async def test_bulk_import_teams_empty_box_name_stores_none(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
    competitor_a: User,
    competitor_b: User,
    db: AsyncSession,
):
    """CSV com box_name vazio (;;) armazena None na equipe criada."""
    from sqlalchemy import select
    from app.models.team import Team

    csv_content = _csv([
        f"{active_competition.id};Dupla Mista;Equipe SemBox;;comp_a@example.com;comp_b@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1

    result = await db.execute(select(Team).where(Team.name == "Equipe SemBox"))
    team = result.scalar_one()
    assert team.box_name is None


@pytest.mark.asyncio
async def test_bulk_import_teams_legacy_format_without_box_name(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_category: Category,
    competitor_a: User,
    competitor_b: User,
):
    """Formato legado (sem coluna box_name, email direto no índice 3) ainda funciona."""
    csv_content = _csv([
        f"{active_competition.id};Dupla Mista;Equipe Legacy;comp_a@example.com;comp_b@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_bulk_import_teams_as_non_admin_returns_403(
    client: AsyncClient, judge_token: str
):
    """Não-admin recebe 403."""
    response = await client.post(
        "/api/v1/admin/bulk/teams",
        files={"file": ("teams.csv", b"1;cat;team;a@b.com", "text/csv")},
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 403
