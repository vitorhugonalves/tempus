"""Constantes nomeadas do projeto — evita magic numbers/strings espalhados no código."""

MAX_CONSENT_TERM_BYTES = 10 * 1024 * 1024  # 10 MB

# Assinatura binária padrão de arquivos PDF (magic bytes) — usada para validar
# o conteúdo real do upload, não só a extensão/content-type declarados pelo cliente.
PDF_MAGIC_BYTES = b"%PDF-"
