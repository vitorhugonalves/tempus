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
