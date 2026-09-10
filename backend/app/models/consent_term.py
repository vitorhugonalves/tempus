"""Modelo do termo de consentimento (LGPD/waiver) de uma competição."""

from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConsentTerm(Base):
    """Versão de um termo de consentimento em PDF vinculado a uma competição.

    Log de versões append-only por competição: cada upload cria uma nova linha,
    nenhuma linha é jamais atualizada ou removida (histórico preservado para que
    um `consent_term_hash` registrado numa inscrição antiga sempre corresponda a
    um PDF recuperável). A versão "vigente" é a mais recente (maior `id`) com
    `deleted_at IS NULL` — ver `ConsentTermRepository.get_by_competition_id`.
    """

    __tablename__ = "consent_terms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # `deferred=True`: esta coluna nunca é carregada por padrão. A rota pública de
    # metadados e o check de inscrição só precisam de file_name/file_hash/datas —
    # forçar o carregamento dos bytes do PDF (até 10MB) em toda query seria uma
    # amplificação de DoS numa rota pública e não autenticada.
    file_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    # Soft delete: quando preenchido, esta versão deixa de ser "vigente" para
    # novas inscrições, mas a linha e os bytes do PDF nunca são removidos.
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="consent_terms"
    )
