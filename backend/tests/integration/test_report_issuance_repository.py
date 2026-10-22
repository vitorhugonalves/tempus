from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.report_issuance import ReportIssuance
from app.repositories.report_issuance import ReportIssuanceRepository


async def _competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Repo")
    db.add(comp)
    await db.flush()
    return comp


def _issuance(
    competition_id: int, code: str = "code-1", sha: str = "f" * 64
) -> ReportIssuance:
    return ReportIssuance(
        verification_code=code,
        report_type="ranking",
        competition_id=competition_id,
        competition_name="Comp Repo",
        category_id=None,
        category_name=None,
        issued_by_user_id=None,
        issued_by_role="admin",
        issued_at=datetime(2026, 10, 22, 12, 0, 0),
        sha256=sha,
        signature="sig",
        pdf_data=b"%PDF-1.7 fake",
    )


async def test_create_and_get_by_code_returns_issuance(db: AsyncSession):
    comp = await _competition(db)
    await ReportIssuanceRepository.create(db, _issuance(comp.id))
    found = await ReportIssuanceRepository.get_by_code(db, "code-1")
    assert found is not None
    assert found.competition_name == "Comp Repo"


async def test_get_by_code_unknown_returns_none(db: AsyncSession):
    assert await ReportIssuanceRepository.get_by_code(db, "nao-existe") is None


async def test_get_by_sha256_returns_issuance(db: AsyncSession):
    comp = await _competition(db)
    await ReportIssuanceRepository.create(db, _issuance(comp.id, sha="1" * 64))
    found = await ReportIssuanceRepository.get_by_sha256(db, "1" * 64)
    assert found is not None and found.verification_code == "code-1"


async def test_load_pdf_data_returns_stored_bytes(db: AsyncSession):
    comp = await _competition(db)
    await ReportIssuanceRepository.create(db, _issuance(comp.id))
    found = await ReportIssuanceRepository.get_by_code(db, "code-1")
    assert await ReportIssuanceRepository.load_pdf_data(db, found) == b"%PDF-1.7 fake"


async def test_exists_for_competition_reflects_issuances(db: AsyncSession):
    comp = await _competition(db)
    assert await ReportIssuanceRepository.exists_for_competition(db, comp.id) is False
    await ReportIssuanceRepository.create(db, _issuance(comp.id))
    assert await ReportIssuanceRepository.exists_for_competition(db, comp.id) is True
