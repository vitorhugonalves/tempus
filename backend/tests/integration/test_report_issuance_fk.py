"""Efeitos de FK reais sobre emissões assinadas.

A fixture `db` padrão roda SQLite sem `PRAGMA foreign_keys`, então ON DELETE nunca
dispara e não pega efeitos colaterais que o Postgres de produção aplica. Este módulo
usa um engine próprio com FKs ativas.
"""

from datetime import datetime

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.competition import Competition
from app.models.report_issuance import ReportIssuance
from app.models.user import User, UserRole
from app.services.report import payload_from_issuance
from app.services.report_signing import ReportSigningService


@pytest_asyncio.fixture
async def fk_db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def test_deleting_issuer_keeps_issuance_signature_valid(fk_db: AsyncSession):
    operator = User(
        full_name="Operador",
        email="operador-fk@example.com",
        hashed_password="x",
        role=UserRole.operator,
    )
    competition = Competition(name="Comp FK")
    fk_db.add_all([operator, competition])
    await fk_db.flush()
    issuance = ReportIssuance(
        verification_code="fk-code",
        report_type="ranking",
        competition_id=competition.id,
        competition_name="Comp FK",
        category_id=None,
        category_name=None,
        issued_by_user_id=operator.id,
        issued_by_role="operator",
        issued_at=datetime(2026, 10, 22, 12, 0, 0),
        sha256="a" * 64,
        signature="",
        pdf_data=b"%PDF-1.7",
    )
    issuance.signature = ReportSigningService.sign(payload_from_issuance(issuance))
    fk_db.add(issuance)
    await fk_db.flush()

    await fk_db.delete(operator)
    await fk_db.flush()
    await fk_db.refresh(issuance)

    assert ReportSigningService.verify(
        payload_from_issuance(issuance), issuance.signature
    )
