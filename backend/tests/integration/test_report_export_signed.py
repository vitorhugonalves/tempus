import hashlib

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.report_issuance import ReportIssuance
from app.services import report_rendering
from app.services.report_rendering import PdfRendererUnavailableError


async def _competition_id(client: AsyncClient, admin_token: str) -> int:
    r = await client.post(
        "/api/v1/competitions",
        json={"name": "Comp PDF"},
        cookies={"session_id": admin_token},
    )
    return r.json()["id"]


async def _issuances(db: AsyncSession) -> list[ReportIssuance]:
    return list((await db.execute(select(ReportIssuance))).scalars().all())


async def test_export_pdf_creates_signed_issuance_matching_bytes(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    [issuance] = await _issuances(db)
    assert issuance.report_type == "ranking"
    assert issuance.competition_name == "Comp PDF"
    assert issuance.issued_by_role == "admin"
    assert issuance.sha256 == hashlib.sha256(r.content).hexdigest()
    assert r.headers["x-verification-code"] == issuance.verification_code


async def test_export_pdf_as_operator_returns_200(
    client: AsyncClient, admin_token: str, operator_token: str
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf",
        cookies={"session_id": operator_token},
    )
    assert r.status_code == 200


async def test_export_pdf_as_competitor_returns_403(
    client: AsyncClient, admin_token: str, competitor_token: str
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf",
        cookies={"session_id": competitor_token},
    )
    assert r.status_code == 403


async def test_export_pdf_unknown_competition_returns_404(
    client: AsyncClient, admin_token: str
):
    r = await client.get(
        "/api/v1/competitions/999999/export/pdf", cookies={"session_id": admin_token}
    )
    assert r.status_code == 404


async def test_export_pdf_without_renderer_returns_503_and_no_issuance(
    client: AsyncClient, admin_token: str, db: AsyncSession, monkeypatch
):
    comp_id = await _competition_id(client, admin_token)

    def _unavailable(_html: str) -> bytes:
        raise PdfRendererUnavailableError("WeasyPrint não disponível")

    monkeypatch.setattr(report_rendering, "html_to_pdf", _unavailable)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 503
    assert await _issuances(db) == []


async def test_export_pdf_without_signing_key_returns_500(
    client: AsyncClient, admin_token: str, db: AsyncSession, monkeypatch
):
    comp_id = await _competition_id(client, admin_token)
    monkeypatch.setattr(settings, "REPORT_SIGNING_PRIVATE_KEY", "")
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 500
    assert "assinatura" in r.json()["detail"].lower()
    assert await _issuances(db) == []


async def test_export_crossfit_pdf_creates_wod_leaderboard_issuance(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/crossfit-pdf",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    [issuance] = await _issuances(db)
    assert issuance.report_type == "wod_leaderboard"
    assert issuance.sha256 == hashlib.sha256(r.content).hexdigest()


async def test_delete_competition_with_issued_reports_returns_409(
    client: AsyncClient, admin_token: str
):
    comp_id = await _competition_id(client, admin_token)
    await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf",
        cookies={"session_id": admin_token},
    )
    r = await client.delete(
        f"/api/v1/competitions/{comp_id}", cookies={"session_id": admin_token}
    )
    assert r.status_code == 409
    assert "relatórios" in r.json()["detail"]


async def test_delete_competition_without_reports_still_returns_204(
    client: AsyncClient, admin_token: str
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.delete(
        f"/api/v1/competitions/{comp_id}", cookies={"session_id": admin_token}
    )
    assert r.status_code == 204
