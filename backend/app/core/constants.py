"""Constantes nomeadas do projeto — evita magic numbers/strings espalhados no código."""

MAX_CONSENT_TERM_BYTES = 10 * 1024 * 1024  # 10 MB

# Assinatura binária padrão de arquivos PDF (magic bytes) — usada para validar
# o conteúdo real do upload, não só a extensão/content-type declarados pelo cliente.
PDF_MAGIC_BYTES = b"%PDF-"

# Ajuste manual de tempo de timer finalizado (somente admin).
# Teto de 24h barra erro de digitação grosseiro (ex.: um zero a mais).
MAX_ADJUSTED_TIME_MS = 24 * 60 * 60 * 1000
# Mínimo conta caracteres sem os espaços das pontas: "ok" ou "erro" não explicam nada.
MIN_ADJUST_JUSTIFICATION_CHARS = 10
MAX_ADJUST_JUSTIFICATION_CHARS = 500

AUDIT_ACTION_TIMER_ADJUSTED = "timer.adjusted"
AUDIT_RESOURCE_TIMER = "timer"
