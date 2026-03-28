"""Seed de inicialização executado pela migration inicial.

Cria o usuário administrador padrão caso não exista nenhum admin no banco,
e persiste as credenciais geradas em .temp_cred na raiz do projeto.
"""

import logging
import secrets
import string
from pathlib import Path

import bcrypt
import sqlalchemy as sa

logger = logging.getLogger(__name__)

def _get_admin_email() -> str:
    from app.core.config import settings
    return settings.ADMIN_EMAIL


def _get_admin_full_name() -> str:
    from app.core.config import settings
    return settings.ADMIN_FULL_NAME
_PASSWORD_LENGTH = 20
_PASSWORD_CHARS = string.ascii_letters + string.digits + "!@#$%&*"

# Raiz do projeto: backend/app/db/seed.py → 3 níveis acima = backend/, mais 1 = raiz
_PROJECT_ROOT = Path(__file__).parents[3]
_CRED_FILE = _PROJECT_ROOT / ".temp_cred"


def _generate_password() -> str:
    """Gera uma senha aleatória segura.

    Returns:
        Senha de 20 caracteres com letras, dígitos e símbolos.
    """
    return "".join(secrets.choice(_PASSWORD_CHARS) for _ in range(_PASSWORD_LENGTH))


def _hash_password(password: str) -> str:
    """Gera hash bcrypt da senha.

    Args:
        password: Senha em texto puro.

    Returns:
        Hash bcrypt em string UTF-8.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _save_credentials(email: str, password: str, cred_file: Path) -> None:
    """Persiste as credenciais do admin em arquivo de texto.

    Args:
        email: E-mail do administrador criado.
        password: Senha em texto puro.
        cred_file: Caminho do arquivo de saída.
    """
    cred_file.write_text(
        f"email: {email}\n"
        f"password: {password}\n"
        f"role: admin\n"
        f"\n"
        f"IMPORTANTE: Delete este arquivo apos o primeiro login!\n",
        encoding="utf-8",
    )
    logger.info("Credenciais do admin salvas em: %s", cred_file)


def create_default_admin(conn: sa.engine.Connection, cred_file: Path = _CRED_FILE) -> None:
    """Cria o administrador padrão se não existir nenhum admin no banco.

    Deve ser chamada ao final do upgrade() da migration inicial.
    É idempotente: não cria duplicatas em re-execuções.

    Args:
        conn: Conexão síncrona do Alembic (op.get_bind()).
        cred_file: Caminho do arquivo onde as credenciais serão salvas.
    """
    result = conn.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    )
    admin_count = result.scalar()

    if admin_count and admin_count > 0:
        logger.info("Admin já existe — seed ignorado.")
        return

    admin_email = _get_admin_email()
    admin_full_name = _get_admin_full_name()
    password = _generate_password()
    hashed = _hash_password(password)

    conn.execute(
        sa.text(
            "INSERT INTO users (full_name, email, hashed_password, role, is_active) "
            "VALUES (:full_name, :email, :hashed_password, :role, :is_active)"
        ),
        {
            "full_name": admin_full_name,
            "email": admin_email,
            "hashed_password": hashed,
            "role": "admin",
            "is_active": True,
        },
    )

    _save_credentials(admin_email, password, cred_file)
    logger.info("Admin padrão criado: %s", admin_email)
    print(f"\n[Tempus] Admin criado. Credenciais salvas em: {cred_file}\n")
