"""Testes de integração para o fluxo de check-in (unificação Athlete/User)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category, CategoryType
from app.models.competition import Competition, CompetitionStatus


@pytest.fixture
async def competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Checkin", status=CompetitionStatus.active)
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


async def test_busca_encontra_atleta_importado_em_massa(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Carlos Bulk", "category_id": category.id},
        cookies={"session_id": admin_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search?q=Carlos",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["kind"] == "athlete"
    assert results[0]["has_athlete_record"] is True


async def test_busca_encontra_inscricao_online_sem_atleta_ainda(
    client: AsyncClient,
    admin_token: str,
    competitor_token: str,
    competition: Competition,
    category: Category,
):
    await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )

    r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search?q=Competidor",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["kind"] == "registration"
    assert results[0]["has_athlete_record"] is False


async def test_ensure_athlete_cria_atleta_a_partir_de_inscricao_online(
    client: AsyncClient,
    admin_token: str,
    competitor_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    from sqlalchemy import select

    from app.models.competitor import CompetitorRegistration

    reg_r = await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )
    team_id = reg_r.json()["team_id"]

    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.competition_id == competition.id
        )
    )
    registration = result.scalar_one()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["team_id"] == team_id
    assert data["name"] == "Competidor Teste"

    # Idempotente: chamar de novo não cria um segundo Athlete
    r2 = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]


async def test_ensure_athlete_com_kind_athlete_retorna_o_proprio(
    client: AsyncClient, admin_token: str, competition: Competition, category: Category
):
    create_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={"name": "Ja Existe", "category_id": category.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "athlete", "source_id": athlete_id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.json()["id"] == athlete_id


# ── Unificação por e-mail (mesma pessoa como Athlete bulk + User auto-inscrito) ─


async def test_ensure_unifica_atleta_bulk_e_inscricao_pelo_mesmo_email(
    client: AsyncClient,
    admin_token: str,
    competitor_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    """Mesma pessoa (mesmo e-mail) importada em massa e auto-inscrita depois
    deve resultar em um único Athlete — nunca dois cadastros duplicados."""
    from sqlalchemy import select

    from app.models.competitor import CompetitorRegistration

    bulk_r = await client.post(
        f"/api/v1/competitions/{competition.id}/athletes",
        json={
            "name": "Duplicado Bulk",
            "email": "competidor@example.com",
            "category_id": category.id,
        },
        cookies={"session_id": admin_token},
    )
    assert bulk_r.status_code == 201
    bulk_athlete_id = bulk_r.json()["id"]

    await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )

    search_r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search",
        params={"q": "competidor@example.com"},
        cookies={"session_id": admin_token},
    )
    assert search_r.status_code == 200
    results = search_r.json()
    assert len(results) == 1
    assert results[0]["kind"] == "athlete"
    assert results[0]["source_id"] == bulk_athlete_id

    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.competition_id == competition.id
        )
    )
    registration = result.scalar_one()

    ensure_r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert ensure_r.status_code == 200
    assert ensure_r.json()["id"] == bulk_athlete_id

    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.competition_id == competition.id
        )
    )
    registration = result.scalar_one()
    from app.repositories.athlete import AthleteRepository

    linked = await AthleteRepository.get_by_id(db, bulk_athlete_id)
    assert linked is not None
    assert linked.user_id == registration.user_id


# ── Validação de tamanho de campos (Finding 2) ──────────────────────────────────


async def test_ensure_athlete_com_documento_excedendo_tamanho_retorna_422(
    client: AsyncClient,
    admin_token: str,
    competitor_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    """CompetitorRegistration.document (String(30)) aceita mais caracteres do
    que Athlete.document (String(20)) — precisa ser rejeitado antes do insert."""
    from sqlalchemy import select

    from app.models.competitor import CompetitorRegistration

    documento_muito_longo = "1" * 25
    await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id, "document": documento_muito_longo},
        cookies={"session_id": competitor_token},
    )

    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.competition_id == competition.id
        )
    )
    registration = result.scalar_one()

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "registration", "source_id": registration.id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 422


# ── Autorização (Finding 3) ─────────────────────────────────────────────────────


async def test_search_checkin_como_competidor_retorna_403(
    client: AsyncClient, competitor_token: str, competition: Competition
):
    r = await client.get(
        f"/api/v1/competitions/{competition.id}/checkin/search?q=x",
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403


async def test_ensure_checkin_como_competidor_retorna_403(
    client: AsyncClient, competitor_token: str, competition: Competition
):
    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "athlete", "source_id": 1},
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403


async def test_ensure_checkin_atleta_de_outra_competicao_retorna_404(
    client: AsyncClient,
    admin_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    from app.models.category import Category as CategoryModel
    from app.models.competition import Competition as CompModel

    outra_comp = CompModel(name="Outra Comp Checkin", status=CompetitionStatus.active)
    db.add(outra_comp)
    await db.commit()
    await db.refresh(outra_comp)

    outra_categoria = CategoryModel(
        competition_id=outra_comp.id,
        name="Elite Alheia",
        category_type=CategoryType.individual,
    )
    db.add(outra_categoria)
    await db.commit()
    await db.refresh(outra_categoria)

    create_r = await client.post(
        f"/api/v1/competitions/{outra_comp.id}/athletes",
        json={"name": "Alheio", "category_id": outra_categoria.id},
        cookies={"session_id": admin_token},
    )
    athlete_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/competitions/{competition.id}/checkin/ensure",
        json={"kind": "athlete", "source_id": athlete_id},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 404


# ── Corrida de duplo-clique (Finding 4) ──────────────────────────────────────────


async def test_ensure_athlete_trata_corrida_de_duplo_clique_retornando_o_vencedor(
    client: AsyncClient,
    competitor_token: str,
    competition: Competition,
    category: Category,
    db: AsyncSession,
):
    """Simula duas requisições de 'Confirmar check-in' quase simultâneas para a
    mesma inscrição: a UniqueConstraint (competition_id, user_id) barra a
    segunda no banco com IntegrityError — o service deve devolver o Athlete
    criado pela primeira em vez de propagar um 500."""
    from unittest.mock import AsyncMock, patch

    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.models.athlete import Athlete
    from app.models.competitor import CompetitorRegistration
    from app.repositories.athlete import AthleteRepository
    from app.schemas.checkin import CheckinEnsureRequest
    from app.services.checkin import CheckinService

    reg_r = await client.post(
        f"/api/v1/competitions/{competition.id}/register",
        json={"category_id": category.id},
        cookies={"session_id": competitor_token},
    )
    assert reg_r.status_code == 201

    result = await db.execute(
        select(CompetitorRegistration).where(
            CompetitorRegistration.competition_id == competition.id
        )
    )
    registration = result.scalar_one()
    await db.refresh(registration, attribute_names=["user"])
    # Capturado antes do rollback simulado abaixo: `registration` fica
    # expirado após `db.rollback()` e um acesso tardio a `.user_id` dispararia
    # um reload síncrono inválido em sessão assíncrona.
    registration_user_id = registration.user_id

    # Athlete "vencedor" — representa o registro que a requisição concorrente
    # já teria criado no instante entre nossa checagem `already` e nosso insert.
    winner = Athlete(
        id=999_999,
        competition_id=competition.id,
        category_id=registration.category_id,
        team_id=1,
        user_id=registration_user_id,
        name=registration.user.full_name,
        email=registration.user.email,
    )
    call_count = {"n": 0}

    async def _list_by_competition_side_effect(_db, _competition_id, **_kwargs):
        call_count["n"] += 1
        # 1ª chamada (checagens `already`/e-mail): ninguém venceu ainda.
        # 2ª chamada (dentro do except): o vencedor já está persistido.
        return [] if call_count["n"] == 1 else [winner]

    with (
        patch.object(
            AthleteRepository,
            "list_by_competition",
            AsyncMock(side_effect=_list_by_competition_side_effect),
        ),
        patch.object(
            AthleteRepository,
            "create",
            AsyncMock(
                side_effect=IntegrityError(
                    "insert", {}, Exception("uq_athlete_user_per_competition")
                )
            ),
        ),
    ):
        athlete = await CheckinService.ensure_athlete(
            db,
            competition.id,
            CheckinEnsureRequest(kind="registration", source_id=registration.id),
        )

    assert athlete is winner
    assert athlete.user_id == registration_user_id
    assert call_count["n"] == 2
