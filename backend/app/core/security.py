import secrets

import bcrypt

_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Gera o hash bcrypt de uma senha.

    Args:
        password: Senha em texto puro.

    Returns:
        Hash bcrypt da senha (string UTF-8).
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode(
        "utf-8"
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto puro corresponde ao hash armazenado.

    Args:
        plain_password: Senha em texto puro.
        hashed_password: Hash armazenado no banco de dados.

    Returns:
        True se a senha for correta, False caso contrário.
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def generate_session_token() -> str:
    """Gera um token de sessão seguro com 32 bytes aleatórios.

    Returns:
        Token URL-safe codificado em base64.
    """
    return secrets.token_urlsafe(32)


def generate_invite_token() -> str:
    """Gera um token de convite de uso único.

    Returns:
        Token URL-safe de 32 bytes em base64.
    """
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Gera um token para redefinição de senha.

    Returns:
        Token URL-safe de 32 bytes em base64.
    """
    return secrets.token_urlsafe(32)
