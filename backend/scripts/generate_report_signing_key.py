"""Gera uma chave Ed25519 nova para REPORT_SIGNING_PRIVATE_KEY (ADR-012).

Uso: python scripts/generate_report_signing_key.py
Guarde a saída só no .env do servidor. Trocar a chave invalida a verificação de
todos os PDFs já emitidos — faça isso apenas se a chave vazar.
"""

import base64
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    raw = Ed25519PrivateKey.generate().private_bytes_raw()
    sys.stdout.write(f"REPORT_SIGNING_PRIVATE_KEY={base64.b64encode(raw).decode()}\n")


if __name__ == "__main__":
    main()
