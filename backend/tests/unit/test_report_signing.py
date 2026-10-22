import base64
from dataclasses import replace
from datetime import datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import settings
from app.services.report_signing import (
    IssuancePayload,
    ReportSigningKeyError,
    ReportSigningService,
)


def _payload() -> IssuancePayload:
    return IssuancePayload(
        code="abc123",
        report_type="ranking",
        competition_id=7,
        competition_name="Hyrox Floripa",
        category_id=None,
        category_name=None,
        issued_at=datetime(2026, 10, 22, 15, 30, 0),
        issued_by_user_id=1,
        issued_by_role="admin",
        sha256="a" * 64,
    )


def _random_key_b64() -> str:
    return base64.b64encode(Ed25519PrivateKey.generate().private_bytes_raw()).decode()


def test_sign_then_verify_same_payload_returns_true():
    signature = ReportSigningService.sign(_payload())
    assert ReportSigningService.verify(_payload(), signature) is True


def test_verify_altered_payload_returns_false():
    signature = ReportSigningService.sign(_payload())
    altered = replace(_payload(), sha256="b" * 64)
    assert ReportSigningService.verify(altered, signature) is False


def test_verify_signature_from_other_key_returns_false(monkeypatch):
    signature = ReportSigningService.sign(_payload())
    monkeypatch.setattr(settings, "REPORT_SIGNING_PRIVATE_KEY", _random_key_b64())
    assert ReportSigningService.verify(_payload(), signature) is False


def test_verify_garbage_signature_returns_false():
    assert ReportSigningService.verify(_payload(), "não-é-base64!!") is False


def test_sign_without_key_raises_explicit_error(monkeypatch):
    monkeypatch.setattr(settings, "REPORT_SIGNING_PRIVATE_KEY", "")
    with pytest.raises(ReportSigningKeyError, match="REPORT_SIGNING_PRIVATE_KEY"):
        ReportSigningService.sign(_payload())


def test_sign_with_malformed_key_raises_explicit_error(monkeypatch):
    monkeypatch.setattr(settings, "REPORT_SIGNING_PRIVATE_KEY", "curta")
    with pytest.raises(ReportSigningKeyError):
        ReportSigningService.sign(_payload())


def test_payload_bytes_are_canonical_and_key_order_independent():
    data = _payload().to_bytes()
    assert data.startswith(b'{"category_id":null,"category_name":null,"code":"abc123"')
    assert b'"issued_at":"2026-10-22T15:30:00"' in data
    assert b" " not in data.replace(b"Hyrox Floripa", b"")


def test_public_key_pem_is_pem_encoded():
    pem = ReportSigningService.public_key_pem()
    assert pem.startswith("-----BEGIN PUBLIC KEY-----")
