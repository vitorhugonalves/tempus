"""Router de administração: configurações do Box e logotipo."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.repositories.box_settings import BoxSettingsRepository
from app.schemas.box_settings import BoxSettingsResponse, BoxSettingsUpdate
from app.services.box_settings import BoxSettingsService

router = APIRouter()

_ALLOWED_LOGO_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}
_MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5 MB

# Mapeamento de extensão → MIME type (fallback quando content_type é None ou genérico)
_EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _resolve_mime(file: UploadFile) -> str | None:
    """Retorna o MIME type do arquivo, inferindo pela extensão quando necessário."""
    ct = (file.content_type or "").lower()
    if ct in _ALLOWED_LOGO_MIME:
        return ct
    # content_type genérico ou ausente — tenta inferir pela extensão do filename
    if file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext in _EXT_TO_MIME:
            return _EXT_TO_MIME[ext]
    return None


def _to_response(obj: object | None) -> BoxSettingsResponse:
    """Converte ORM BoxSettings para BoxSettingsResponse, tratando None como defaults."""
    if obj is None:
        return BoxSettingsResponse(
            id=1,
            name="",
            address=None,
            website=None,
            instagram=None,
            has_logo=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    return BoxSettingsResponse(
        id=obj.id,  # type: ignore[attr-defined]
        name=obj.name,  # type: ignore[attr-defined]
        address=obj.address,  # type: ignore[attr-defined]
        website=obj.website,  # type: ignore[attr-defined]
        instagram=obj.instagram,  # type: ignore[attr-defined]
        has_logo=obj.logo_data is not None,  # type: ignore[attr-defined]
        created_at=obj.created_at,  # type: ignore[attr-defined]
        updated_at=obj.updated_at,  # type: ignore[attr-defined]
    )


@router.get("/admin/settings", response_model=BoxSettingsResponse)
async def get_settings(
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> BoxSettingsResponse:
    """Retorna as configurações do Box (somente admin).

    Retorna valores padrão caso ainda não tenha sido configurado.
    """
    obj = await BoxSettingsService.get(db)
    return _to_response(obj)


@router.put("/admin/settings", response_model=BoxSettingsResponse)
async def update_settings(
    payload: BoxSettingsUpdate,
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> BoxSettingsResponse:
    """Cria ou atualiza as configurações do Box (somente admin)."""
    obj = await BoxSettingsService.update(db, payload)
    return _to_response(obj)


@router.post(
    "/admin/settings/logo",
    response_model=BoxSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_logo(
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> BoxSettingsResponse:
    """Faz upload do logotipo do Box (somente admin).

    Formatos aceitos: PNG, JPEG, GIF, WebP. Tamanho máximo: 5 MB.
    """
    mime_type = _resolve_mime(file)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Formato de imagem não suportado. Aceitos: PNG, JPEG, GIF, WebP",
        )
    data = await file.read()
    if len(data) > _MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Imagem muito grande. Tamanho máximo permitido: 5 MB",
        )
    obj = await BoxSettingsService.update_logo(db, data, mime_type)
    return _to_response(obj)


@router.get("/admin/settings/logo")
async def get_logo(
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Retorna o logotipo do Box como imagem binária (público).

    Retorna 404 se nenhum logotipo estiver configurado.
    """
    obj = await BoxSettingsRepository.get(db)
    if not obj or not obj.logo_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Logotipo não configurado",
        )
    return Response(
        content=obj.logo_data,
        media_type=obj.logo_mime_type or "image/png",
    )
