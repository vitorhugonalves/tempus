"""Testes de integração para certificados e imagens sociais (RF-41, RF-42, RF-43)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, CompetitionStatus
from app.models.timer import Timer, TimerStatus


async def _setup_finished_competition(db: AsyncSession, user_id: int) -> tuple[int, int]:
    """Cria competição encerrada com timer finalizado para o usuário.

    Returns:
        (competition_id, timer_id)
    """
    comp = Competition(name="Comp Finalizada", status=CompetitionStatus.finished)
    db.add(comp)
    await db.flush()
    await db.refresh(comp)

    timer = Timer(
        competition_id=comp.id,
        user_id=user_id,
        status=TimerStatus.finished,
    )
    db.add(timer)
    await db.flush()
    await db.refresh(timer)
    await db.commit()

    return comp.id, timer.id


async def _setup_active_competition(db: AsyncSession, user_id: int) -> tuple[int, int]:
    """Cria competição ativa (não encerrada)."""
    comp = Competition(name="Comp Ativa", status=CompetitionStatus.active)
    db.add(comp)
    await db.flush()
    await db.refresh(comp)

    timer = Timer(
        competition_id=comp.id,
        user_id=user_id,
        status=TimerStatus.created,
    )
    db.add(timer)
    await db.flush()
    await db.refresh(timer)
    await db.commit()

    return comp.id, timer.id


# ── Certificado PDF (RF-41, RF-43) ───────────────────────────────────────────


async def test_certificado_como_admin_retorna_arquivo(
    client: AsyncClient, admin_token, admin_user, db: AsyncSession
):
    competition_id, _ = await _setup_finished_competition(db, admin_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/certificate/{admin_user.id}",
        cookies={"session_id": admin_token},
    )
    # WeasyPrint pode não estar instalado, então aceita PDF ou HTML
    assert response.status_code == 200
    assert response.headers["content-type"] in (
        "application/pdf",
        "text/html; charset=utf-8",
        "text/html",
    )


async def test_certificado_competidor_acessa_proprio(
    client: AsyncClient, competitor_token, competitor_user, db: AsyncSession
):
    """Competidor pode gerar o próprio certificado (RF-43)."""
    competition_id, _ = await _setup_finished_competition(db, competitor_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/certificate/{competitor_user.id}",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 200


async def test_certificado_competidor_nao_acessa_terceiro(
    client: AsyncClient, competitor_token, admin_user, db: AsyncSession
):
    """Competidor não pode gerar certificado de outro usuário (RF-43)."""
    competition_id, _ = await _setup_finished_competition(db, admin_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/certificate/{admin_user.id}",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_certificado_competicao_nao_encerrada_retorna_403(
    client: AsyncClient, admin_token, admin_user, db: AsyncSession
):
    """RN-06: certificado indisponível antes de encerrar a competição."""
    competition_id, _ = await _setup_active_competition(db, admin_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/certificate/{admin_user.id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 403


async def test_certificado_sem_autenticacao_retorna_401(
    client: AsyncClient, admin_user, db: AsyncSession
):
    competition_id, _ = await _setup_finished_competition(db, admin_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/certificate/{admin_user.id}",
    )
    assert response.status_code == 401


# ── Imagem social PNG (RF-42, RF-43) ─────────────────────────────────────────


async def test_imagem_social_como_admin_retorna_png(
    client: AsyncClient, admin_token, admin_user, db: AsyncSession
):
    competition_id, _ = await _setup_finished_competition(db, admin_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/social-image/{admin_user.id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


async def test_imagem_social_competidor_acessa_proprio(
    client: AsyncClient, competitor_token, competitor_user, db: AsyncSession
):
    competition_id, _ = await _setup_finished_competition(db, competitor_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/social-image/{competitor_user.id}",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 200


async def test_imagem_social_competidor_nao_acessa_terceiro(
    client: AsyncClient, competitor_token, admin_user, db: AsyncSession
):
    competition_id, _ = await _setup_finished_competition(db, admin_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/social-image/{admin_user.id}",
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


async def test_imagem_social_competicao_nao_encerrada_retorna_403(
    client: AsyncClient, admin_token, admin_user, db: AsyncSession
):
    competition_id, _ = await _setup_active_competition(db, admin_user.id)

    response = await client.get(
        f"/api/v1/competitions/{competition_id}/social-image/{admin_user.id}",
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 403
