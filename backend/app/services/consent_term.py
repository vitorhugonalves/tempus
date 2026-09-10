"""Serviço de termo de consentimento — upload, validação e remoção por competição."""

import hashlib

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MAX_CONSENT_TERM_BYTES, PDF_MAGIC_BYTES
from app.models.consent_term import ConsentTerm
from app.repositories.consent_term import ConsentTermRepository


def _invalid_pdf_format() -> HTTPException:
    """Erro padrão para upload que não é um PDF válido (extensão ou conteúdo)."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "Formato não suportado. Apenas PDF é aceito para o termo de consentimento."
        ),
    )


class ConsentTermService:
    """Regras de negócio para o termo de consentimento de uma competição."""

    @staticmethod
    async def get(db: AsyncSession, competition_id: int) -> ConsentTerm | None:
        """Retorna o termo de consentimento vigente da competição, se houver.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            ConsentTerm ou None se a competição não possui termo cadastrado.
        """
        return await ConsentTermRepository.get_by_competition_id(db, competition_id)

    @staticmethod
    async def upload(
        db: AsyncSession, competition_id: int, file: UploadFile
    ) -> ConsentTerm:
        """Faz upload (ou substitui) o termo de consentimento em PDF de uma competição.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            file: Arquivo enviado (deve ser PDF).

        Returns:
            ConsentTerm criado ou atualizado.

        Raises:
            HTTPException 422: formato não é PDF (pela extensão/content-type
                declarados ou pelos magic bytes do conteúdo real).
            HTTPException 413: arquivo excede o tamanho máximo.
        """
        content_type = (file.content_type or "").lower()
        filename = file.filename or ""
        is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")
        if not is_pdf:
            raise _invalid_pdf_format()
        data = await file.read()
        if len(data) > MAX_CONSENT_TERM_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "Arquivo muito grande. Tamanho máximo permitido: "
                    f"{MAX_CONSENT_TERM_BYTES // (1024 * 1024)} MB."
                ),
            )
        # Não confia apenas em extensão/content-type (facilmente forjáveis pelo
        # cliente): valida os magic bytes reais do conteúdo antes de aceitar.
        if not data.startswith(PDF_MAGIC_BYTES):
            raise _invalid_pdf_format()
        file_hash = hashlib.sha256(data).hexdigest()
        return await ConsentTermRepository.create_version(
            db, competition_id, data, filename or "termo.pdf", file_hash
        )

    @staticmethod
    async def delete(db: AsyncSession, competition_id: int) -> None:
        """Remove (soft delete) a versão vigente do termo de consentimento.

        Torna a competição sem exigência de aceite novamente (feature opcional),
        de forma não-destrutiva: a versão marcada como excluída permanece no
        banco, com os bytes do PDF intactos, para que inscrições antigas que a
        referenciam continuem tendo um arquivo recuperável.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Raises:
            HTTPException 404: nenhum termo vigente para esta competição.
        """
        term = await ConsentTermRepository.get_by_competition_id(db, competition_id)
        if not term:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nenhum termo de consentimento cadastrado para esta competição.",
            )
        await ConsentTermRepository.soft_delete(db, competition_id)
