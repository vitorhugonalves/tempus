"""Testes de integração para o termo de consentimento por competição."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition

_MINIMAL_PDF = b"%PDF-1.4\n%mock pdf content for tests\n%%EOF"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def competition(client: AsyncClient, admin_token: str) -> dict:
    """Cria uma competição simples para os testes de termo de consentimento."""
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": "Copa Consentimento"},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()


def _pdf_file(name: str = "termo.pdf", content: bytes = _MINIMAL_PDF):
    return {"file": (name, content, "application/pdf")}


# ── Upload ────────────────────────────────────────────────────────────────────


async def test_upload_termo_como_admin_retorna_200_e_has_term_true(
    client: AsyncClient, competition: dict, admin_token: str
):
    resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files=_pdf_file(),
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_term"] is True
    assert data["file_name"] == "termo.pdf"
    assert data["uploaded_at"] is not None


async def test_upload_termo_como_competidor_retorna_403(
    client: AsyncClient, competition: dict, competitor_token: str
):
    resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files=_pdf_file(),
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403


async def test_upload_termo_formato_invalido_retorna_422(
    client: AsyncClient, competition: dict, admin_token: str
):
    resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files={"file": ("termo.txt", b"nao e um pdf", "text/plain")},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 422


async def test_upload_termo_com_extensao_pdf_mas_bytes_invalidos_retorna_422(
    client: AsyncClient, competition: dict, admin_token: str
):
    """Extensão/content-type de PDF não bastam — magic bytes reais são validados."""
    resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files={"file": ("termo.pdf", b"not a real pdf", "application/pdf")},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 422


async def test_upload_termo_maior_que_limite_retorna_413(
    client: AsyncClient, competition: dict, admin_token: str
):
    big_content = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1)
    resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files={"file": ("termo.pdf", big_content, "application/pdf")},
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 413


async def test_upload_termo_competicao_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/api/v1/competitions/999999/consent-term",
        files=_pdf_file(),
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 404


# ── GET metadata ──────────────────────────────────────────────────────────────


async def test_get_metadata_sem_termo_cadastrado_retorna_has_term_false(
    client: AsyncClient, competition: dict, competitor_token: str
):
    resp = await client.get(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_term"] is False
    assert data["file_name"] is None


async def test_get_metadata_competicao_inexistente_retorna_404(
    client: AsyncClient, competitor_token: str
):
    resp = await client.get(
        "/api/v1/competitions/999999/consent-term",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 404


async def test_get_metadata_sem_autenticacao_retorna_404_para_competicao_inexistente(
    client: AsyncClient,
):
    """Rota é pública (a página de auto-inscrição também é pública) — sem cookie
    de sessão, o único erro possível é a competição não existir, não 401.

    Não usa a fixture `competition` (que autentica como admin) para evitar que o
    cookie de sessão fique persistido no client — ver armadilha conhecida de testes.
    """
    resp = await client.get("/api/v1/competitions/999999/consent-term")
    assert resp.status_code == 404


async def test_get_metadata_sem_autenticacao_retorna_200(
    client: AsyncClient, db: AsyncSession
):
    """Um visitante sem conta precisa conseguir ver se há termo antes de se cadastrar.

    Cria a competição direto no banco (não via API+admin_token) para garantir que
    o `client` nunca autentica nesta sessão de teste — verificação genuína de acesso
    público, não apenas "a rota não checa o cookie que por acaso está no jar".
    """
    comp = Competition(name="Copa Pública Sem Auth")
    db.add(comp)
    await db.commit()
    await db.refresh(comp)

    resp = await client.get(f"/api/v1/competitions/{comp.id}/consent-term")
    assert resp.status_code == 200
    assert resp.json()["has_term"] is False


# ── GET file ──────────────────────────────────────────────────────────────────


async def test_get_arquivo_sem_termo_retorna_404(
    client: AsyncClient, competition: dict, competitor_token: str
):
    resp = await client.get(
        f"/api/v1/competitions/{competition['id']}/consent-term/file",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 404


async def test_get_arquivo_competicao_inexistente_retorna_404(
    client: AsyncClient, competitor_token: str
):
    resp = await client.get(
        "/api/v1/competitions/999999/consent-term/file",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 404


async def test_get_arquivo_apos_upload_retorna_200_com_pdf(
    client: AsyncClient, competition: dict, admin_token: str, competitor_token: str
):
    upload_resp = await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files=_pdf_file(),
        cookies={"session_id": admin_token},
    )
    assert upload_resp.status_code == 200

    resp = await client.get(
        f"/api/v1/competitions/{competition['id']}/consent-term/file",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == _MINIMAL_PDF


async def test_get_arquivo_sem_autenticacao_competicao_inexistente_retorna_404(
    client: AsyncClient,
):
    """Rota é pública — sem cookie de sessão, o único erro possível é a competição
    não existir, não 401.
    """
    resp = await client.get("/api/v1/competitions/999999/consent-term/file")
    assert resp.status_code == 404


async def test_get_arquivo_sem_autenticacao_retorna_200_com_pdf(
    client: AsyncClient, db: AsyncSession
):
    """Um visitante sem conta precisa poder ler o termo antes de aceitar/se inscrever.

    Cria competição + termo direto no banco (nunca autentica o `client`) para uma
    verificação genuína de acesso público.
    """
    from app.models.consent_term import ConsentTerm

    comp = Competition(name="Copa Arquivo Público Sem Auth")
    db.add(comp)
    await db.commit()
    await db.refresh(comp)

    import hashlib

    term = ConsentTerm(
        competition_id=comp.id,
        file_data=_MINIMAL_PDF,
        file_name="termo.pdf",
        file_hash=hashlib.sha256(_MINIMAL_PDF).hexdigest(),
    )
    db.add(term)
    await db.commit()

    resp = await client.get(f"/api/v1/competitions/{comp.id}/consent-term/file")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == _MINIMAL_PDF


# ── DELETE ────────────────────────────────────────────────────────────────────


async def test_delete_termo_como_admin_retorna_204_e_remove(
    client: AsyncClient, competition: dict, admin_token: str, competitor_token: str
):
    await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files=_pdf_file(),
        cookies={"session_id": admin_token},
    )

    resp = await client.delete(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 204

    meta_resp = await client.get(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        cookies={"session_id": competitor_token},
    )
    assert meta_resp.json()["has_term"] is False


async def test_delete_termo_inexistente_retorna_404(
    client: AsyncClient, competition: dict, admin_token: str
):
    resp = await client.delete(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 404


async def test_delete_termo_como_competidor_retorna_403(
    client: AsyncClient, competition: dict, admin_token: str, competitor_token: str
):
    await client.post(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        files=_pdf_file(),
        cookies={"session_id": admin_token},
    )
    resp = await client.delete(
        f"/api/v1/competitions/{competition['id']}/consent-term",
        cookies={"session_id": competitor_token},
    )
    assert resp.status_code == 403


async def test_delete_termo_competicao_inexistente_retorna_404(
    client: AsyncClient, admin_token: str
):
    resp = await client.delete(
        "/api/v1/competitions/999999/consent-term",
        cookies={"session_id": admin_token},
    )
    assert resp.status_code == 404
