"""Testes de integração para o proxy CEP."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


def _make_http_mock(json_data: dict) -> MagicMock:
    """Cria mock completo do cliente httpx para uso como context manager."""
    mock_response = MagicMock()
    mock_response.json.return_value = json_data

    mock_instance = MagicMock()
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=False)
    mock_instance.get = AsyncMock(return_value=mock_response)
    return mock_instance


async def test_cep_valido_retorna_dados(client: AsyncClient):
    json_data = {
        "cep": "01310-100",
        "logradouro": "Avenida Paulista",
        "bairro": "Bela Vista",
        "localidade": "São Paulo",
        "uf": "SP",
    }
    with patch("app.api.v1.cep.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_http_mock(json_data)
        r = await client.get("/api/v1/cep/01310100")
    assert r.status_code == 200
    data = r.json()
    assert data["logradouro"] == "Avenida Paulista"
    assert data["uf"] == "SP"


async def test_cep_invalido_retorna_404(client: AsyncClient):
    with patch("app.api.v1.cep.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_http_mock({"erro": True})
        r = await client.get("/api/v1/cep/00000000")
    assert r.status_code == 404


async def test_cep_formato_incorreto_retorna_422(client: AsyncClient):
    r = await client.get("/api/v1/cep/0131")
    assert r.status_code == 422
