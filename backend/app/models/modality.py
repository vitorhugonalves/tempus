from datetime import datetime

from sqlalchemy import Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Modality(Base):
    """Modalidade esportiva (ex: Hyrox, CrossFit).

    Cada modalidade pode definir um tempo padrão de competição (default_duration_seconds)
    que é pré-preenchido ao criar uma nova competição daquela modalidade.
    """

    __tablename__ = "modalities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    competitions: Mapped[list["Competition"]] = relationship(  # noqa: F821
        "Competition", back_populates="modality_rel"
    )
