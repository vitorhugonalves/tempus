"""Proxy para ViaCEP — evita CORS do frontend."""
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException, Path, status

logger = logging.getLogger(__name__)

router = APIRouter()

_CEP_PATTERN = re.compile(r"^\d{8}$")
_VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"


@router.get("/cep/{cep}")
async def lookup_cep(
    cep: str = Path(..., description="CEP sem traço (8 dígitos)"),
) -> dict:
    """Consulta dados de endereço via ViaCEP.

    Args:
        cep: CEP sem traço, exatamente 8 dígitos.

    Returns:
        Dicionário com logradouro, bairro, localidade, uf.

    Raises:
        HTTPException 422: CEP com formato inválido.
        HTTPException 404: CEP não encontrado.
        HTTPException 502: ViaCEP indisponível.
    """
    if not _CEP_PATTERN.match(cep):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CEP deve ter exatamente 8 dígitos numéricos",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(_VIACEP_URL.format(cep=cep))
    except httpx.RequestError as exc:
        logger.warning("ViaCEP indisponível: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Serviço de CEP temporariamente indisponível",
        ) from exc

    data = response.json()
    if data.get("erro"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CEP não encontrado")

    return {
        "cep": data.get("cep"),
        "logradouro": data.get("logradouro"),
        "complemento": data.get("complemento"),
        "bairro": data.get("bairro"),
        "localidade": data.get("localidade"),
        "uf": data.get("uf"),
    }
