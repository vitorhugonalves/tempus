"""Testes de integração para CRUD de atletas."""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryType
from app.models.competition import Competition, CompetitionStatus

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Atletas", status=CompetitionStatus.active)
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


@pytest.fixture
async def category(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Elite",
        category_type=CategoryType.individual,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@pytest.fixture
async def outra_categoria(db: AsyncSession, competition: Competition) -> Category:
    cat = Category(
        competition_id=competition.id,
        name="Master",
        category_type=CategoryType.individual,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


# ── Testes CRUD ───────────────────────────────────────────────────────────────


async def test_listar_atletas_vazio_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_criar_atleta_retorna_201(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={
            "name": "Carlos Mendes",
            "email": "carlos@example.com",
            "category_id": category.id,
        },
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Carlos Mendes"
    assert data["email"] == "carlos@example.com"
    assert data["competition_id"] == competition.id
    assert data["category_id"] == category.id


async def test_criar_atleta_campos_minimos(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Ana Lima", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Ana Lima"
    assert r.json()["team_id"] is not None


async def test_editar_atleta_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "João Silva", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"name": "João P. Silva", "phone": "(11)99999-0000"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "João P. Silva"
    assert data["phone"] == "(11)99999-0000"


async def test_editar_atleta_reatribui_equipe(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    from app.models.team import Team as TeamModel

    nova_equipe = TeamModel(
        competition_id=competition.id, name="Nova Equipe", category_id=category.id
    )
    db.add(nova_equipe)
    await db.commit()
    await db.refresh(nova_equipe)

    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Reatribuido", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"team_id": nova_equipe.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json()["team_id"] == nova_equipe.id


async def test_editar_atleta_equipe_de_outra_competicao_retorna_404(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    from app.models.competition import Competition as CompModel
    from app.models.team import Team as TeamModel

    outra_comp = CompModel(name="Outra Comp", status=CompetitionStatus.active)
    db.add(outra_comp)
    await db.commit()
    await db.refresh(outra_comp)
    equipe_alheia = TeamModel(
        competition_id=outra_comp.id, name="Alheia", category_id=category.id
    )
    db.add(equipe_alheia)
    await db.commit()
    await db.refresh(equipe_alheia)

    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Vitima", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"team_id": equipe_alheia.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 404


async def test_editar_atleta_team_id_nulo_retorna_422(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    category: Category,
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Sem Equipe Nula", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.put(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        json={"team_id": None},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 422


async def test_remover_atleta_retorna_204(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Maria Costa", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.delete(
        f"/api/v1/competitions/{competition.id}/athletes/{athlete_id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 204

    list_r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    assert all(a["id"] != athlete_id for a in list_r.json())


async def test_competidor_nao_pode_criar_atleta(
    client: AsyncClient, competitor_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Intruso"},
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403


async def test_listar_atletas_filtra_por_categoria(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    category: Category,
    outra_categoria: Category,
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Com Categoria", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Outra Categoria", "category_id": outra_categoria.id},
        cookies={"session_id": admin_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes?category_id={category.id}",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Com Categoria"


async def test_criar_atleta_sem_equipe_nem_categoria_retorna_422(
    client: AsyncClient, admin_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Sem Vinculo"},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 422
    assert "equipe" in r.json()["detail"].lower()


async def test_criar_atleta_com_categoria_cria_equipe_solo_automaticamente(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Carlos Solo", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["team_id"] is not None
    assert data["team_name"] == "Equipe Carlos Solo"


async def test_criar_atleta_com_team_id_existente_usa_equipe_informada(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    from app.models.team import Team as TeamModel

    team = TeamModel(
        competition_id=competition.id,
        name="Equipe Existente",
        category_id=category.id,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Maria Vinculada", "team_id": team.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 201
    assert r.json()["team_id"] == team.id


async def test_importar_atletas_csv_retorna_200(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome;email;documento;telefone;categoria;tamanho_camiseta\n"
        f"Pedro Alves;pedro@example.com;123.456.789-00;(11)91111-2222;"
        f"{category.name};M\n"
        f"Rita Souza;;;;;;"
    ).encode()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 1
    assert "equipe" in data["errors"][0]["error"].lower()


async def test_importar_atletas_csv_sem_nome_gera_erro(
    client: AsyncClient, admin_token: str, competition: Competition
):
    csv_content = b"nome;email\n;pedro@example.com"

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 1


async def test_importar_atletas_csv_cria_equipe_automaticamente(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    csv_content = (
        "nome;categoria;equipe\n"
        f"Carlos Silva;{category.name};Equipe Alpha\n"
        f"Ana Souza;{category.name};Equipe Alpha\n"
    ).encode()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []

    # Verifica que apenas UMA equipe foi criada (reutilizada na segunda linha)
    teams_r = await client.get(
        f"/api/v1/competitions/{competition.id}/teams",
        cookies={"session_id": admin_token},
    )
    teams = teams_r.json()
    assert len([t for t in teams if t["name"] == "Equipe Alpha"]) == 1


async def test_importar_atletas_csv_sem_equipe_nem_categoria_gera_erro_e_nao_cria(
    client: AsyncClient, admin_token: str, competition: Competition
):
    """Sem equipe resolvível e sem categoria: linha inteira falha."""
    csv_content = b"nome;categoria;equipe\nJoao Lima;;Orfaos FC"

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 0
    assert len(data["errors"]) == 1
    assert "equipe" in data["errors"][0]["error"].lower()


async def test_importar_atletas_csv_sem_coluna_equipe_cria_equipe_solo(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    """Sem coluna 'equipe' no CSV, mas com categoria: cria equipe solo."""
    csv_content = f"nome;categoria\nPedro Alves;{category.name}\n".encode()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1
    assert data["errors"] == []

    athletes_r = await client.get(
        f"/api/v1/competitions/{competition.id}/athletes",
        cookies={"session_id": admin_token},
    )
    athlete = athletes_r.json()[0]
    assert athlete["team_name"] == "Equipe Pedro Alves"


async def test_importar_atletas_csv_vincula_equipe_existente(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    """Se a equipe já existe, o atleta é vinculado sem criar duplicata."""
    from app.models.team import Team as TeamModel

    existing_team = TeamModel(
        competition_id=competition.id,
        name="Time Beta",
        category_id=category.id,
    )
    db.add(existing_team)
    await db.commit()
    await db.refresh(existing_team)

    csv_content = (
        f"nome;categoria;equipe\nMaria Nunes;{category.name};Time Beta\n"
    ).encode()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1
    assert data["errors"] == []

    # Verifica que nenhuma equipe duplicada foi criada
    teams_r = await client.get(
        f"/api/v1/competitions/{competition.id}/teams",
        cookies={"session_id": admin_token},
    )
    assert len([t for t in teams_r.json() if t["name"] == "Time Beta"]) == 1


async def test_importar_atletas_csv_case_insensitive_team_matching(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    """Equipes com mesmo nome em diferentes cases são tratadas como uma."""
    csv_content = (
        f"nome;categoria;equipe\n"
        f"Pedro Silva;{category.name};Equipe Teste\n"
        f"Ana Costa;{category.name};equipe teste\n"
    ).encode()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes/import",
        files={"file": ("atletas.csv", io.BytesIO(csv_content), "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []

    # Verifica que apenas UMA equipe foi criada (case-insensitive matching)
    teams_r = await client.get(
        f"/api/v1/competitions/{competition.id}/teams",
        cookies={"session_id": admin_token},
    )
    teams = teams_r.json()
    # Should have exactly one team with "Equipe Teste" (first case used)
    matching_teams = [t for t in teams if t["name"].lower() == "equipe teste"]
    assert len(matching_teams) == 1
