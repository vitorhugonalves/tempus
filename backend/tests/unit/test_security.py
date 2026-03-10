import pytest

from app.core.security import (
    generate_invite_token,
    generate_session_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_hash_different_from_plain():
    plain = "minha-senha-secreta"
    hashed = hash_password(plain)
    assert hashed != plain


def test_hash_password_generates_bcrypt_hash():
    hashed = hash_password("qualquer-senha")
    assert hashed.startswith("$2b$")


def test_verify_password_returns_true_for_correct_password():
    plain = "senha-correta-123"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_returns_false_for_wrong_password():
    hashed = hash_password("senha-original")
    assert verify_password("senha-errada", hashed) is False


def test_hash_password_same_input_generates_different_hashes():
    plain = "mesma-senha"
    hash1 = hash_password(plain)
    hash2 = hash_password(plain)
    assert hash1 != hash2


def test_generate_session_token_has_sufficient_length():
    token = generate_session_token()
    assert len(token) >= 40


def test_generate_session_token_is_unique():
    token1 = generate_session_token()
    token2 = generate_session_token()
    assert token1 != token2


def test_generate_invite_token_is_url_safe():
    token = generate_invite_token()
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in token)
