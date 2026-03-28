"""Testes de integração para importação em lote de baterias."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.heat import Heat
from app.models.team import Team
from app.models.category import Category, CategoryType


def _csv(rows: list[str]) -> bytes:
    """Gera conteúdo CSV como bytes com separador ponto-e-vírgula."""
    return "\n".join(rows).encode("utf-8")


# ── Fixtures auxiliares ─────────────────────────────────────────────────────────


@pytest.fixture
async def active_competition(db: AsyncSession) -> Competition:
    comp = Competition(
        name="Competição Heats Batch",
        status=CompetitionStatus.active,
        max_athletes=100,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def team_alpha(db: AsyncSession, active_competition: Competition) -> Team:
    cat = Category(
        competition_id=active_competition.id,
        name="Individual",
        category_type=CategoryType.individual,
        is_active=True,
    )
    db.add(cat)
    await db.flush()
    await db.refresh(cat)

    team = Team(
        competition_id=active_competition.id,
        category_id=cat.id,
        name="Equipe Alpha",
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


@pytest.fixture
async def team_beta(db: AsyncSession, active_competition: Competition, team_alpha: Team) -> Team:
    team = Team(
        competition_id=active_competition.id,
        category_id=team_alpha.category_id,
        name="Equipe Beta",
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


# ── Testes ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_import_heats_valid_csv_creates_heat(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
):
    """CSV válido cria uma bateria simples sem equipes vinculadas."""
    csv_content = _csv([
        f"{active_competition.id};Bateria 1;;",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_bulk_import_heats_with_max_participants(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    db: AsyncSession,
):
    """CSV com max_participantes persiste o valor na bateria."""
    from sqlalchemy import select

    csv_content = _csv([
        f"{active_competition.id};Bateria Com Limite;20;",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.json()["created_count"] == 1

    result = await db.execute(select(Heat).where(Heat.name == "Bateria Com Limite"))
    heat = result.scalar_one()
    assert heat.max_participants == 20


@pytest.mark.asyncio
async def test_bulk_import_heats_with_teams_links_them(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    team_alpha: Team,
    team_beta: Team,
    db: AsyncSession,
):
    """CSV com nomes de equipes vincula as equipes à bateria criada."""
    from sqlalchemy import select
    from app.models.heat import HeatTeam

    csv_content = _csv([
        f"{active_competition.id};Bateria Equipes;;Equipe Alpha;Equipe Beta",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["errors"] == []

    result = await db.execute(select(Heat).where(Heat.name == "Bateria Equipes"))
    heat = result.scalar_one()

    ht_result = await db.execute(select(HeatTeam).where(HeatTeam.heat_id == heat.id))
    linked = ht_result.scalars().all()
    assert len(linked) == 2
    linked_team_ids = {ht.team_id for ht in linked}
    assert team_alpha.id in linked_team_ids
    assert team_beta.id in linked_team_ids


@pytest.mark.asyncio
async def test_bulk_import_heats_with_header_ignores_it(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
):
    """Cabeçalho 'id_competicao' é ignorado automaticamente."""
    csv_content = _csv([
        "id_competicao;nome_bateria;max_participantes;equipe_01",
        f"{active_competition.id};Bateria Header;;",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_bulk_import_heats_multiple_rows(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
):
    """Múltiplas linhas criam múltiplas baterias."""
    csv_content = _csv([
        f"{active_competition.id};Bateria Multi 1;;",
        f"{active_competition.id};Bateria Multi 2;10;",
        f"{active_competition.id};Bateria Multi 3;;",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 3
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_bulk_import_heats_invalid_competition_id_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
):
    """ID de competição inexistente gera erro."""
    csv_content = _csv([
        "9999;Bateria X;;",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "9999" in data["errors"][0]["reason"]


@pytest.mark.asyncio
async def test_bulk_import_heats_duplicate_name_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
):
    """Nome de bateria duplicado na mesma competição gera erro."""
    csv_content = _csv([f"{active_competition.id};Bateria Dup;;"])

    r1 = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r1.json()["created_count"] == 1

    r2 = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    data = r2.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "já existe" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_bulk_import_heats_invalid_max_participants_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
):
    """max_participantes inválido (não numérico) gera erro."""
    csv_content = _csv([f"{active_competition.id};Bateria Inválida;abc;"])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "max_participantes" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_bulk_import_heats_unknown_team_adds_to_errors(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
):
    """Equipe inexistente na competição gera erro."""
    csv_content = _csv([f"{active_competition.id};Bateria SemEquipe;;Equipe Fantasma"])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "equipe fantasma" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_bulk_import_heats_partial_errors_creates_valid_rows(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
):
    """Linhas válidas são criadas mesmo quando outras têm erros."""
    csv_content = _csv([
        f"{active_competition.id};Bateria OK;;",
        "9999;Bateria Inválida;;",
        f"{active_competition.id};Outra Bateria OK;;",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 2
    assert len(data["errors"]) == 1


@pytest.mark.asyncio
async def test_bulk_import_heats_as_non_admin_returns_403(
    client: AsyncClient, judge_token: str
):
    """Não-admin recebe 403."""
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", b"1;Bateria;;", "text/csv")},
        cookies={"session_id": judge_token},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_bulk_import_heats_sets_sort_order_sequentially(
    client: AsyncClient,
    admin_token: str,
    active_competition: Competition,
    db: AsyncSession,
):
    """Baterias importadas recebem sort_order sequencial."""
    from sqlalchemy import select

    csv_content = _csv([
        f"{active_competition.id};Bateria Ordem 1;;",
        f"{active_competition.id};Bateria Ordem 2;;",
        f"{active_competition.id};Bateria Ordem 3;;",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/heats",
        files={"file": ("heats.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.json()["created_count"] == 3

    result = await db.execute(
        select(Heat)
        .where(Heat.competition_id == active_competition.id)
        .order_by(Heat.sort_order)
    )
    heats = result.scalars().all()
    orders = [h.sort_order for h in heats]
    # sort_orders devem ser crescentes e distintos
    assert orders == sorted(orders)
    assert len(set(orders)) == len(orders)
