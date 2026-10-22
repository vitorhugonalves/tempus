"""Assinatura Ed25519 dos PDFs de relatório emitidos (ADR-012).

A assinatura cobre os metadados da emissão + o SHA-256 dos bytes do PDF. Prova que
o arquivo foi emitido pelo Tempus e não foi alterado depois; não prova que os dados
estavam corretos antes da emissão (isso é papel da justificativa + audit_logs).
"""

import base64
import binascii
import json
from dataclasses import asdict, dataclass
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import settings

_ED25519_PRIVATE_KEY_BYTES = 32


class ReportSigningKeyError(RuntimeError):
    """Chave de assinatura ausente ou inválida — nenhum PDF pode ser emitido."""


@dataclass(frozen=True)
class IssuancePayload:
    """Campos de uma emissão cobertos pela assinatura."""

    code: str
    report_type: str
    competition_id: int
    competition_name: str
    category_id: int | None
    category_name: str | None
    issued_at: datetime
    issued_by_user_id: int | None
    issued_by_role: str | None
    sha256: str

    def to_bytes(self) -> bytes:
        """Serializa em JSON canônico: mesma emissão → mesmos bytes, sempre."""
        data = asdict(self)
        data["issued_at"] = self.issued_at.isoformat()
        return json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")


def _load_private_key() -> Ed25519PrivateKey:
    encoded = settings.REPORT_SIGNING_PRIVATE_KEY
    if not encoded:
        raise ReportSigningKeyError(
            "REPORT_SIGNING_PRIVATE_KEY não configurada — PDFs de relatório não "
            "podem ser emitidos sem assinatura"
        )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ReportSigningKeyError(
            "REPORT_SIGNING_PRIVATE_KEY não é base64 válido"
        ) from exc
    if len(raw) != _ED25519_PRIVATE_KEY_BYTES:
        raise ReportSigningKeyError(
            f"REPORT_SIGNING_PRIVATE_KEY deve ter {_ED25519_PRIVATE_KEY_BYTES} bytes, "
            f"tem {len(raw)}"
        )
    return Ed25519PrivateKey.from_private_bytes(raw)


class ReportSigningService:
    """Assina e verifica emissões de relatório com Ed25519."""

    @staticmethod
    def sign(payload: IssuancePayload) -> str:
        """Assina o payload de uma emissão.

        Args:
            payload: Campos da emissão, incluindo o SHA-256 do PDF.

        Returns:
            Assinatura em base64.

        Raises:
            ReportSigningKeyError: chave ausente ou malformada.
        """
        signature = _load_private_key().sign(payload.to_bytes())
        return base64.b64encode(signature).decode("ascii")

    @staticmethod
    def verify(payload: IssuancePayload, signature: str) -> bool:
        """Confere se a assinatura corresponde ao payload.

        Args:
            payload: Campos da emissão como estão no banco agora.
            signature: Assinatura base64 gravada na emissão.

        Returns:
            True se íntegra; False se payload ou assinatura foram alterados.
        """
        public_key = _load_private_key().public_key()
        try:
            public_key.verify(
                base64.b64decode(signature, validate=True), payload.to_bytes()
            )
        except (InvalidSignature, binascii.Error, ValueError):
            return False
        return True

    @staticmethod
    def public_key_pem() -> str:
        """Retorna a chave pública em PEM, para verificação independente.

        Returns:
            Chave pública SubjectPublicKeyInfo em PEM.
        """
        return (
            _load_private_key()
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("ascii")
        )
