"""Router do termo de consentimento (LGPD/waiver) por competição."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.consent_term import ConsentTerm
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.schemas.consent_term import ConsentTermResponse
from app.services.consent_term import ConsentTermService

router = APIRouter()


def _competition_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
    )


async def _ensure_competition_exists(db: AsyncSession, competition_id: int) -> None:
    if not await CompetitionRepository.get_by_id(db, competition_id):
        raise _competition_not_found()


def _to_response(term: ConsentTerm | None) -> ConsentTermResponse:
    """Converte ORM ConsentTerm para o schema de resposta (None = sem termo)."""
    if term is None:
        return ConsentTermResponse(has_term=False)
    return ConsentTermResponse(
        has_term=True,
        file_name=term.file_name,
        uploaded_at=term.updated_at,
    )


@router.post(
    "/competitions/{competition_id}/consent-term",
    response_model=ConsentTermResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_consent_term(
    competition_id: int,
    file: UploadFile = File(...),
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> ConsentTermResponse:
    """Faz upload (ou substitui) o termo de consentimento da competição.

    Somente Operador/Admin.

    Formato aceito: PDF. Tamanho máximo: 10 MB.
    """
    await _ensure_competition_exists(db, competition_id)
    term = await ConsentTermService.upload(db, competition_id, file)
    return _to_response(term)


@router.get(
    "/competitions/{competition_id}/consent-term",
    response_model=ConsentTermResponse,
)
async def get_consent_term_metadata(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> ConsentTermResponse:
    """Retorna os metadados do termo de consentimento da competição.

    Pública — a página de auto-inscrição é pública e precisa saber, antes de
    qualquer login, se deve exibir o checkbox de aceite. Retorna `has_term=false`
    (não 404) quando a competição não possui termo cadastrado.
    """
    await _ensure_competition_exists(db, competition_id)
    term = await ConsentTermService.get(db, competition_id)
    return _to_response(term)


@router.get("/competitions/{competition_id}/consent-term/file")
async def get_consent_term_file(
    competition_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Retorna o arquivo PDF do termo de consentimento.

    Pública — igual ao logotipo público do Box: um visitante precisa poder ler
    o termo antes de criar conta e se inscrever, na página pública de
    auto-inscrição. Retorna 404 se não houver termo.
    """
    await _ensure_competition_exists(db, competition_id)
    term = await ConsentTermService.get(db, competition_id)
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum termo de consentimento cadastrado para esta competição.",
        )
    # `file_data` é `deferred=True` (não vem na query de `get`, que serve também
    # a rota pública de metadados — ver Finding 3). Esta é a única rota que
    # realmente precisa dos bytes, então carrega explicitamente aqui via
    # `db.refresh`: em SQLAlchemy assíncrono, um carregamento adiado disparado
    # implicitamente por um simples acesso de atributo (`term.file_data`) fora
    # de uma chamada do AsyncSession lança `MissingGreenlet` — não existe
    # "carregamento preguiçoso automático" fora do event loop aqui.
    await db.refresh(term, attribute_names=["file_data"])
    return Response(content=term.file_data, media_type="application/pdf")


@router.delete(
    "/competitions/{competition_id}/consent-term",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_consent_term(
    competition_id: int,
    _current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove o termo de consentimento da competição (Operador/Admin).

    Torna a inscrição sem exigência de aceite novamente.
    """
    await _ensure_competition_exists(db, competition_id)
    await ConsentTermService.delete(db, competition_id)
