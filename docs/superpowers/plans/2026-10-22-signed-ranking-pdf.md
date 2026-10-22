# PDF de Ranking Assinado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDFs de ranking (tempo e Leaderboard WODs) com data/hora de geração, coluna de justificativa do último ajuste de timer e assinatura Ed25519 verificável numa página pública `/verificar`.

**Architecture:** Cada exportação de PDF vira uma *emissão* (`report_issuances`): código de verificação aleatório impresso no PDF + QR; o SHA-256 dos bytes finais, os metadados e os próprios bytes ficam no banco, e uma assinatura Ed25519 cobre os metadados + hash. A montagem de HTML sai de `app/api/v1/reports.py` para `app/services/report_rendering.py` (funções puras) e `app/services/report.py` (orquestração). Endpoints públicos verificam por código ou por upload do arquivo.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, WeasyPrint, `cryptography` (Ed25519), `segno` (QR SVG), `tzdata`; React + TS + Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-22-signed-ranking-pdf-design.md`

## Global Constraints

- Branch: `feat/ranking-pdf-assinado`. Commits: `<tipo>(<escopo>): <descrição em português>` + linha `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Repositories/services usam só `flush()`, nunca `commit()`.
- Sem magic strings/numbers: tudo em `app/core/constants.py`.
- Docstrings Google Style em services e repositories; type hints em funções públicas.
- Datas no banco: `datetime` **naive em UTC** (padrão do projeto, ver `_utcnow()` em `app/services/timer.py`). Exibição em `America/Sao_Paulo`.
- Revision ID de migration ≤ 32 caracteres.
- Dependências novas sempre com piso **e** teto de versão maior.
- Rodar a partir de `backend/`: `.venv/bin/pytest`, `.venv/bin/ruff check app tests`, `.venv/bin/ruff format --check app tests`. Frontend a partir de `frontend/`: `npx vitest run`, `npx tsc --noEmit`, `npx eslint src`.
- Exportação de PDF continua restrita a `operator`/`admin`; verificação é pública.

### Desvios da spec (decididos no plano — confirmar na revisão)

1. **Chave em base64 bruta (32 bytes), não PEM**, em `REPORT_SIGNING_PRIVATE_KEY`: PEM é multilinha e quebra no `env_file` do docker-compose. A chave pública continua exposta em PEM.
2. **Snapshot de `competition_name`, `category_name` e `issued_by_role`** na emissão, incluídos no payload assinado: o documento reflete os nomes do momento da emissão e a verificação não depende de categoria/usuário ainda existirem.
3. **Status `tampered` em vez de `invalid_signature`**: a verificação também confere `sha256(pdf_data) == sha256` (o PDF guardado poderia ser trocado no banco sem tocar na assinatura); `tampered` cobre os dois casos.
4. **Exclusão de competição com emissões → 409** (guarda explícita), em vez de deixar o `RESTRICT` estourar 500 no Postgres.
5. `issued_at` truncado em segundos antes de assinar (evita divergência de microssegundos entre bancos).
6. **Exportar PDF de competição inexistente → 404** (hoje gera um PDF vazio com título "Competição #id"; não faz sentido assinar isso).

## Review Focus

1. Justificativa com HTML/JS (`<script>`, `&`, aspas) → deve sair escapada no PDF, nunca interpretada. (Task 4, teste `test_ranking_document_escapes_adjustment_note`.)
2. Timer ajustado duas vezes → coluna mostra só o **último** ajuste. (Task 3, `test_ranking_entry_shows_last_adjustment_only`.)
3. PDF guardado trocado no banco sem mexer no hash/assinatura → verificação deve acusar `tampered` e bloquear o download. (Task 6, `test_verify_code_with_swapped_pdf_data_returns_tampered`.)
4. Exportação sem chave configurada → erro explícito 500, nenhuma emissão gravada. (Task 4, `test_export_pdf_without_signing_key_returns_500`.)
5. Upload de arquivo enorme ou não-PDF na rota pública → 413/422 sem processar. (Task 6, `test_verify_upload_too_large_returns_413`, `test_verify_upload_not_pdf_returns_422`.)

---

### Task 1: Dependências, configuração e `ReportSigningService`

**Files:**
- Modify: `backend/pyproject.toml` (dependencies)
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/constants.py`
- Create: `backend/app/services/report_signing.py`
- Create: `backend/scripts/generate_report_signing_key.py`
- Modify: `backend/tests/conftest.py` (chave de teste)
- Test: `backend/tests/unit/test_report_signing.py`

**Interfaces:**
- Produces:
  - `IssuancePayload` (dataclass frozen): `code: str, report_type: str, competition_id: int, competition_name: str, category_id: int | None, category_name: str | None, issued_at: datetime, issued_by_user_id: int | None, issued_by_role: str | None, sha256: str`; método `to_bytes() -> bytes`.
  - `ReportSigningKeyError(RuntimeError)`
  - `ReportSigningService.sign(payload: IssuancePayload) -> str` (base64)
  - `ReportSigningService.verify(payload: IssuancePayload, signature: str) -> bool`
  - `ReportSigningService.public_key_pem() -> str`
  - Constantes: `REPORT_TYPE_RANKING = "ranking"`, `REPORT_TYPE_WOD_LEADERBOARD = "wod_leaderboard"`, `REPORT_TIMEZONE = "America/Sao_Paulo"`, `REPORT_VERIFY_MAX_UPLOAD_BYTES = 10 * 1024 * 1024`, `REPORT_VERIFY_RATE_LIMIT = "30/minute"`, `REPORT_VERIFICATION_CODE_BYTES = 16`, `REPORT_VERIFY_PATH = "/verificar"`.

- [ ] **Step 1: Instalar dependências e fixar versões**

```bash
cd backend && .venv/bin/pip install cryptography segno tzdata && .venv/bin/pip show cryptography segno tzdata | grep -E "^(Name|Version)"
```

Em `pyproject.toml`, após `"redis[hiredis]>=5.0.0",`, adicionar (usar as versões instaladas como piso, teto = próximo major; ex. se instalou cryptography 46.0.2 → `>=46.0.2,<47`):

```toml
    # Assinatura Ed25519 dos PDFs de relatório (ADR-012).
    "cryptography>=<INSTALADA>,<<MAJOR+1>",
    # QR code em SVG puro para o rodapé dos PDFs (sem dependência nativa).
    "segno>=<INSTALADA>,<<MAJOR+1>",
    # Base de fusos para zoneinfo na imagem slim (horário de Brasília no PDF).
    "tzdata>=<INSTALADA>",
```

(`tzdata` é versionado por ano — sem teto.)

- [ ] **Step 2: Config e constantes**

`app/core/config.py`, abaixo de `FRONTEND_URL`:

```python
    # Chave privada Ed25519 (32 bytes em base64) que assina os PDFs de relatório.
    # Gere com `python scripts/generate_report_signing_key.py`. Vazia = exportação
    # de PDF falha com erro explícito (nunca emite PDF sem assinatura).
    REPORT_SIGNING_PRIVATE_KEY: str = ""
```

`app/core/constants.py`, ao final:

```python

# PDFs de relatório assinados (ADR-012).
REPORT_TYPE_RANKING = "ranking"
REPORT_TYPE_WOD_LEADERBOARD = "wod_leaderboard"
# Fuso exibido no "Gerado em" — o banco guarda UTC naive.
REPORT_TIMEZONE = "America/Sao_Paulo"
# 16 bytes → 22 caracteres url-safe: inviável de adivinhar por força bruta.
REPORT_VERIFICATION_CODE_BYTES = 16
REPORT_VERIFY_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
# Rotas públicas de verificação: barra enumeração de códigos.
REPORT_VERIFY_RATE_LIMIT = "30/minute"
# Rota do frontend apontada pelo QR code do PDF.
REPORT_VERIFY_PATH = "/verificar"
```

- [ ] **Step 3: Escrever os testes que falham** — `tests/unit/test_report_signing.py`

```python
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
```

- [ ] **Step 4: Chave de teste no `conftest.py`**

Logo após `app.state.limiter.enabled = False`:

```python
# Chave de assinatura de relatórios efêmera — gerada por execução, nunca versionada.
settings.REPORT_SIGNING_PRIVATE_KEY = base64.b64encode(
    Ed25519PrivateKey.generate().private_bytes_raw()
).decode()
```

Imports novos no topo (respeitando a ordem stdlib → third-party → local): `import base64`, `from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey`, `from app.core.config import settings`.

- [ ] **Step 5: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/unit/test_report_signing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.report_signing'`

- [ ] **Step 6: Implementar** — `app/services/report_signing.py`

```python
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
            public_key.verify(base64.b64decode(signature, validate=True), payload.to_bytes())
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
```

- [ ] **Step 7: Script de geração de chave** — `backend/scripts/generate_report_signing_key.py`

```python
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
```

(Se `backend/scripts/` não existir, criar. Usa `sys.stdout.write` porque o projeto proíbe `print()` para logging — aqui é saída de CLI.)

- [ ] **Step 8: Rodar e ver passar**

Run: `.venv/bin/pytest tests/unit/test_report_signing.py -v && .venv/bin/ruff check app tests scripts`
Expected: 8 passed, ruff sem erros.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml app/core/config.py app/core/constants.py app/services/report_signing.py scripts/generate_report_signing_key.py tests/conftest.py tests/unit/test_report_signing.py
git commit -m "feat(reports): serviço de assinatura Ed25519 para PDFs de relatório

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Modelo `ReportIssuance`, migration e repositório

**Files:**
- Create: `backend/app/models/report_issuance.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/db/migrations/versions/20261022_report_issuances.py`
- Create: `backend/app/repositories/report_issuance.py`
- Test: `backend/tests/integration/test_report_issuance_repository.py`

**Interfaces:**
- Consumes: nada de tasks anteriores além de constantes.
- Produces:
  - `ReportIssuance` (campos: `id, verification_code, report_type, competition_id, competition_name, category_id, category_name, issued_by_user_id, issued_by_role, issued_at, sha256, signature, pdf_data (deferred), created_at, updated_at`)
  - `ReportIssuanceRepository.create(db, issuance) -> ReportIssuance`
  - `ReportIssuanceRepository.get_by_code(db, code: str) -> ReportIssuance | None`
  - `ReportIssuanceRepository.get_by_sha256(db, sha256: str) -> ReportIssuance | None`
  - `ReportIssuanceRepository.load_pdf_data(db, issuance) -> bytes`
  - `ReportIssuanceRepository.exists_for_competition(db, competition_id: int) -> bool`

- [ ] **Step 1: Teste que falha** — `tests/integration/test_report_issuance_repository.py`

```python
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition
from app.models.report_issuance import ReportIssuance
from app.repositories.report_issuance import ReportIssuanceRepository


async def _competition(db: AsyncSession) -> Competition:
    comp = Competition(name="Comp Repo")
    db.add(comp)
    await db.flush()
    return comp


def _issuance(competition_id: int, code: str = "code-1", sha: str = "f" * 64) -> ReportIssuance:
    return ReportIssuance(
        verification_code=code,
        report_type="ranking",
        competition_id=competition_id,
        competition_name="Comp Repo",
        category_id=None,
        category_name=None,
        issued_by_user_id=None,
        issued_by_role="admin",
        issued_at=datetime(2026, 10, 22, 12, 0, 0),
        sha256=sha,
        signature="sig",
        pdf_data=b"%PDF-1.7 fake",
    )


async def test_create_and_get_by_code_returns_issuance(db: AsyncSession):
    comp = await _competition(db)
    await ReportIssuanceRepository.create(db, _issuance(comp.id))
    found = await ReportIssuanceRepository.get_by_code(db, "code-1")
    assert found is not None
    assert found.competition_name == "Comp Repo"


async def test_get_by_code_unknown_returns_none(db: AsyncSession):
    assert await ReportIssuanceRepository.get_by_code(db, "nao-existe") is None


async def test_get_by_sha256_returns_issuance(db: AsyncSession):
    comp = await _competition(db)
    await ReportIssuanceRepository.create(db, _issuance(comp.id, sha="1" * 64))
    found = await ReportIssuanceRepository.get_by_sha256(db, "1" * 64)
    assert found is not None and found.verification_code == "code-1"


async def test_load_pdf_data_returns_stored_bytes(db: AsyncSession):
    comp = await _competition(db)
    await ReportIssuanceRepository.create(db, _issuance(comp.id))
    found = await ReportIssuanceRepository.get_by_code(db, "code-1")
    assert await ReportIssuanceRepository.load_pdf_data(db, found) == b"%PDF-1.7 fake"


async def test_exists_for_competition_reflects_issuances(db: AsyncSession):
    comp = await _competition(db)
    assert await ReportIssuanceRepository.exists_for_competition(db, comp.id) is False
    await ReportIssuanceRepository.create(db, _issuance(comp.id))
    assert await ReportIssuanceRepository.exists_for_competition(db, comp.id) is True
```

(Se `Competition(name=...)` exigir outros campos obrigatórios, conferir `app/models/competition.py` e preencher os mínimos.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/integration/test_report_issuance_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: app.models.report_issuance`

- [ ] **Step 3: Modelo** — `app/models/report_issuance.py`

```python
"""Registro imutável de cada PDF de relatório emitido e assinado (ADR-012)."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportIssuance(Base):
    """Uma emissão de PDF de relatório.

    Append-only: nenhuma linha é atualizada ou removida. Nomes de competição,
    categoria e o papel do emissor são *snapshots* do momento da emissão e entram
    no payload assinado — o documento continua verificável mesmo que a categoria
    seja renomeada/excluída ou o usuário removido.
    Sem `relationship` de propósito: a emissão nunca deve ser carregada/cascateada
    junto com a competição.
    """

    __tablename__ = "report_issuances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    verification_code: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # RESTRICT: excluir a competição apagaria a prova; a exclusão é barrada antes (409).
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    competition_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issued_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_by_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    # deferred: rota pública de metadados não carrega os bytes do PDF por padrão.
    pdf_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
```

Em `app/models/__init__.py`: adicionar `from app.models.report_issuance import ReportIssuance` (ordem alfabética dos imports) e `"ReportIssuance"` no `__all__`.

- [ ] **Step 4: Repositório** — `app/repositories/report_issuance.py`

```python
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report_issuance import ReportIssuance


class ReportIssuanceRepository:
    """Acesso ao banco para emissões de relatório. Sem update/delete: registro imutável."""

    @staticmethod
    async def create(db: AsyncSession, issuance: ReportIssuance) -> ReportIssuance:
        """Persiste uma emissão (só flush; commit é do get_db).

        Args:
            db: Sessão assíncrona.
            issuance: Instância ORM não persistida.

        Returns:
            Emissão persistida.
        """
        db.add(issuance)
        await db.flush()
        return issuance

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> ReportIssuance | None:
        """Busca uma emissão pelo código de verificação impresso no PDF.

        Args:
            db: Sessão assíncrona.
            code: Código de verificação.

        Returns:
            Emissão ou None se não existir.
        """
        result = await db.execute(
            select(ReportIssuance).where(ReportIssuance.verification_code == code)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_sha256(db: AsyncSession, sha256: str) -> ReportIssuance | None:
        """Busca uma emissão pelo hash dos bytes do PDF.

        Args:
            db: Sessão assíncrona.
            sha256: Hash hex (64 chars).

        Returns:
            Emissão ou None se nenhum PDF emitido tiver esse hash.
        """
        result = await db.execute(
            select(ReportIssuance).where(ReportIssuance.sha256 == sha256).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def load_pdf_data(db: AsyncSession, issuance: ReportIssuance) -> bytes:
        """Carrega os bytes do PDF (coluna deferred) de forma explícita.

        Acesso direto a `issuance.pdf_data` fora do greenlet quebra com
        MissingGreenlet em AsyncSession — por isso o refresh explícito.

        Args:
            db: Sessão assíncrona.
            issuance: Emissão já carregada na sessão.

        Returns:
            Bytes do PDF original.
        """
        await db.refresh(issuance, attribute_names=["pdf_data"])
        return issuance.pdf_data

    @staticmethod
    async def exists_for_competition(db: AsyncSession, competition_id: int) -> bool:
        """Indica se a competição já tem algum relatório emitido.

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            True se houver ao menos uma emissão.
        """
        result = await db.execute(
            select(exists().where(ReportIssuance.competition_id == competition_id))
        )
        return bool(result.scalar())
```

- [ ] **Step 5: Migration** — `app/db/migrations/versions/20261022_report_issuances.py`

```python
"""report issuances — registro assinado de PDFs de relatório emitidos

Revision ID: 20261022_report_issuances
Revises: 20260911_drop_competition_links
Create Date: 2026-10-22

Cria a tabela report_issuances (ADR-012): uma linha imutável por PDF de ranking
emitido, com código de verificação, SHA-256, assinatura Ed25519 e os bytes do PDF.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261022_report_issuances"
down_revision = "20260911_drop_competition_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_issuances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("verification_code", sa.String(32), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column(
            "competition_id",
            sa.Integer(),
            sa.ForeignKey("competitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("competition_name", sa.String(200), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("category_name", sa.String(200), nullable=True),
        sa.Column(
            "issued_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("issued_by_role", sa.String(20), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("pdf_data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_issuances_id", "report_issuances", ["id"])
    op.create_index(
        "ix_report_issuances_verification_code",
        "report_issuances",
        ["verification_code"],
        unique=True,
    )
    op.create_index(
        "ix_report_issuances_competition_id", "report_issuances", ["competition_id"]
    )
    op.create_index("ix_report_issuances_sha256", "report_issuances", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_report_issuances_sha256", table_name="report_issuances")
    op.drop_index("ix_report_issuances_competition_id", table_name="report_issuances")
    op.drop_index("ix_report_issuances_verification_code", table_name="report_issuances")
    op.drop_index("ix_report_issuances_id", table_name="report_issuances")
    op.drop_table("report_issuances")
```

Conferir o formato de `created_at` nas migrations vizinhas (`20260910_consent_term.py`) e igualar.

- [ ] **Step 6: Validar migration num SQLite descartável**

```bash
cd backend && DATABASE_URL=sqlite+aiosqlite:////tmp/claude-1000/mig_check.db .venv/bin/python -m alembic upgrade head && DATABASE_URL=sqlite+aiosqlite:////tmp/claude-1000/mig_check.db .venv/bin/python -m alembic downgrade -1 && DATABASE_URL=sqlite+aiosqlite:////tmp/claude-1000/mig_check.db .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic heads; rm -f /tmp/claude-1000/mig_check.db
```
Expected: upgrade/downgrade/upgrade sem erro; `heads` → `20261022_report_issuances (head)`. (Se o env exigir outras variáveis, como `SECRET_KEY`/`ADMIN_EMAIL`, exportá-las com valores fictícios no mesmo comando.)

- [ ] **Step 7: Rodar e ver passar**

Run: `.venv/bin/pytest tests/integration/test_report_issuance_repository.py -v`
Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
git add app/models/report_issuance.py app/models/__init__.py app/db/migrations/versions/20261022_report_issuances.py app/repositories/report_issuance.py tests/integration/test_report_issuance_repository.py
git commit -m "db(reports): tabela report_issuances e repositório

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Justificativa do último ajuste no `RankingEntry`

**Files:**
- Modify: `backend/app/schemas/timer.py` (`RankingEntry`, ~linha 193)
- Modify: `backend/app/services/timer.py` (`RankingService.get_ranking`, ~linha 784)
- Test: `backend/tests/integration/test_ranking_adjustment_note.py`

**Interfaces:**
- Produces: `RankingEntry.adjustment_note: str | None = None`, `RankingEntry.adjusted_at: datetime | None = None` (UTC naive, `event_at` do evento `adjusted` de maior `id`).

- [ ] **Step 1: Teste que falha** — `tests/integration/test_ranking_adjustment_note.py`

```python
from httpx import AsyncClient


async def _finished_timer(client: AsyncClient, admin_token: str, judge_token: str, competitor_user) -> tuple[int, int]:
    """Competição ativa + timer finalizado. Função, não fixture (ver memória: loop do fakeredis)."""
    comp = (
        await client.post(
            "/api/v1/competitions", json={"name": "Comp Justificativa"},
            cookies={"session_id": admin_token},
        )
    ).json()
    await client.patch(
        f"/api/v1/competitions/{comp['id']}", json={"status": "active"},
        cookies={"session_id": admin_token},
    )
    timer_id = (
        await client.post(
            "/api/v1/timers",
            json={"competition_id": comp["id"], "user_id": competitor_user.id},
            cookies={"session_id": admin_token},
        )
    ).json()["id"]
    for action in ("start", "finish"):
        r = await client.post(
            f"/api/v1/timers/{timer_id}/{action}", json={},
            cookies={"session_id": judge_token},
        )
        assert r.status_code == 200, r.text
    return comp["id"], timer_id


async def _adjust(client: AsyncClient, admin_token: str, timer_id: int, justification: str) -> None:
    r = await client.post(
        f"/api/v1/timers/{timer_id}/adjust",
        json={"final_time_ms": 4_680_000, "justification": justification},
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200, r.text


async def test_ranking_entry_without_adjustment_has_null_note(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    comp_id, _ = await _finished_timer(client, admin_token, judge_token, competitor_user)
    entry = (await client.get(f"/api/v1/competitions/{comp_id}/ranking")).json()[0]
    assert entry["adjustment_note"] is None
    assert entry["adjusted_at"] is None


async def test_ranking_entry_shows_last_adjustment_only(
    client: AsyncClient, admin_token: str, judge_token: str, competitor_user
):
    comp_id, timer_id = await _finished_timer(client, admin_token, judge_token, competitor_user)
    await _adjust(client, admin_token, timer_id, "Primeira correção do tempo")
    await _adjust(client, admin_token, timer_id, "Segunda correção — falha na largada")
    entry = (await client.get(f"/api/v1/competitions/{comp_id}/ranking")).json()[0]
    assert entry["adjustment_note"] == "Segunda correção — falha na largada"
    assert entry["adjusted_at"] is not None
```

(Se `/adjust` responder 409 no segundo ajuste por alguma trava existente, conferir `TimerService.adjust` — ADR-011 permite reajustar timer `finished`; ajustar o teste somente após confirmar a regra.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/integration/test_ranking_adjustment_note.py -v`
Expected: FAIL — `KeyError: 'adjustment_note'`

- [ ] **Step 3: Implementar**

`app/schemas/timer.py`, em `RankingEntry`, após `status: TimerStatus` (garantir `from datetime import datetime` no topo):

```python
    # Último ajuste manual de tempo (ADR-011): exibido no PDF assinado (ADR-012).
    adjustment_note: str | None = None
    adjusted_at: datetime | None = None
```

`app/services/timer.py`, função de módulo perto de `_compute_accumulated_ms_from_stopped_state`:

```python
def _last_adjustment_event(timer: Timer) -> TimerEvent | None:
    """Evento `adjusted` mais recente (maior id) do timer, se houver."""
    adjustments = [e for e in timer.events if e.event_type == TimerEventType.adjusted]
    return max(adjustments, key=lambda e: e.id, default=None)
```

Em `get_ranking`, dentro do loop, antes de `entries.append(`:

```python
            last_adjustment = _last_adjustment_event(timer)
```

e no construtor `RankingEntry(...)`, após `status=timer.status,`:

```python
                    adjustment_note=last_adjustment.note if last_adjustment else None,
                    adjusted_at=last_adjustment.event_at if last_adjustment else None,
```

(Conferir que `TimerEvent` está importado em `app/services/timer.py`; `TimerEventType` já está.)

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/integration/test_ranking_adjustment_note.py tests/integration/test_timer_adjust.py -v`
Expected: tudo passa.

- [ ] **Step 5: Frontend — tipo**

Em `frontend/src/types/index.ts`, na interface `RankingEntry`, adicionar:

```ts
  adjustment_note: string | null;
  adjusted_at: string | null;
```

Run (em `frontend/`): `npx tsc --noEmit` → sem erros.

- [ ] **Step 6: Commit**

```bash
git add app/schemas/timer.py app/services/timer.py tests/integration/test_ranking_adjustment_note.py ../frontend/src/types/index.ts
git commit -m "feat(ranking): expor justificativa do último ajuste de timer

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Renderização + emissão do PDF de ranking assinado

**Files:**
- Create: `backend/app/services/report_rendering.py` (funções puras de HTML/PDF)
- Create: `backend/app/services/report.py` (`ReportService`)
- Modify: `backend/app/api/v1/reports.py` (`export_ranking_pdf`)
- Test: `backend/tests/unit/test_report_rendering.py`
- Test: `backend/tests/integration/test_report_export_signed.py`

**Interfaces:**
- Consumes: `IssuancePayload`, `ReportSigningService`, `ReportSigningKeyError` (Task 1); `ReportIssuance`, `ReportIssuanceRepository` (Task 2); `RankingEntry.adjustment_note/adjusted_at` (Task 3).
- Produces:
  - `report_rendering.PdfRendererUnavailableError(RuntimeError)`
  - `report_rendering.format_local_datetime(dt_utc_naive: datetime) -> str` → `"22/10/2026 12:30:00"`
  - `report_rendering.verification_url(code: str) -> str`
  - `report_rendering.qr_svg(url: str) -> str`
  - `report_rendering.ranking_rows_html(entries: list[RankingEntry]) -> str`
  - `report_rendering.ranking_table_html(entries: list[RankingEntry]) -> str`
  - `report_rendering.build_document_html(*, title: str, table_html: str, issued_at: datetime, code: str, font_size_px: int) -> str`
  - `report_rendering.html_to_pdf(document_html: str) -> bytes`
  - `ReportService.issue_ranking_pdf(db, competition_id: int, category_id: int | None, issued_by: User) -> ReportIssuance`
  - `ReportService._issue(db, *, report_type, competition_id, category_id, issued_by, title, table_html, font_size_px) -> ReportIssuance` (usado pela Task 5)

- [ ] **Step 1: Testes unitários que falham** — `tests/unit/test_report_rendering.py`

```python
import sys
from datetime import datetime

import pytest

from app.models.timer import TimerStatus
from app.schemas.timer import RankingEntry
from app.services import report_rendering
from app.services.report_rendering import (
    PdfRendererUnavailableError,
    build_document_html,
    format_local_datetime,
    ranking_table_html,
)


def _entry(**overrides) -> RankingEntry:
    base = dict(
        position=1, timer_id=1, user_id=None, team_id=1, athlete_name="Equipe A",
        team_name="Equipe A", box_name=None, category_name="Dupla", accumulated_ms=0,
        elapsed_seconds=4680, total_penalty_seconds=0, final_seconds=4680,
        infractions_count=0, remaining_seconds=None, status=TimerStatus.finished,
    )
    base.update(overrides)
    return RankingEntry(**base)


def test_format_local_datetime_converts_utc_to_brasilia():
    assert format_local_datetime(datetime(2026, 10, 22, 15, 30, 5)) == "22/10/2026 12:30:05"


def test_ranking_table_shows_note_with_adjusted_date():
    html = ranking_table_html([
        _entry(adjustment_note="Timer finalizado por engano",
               adjusted_at=datetime(2026, 10, 18, 17, 32, 0)),
    ])
    assert "Justificativa" in html
    assert "Timer finalizado por engano — ajustado em 18/10/2026 14:32" in html


def test_ranking_table_without_adjustment_shows_dash():
    html = ranking_table_html([_entry()])
    assert "<td class=\"note\">—</td>" in html


def test_ranking_document_escapes_adjustment_note():
    html = ranking_table_html([
        _entry(adjustment_note="<script>alert('x')</script> & cia",
               adjusted_at=datetime(2026, 10, 18, 17, 32, 0)),
    ])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; cia" in html


def test_document_has_generated_at_code_and_qr():
    html = build_document_html(
        title="Ranking — Comp", table_html="<table></table>",
        issued_at=datetime(2026, 10, 22, 15, 30, 5), code="CODE123", font_size_px=12,
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/unit/test_report_rendering.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.report_rendering`

- [ ] **Step 3: Implementar** — `app/services/report_rendering.py`

```python
"""Montagem de HTML e conversão para PDF dos relatórios de ranking (ADR-012).

Funções puras (sem banco): recebem dados prontos e devolvem HTML/bytes.
"""

import html
from datetime import datetime, timezone
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
    local = dt_utc_naive.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(REPORT_TIMEZONE))
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
        f"<td class=\"note\">{_adjustment_cell(entry)}</td>"
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
    """Documento HTML completo: cabeçalho com data de geração, tabela e rodapé de verificação.

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
    @bottom-left {{ content: "Código de verificação: {code}"; font-size: 8px; color: #555; }}
    @bottom-right {{ content: "Página " counter(page) " de " counter(pages); font-size: 8px; color: #555; }}
  }}
  body {{ font-family: Arial, sans-serif; font-size: {font_size_px}px; }}
  h1 {{ text-align: center; font-size: 16px; margin-bottom: 2px; }}
  .generated {{ text-align: center; color: #555; font-size: 10px; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  th {{ background: #1a1a2e; color: white; padding: 6px 4px; font-size: 10px; }}
  td {{ padding: 5px 4px; border-bottom: 1px solid #ddd; text-align: center; }}
  td.note {{ text-align: left; font-size: 9px; max-width: 180px; word-wrap: break-word; }}
  tr:nth-child(even) {{ background: #f5f5f5; }}
  small {{ color: #666; }}
  .verification {{ margin-top: 24px; border-top: 1px solid #ccc; padding-top: 10px;
                   display: flex; gap: 12px; align-items: center; font-size: 9px; color: #333; }}
  .verification svg {{ width: 90px; height: 90px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p class="generated">Gerado em {generated_at} (horário de Brasília)</p>
{table_html}
<div class="verification">
  {qr_svg(url)}
  <div>
    <strong>Documento assinado digitalmente pelo Tempus.</strong><br>
    Código de verificação: <strong>{code}</strong><br>
    Confira a autenticidade em {html.escape(url)}<br>
    Qualquer alteração neste arquivo invalida a verificação.
  </div>
</div>
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
    return weasyprint.HTML(string=document_html, url_fetcher=_deny_url_fetcher).write_pdf()
```

Se o `display: flex` não renderizar bem no WeasyPrint, trocar por `<table>` de duas colunas sem bordas (verificar visualmente no Step 9).

- [ ] **Step 4: Rodar unit**

Run: `.venv/bin/pytest tests/unit/test_report_rendering.py -v`
Expected: 7 passed.

- [ ] **Step 5: Testes de integração que falham** — `tests/integration/test_report_export_signed.py`

```python
import hashlib

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.report_issuance import ReportIssuance
from app.services import report_rendering
from app.services.report_rendering import PdfRendererUnavailableError


async def _competition_id(client: AsyncClient, admin_token: str) -> int:
    r = await client.post(
        "/api/v1/competitions", json={"name": "Comp PDF"},
        cookies={"session_id": admin_token},
    )
    return r.json()["id"]


async def _issuances(db: AsyncSession) -> list[ReportIssuance]:
    return list((await db.execute(select(ReportIssuance))).scalars().all())


async def test_export_pdf_creates_signed_issuance_matching_bytes(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf", cookies={"session_id": admin_token}
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    [issuance] = await _issuances(db)
    assert issuance.report_type == "ranking"
    assert issuance.competition_name == "Comp PDF"
    assert issuance.issued_by_role == "admin"
    assert issuance.sha256 == hashlib.sha256(r.content).hexdigest()
    assert issuance.verification_code in r.headers["x-verification-code"]


async def test_export_pdf_as_operator_returns_200(
    client: AsyncClient, admin_token: str, operator_token: str
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf", cookies={"session_id": operator_token}
    )
    assert r.status_code == 200


async def test_export_pdf_as_competitor_returns_403(
    client: AsyncClient, admin_token: str, competitor_token: str
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf", cookies={"session_id": competitor_token}
    )
    assert r.status_code == 403


async def test_export_pdf_unknown_competition_returns_404(client: AsyncClient, admin_token: str):
    r = await client.get(
        "/api/v1/competitions/999999/export/pdf", cookies={"session_id": admin_token}
    )
    assert r.status_code == 404


async def test_export_pdf_without_renderer_returns_503_and_no_issuance(
    client: AsyncClient, admin_token: str, db: AsyncSession, monkeypatch
):
    comp_id = await _competition_id(client, admin_token)

    def _unavailable(_html: str) -> bytes:
        raise PdfRendererUnavailableError("WeasyPrint não disponível")

    monkeypatch.setattr(report_rendering, "html_to_pdf", _unavailable)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf", cookies={"session_id": admin_token}
    )
    assert r.status_code == 503
    assert await _issuances(db) == []


async def test_export_pdf_without_signing_key_returns_500(
    client: AsyncClient, admin_token: str, db: AsyncSession, monkeypatch
):
    comp_id = await _competition_id(client, admin_token)
    monkeypatch.setattr(settings, "REPORT_SIGNING_PRIVATE_KEY", "")
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf", cookies={"session_id": admin_token}
    )
    assert r.status_code == 500
    assert "assinatura" in r.json()["detail"].lower()
    assert await _issuances(db) == []
```

Nota: o header `X-Verification-Code` é exposto na resposta para facilitar testes e logs; não é segredo (o código está impresso no PDF).

- [ ] **Step 6: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/integration/test_report_export_signed.py -v`
Expected: FAIL (sem emissão, sem header, sem 404/503/500).

- [ ] **Step 7: Implementar `ReportService`** — `app/services/report.py`

```python
"""Emissão e verificação de PDFs de relatório assinados (ADR-012)."""

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import REPORT_TYPE_RANKING, REPORT_VERIFICATION_CODE_BYTES
from app.models.report_issuance import ReportIssuance
from app.models.user import User
from app.repositories.competition import CompetitionRepository
from app.repositories.report_issuance import ReportIssuanceRepository
from app.services import report_rendering
from app.services.report_signing import IssuancePayload, ReportSigningService
from app.services.timer import RankingService

logger = logging.getLogger(__name__)


def _utcnow_seconds() -> datetime:
    # Truncado em segundos: o valor entra no payload assinado e precisa voltar
    # idêntico do banco (SQLite/Postgres tratam microssegundos de forma diferente).
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def payload_from_issuance(issuance: ReportIssuance) -> IssuancePayload:
    """Monta o payload assinável a partir de uma emissão (nova ou do banco)."""
    return IssuancePayload(
        code=issuance.verification_code,
        report_type=issuance.report_type,
        competition_id=issuance.competition_id,
        competition_name=issuance.competition_name,
        category_id=issuance.category_id,
        category_name=issuance.category_name,
        issued_at=issuance.issued_at,
        issued_by_user_id=issuance.issued_by_user_id,
        issued_by_role=issuance.issued_by_role,
        sha256=issuance.sha256,
    )


class ReportService:
    """Gera PDFs de ranking assinados e registra cada emissão."""

    @staticmethod
    async def _competition_name(db: AsyncSession, competition_id: int) -> str:
        competition = await CompetitionRepository.get_by_id(db, competition_id)
        if competition is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Competição não encontrada"
            )
        return competition.name

    @staticmethod
    async def _issue(
        db: AsyncSession,
        *,
        report_type: str,
        competition_id: int,
        competition_name: str,
        category_id: int | None,
        category_name: str | None,
        issued_by: User,
        title: str,
        table_html: str,
        font_size_px: int,
    ) -> ReportIssuance:
        """Renderiza, assina e grava uma emissão.

        Args:
            db: Sessão assíncrona.
            report_type: REPORT_TYPE_RANKING ou REPORT_TYPE_WOD_LEADERBOARD.
            competition_id: ID da competição.
            competition_name: Nome da competição (snapshot).
            category_id: Filtro de categoria usado, se houver.
            category_name: Nome da categoria (snapshot), se houver.
            issued_by: Usuário que exportou.
            title: Título do documento.
            table_html: Tabela já montada (dados escapados).
            font_size_px: Tamanho da fonte do corpo.

        Returns:
            Emissão persistida (com pdf_data em memória).

        Raises:
            PdfRendererUnavailableError: WeasyPrint ausente.
            ReportSigningKeyError: chave de assinatura ausente/inválida.
        """
        code = secrets.token_urlsafe(REPORT_VERIFICATION_CODE_BYTES)
        issued_at = _utcnow_seconds()
        document_html = report_rendering.build_document_html(
            title=title, table_html=table_html, issued_at=issued_at, code=code,
            font_size_px=font_size_px,
        )
        pdf_bytes = report_rendering.html_to_pdf(document_html)
        issuance = ReportIssuance(
            verification_code=code,
            report_type=report_type,
            competition_id=competition_id,
            competition_name=competition_name,
            category_id=category_id,
            category_name=category_name,
            issued_by_user_id=issued_by.id,
            issued_by_role=issued_by.role.value,
            issued_at=issued_at,
            sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            signature="",
            pdf_data=pdf_bytes,
        )
        issuance.signature = ReportSigningService.sign(payload_from_issuance(issuance))
        await ReportIssuanceRepository.create(db, issuance)
        logger.info(
            "Relatório emitido: type=%s competition_id=%s code=%s",
            report_type, competition_id, code,
        )
        return issuance

    @staticmethod
    async def issue_ranking_pdf(
        db: AsyncSession, competition_id: int, category_id: int | None, issued_by: User
    ) -> ReportIssuance:
        """Emite o PDF assinado do ranking de tempo (com coluna de justificativa).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro de categoria (opcional).
            issued_by: Usuário que exportou.

        Returns:
            Emissão persistida.

        Raises:
            HTTPException 404: competição inexistente.
        """
        competition_name = await ReportService._competition_name(db, competition_id)
        entries = await RankingService.get_ranking(db, competition_id, category_id)
        category_name = await ReportService._category_name(db, category_id)
        return await ReportService._issue(
            db,
            report_type=REPORT_TYPE_RANKING,
            competition_id=competition_id,
            competition_name=competition_name,
            category_id=category_id,
            category_name=category_name,
            issued_by=issued_by,
            title=f"Ranking — {competition_name}",
            table_html=report_rendering.ranking_table_html(entries),
            font_size_px=11,
        )
```

`_category_name`: localizar o repositório de categorias (`grep -rn "class CategoryRepository" app/repositories`) e implementar:

```python
    @staticmethod
    async def _category_name(db: AsyncSession, category_id: int | None) -> str | None:
        if category_id is None:
            return None
        category = await CategoryRepository.get_by_id(db, category_id)
        return category.name if category else None
```

(Se não houver `CategoryRepository.get_by_id`, adicionar o método no repositório existente de categorias com docstring, no mesmo padrão de `get_by_code` da Task 2. **Não** consultar o ORM direto no service.)

- [ ] **Step 8: Router** — substituir o corpo inteiro de `export_ranking_pdf` em `app/api/v1/reports.py`:

```python
@router.get("/competitions/{competition_id}/export/pdf")
async def export_ranking_pdf(
    competition_id: int,
    category_id: int | None = None,
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Exporta ranking em PDF assinado, com justificativa de ajustes (RF-40, ADR-012)."""
    issuance = await _issue_or_http_error(
        ReportService.issue_ranking_pdf(db, competition_id, category_id, current_user)
    )
    return _signed_pdf_response(issuance, f"ranking_{competition_id}.pdf")
```

E os helpers no topo do módulo (após `router = APIRouter()`):

```python
async def _issue_or_http_error(issue: Awaitable[ReportIssuance]) -> ReportIssuance:
    """Traduz falhas de infraestrutura da emissão em respostas HTTP explícitas."""
    try:
        return await issue
    except PdfRendererUnavailableError as exc:
        logger.error("PDF não gerado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gerador de PDF indisponível no servidor",
        ) from exc
    except ReportSigningKeyError as exc:
        logger.error("PDF não gerado: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assinatura de relatórios não configurada no servidor",
        ) from exc


def _signed_pdf_response(issuance: ReportIssuance, filename: str) -> Response:
    return Response(
        content=issuance.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Verification-Code": issuance.verification_code,
        },
    )
```

Imports a ajustar no router: `from collections.abc import Awaitable`; `from fastapi import APIRouter, Depends, HTTPException, status`; `from fastapi.responses import Response, StreamingResponse`; `from app.models.report_issuance import ReportIssuance`; `from app.services.report import ReportService`; `from app.services.report_rendering import PdfRendererUnavailableError`; `from app.services.report_signing import ReportSigningKeyError`. Remover `_seconds_to_hms` do router se não houver mais uso local (CSV e crossfit CSV usam — então trocar esses usos por `report_rendering.seconds_to_hms` e apagar a cópia local). **Atenção:** `issuance.pdf_data` está em memória porque a instância foi criada nesta sessão — não há lazy load aqui.

Em `export_ranking_pdf`, o `_current_user` virou `current_user` (agora é usado).

- [ ] **Step 9: Rodar, conferir visual e commitar**

Run: `.venv/bin/pytest tests/integration/test_report_export_signed.py tests/unit/test_report_rendering.py -v`
Expected: tudo passa.

Conferência visual: gerar um PDF de amostra para o scratchpad e abrir:

```bash
.venv/bin/python - <<'EOF'
from datetime import datetime
from app.services import report_rendering as r
html = r.build_document_html(title="Ranking — Amostra", table_html="<table><tr><td>x</td></tr></table>",
    issued_at=datetime(2026,10,22,15,0,0), code="AmostraCodigo123456789", font_size_px=11)
open("/tmp/claude-1000/amostra_ranking.pdf","wb").write(r.html_to_pdf(html))
EOF
```
Abrir `/tmp/claude-1000/amostra_ranking.pdf` (Read tool) e confirmar: "Gerado em", QR legível, código no rodapé de página.

```bash
git add app/services/report_rendering.py app/services/report.py app/api/v1/reports.py tests/unit/test_report_rendering.py tests/integration/test_report_export_signed.py
git commit -m "feat(reports): PDF de ranking assinado com data de geração e justificativa

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Leaderboard WODs (CrossFit) assinado

**Files:**
- Modify: `backend/app/services/report_rendering.py` (+ `wod_leaderboard_table_html`)
- Modify: `backend/app/services/report.py` (+ `issue_wod_leaderboard_pdf`)
- Modify: `backend/app/api/v1/reports.py` (`export_crossfit_ranking_pdf`)
- Test: `backend/tests/unit/test_report_rendering.py`, `backend/tests/integration/test_report_export_signed.py`

**Interfaces:**
- Consumes: `ReportService._issue`, `_issue_or_http_error`, `_signed_pdf_response` (Task 4); `WodResultService.compute_leaderboard(db, competition_id, category_id)` (existente, retorna objeto com `.entries`, cada entry com `.position, .team_name, .total_points, .wod_entries`; cada wod entry com `.wod_name, .wod_type, .walkover, .points, .rank, .reps, .time_seconds`).
- Produces: `report_rendering.wod_leaderboard_table_html(leaderboard) -> str`; `ReportService.issue_wod_leaderboard_pdf(db, competition_id, category_id, issued_by) -> ReportIssuance`.

- [ ] **Step 1: Testes que falham**

Em `tests/unit/test_report_rendering.py`:

```python
from types import SimpleNamespace

from app.services.report_rendering import wod_leaderboard_table_html


def test_wod_leaderboard_table_renders_walkover_and_escapes_names():
    wod = SimpleNamespace(wod_name="<b>WOD 1</b>", wod_type="for_time", walkover=True,
                          points=0, rank=None, reps=None, time_seconds=None)
    entry = SimpleNamespace(position=1, team_name="Equipe & Cia", total_points=10, wod_entries=[wod])
    html = wod_leaderboard_table_html(SimpleNamespace(entries=[entry]))
    assert "W.O." in html
    assert "Equipe &amp; Cia" in html
    assert "&lt;b&gt;WOD 1&lt;/b&gt;" in html
```

Em `tests/integration/test_report_export_signed.py`:

```python
async def test_export_crossfit_pdf_creates_wod_leaderboard_issuance(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.get(
        f"/api/v1/competitions/{comp_id}/export/crossfit-pdf",
        cookies={"session_id": admin_token},
    )
    assert r.status_code == 200
    [issuance] = await _issuances(db)
    assert issuance.report_type == "wod_leaderboard"
    assert issuance.sha256 == hashlib.sha256(r.content).hexdigest()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/unit/test_report_rendering.py tests/integration/test_report_export_signed.py -v`
Expected: FAIL nos dois testes novos.

- [ ] **Step 3: Implementar**

`report_rendering.py` — mover a lógica de célula que hoje está em `export_crossfit_ranking_pdf` (router, ~linhas 235-265), sem mudar o comportamento:

```python
def _wod_cell_html(we) -> str:
    if we.walkover:
        return "<span style='color:#dc2626;font-weight:bold'>W.O.</span>"
    if we.points == 0 and we.rank is None and we.reps is None and we.time_seconds is None:
        return "N/A"
    if we.wod_type == "amrap":
        if we.reps is None:
            return "—"
        return f"{we.reps or 0} reps<br><small>({we.points} pts)</small>"
    if we.wod_type == "for_time":
        if we.time_seconds is None:
            return "—"
        reps_part = f" +{we.reps}r" if we.reps else ""
        return f"{seconds_to_hms(we.time_seconds)}{reps_part}<br><small>({we.points} pts)</small>"
    return "N/D"


def wod_leaderboard_table_html(leaderboard) -> str:
    """Tabela do Leaderboard WODs (CrossFit)."""
    first_wods = leaderboard.entries[0].wod_entries if leaderboard.entries else []
    headers = "".join(
        f"<th>{html.escape(we.wod_name)}<br><small>({html.escape(we.wod_type)})</small></th>"
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
        f"<table><thead><tr><th>Pos.</th><th>Equipe</th>{headers}<th>Total</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )
```

`report.py` — adicionar (import `REPORT_TYPE_WOD_LEADERBOARD` e `from app.services.wod_result import WodResultService`; se houver import circular, importar dentro da função como o router fazia):

```python
    @staticmethod
    async def issue_wod_leaderboard_pdf(
        db: AsyncSession, competition_id: int, category_id: int | None, issued_by: User
    ) -> ReportIssuance:
        """Emite o PDF assinado do Leaderboard WODs (CrossFit).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.
            category_id: Filtro de categoria (opcional).
            issued_by: Usuário que exportou.

        Returns:
            Emissão persistida.

        Raises:
            HTTPException 404: competição inexistente.
        """
        competition_name = await ReportService._competition_name(db, competition_id)
        leaderboard = await WodResultService.compute_leaderboard(db, competition_id, category_id)
        return await ReportService._issue(
            db,
            report_type=REPORT_TYPE_WOD_LEADERBOARD,
            competition_id=competition_id,
            competition_name=competition_name,
            category_id=category_id,
            category_name=await ReportService._category_name(db, category_id),
            issued_by=issued_by,
            title=f"Leaderboard WODs — {competition_name}",
            table_html=report_rendering.wod_leaderboard_table_html(leaderboard),
            font_size_px=11,
        )
```

Router — substituir o corpo de `export_crossfit_ranking_pdf`:

```python
@router.get("/competitions/{competition_id}/export/crossfit-pdf")
async def export_crossfit_ranking_pdf(
    competition_id: int,
    category_id: int | None = None,
    current_user: User = Depends(require_roles("operator", "admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Exporta leaderboard de WODs em PDF assinado (espelha /ranking, ADR-012)."""
    issuance = await _issue_or_http_error(
        ReportService.issue_wod_leaderboard_pdf(db, competition_id, category_id, current_user)
    )
    return _signed_pdf_response(issuance, f"leaderboard_wods_{competition_id}.pdf")
```

Remover `import html` do router se ficou sem uso.

- [ ] **Step 4: Rodar suíte de relatórios + regressões existentes**

Run: `.venv/bin/pytest tests -k "report or ranking or crossfit or wod" -v`
Expected: tudo passa (inclui testes antigos de export CSV/crossfit, se houver).

- [ ] **Step 5: Commit**

```bash
git add app/services/report_rendering.py app/services/report.py app/api/v1/reports.py tests/unit/test_report_rendering.py tests/integration/test_report_export_signed.py
git commit -m "feat(reports): assinar também o PDF do Leaderboard WODs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Endpoints públicos de verificação

**Files:**
- Create: `backend/app/schemas/report.py`
- Modify: `backend/app/services/report.py` (+ verificação)
- Modify: `backend/app/api/v1/reports.py` (+ 4 rotas)
- Test: `backend/tests/integration/test_report_verify.py`

**Interfaces:**
- Consumes: Tasks 1, 2, 4.
- Produces:
  - `ReportVerificationStatus(str, Enum)`: `valid`, `tampered`
  - `ReportVerificationResponse`: `status, verification_code, report_type, competition_name, category_name: str | None, issued_at: datetime (UTC aware), issued_by_role: str | None, sha256`
  - `ReportService.verify_by_code(db, code) -> ReportVerificationResponse` (404)
  - `ReportService.verify_by_file(db, data: bytes) -> ReportVerificationResponse` (404)
  - `ReportService.original_pdf(db, code) -> bytes` (404 / 409 se `tampered`)
  - `ReportService.validate_upload(data: bytes) -> None` (413 / 422)
  - HTTP: `GET /api/v1/reports/verify/{code}`, `GET /api/v1/reports/verify/{code}/pdf`, `POST /api/v1/reports/verify` (multipart `file`), `GET /api/v1/reports/public-key` (text/plain).

- [ ] **Step 1: Testes que falham** — `tests/integration/test_report_verify.py`

```python
import hashlib

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import REPORT_VERIFY_MAX_UPLOAD_BYTES
from app.models.report_issuance import ReportIssuance


async def _export(client: AsyncClient, admin_token: str) -> tuple[str, bytes]:
    comp = (
        await client.post(
            "/api/v1/competitions", json={"name": "Comp Verif"},
            cookies={"session_id": admin_token},
        )
    ).json()
    r = await client.get(
        f"/api/v1/competitions/{comp['id']}/export/pdf", cookies={"session_id": admin_token}
    )
    assert r.status_code == 200
    client.cookies.clear()  # o resto do teste é de visitante anônimo
    return r.headers["x-verification-code"], r.content


async def test_verify_code_anonymous_returns_valid(client: AsyncClient, admin_token: str):
    code, pdf = await _export(client, admin_token)
    r = await client.get(f"/api/v1/reports/verify/{code}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "valid"
    assert body["competition_name"] == "Comp Verif"
    assert body["issued_by_role"] == "admin"
    assert body["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert body["issued_at"].endswith(("Z", "+00:00"))


async def test_verify_unknown_code_returns_404(client: AsyncClient):
    r = await client.get("/api/v1/reports/verify/nao-existe")
    assert r.status_code == 404


async def test_download_original_returns_identical_bytes(client: AsyncClient, admin_token: str):
    code, pdf = await _export(client, admin_token)
    r = await client.get(f"/api/v1/reports/verify/{code}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == pdf


async def test_verify_upload_same_file_returns_valid(client: AsyncClient, admin_token: str):
    code, pdf = await _export(client, admin_token)
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("ranking.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    assert r.json()["verification_code"] == code
    assert r.json()["status"] == "valid"


async def test_verify_upload_one_byte_changed_returns_404(client: AsyncClient, admin_token: str):
    _, pdf = await _export(client, admin_token)
    altered = pdf[:-10] + bytes([pdf[-10] ^ 0x01]) + pdf[-9:]
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("ranking.pdf", altered, "application/pdf")},
    )
    assert r.status_code == 404


async def test_verify_upload_not_pdf_returns_422(client: AsyncClient):
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("x.pdf", b"not a pdf", "application/pdf")},
    )
    assert r.status_code == 422


async def test_verify_upload_too_large_returns_413(client: AsyncClient):
    big = b"%PDF-" + b"0" * REPORT_VERIFY_MAX_UPLOAD_BYTES
    r = await client.post(
        "/api/v1/reports/verify",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413


async def test_verify_code_with_tampered_hash_returns_tampered(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    code, _ = await _export(client, admin_token)
    await db.execute(
        update(ReportIssuance)
        .where(ReportIssuance.verification_code == code)
        .values(sha256="0" * 64)
    )
    await db.flush()
    db.expire_all()
    r = await client.get(f"/api/v1/reports/verify/{code}")
    assert r.json()["status"] == "tampered"
    assert (await client.get(f"/api/v1/reports/verify/{code}/pdf")).status_code == 409


async def test_verify_code_with_swapped_pdf_data_returns_tampered(
    client: AsyncClient, admin_token: str, db: AsyncSession
):
    code, _ = await _export(client, admin_token)
    await db.execute(
        update(ReportIssuance)
        .where(ReportIssuance.verification_code == code)
        .values(pdf_data=b"%PDF-1.7 trocado")
    )
    await db.flush()
    db.expire_all()
    r = await client.get(f"/api/v1/reports/verify/{code}")
    assert r.json()["status"] == "tampered"
    assert (await client.get(f"/api/v1/reports/verify/{code}/pdf")).status_code == 409


async def test_public_key_endpoint_returns_pem(client: AsyncClient):
    r = await client.get("/api/v1/reports/public-key")
    assert r.status_code == 200
    assert r.text.startswith("-----BEGIN PUBLIC KEY-----")
```

(Se `db` e `client` não compartilharem a mesma sessão no `conftest` — conferir `override_get_db` —, aplicar o `update` com `await db.commit()` em vez de `flush()`; o `commit` aqui é aceitável porque é código de teste, não de request.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/integration/test_report_verify.py -v`
Expected: FAIL — 404/405 nas rotas novas.

- [ ] **Step 3: Schemas** — `app/schemas/report.py`

```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ReportVerificationStatus(str, Enum):
    valid = "valid"
    # Assinatura não confere OU o PDF guardado não bate com o hash assinado.
    tampered = "tampered"


class ReportVerificationResponse(BaseModel):
    status: ReportVerificationStatus
    verification_code: str
    report_type: str
    competition_name: str
    category_name: str | None
    issued_at: datetime  # UTC com timezone explícito
    issued_by_role: str | None
    sha256: str
```

- [ ] **Step 4: Service** — em `app/services/report.py` adicionar (imports: `REPORT_VERIFY_MAX_UPLOAD_BYTES`, `PDF_MAGIC_BYTES`, os schemas):

```python
    @staticmethod
    async def _is_authentic(db: AsyncSession, issuance: ReportIssuance) -> bool:
        signature_ok = ReportSigningService.verify(
            payload_from_issuance(issuance), issuance.signature
        )
        pdf_data = await ReportIssuanceRepository.load_pdf_data(db, issuance)
        stored_pdf_ok = hashlib.sha256(pdf_data).hexdigest() == issuance.sha256
        if not (signature_ok and stored_pdf_ok):
            logger.warning(
                "Emissão adulterada: code=%s signature_ok=%s stored_pdf_ok=%s",
                issuance.verification_code, signature_ok, stored_pdf_ok,
            )
        return signature_ok and stored_pdf_ok

    @staticmethod
    async def _verification(db: AsyncSession, issuance: ReportIssuance) -> ReportVerificationResponse:
        authentic = await ReportService._is_authentic(db, issuance)
        return ReportVerificationResponse(
            status=ReportVerificationStatus.valid if authentic else ReportVerificationStatus.tampered,
            verification_code=issuance.verification_code,
            report_type=issuance.report_type,
            competition_name=issuance.competition_name,
            category_name=issuance.category_name,
            issued_at=issuance.issued_at.replace(tzinfo=timezone.utc),
            issued_by_role=issuance.issued_by_role,
            sha256=issuance.sha256,
        )

    @staticmethod
    async def _get_or_404(db: AsyncSession, code: str) -> ReportIssuance:
        issuance = await ReportIssuanceRepository.get_by_code(db, code)
        if issuance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Código de verificação não encontrado",
            )
        return issuance

    @staticmethod
    async def verify_by_code(db: AsyncSession, code: str) -> ReportVerificationResponse:
        """Verifica uma emissão pelo código impresso no PDF.

        Args:
            db: Sessão assíncrona.
            code: Código de verificação.

        Returns:
            Resultado da verificação.

        Raises:
            HTTPException 404: código inexistente.
        """
        return await ReportService._verification(db, await ReportService._get_or_404(db, code))

    @staticmethod
    def validate_upload(data: bytes) -> None:
        """Valida o arquivo enviado para verificação (tamanho e assinatura binária PDF).

        Args:
            data: Bytes lidos (até MAX + 1).

        Raises:
            HTTPException 413: arquivo acima do limite.
            HTTPException 422: conteúdo não é PDF.
        """
        if len(data) > REPORT_VERIFY_MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Arquivo excede {REPORT_VERIFY_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            )
        if not data.startswith(PDF_MAGIC_BYTES):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="O arquivo enviado não é um PDF",
            )

    @staticmethod
    async def verify_by_file(db: AsyncSession, data: bytes) -> ReportVerificationResponse:
        """Verifica se um arquivo é, byte a byte, um PDF emitido pelo Tempus.

        Args:
            db: Sessão assíncrona.
            data: Bytes do arquivo (já validados por validate_upload).

        Returns:
            Resultado da verificação da emissão correspondente.

        Raises:
            HTTPException 404: nenhum PDF emitido tem esse hash.
        """
        issuance = await ReportIssuanceRepository.get_by_sha256(
            db, hashlib.sha256(data).hexdigest()
        )
        if issuance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Este arquivo não corresponde a nenhum relatório emitido pelo Tempus",
            )
        return await ReportService._verification(db, issuance)

    @staticmethod
    async def original_pdf(db: AsyncSession, code: str) -> bytes:
        """Retorna os bytes do PDF original de uma emissão íntegra.

        Args:
            db: Sessão assíncrona.
            code: Código de verificação.

        Returns:
            Bytes do PDF.

        Raises:
            HTTPException 404: código inexistente.
            HTTPException 409: emissão adulterada — o original não é servido.
        """
        issuance = await ReportService._get_or_404(db, code)
        if not await ReportService._is_authentic(db, issuance):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Registro deste documento foi adulterado; o original não pode ser fornecido",
            )
        return await ReportIssuanceRepository.load_pdf_data(db, issuance)
```

- [ ] **Step 5: Rotas** — em `app/api/v1/reports.py` (imports: `Request`, `UploadFile`, `File`, `PlainTextResponse`; `from app.core.limiter import limiter as _limiter`; `from app.core.constants import REPORT_VERIFY_MAX_UPLOAD_BYTES, REPORT_VERIFY_RATE_LIMIT`; `from app.schemas.report import ReportVerificationResponse`; `from app.services.report_signing import ReportSigningService`):

```python
# ── Verificação pública de PDFs assinados (ADR-012) ─────────────────────────


@router.get("/reports/public-key", response_class=PlainTextResponse)
@_limiter.limit(REPORT_VERIFY_RATE_LIMIT)
async def get_report_public_key(request: Request) -> str:
    """Chave pública Ed25519 (PEM) para verificação independente das emissões."""
    return ReportSigningService.public_key_pem()


@router.get("/reports/verify/{code}", response_model=ReportVerificationResponse)
@_limiter.limit(REPORT_VERIFY_RATE_LIMIT)
async def verify_report_by_code(
    request: Request, code: str, db: AsyncSession = Depends(get_db)
) -> ReportVerificationResponse:
    """Verifica um PDF emitido pelo código impresso nele (público)."""
    return await ReportService.verify_by_code(db, code)


@router.get("/reports/verify/{code}/pdf")
@_limiter.limit(REPORT_VERIFY_RATE_LIMIT)
async def download_original_report(
    request: Request, code: str, db: AsyncSession = Depends(get_db)
) -> Response:
    """Baixa o PDF original de uma emissão íntegra (público)."""
    pdf_bytes = await ReportService.original_pdf(db, code)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=original_{code}.pdf"},
    )


@router.post("/reports/verify", response_model=ReportVerificationResponse)
@_limiter.limit(REPORT_VERIFY_RATE_LIMIT)
async def verify_report_by_file(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ReportVerificationResponse:
    """Verifica se um arquivo é idêntico a um PDF emitido (público).

    Lê no máximo MAX + 1 bytes: o arquivo nunca é parseado nem armazenado.
    """
    data = await file.read(REPORT_VERIFY_MAX_UPLOAD_BYTES + 1)
    ReportService.validate_upload(data)
    return await ReportService.verify_by_file(db, data)
```

Se o `public-key` com chave ausente lançar `ReportSigningKeyError`, envolver: capturar e responder 503 `"Assinatura de relatórios não configurada"` (adicionar teste análogo ao da Task 4 se fizer).

- [ ] **Step 6: Rodar e ver passar**

Run: `.venv/bin/pytest tests/integration/test_report_verify.py -v`
Expected: 10 passed.

- [ ] **Step 7: Commit**

```bash
git add app/schemas/report.py app/services/report.py app/api/v1/reports.py tests/integration/test_report_verify.py
git commit -m "feat(reports): endpoints públicos de verificação de PDF assinado

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Bloquear exclusão de competição com relatórios emitidos

**Files:**
- Modify: `backend/app/services/report.py` (+ `competition_has_issuances`)
- Modify: `backend/app/api/v1/competitions.py` (`delete_competition`, ~linha 232)
- Test: `backend/tests/integration/test_report_export_signed.py`

**Interfaces:**
- Produces: `ReportService.competition_has_issuances(db, competition_id: int) -> bool`.

- [ ] **Step 1: Teste que falha** (em `test_report_export_signed.py`)

```python
async def test_delete_competition_with_issued_reports_returns_409(
    client: AsyncClient, admin_token: str
):
    comp_id = await _competition_id(client, admin_token)
    await client.get(
        f"/api/v1/competitions/{comp_id}/export/pdf", cookies={"session_id": admin_token}
    )
    r = await client.delete(
        f"/api/v1/competitions/{comp_id}", cookies={"session_id": admin_token}
    )
    assert r.status_code == 409
    assert "relatórios" in r.json()["detail"]


async def test_delete_competition_without_reports_still_returns_204(
    client: AsyncClient, admin_token: str
):
    comp_id = await _competition_id(client, admin_token)
    r = await client.delete(
        f"/api/v1/competitions/{comp_id}", cookies={"session_id": admin_token}
    )
    assert r.status_code == 204
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/integration/test_report_export_signed.py -k delete -v`
Expected: o primeiro FAIL (204 em vez de 409; no SQLite a FK pode não ser aplicada).

- [ ] **Step 3: Implementar**

`report.py`:

```python
    @staticmethod
    async def competition_has_issuances(db: AsyncSession, competition_id: int) -> bool:
        """Indica se a competição tem PDFs assinados emitidos (impede exclusão).

        Args:
            db: Sessão assíncrona.
            competition_id: ID da competição.

        Returns:
            True se houver emissões.
        """
        return await ReportIssuanceRepository.exists_for_competition(db, competition_id)
```

`competitions.py`, em `delete_competition`, logo após a checagem de competição ativa:

```python
    if await ReportService.competition_has_issuances(db, competition_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Competição possui relatórios assinados emitidos e não pode ser "
                "excluída (são a prova dos resultados publicados)"
            ),
        )
```

(import `from app.services.report import ReportService`; se gerar import circular, importar dentro da função.)

- [ ] **Step 4: Rodar e ver passar** — `.venv/bin/pytest tests/integration/test_report_export_signed.py tests/integration -k "competition" -v` → tudo passa.

- [ ] **Step 5: Commit**

```bash
git add app/services/report.py app/api/v1/competitions.py tests/integration/test_report_export_signed.py
git commit -m "feat(competitions): impedir exclusão de competição com relatórios assinados

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Frontend — página pública `/verificar`

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/api/reports.ts`
- Modify: `frontend/src/api/client.ts` (`PUBLIC_PATHS`)
- Create: `frontend/src/pages/VerifyReportPage.tsx`
- Modify: `frontend/src/App.tsx` (rotas públicas)
- Test: `frontend/src/test/VerifyReportPage.test.tsx`

**Interfaces:**
- Consumes: endpoints da Task 6.
- Produces: `reportsApi.verifyByCode(code: string): Promise<ReportVerification>`, `reportsApi.verifyByFile(file: File): Promise<ReportVerification>`, `reportsApi.originalPdfUrl(code: string): string`.

- [ ] **Step 1: Tipos** — `src/types/index.ts`

```ts
export type ReportVerificationStatus = "valid" | "tampered";
export type ReportType = "ranking" | "wod_leaderboard";

export interface ReportVerification {
  status: ReportVerificationStatus;
  verification_code: string;
  report_type: ReportType;
  competition_name: string;
  category_name: string | null;
  issued_at: string;
  issued_by_role: string | null;
  sha256: string;
}
```

- [ ] **Step 2: API** — `src/api/reports.ts`

```ts
import apiClient from "./client";
import type { ReportVerification } from "../types";

export const reportsApi = {
  verifyByCode: (code: string) =>
    apiClient
      .get<ReportVerification>(`/api/v1/reports/verify/${encodeURIComponent(code)}`)
      .then((r) => r.data),

  verifyByFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<ReportVerification>("/api/v1/reports/verify", form).then((r) => r.data);
  },

  originalPdfUrl: (code: string) => `/api/v1/reports/verify/${encodeURIComponent(code)}/pdf`,
};
```

Em `src/api/client.ts`, adicionar `"/verificar"` ao array `PUBLIC_PATHS`.

- [ ] **Step 3: Teste que falha** — `src/test/VerifyReportPage.test.tsx`

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it, vi, beforeEach } from "vitest";
import VerifyReportPage from "../pages/VerifyReportPage";
import { reportsApi } from "../api/reports";
import type { ReportVerification } from "../types";

vi.mock("../api/reports", () => ({
  reportsApi: {
    verifyByCode: vi.fn(),
    verifyByFile: vi.fn(),
    originalPdfUrl: (code: string) => `/api/v1/reports/verify/${code}/pdf`,
  },
}));

const valid: ReportVerification = {
  status: "valid",
  verification_code: "ABC",
  report_type: "ranking",
  competition_name: "Hyrox Floripa",
  category_name: null,
  issued_at: "2026-10-22T15:30:00Z",
  issued_by_role: "admin",
  sha256: "a".repeat(64),
};

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/verificar" element={<VerifyReportPage />} />
        <Route path="/verificar/:code" element={<VerifyReportPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function notFound(): AxiosError {
  return new AxiosError("nf", "ERR", undefined, undefined, {
    status: 404, statusText: "Not Found", data: {}, headers: {},
    config: { headers: new AxiosHeaders() },
  });
}

describe("VerifyReportPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra documento autêntico com link do original", async () => {
    vi.mocked(reportsApi.verifyByCode).mockResolvedValue(valid);
    renderAt("/verificar/ABC");
    expect(await screen.findByText("Documento autêntico")).toBeInTheDocument();
    expect(screen.getByText("Hyrox Floripa")).toBeInTheDocument();
    expect(screen.getByText(/22\/10\/2026 12:30/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /baixar original/i })).toHaveAttribute(
      "href", "/api/v1/reports/verify/ABC/pdf",
    );
  });

  it("alerta documento adulterado sem oferecer download", async () => {
    vi.mocked(reportsApi.verifyByCode).mockResolvedValue({ ...valid, status: "tampered" });
    renderAt("/verificar/ABC");
    expect(await screen.findByText("Documento adulterado")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /baixar original/i })).not.toBeInTheDocument();
  });

  it("informa código não encontrado", async () => {
    vi.mocked(reportsApi.verifyByCode).mockRejectedValue(notFound());
    renderAt("/verificar/XYZ");
    await waitFor(() =>
      expect(screen.getByText(/não corresponde a nenhum relatório/i)).toBeInTheDocument(),
    );
  });

  it("sem código mostra campo de código e upload", () => {
    renderAt("/verificar");
    expect(screen.getByLabelText(/código de verificação/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/arquivo pdf/i)).toBeInTheDocument();
  });
});
```

Run (em `frontend/`): `npx vitest run src/test/VerifyReportPage.test.tsx`
Expected: FAIL — módulo `../pages/VerifyReportPage` inexistente.

- [ ] **Step 4: Página** — `src/pages/VerifyReportPage.tsx`

```tsx
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { isAxiosError } from "axios";
import { Card } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";
import { reportsApi } from "../api/reports";
import type { ReportType, ReportVerification } from "../types";

const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  ranking: "Ranking de tempo",
  wod_leaderboard: "Leaderboard WODs",
};

const ROLE_LABELS: Record<string, string> = {
  admin: "Administração",
  operator: "Operação",
};

type LookupState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "found"; result: ReportVerification }
  | { kind: "not_found" }
  | { kind: "error"; message: string };

// Data e hora separadas: toLocaleString("pt-BR") insere vírgula ("22/10/2026, 12:30:00").
function formatBrasilia(isoUtc: string): string {
  const date = new Date(isoUtc);
  const options = { timeZone: "America/Sao_Paulo" } as const;
  return `${date.toLocaleDateString("pt-BR", options)} ${date.toLocaleTimeString("pt-BR", options)}`;
}

function lookupErrorState(error: unknown): LookupState {
  if (isAxiosError(error) && error.response?.status === 404) return { kind: "not_found" };
  if (isAxiosError(error) && error.response?.status === 413) {
    return { kind: "error", message: "Arquivo grande demais (máximo 10 MB)." };
  }
  if (isAxiosError(error) && error.response?.status === 422) {
    return { kind: "error", message: "O arquivo enviado não é um PDF." };
  }
  return { kind: "error", message: "Não foi possível verificar agora. Tente novamente." };
}

interface VerificationResultProps {
  result: ReportVerification;
}

function VerificationResult({ result }: VerificationResultProps) {
  const authentic = result.status === "valid";
  return (
    <Card>
      <Alert
        variant={authentic ? "success" : "error"}
        title={authentic ? "Documento autêntico" : "Documento adulterado"}
      >
        {authentic
          ? "Este relatório foi emitido pelo Tempus e não foi alterado desde a emissão."
          : "O registro deste relatório não confere com a assinatura digital. Não confie neste documento e contate a organização."}
      </Alert>
      <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="font-medium text-gray-500">Competição</dt>
        <dd>{result.competition_name}</dd>
        <dt className="font-medium text-gray-500">Relatório</dt>
        <dd>{REPORT_TYPE_LABELS[result.report_type]}</dd>
        <dt className="font-medium text-gray-500">Categoria</dt>
        <dd>{result.category_name ?? "Todas"}</dd>
        <dt className="font-medium text-gray-500">Gerado em</dt>
        <dd>{formatBrasilia(result.issued_at)} (horário de Brasília)</dd>
        <dt className="font-medium text-gray-500">Emitido por</dt>
        <dd>{ROLE_LABELS[result.issued_by_role ?? ""] ?? "—"}</dd>
        <dt className="font-medium text-gray-500">Código</dt>
        <dd className="font-mono">{result.verification_code}</dd>
        <dt className="font-medium text-gray-500">SHA-256</dt>
        <dd className="break-all font-mono text-xs">{result.sha256}</dd>
      </dl>
      {authentic && (
        <a
          href={reportsApi.originalPdfUrl(result.verification_code)}
          className="mt-4 inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Baixar original
        </a>
      )}
    </Card>
  );
}

export default function VerifyReportPage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<LookupState>({ kind: "idle" });
  const [typedCode, setTypedCode] = useState("");

  useEffect(() => {
    if (!code) {
      setState({ kind: "idle" });
      return;
    }
    setState({ kind: "loading" });
    reportsApi
      .verifyByCode(code)
      .then((result) => setState({ kind: "found", result }))
      .catch((error: unknown) => setState(lookupErrorState(error)));
  }, [code]);

  const handleCodeSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = typedCode.trim();
    if (trimmed) navigate(`/verificar/${encodeURIComponent(trimmed)}`);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setState({ kind: "loading" });
    reportsApi
      .verifyByFile(file)
      .then((result) => setState({ kind: "found", result }))
      .catch((error: unknown) => setState(lookupErrorState(error)));
  };

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Verificar relatório</h1>
        <p className="text-sm text-gray-600">
          Confira se um PDF de ranking foi emitido pelo Tempus e não foi alterado.
        </p>

        <Card>
          <form onSubmit={handleCodeSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <Input
                id="verification-code"
                label="Código de verificação"
                value={typedCode}
                onChange={(e) => setTypedCode(e.target.value)}
                placeholder="Impresso no rodapé do PDF"
              />
            </div>
            <Button type="submit">Verificar</Button>
          </form>
          <div className="mt-4">
            <label htmlFor="verify-file" className="block text-sm font-medium text-gray-700">
              Ou envie o arquivo PDF
            </label>
            <input
              id="verify-file"
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="mt-1 block w-full text-sm"
            />
          </div>
        </Card>

        {state.kind === "loading" && <p className="text-sm text-gray-500">Verificando…</p>}
        {state.kind === "found" && <VerificationResult result={state.result} />}
        {state.kind === "not_found" && (
          <Alert variant="warning" title="Não encontrado">
            Este código ou arquivo não corresponde a nenhum relatório emitido pelo Tempus. Se o
            arquivo foi editado, mesmo que minimamente, ele deixa de corresponder.
          </Alert>
        )}
        {state.kind === "error" && <Alert variant="error">{state.message}</Alert>}
      </div>
    </div>
  );
}
```

Conferir: `Input` repassa `id` para o `<input>` e associa `label` via `htmlFor` (abrir `src/components/ui/Input.tsx`). Se não associar, o teste `getByLabelText` falha — nesse caso, passar `id` explicitamente e ajustar o componente **somente** se já houver suporte parcial; caso contrário, usar `<label htmlFor>` próprio como no input de arquivo. O texto "Ou envie o arquivo PDF" casa com `/arquivo pdf/i`.

- [ ] **Step 5: Rotas** — `src/App.tsx`, após o bloco "Ranking público":

```tsx
          {/* Verificação pública de PDFs assinados (ADR-012) */}
          <Route path="/verificar" element={<VerifyReportPage />} />
          <Route path="/verificar/:code" element={<VerifyReportPage />} />
```

e `import VerifyReportPage from "./pages/VerifyReportPage";`.

- [ ] **Step 6: Rodar e ver passar**

Run (em `frontend/`): `npx vitest run src/test/VerifyReportPage.test.tsx && npx tsc --noEmit && npx eslint src`
Expected: 4 passed; tsc e eslint sem erros.

- [ ] **Step 7: Commit**

```bash
git add src/types/index.ts src/api/reports.ts src/api/client.ts src/pages/VerifyReportPage.tsx src/App.tsx src/test/VerifyReportPage.test.tsx
git commit -m "feat(frontend): página pública de verificação de relatórios assinados

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Documentação, verificação final e memória

**Files:**
- Create: `docs/ADR/012-assinatura-relatorios-pdf.md`
- Modify: `backend/.env.example`
- Modify: `README.md` (seção de configuração/deploy)
- Modify: memória do projeto (`~/.claude/projects/-home-vitoralves-projects-tempus/memory/`)

- [ ] **Step 1: ADR-012** — seguir o formato de `docs/ADR/011-timer-time-adjustment-event.md` (abrir e copiar a estrutura de seções). Conteúdo obrigatório:
  - Contexto: ajustes manuais pós-falha de inicialização de timer; alegações de manipulação.
  - Decisão: registro `report_issuances` + Ed25519 sobre payload canônico (lista de campos), código + QR no PDF, PDF original guardado, verificação pública por código/arquivo, status `valid`/`tampered` (assinatura **e** hash do PDF guardado).
  - Limite da garantia (o hash não cabe no próprio PDF; prova origem/integridade pós-emissão, não correção dos dados pré-emissão — coberto por justificativa + `audit_logs`).
  - Alternativas descartadas: PAdES/ICP-Brasil (custo, "identidade desconhecida" com autoassinado), HMAC (simétrico, não verificável fora do servidor), só hash (banco vira a prova).
  - Gestão da chave: base64 em `REPORT_SIGNING_PRIVATE_KEY`; trocar a chave invalida verificações antigas → só em vazamento; backup obrigatório.
  - Diagrama Mermaid (copiar o `sequenceDiagram` da spec).

- [ ] **Step 2: `.env.example`** — adicionar:

```dotenv
# Assinatura digital dos PDFs de ranking (ADR-012). OBRIGATÓRIA para exportar PDF.
# Gere com: python scripts/generate_report_signing_key.py
# Guarde backup seguro: trocar/perder a chave invalida a verificação de todos os PDFs já emitidos.
REPORT_SIGNING_PRIVATE_KEY=
```

- [ ] **Step 3: README** — na seção de configuração/deploy, um parágrafo curto: gerar a chave antes do primeiro deploy desta versão, onde colocá-la (`.env` do servidor, via `env_file`), e que a página `/verificar` é pública.

- [ ] **Step 4: Verificação completa**

```bash
cd backend && .venv/bin/ruff check app tests scripts && .venv/bin/ruff format --check app tests scripts && .venv/bin/pytest --cov=app -q
cd ../frontend && npx vitest run && npx tsc --noEmit && npx eslint src
cd .. && docker build --no-cache -f docker/Dockerfile.backend -t tempus-backend-check . 2>&1 | tail -5
```
Expected: ruff limpo; pytest todo verde com cobertura ≥ 80%; vitest/tsc/eslint limpos (exceto `proxy.test.ts`, que exige backend rodando — usar `SKIP_PROXY_TESTS=true`); imagem builda (confirma `cryptography`/`segno`/`tzdata` na imagem). Se o `docker build` precisar de contexto diferente, conferir `docker/docker-compose.yml`. Se algo falhar, **parar e perguntar ao Vitor antes de ajustar testes** (CLAUDE.md, regra 10).

- [ ] **Step 5: Commit de docs**

```bash
git add docs/ADR/012-assinatura-relatorios-pdf.md backend/.env.example README.md
git commit -m "docs(reports): ADR-012 e configuração da chave de assinatura

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Memória do projeto**
  - Criar `project_signed_reports.md` (frontmatter `type: project`): origem (alegações de manipulação, 2026-10-22), decisões do Vitor (verificação no Tempus, texto+data no ajuste, ambos os PDFs, guardar original), branch/commits, pendências (gerar chave em produção antes do deploy; rate limit da verificação; exclusão de competição bloqueada com emissões).
  - `MEMORY.md`: linha nova no topo de "Mudanças recentes" com pointer para o arquivo; lição: "hash do PDF não cabe no próprio PDF → código + registro no servidor".
  - Linkar `[[project-timer-adjust]]`.
