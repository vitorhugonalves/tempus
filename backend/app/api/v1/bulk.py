"""Router de importação em lote via CSV (somente admin)."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.bulk import BulkImportResult, BulkService

router = APIRouter()

_MAX_CSV_BYTES = 1 * 1024 * 1024  # 1 MB


@router.post(
    "/admin/bulk/users",
    response_model=BulkImportResult,
    status_code=status.HTTP_200_OK,
)
async def bulk_import_users(
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> BulkImportResult:
    """Importa usuários em lote via CSV (somente admin).

    Formato CSV: nome_completo;email;perfil (separado por ponto-e-vírgula).
    Perfis aceitos: competitor, judge, operator, admin.
    Uma senha aleatória é gerada para cada usuário criado.
    """
    content = await file.read()
    if len(content) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo CSV muito grande. Tamanho máximo: 1 MB",
        )
    csv_text = content.decode("utf-8", errors="replace")
    return await BulkService.import_users(csv_text, db)


@router.post(
    "/admin/bulk/teams",
    response_model=BulkImportResult,
    status_code=status.HTTP_200_OK,
)
async def bulk_import_teams(
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> BulkImportResult:
    """Importa equipes em lote via CSV (somente admin).

    Formato CSV: id_competicao;categoria_equipe;nome_equipe;email1;email2;...
    O número de e-mails deve corresponder ao max_team_size da categoria.
    """
    content = await file.read()
    if len(content) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo CSV muito grande. Tamanho máximo: 1 MB",
        )
    csv_text = content.decode("utf-8", errors="replace")
    return await BulkService.import_teams(csv_text, db)


@router.post(
    "/admin/bulk/heats",
    response_model=BulkImportResult,
    status_code=status.HTTP_200_OK,
)
async def bulk_import_heats(
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> BulkImportResult:
    """Importa baterias em lote via CSV (somente admin).

    Formato CSV: id_competicao;nome_bateria;max_participantes;nome_equipe_01;nome_equipe_02;...
    max_participantes é opcional (deixe vazio). Equipes devem já existir na competição.
    """
    content = await file.read()
    if len(content) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo CSV muito grande. Tamanho máximo: 1 MB",
        )
    csv_text = content.decode("utf-8", errors="replace")
    return await BulkService.import_heats(csv_text, db)
