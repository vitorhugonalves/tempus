import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models.timer import TimerStatus
from app.schemas.timer import RankingEntry
from app.services import report_rendering
from app.services.report_rendering import (
    PdfRendererUnavailableError,
    build_document_html,
    format_local_datetime,
    ranking_table_html,
    wod_leaderboard_table_html,
)


def _entry(**overrides) -> RankingEntry:
    base = dict(
        position=1,
        timer_id=1,
        user_id=None,
        team_id=1,
        athlete_name="Equipe A",
        team_name="Equipe A",
        box_name=None,
        category_name="Dupla",
        accumulated_ms=0,
        elapsed_seconds=4680,
        total_penalty_seconds=0,
        final_seconds=4680,
        infractions_count=0,
        remaining_seconds=None,
        status=TimerStatus.finished,
    )
    base.update(overrides)
    return RankingEntry(**base)


def test_format_local_datetime_converts_utc_to_brasilia():
    utc_afternoon = datetime(2026, 10, 22, 15, 30, 5)
    assert format_local_datetime(utc_afternoon) == "22/10/2026 12:30:05"


def test_ranking_table_shows_note_with_adjusted_date():
    html = ranking_table_html(
        [
            _entry(
                adjustment_note="Timer finalizado por engano",
                adjusted_at=datetime(2026, 10, 18, 17, 32, 0),
            ),
        ]
    )
    assert "Justificativa" in html
    assert "Timer finalizado por engano — ajustado em 18/10/2026 14:32" in html


def test_ranking_table_without_adjustment_shows_dash():
    html = ranking_table_html([_entry()])
    assert '<td class="note">—</td>' in html


def test_ranking_document_escapes_adjustment_note():
    html = ranking_table_html(
        [
            _entry(
                adjustment_note="<script>alert('x')</script> & cia",
                adjusted_at=datetime(2026, 10, 18, 17, 32, 0),
            ),
        ]
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; cia" in html


def test_document_has_generated_at_code_and_qr():
    html = build_document_html(
        title="Ranking — Comp",
        table_html="<table></table>",
        issued_at=datetime(2026, 10, 22, 15, 30, 5),
        code="CODE123",
        font_size_px=12,
    )
    assert "Gerado em 22/10/2026 12:30:05 (horário de Brasília)" in html
    assert "CODE123" in html
    assert "/verificar/CODE123" in html
    assert "<svg" in html


def test_html_to_pdf_without_weasyprint_raises_explicit_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    with pytest.raises(PdfRendererUnavailableError):
        report_rendering.html_to_pdf("<p>x</p>")


def test_html_to_pdf_returns_pdf_bytes():
    assert report_rendering.html_to_pdf("<p>x</p>").startswith(b"%PDF")


def test_wod_leaderboard_table_renders_walkover_and_escapes_names():
    wod = SimpleNamespace(
        wod_name="<b>WOD 1</b>",
        wod_type="for_time",
        walkover=True,
        points=0,
        rank=None,
        reps=None,
        time_seconds=None,
    )
    entry = SimpleNamespace(
        position=1, team_name="Equipe & Cia", total_points=10, wod_entries=[wod]
    )
    html = wod_leaderboard_table_html(SimpleNamespace(entries=[entry]))
    assert "W.O." in html
    assert "Equipe &amp; Cia" in html
    assert "&lt;b&gt;WOD 1&lt;/b&gt;" in html
