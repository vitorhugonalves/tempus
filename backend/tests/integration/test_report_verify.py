import hashlib

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import REPORT_VERIFY_MAX_UPLOAD_BYTES
from app.models.report_issuance import ReportIssuance


async def _export(client: AsyncClient, admin_token: str) -> tuple[str, bytes]:
    comp = (
        await client.post(
            "/api/v1/competitions",
            json={"name": "Comp Verif"},
            cookies={"session_id": admin_token},
        )
    ).json()
    r = await client.get(
        f"/api/v1/competitions/{comp['id']}/export/pdf",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    client.cookies.clear()  # o resto do teste é de visitante anônimo
    return r.headers["x-verification-code"], r.content


async def _tamper(db: AsyncSession, code: str, **values) -> None:
    await db.execute(
        update(ReportIssuance)
        .where(ReportIssuance.verification_code == code)
        .values(**values)
    )
    await db.flush()
    db.expire_all()


async def test_verify_code_anonymous_returns_valid(
    client: AsyncClient, admin_token: str
):
    code, pdf = await _export(client, admin_token)
    r = await client.get(f"/api/v1/reports/verify/{code}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "valid"
    assert body["competition_name"] == "Comp Verif"
    assert body["issued_by_role"] == "admin"
    assert body["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert body["issued_at"].endswith(("Z", "+00:00"))


async def test_verify_unknown_code_returns_404(client: AsyncClient):
    r = await client.get("/api/v1/reports/verify/nao-existe")
    assert r.status_code == 404


async def test_download_original_returns_identical_bytes(
    client: AsyncClient, admin_token: str
):
    code, pdf = await _export(client, admin_token)
    r = await client.get(f"/api/v1/reports/verify/{code}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == pdf


async def test_verify_upload_same_file_returns_valid(
    client: AsyncClient, admin_token: str
):
    code, pdf = await _export(client, admin_token)
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("ranking.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    assert r.json()["verification_code"] == code
    assert r.json()["status"] == "valid"


async def test_verify_upload_one_byte_changed_returns_404(
    client: AsyncClient, admin_token: str
):
    _, pdf = await _export(client, admin_token)
    altered = pdf[:-10] + bytes([pdf[-10] ^ 0x01]) + pdf[-9:]
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("ranking.pdf", altered, "application/pdf")},
    )
    assert r.status_code == 404


async def test_verify_upload_not_pdf_returns_422(client: AsyncClient):
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("x.pdf", b"not a pdf", "application/pdf")},
    )
    assert r.status_code == 422


async def test_verify_upload_too_large_returns_413(client: AsyncClient):
    big = b"%PDF-" + b"0" * REPORT_VERIFY_MAX_UPLOAD_BYTES
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413


async def test_verify_code_with_tampered_hash_returns_tampered(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    code, _ = await _export(client, admin_token)
    await _tamper(db, code, sha256="0" * 64)
    r = await client.get(f"/api/v1/reports/verify/{code}")
    assert r.json()["status"] == "tampered"
    pdf_response = await client.get(f"/api/v1/reports/verify/{code}/pdf")
    assert pdf_response.status_code == 409


async def test_verify_code_with_swapped_pdf_data_returns_tampered(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    code, _ = await _export(client, admin_token)
    await _tamper(db, code, pdf_data=b"%PDF-1.7 trocado")
    r = await client.get(f"/api/v1/reports/verify/{code}")
    assert r.json()["status"] == "tampered"
    pdf_response = await client.get(f"/api/v1/reports/verify/{code}/pdf")
    assert pdf_response.status_code == 409


async def test_public_key_endpoint_returns_pem(client: AsyncClient):
    r = await client.get("/api/v1/reports/public-key")
    assert r.status_code == 200
    assert r.text.startswith("-----BEGIN PUBLIC KEY-----")


async def test_public_key_without_signing_key_returns_503(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "REPORT_SIGNING_PRIVATE_KEY", "")
    r = await client.get("/api/v1/reports/public-key")
    assert r.status_code == 503
