"""Testes de integração para importação em lote de usuários."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _csv(rows: list[str]) -> bytes:
    """Gera conteúdo CSV como bytes com separador ponto-e-vírgula."""
    return "\n".join(rows).encode("utf-8")


@pytest.mark.asyncio
async def test_bulk_import_users_valid_csv_returns_created_count(
    client: AsyncClient, admin_token: str
):
    """CSV com 3 linhas válidas cria 3 usuários."""
    csv_content = _csv([
        "nome_completo;email;perfil",
        "João Silva;joao@example.com;competitor",
        "Maria Santos;maria@example.com;judge",
        "Carlos Alves;carlos@example.com;operator",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/users",
        files={"file": ("users.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 3
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_bulk_import_users_invalid_role_adds_to_errors(
    client: AsyncClient, admin_token: str
):
    """Linha com perfil inválido é reportada nos erros."""
    csv_content = _csv([
        "Super Admin;super@example.com;superadmin",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/users",
        files={"file": ("users.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "super@example.com" in data["errors"][0]["identifier"]


@pytest.mark.asyncio
async def test_bulk_import_users_duplicate_email_adds_to_errors(
    client: AsyncClient, admin_token: str, admin_user
):
    """E-mail já existente é reportado nos erros."""
    csv_content = _csv([
        f"Admin Duplicado;{admin_user.email};admin",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/users",
        files={"file": ("users.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
    assert "cadastrado" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_bulk_import_users_partial_success(
    client: AsyncClient, admin_token: str
):
    """2 válidas + 1 inválida resulta em created_count=2 e 1 erro."""
    csv_content = _csv([
        "nome_completo;email;perfil",
        "Fulano;fulano@example.com;competitor",
        "Ciclano;ciclano@example.com;perfil_errado",
        "Beltrano;beltrano@example.com;judge",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/users",
        files={"file": ("users.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 2
    assert len(data["errors"]) == 1


@pytest.mark.asyncio
async def test_bulk_import_users_empty_csv_returns_zero_created(
    client: AsyncClient, admin_token: str
):
    """CSV vazio retorna created_count=0 e sem erros."""
    response = await client.post(
        "/api/v1/admin/bulk/users",
        files={"file": ("users.csv", b"", "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0


@pytest.mark.asyncio
async def test_bulk_import_users_as_non_admin_returns_403(
    client: AsyncClient, competitor_token: str
):
    """Não-admin recebe 403."""
    response = await client.post(
        "/api/v1/admin/bulk/users",
        files={"file": ("users.csv", b"a;b;c", "text/csv")},
        cookies={"session_id": competitor_token},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_bulk_import_users_missing_columns_adds_to_errors(
    client: AsyncClient, admin_token: str
):
    """Linha com menos de 3 colunas é reportada como erro."""
    csv_content = _csv([
        "SomenteNome;email@example.com",
    ])
    response = await client.post(
        "/api/v1/admin/bulk/users",
        files={"file": ("users.csv", csv_content, "text/csv")},
        cookies={"session_id": admin_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert len(data["errors"]) == 1
