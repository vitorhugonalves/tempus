"""Geração de certificado PDF e imagem PNG por competidor (RF-41, RF-42, RF-43)."""

import io
import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.competition import Competition, CompetitionStatus
from app.models.timer import Penalty, Timer, TimerStatus
from app.models.user import User
from app.services.timer import RankingService

logger = logging.getLogger(__name__)


def _seconds_to_hms(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


async def _get_athlete_result(
    db: AsyncSession, competition_id: int, user_id: int
) -> dict:
    """Coleta dados do atleta para certificado.

    Args:
        db: Sessão assíncrona.
        competition_id: ID da competição.
        user_id: ID do usuário.

    Returns:
        Dict com athlete_name, category_name, final_seconds, position, comp_name, comp_date.

    Raises:
        HTTPException 404: Competição, usuário ou timer não encontrado.
        HTTPException 403: Competição não encerrada (RN-06).
    """
    result_comp = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result_comp.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada")

    # RN-06: só após encerramento oficial
    if competition.status != CompetitionStatus.finished:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Certificados disponíveis apenas após o encerramento da competição (RN-06)",
        )

    result_user = await db.execute(select(User).where(User.id == user_id))
    user = result_user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    result_timer = await db.execute(
        select(Timer)
        .options(
            selectinload(Timer.penalties).selectinload(Penalty.penalty_type),
            selectinload(Timer.category),
            selectinload(Timer.events),
        )
        .where(Timer.competition_id == competition_id, Timer.user_id == user_id)
    )
    timer = result_timer.scalar_one_or_none()
    if not timer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer não encontrado para este atleta")

    from app.schemas.timer import _compute_accumulated_ms

    penalty_seconds = sum(p.seconds_added for p in timer.penalties)
    final_seconds = _compute_accumulated_ms(timer) // 1000 + penalty_seconds

    # Posição no ranking
    ranking = await RankingService.get_ranking(db, competition_id)
    position = next((e.position for e in ranking if e.timer_id == timer.id), 0)

    return {
        "athlete_name": user.full_name,
        "category_name": timer.category.name if timer.category else "Geral",
        "final_seconds": final_seconds,
        "final_time": _seconds_to_hms(final_seconds),
        "penalty_seconds": penalty_seconds,
        "position": position,
        "comp_name": competition.name,
        "comp_date": competition.start_date.strftime("%d/%m/%Y") if competition.start_date else datetime.now().strftime("%d/%m/%Y"),
        "location": competition.location or "",
    }


async def generate_certificate_pdf(
    db: AsyncSession, competition_id: int, user_id: int
) -> bytes:
    """Gera certificado de participação em PDF (RF-41).

    Args:
        db: Sessão assíncrona.
        competition_id: ID da competição.
        user_id: ID do atleta.

    Returns:
        Bytes do PDF gerado.
    """
    data = await _get_athlete_result(db, competition_id, user_id)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4 landscape; margin: 20mm; }}
  body {{
    font-family: Arial, sans-serif;
    background: #fff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 160mm;
    text-align: center;
  }}
  .border {{
    border: 8px double #1a1a2e;
    padding: 40px 60px;
    width: 100%;
    box-sizing: border-box;
  }}
  .logo {{ font-size: 42px; font-weight: bold; color: #1a1a2e; letter-spacing: 4px; }}
  .subtitle {{ font-size: 14px; color: #666; margin-top: 4px; }}
  .divider {{ border: 1px solid #1a1a2e; margin: 20px auto; width: 80%; }}
  .certifies {{ font-size: 18px; color: #444; margin: 16px 0 8px; }}
  .name {{ font-size: 36px; font-weight: bold; color: #1a1a2e; margin: 8px 0; }}
  .text {{ font-size: 16px; color: #555; margin: 8px 0; }}
  .time {{ font-size: 28px; font-weight: bold; color: #4f46e5; margin: 8px 0; }}
  .position {{ font-size: 20px; color: #333; }}
  .footer {{ font-size: 11px; color: #999; margin-top: 24px; }}
</style>
</head>
<body>
<div class="border">
  <div class="logo">TEMPUS</div>
  <div class="subtitle">Gerenciador de Competições Esportivas</div>
  <div class="divider"></div>
  <div class="certifies">Certificamos que</div>
  <div class="name">{data['athlete_name']}</div>
  <div class="text">participou de <strong>{data['comp_name']}</strong></div>
  <div class="text">Categoria: <strong>{data['category_name']}</strong> · {data['comp_date']} {('· ' + data['location']) if data['location'] else ''}</div>
  <div class="time">⏱ {data['final_time']}</div>
  {f'<div class="position">🏆 {data["position"]}º lugar</div>' if data['position'] else ''}
  <div class="divider"></div>
  <div class="footer">Documento gerado automaticamente pelo Tempus · tempus.app</div>
</div>
</body>
</html>"""

    try:
        import weasyprint  # type: ignore[import]
        return weasyprint.HTML(string=html).write_pdf()
    except ImportError:
        logger.warning("WeasyPrint não disponível — retornando HTML como PDF fallback")
        return html.encode("utf-8")


async def generate_social_image(
    db: AsyncSession, competition_id: int, user_id: int
) -> bytes:
    """Gera imagem PNG para redes sociais (RF-42).

    Retorna um PNG 1080×1080px com: nome, competição, tempo final e posição.

    Args:
        db: Sessão assíncrona.
        competition_id: ID da competição.
        user_id: ID do atleta.

    Returns:
        Bytes do PNG gerado.
    """
    from PIL import Image, ImageDraw, ImageFont  # type: ignore[import]

    data = await _get_athlete_result(db, competition_id, user_id)

    img = Image.new("RGB", (1080, 1080), color="#1a1a2e")
    draw = ImageDraw.Draw(img)

    # Tenta carregar fontes do sistema; fallback para default
    try:
        font_xl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except OSError:
        font_xl = font_lg = font_md = font_sm = ImageFont.load_default()

    # Fundo gradiente simulado com retângulos
    draw.rectangle([0, 0, 1080, 300], fill="#0f0f23")
    draw.rectangle([0, 300, 1080, 780], fill="#1a1a2e")
    draw.rectangle([0, 780, 1080, 1080], fill="#12122a")

    # Linha decorativa topo
    draw.rectangle([80, 60, 1000, 64], fill="#4f46e5")

    # TEMPUS logo
    draw.text((540, 100), "TEMPUS", fill="#4f46e5", font=font_xl, anchor="mm")
    draw.text((540, 175), "Competição Esportiva", fill="#8888aa", font=font_sm, anchor="mm")

    # Nome da competição
    draw.text((540, 280), data["comp_name"], fill="#ccccdd", font=font_md, anchor="mm")

    # Separador
    draw.rectangle([80, 330, 1000, 333], fill="#333355")

    # Nome do atleta
    draw.text((540, 430), data["athlete_name"], fill="#ffffff", font=font_lg, anchor="mm")
    draw.text((540, 510), data["category_name"], fill="#8888aa", font=font_md, anchor="mm")

    # Tempo
    draw.text((540, 630), data["final_time"], fill="#4f46e5", font=font_xl, anchor="mm")
    draw.text((540, 710), "Tempo Final", fill="#888899", font=font_sm, anchor="mm")

    # Posição
    if data["position"]:
        pos_text = f"🏆 {data['position']}º LUGAR"
        draw.text((540, 810), pos_text, fill="#fbbf24", font=font_lg, anchor="mm")

    # Data e local
    details = f"{data['comp_date']}"
    if data["location"]:
        details += f"  ·  {data['location']}"
    draw.text((540, 940), details, fill="#666677", font=font_sm, anchor="mm")

    # Linha decorativa rodapé
    draw.rectangle([80, 1010, 1000, 1014], fill="#4f46e5")
    draw.text((540, 1050), "tempus.app", fill="#444455", font=font_sm, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
