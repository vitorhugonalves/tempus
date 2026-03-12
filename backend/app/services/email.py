"""Serviço de envio de e-mails via SMTP (aiosmtplib)."""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _send(to_email: str, subject: str, html_body: str) -> None:
    """Envia um e-mail HTML via SMTP configurado.

    Args:
        to_email: Destinatário.
        subject: Assunto do e-mail.
        html_body: Corpo em HTML.

    Raises:
        Exception: Erro de conexão SMTP (logado e re-lançado).
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER or "noreply@tempus.app"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_PORT == 587,
        )
        logger.info("E-mail enviado para %s | assunto: %s", to_email, subject)
    except Exception as exc:
        logger.error("Falha ao enviar e-mail para %s: %s", to_email, exc)
        raise


async def send_password_reset(to_email: str, reset_link: str) -> None:
    """Envia e-mail de redefinição de senha (RF-05).

    Args:
        to_email: E-mail do usuário.
        reset_link: URL com token de redefinição.
    """
    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
    <h2 style="color:#1a1a2e">Redefinição de Senha — Tempus</h2>
    <p>Recebemos uma solicitação para redefinir a sua senha.</p>
    <p>Clique no botão abaixo. O link expira em <strong>72 horas</strong>.</p>
    <p style="text-align:center;margin:32px 0">
      <a href="{reset_link}"
         style="background:#4f46e5;color:white;padding:12px 24px;border-radius:6px;
                text-decoration:none;font-weight:bold">
        Redefinir Senha
      </a>
    </p>
    <p style="color:#888;font-size:12px">
      Se você não solicitou a redefinição, ignore este e-mail.<br>
      Link: {reset_link}
    </p>
    </body></html>
    """
    await _send(to_email, "Redefinição de Senha — Tempus", html)


async def send_registration_welcome(
    to_email: str,
    full_name: str,
    competition_name: str,
    temporary_password: str,
    login_url: str,
) -> None:
    """Envia e-mail de boas-vindas para novo participante criado automaticamente.

    Args:
        to_email: E-mail do novo usuário.
        full_name: Nome completo do usuário.
        competition_name: Nome da competição em que foi inscrito.
        temporary_password: Senha temporária gerada automaticamente.
        login_url: URL de login da plataforma.
    """
    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
    <h2 style="color:#1a1a2e">Bem-vindo ao Tempus, {full_name}!</h2>
    <p>Você foi inscrito em <strong>{competition_name}</strong>.</p>
    <p>Sua conta foi criada automaticamente. Use as credenciais abaixo para acessar:</p>
    <table style="background:#f4f4f8;padding:16px;border-radius:8px;width:100%;margin:16px 0">
      <tr><td style="color:#555">E-mail:</td><td><strong>{to_email}</strong></td></tr>
      <tr><td style="color:#555">Senha temporária:</td><td><strong>{temporary_password}</strong></td></tr>
    </table>
    <p style="text-align:center;margin:32px 0">
      <a href="{login_url}"
         style="background:#4f46e5;color:white;padding:12px 24px;border-radius:6px;
                text-decoration:none;font-weight:bold">
        Acessar Plataforma
      </a>
    </p>
    <p style="color:#888;font-size:12px">
      Recomendamos que você altere sua senha após o primeiro acesso.<br>
      Link: {login_url}
    </p>
    </body></html>
    """
    await _send(to_email, f"Bem-vindo à {competition_name} — Tempus", html)


async def send_competitor_invite(
    to_email: str,
    invite_link: str,
    competition_name: str,
    invited_by_name: str,
) -> None:
    """Envia convite para competidor se cadastrar (RF-13).

    Args:
        to_email: E-mail do competidor convidado.
        invite_link: URL com token de convite.
        competition_name: Nome da competição.
        invited_by_name: Nome de quem enviou o convite.
    """
    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
    <h2 style="color:#1a1a2e">Convite para Competição — Tempus</h2>
    <p><strong>{invited_by_name}</strong> convidou você para participar de
       <strong>{competition_name}</strong>.</p>
    <p>Clique no botão abaixo para completar o seu cadastro.
       O link expira em <strong>72 horas</strong>.</p>
    <p style="text-align:center;margin:32px 0">
      <a href="{invite_link}"
         style="background:#4f46e5;color:white;padding:12px 24px;border-radius:6px;
                text-decoration:none;font-weight:bold">
        Completar Cadastro
      </a>
    </p>
    <p style="color:#888;font-size:12px">
      Se você não esperava este convite, ignore este e-mail.<br>
      Link: {invite_link}
    </p>
    </body></html>
    """
    await _send(to_email, f"Convite para {competition_name} — Tempus", html)
