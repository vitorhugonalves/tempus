"""Registro imutável de cada PDF de relatório emitido e assinado (ADR-012)."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportIssuance(Base):
    """Uma emissão de PDF de relatório.

    Append-only: nenhuma linha é atualizada ou removida. Nomes de competição,
    categoria e o papel do emissor são *snapshots* do momento da emissão e entram
    no payload assinado — o documento continua verificável mesmo que a categoria
    seja renomeada/excluída ou o usuário removido.
    Sem `relationship` de propósito: a emissão nunca deve ser carregada/cascateada
    junto com a competição.
    """

    __tablename__ = "report_issuances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    verification_code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # RESTRICT: excluir a competição apagaria a prova; a exclusão é barrada antes (409).
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    competition_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Sem FK de propósito: o id entra no payload assinado; um ON DELETE SET NULL
    # mudaria o payload ao excluir o usuário e o PDF passaria a constar adulterado.
    issued_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issued_by_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    # deferred: rota pública de metadados não carrega os bytes do PDF por padrão.
    pdf_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
