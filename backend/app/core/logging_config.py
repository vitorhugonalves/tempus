"""Configuração centralizada de logging do Tempus.

- development: DEBUG para console + arquivo
- testing / production: INFO para console + arquivo
- Logs de acesso (uvicorn) escritos em logs/access.log
- Logs de aplicação escritos em logs/app.log
- Rotação automática: 10 MB por arquivo, 5 backups
"""

import logging
import logging.handlers
from pathlib import Path


_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Raiz do projeto: backend/app/core/logging_config.py → 3 parents acima = raiz
_PROJECT_ROOT = Path(__file__).parents[3]
_LOG_DIR = _PROJECT_ROOT / "logs"


def _rotating_handler(filename: str) -> logging.handlers.RotatingFileHandler:
    handler = logging.handlers.RotatingFileHandler(
        _LOG_DIR / filename,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(_FORMATTER)
    return handler


def _stream_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler()
    handler.setFormatter(_FORMATTER)
    return handler


def setup_logging(app_env: str) -> None:
    """Configura os handlers de logging de acordo com o ambiente.

    Args:
        app_env: Valor de APP_ENV ('development', 'testing', 'production').
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if app_env == "development" else logging.INFO

    # Logger raiz — captura tudo da aplicação
    root = logging.getLogger()
    root.setLevel(level)

    # Evita duplicar handlers em reloads (uvicorn --reload)
    if root.handlers:
        root.handlers.clear()

    root.addHandler(_stream_handler())
    root.addHandler(_rotating_handler("app.log"))

    # Logger de acesso HTTP do uvicorn — adiciona file handler se ainda não tiver
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.propagate = False
    access_logger.setLevel(logging.INFO)
    already_has_file = any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in access_logger.handlers
    )
    if not already_has_file:
        access_logger.addHandler(_rotating_handler("access.log"))

    # Silenciar loggers ruidosos em produção
    if app_env != "development":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging iniciado | env=%s | level=%s | log_dir=%s",
        app_env,
        logging.getLevelName(level),
        _LOG_DIR,
    )
