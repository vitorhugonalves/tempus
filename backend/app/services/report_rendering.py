"""Montagem de HTML e conversão para PDF dos relatórios de ranking (ADR-012).

Funções puras (sem banco): recebem dados prontos e devolvem HTML/bytes.
"""

import html
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import segno

from app.core.config import settings
from app.core.constants import REPORT_TIMEZONE, REPORT_VERIFY_PATH
from app.schemas.timer import RankingEntry

_NO_ADJUSTMENT = "—"


class PdfRendererUnavailableError(RuntimeError):
    """WeasyPrint não instalado — PDF assinado não pode ser gerado."""


def seconds_to_hms(seconds: int) -> str:
    """Converte segundos para HH:MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_local_datetime(dt_utc_naive: datetime, with_seconds: bool = True) -> str:
    """Formata um datetime UTC naive (padrão do banco) no horário de Brasília."""
    local = dt_utc_naive.replace(tzinfo=UTC).astimezone(ZoneInfo(REPORT_TIMEZONE))
    return local.strftime("%d/%m/%Y %H:%M:%S" if with_seconds else "%d/%m/%Y %H:%M")


def verification_url(code: str) -> str:
    """URL pública da página de verificação de um código."""
    return f"{settings.FRONTEND_URL.rstrip('/')}{REPORT_VERIFY_PATH}/{code}"


def qr_svg(url: str) -> str:
    """QR code em SVG inline (dispensa url_fetcher, que fica bloqueado)."""
    return segno.make(url, error="m").svg_inline(scale=2, border=1)


def _adjustment_cell(entry: RankingEntry) -> str:
    if not entry.adjustment_note or entry.adjusted_at is None:
        return _NO_ADJUSTMENT
    when = format_local_datetime(entry.adjusted_at, with_seconds=False)
    return f"{html.escape(entry.adjustment_note)} — ajustado em {when}"


def ranking_rows_html(entries: list[RankingEntry]) -> str:
    """Linhas <tr> do ranking de tempo, com coluna de justificativa."""
    return "".join(
        "<tr>"
        f"<td>{entry.position or '-'}</td>"
        f"<td>{html.escape(entry.athlete_name)}</td>"
        f"<td>{html.escape(entry.category_name or '-')}</td>"
        f"<td>{seconds_to_hms(entry.elapsed_seconds)}</td>"
        f"<td>{entry.total_penalty_seconds}s</td>"
        f"<td><strong>{seconds_to_hms(entry.final_seconds)}</strong></td>"
        f"<td>{html.escape(entry.status.value)}</td>"
        f'<td class="note">{_adjustment_cell(entry)}</td>'
        "</tr>"
        for entry in entries
    )


def ranking_table_html(entries: list[RankingEntry]) -> str:
    """Tabela completa do ranking de tempo."""
    return (
        "<table><thead><tr>"
        "<th>Pos.</th><th>Atleta/Equipe</th><th>Categoria</th><th>Cronometrado</th>"
        "<th>Penalidades</th><th>Tempo Final</th><th>Status</th><th>Justificativa</th>"
        f"</tr></thead><tbody>{ranking_rows_html(entries)}</tbody></table>"
    )


def build_document_html(
    *, title: str, table_html: str, issued_at: datetime, code: str, font_size_px: int
) -> str:
    """Documento completo: cabeçalho com data de geração, tabela e verificação.

    O código vai também no rodapé de toda página (CSS @page); é url-safe
    ([A-Za-z0-9_-]), então pode entrar numa string CSS sem escape.
    """
    generated_at = format_local_datetime(issued_at)
    url = verification_url(code)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  @page {{
    margin: 18mm 12mm 20mm 12mm;
    @bottom-left {{
      content: "Código de verificação: {code}";
      font-family: Arial, sans-serif; font-size: 8px; color: #555;
    }}
    @bottom-right {{
      content: "Página " counter(page) " de " counter(pages);
      font-family: Arial, sans-serif; font-size: 8px; color: #555;
    }}
  }}
  body {{ font-family: Arial, sans-serif; font-size: {font_size_px}px; }}
  h1 {{ text-align: center; font-size: 16px; margin-bottom: 2px; }}
  .generated {{ text-align: center; color: #555; font-size: 10px; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  th {{ background: #1a1a2e; color: white; padding: 6px 4px; font-size: 10px; }}
  td {{ padding: 5px 4px; border-bottom: 1px solid #ddd; text-align: center; }}
  td.note {{ text-align: left; font-size: 9px; max-width: 180px; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  small {{ color: #666; }}
  table.verification {{ width: auto; margin-top: 24px; border-top: 1px solid #ccc; }}
  table.verification td {{ border: none; text-align: left; vertical-align: middle;
                           font-size: 9px; color: #333; background: white; }}
  table.verification svg {{ width: 90px; height: 90px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p class="generated">Gerado em {generated_at} (horário de Brasília)</p>
{table_html}
<table class="verification"><tr>
  <td>{qr_svg(url)}</td>
  <td>
    <strong>Documento assinado digitalmente pelo Tempus.</strong><br>
    Código de verificação: <strong>{code}</strong><br>
    Confira a autenticidade em {html.escape(url)}<br>
    Qualquer alteração neste arquivo invalida a verificação.
  </td>
</tr></table>
</body>
</html>"""


def _deny_url_fetcher(url: str, **_kw: object) -> dict:
    # Impede o WeasyPrint de buscar file:// ou IPs internos (SSRF).
    return {"string": b"", "mime_type": "text/plain"}


def html_to_pdf(document_html: str) -> bytes:
    """Converte HTML em PDF com WeasyPrint.

    Raises:
        PdfRendererUnavailableError: WeasyPrint não instalado.
    """
    try:
        import weasyprint  # type: ignore[import]
    except ImportError as exc:
        raise PdfRendererUnavailableError("WeasyPrint não disponível") from exc
    return weasyprint.HTML(
        string=document_html, url_fetcher=_deny_url_fetcher
    ).write_pdf()


def _wod_cell_html(we) -> str:
    if we.walkover:
        return "<span style='color:#dc2626;font-weight:bold'>W.O.</span>"
    if (
        we.points == 0
        and we.rank is None
        and we.reps is None
        and we.time_seconds is None
    ):
        return "N/A"
    if we.wod_type == "amrap":
        if we.reps is None:
            return "—"
        return f"{we.reps or 0} reps<br><small>({we.points} pts)</small>"
    if we.wod_type == "for_time":
        if we.time_seconds is None:
            return "—"
        reps_part = f" +{we.reps}r" if we.reps else ""
        time_text = seconds_to_hms(we.time_seconds)
        return f"{time_text}{reps_part}<br><small>({we.points} pts)</small>"
    return "N/D"


def wod_leaderboard_table_html(leaderboard) -> str:
    """Tabela do Leaderboard WODs (CrossFit)."""
    first_wods = leaderboard.entries[0].wod_entries if leaderboard.entries else []
    headers = "".join(
        f"<th>{html.escape(we.wod_name)}<br>"
        f"<small>({html.escape(we.wod_type)})</small></th>"
        for we in first_wods
    )
    rows = "".join(
        "<tr>"
        f"<td>{entry.position}º</td>"
        f"<td>{html.escape(entry.team_name)}</td>"
        + "".join(f"<td>{_wod_cell_html(we)}</td>" for we in entry.wod_entries)
        + f"<td><strong>{entry.total_points} pts</strong></td>"
        "</tr>"
        for entry in leaderboard.entries
    )
    return (
        "<table><thead><tr><th>Pos.</th><th>Equipe</th>"
        f"{headers}<th>Total</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )
