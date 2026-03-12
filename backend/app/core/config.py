from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    SECRET_KEY: str = "troque-isso-por-um-valor-seguro"
    SESSION_TTL_SECONDS: int = 28800  # 8 horas

    DATABASE_URL: str = "sqlite+aiosqlite:///./tempus.db"

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TIMER_TTL_SECONDS: int = 86400  # 24h — expira estado de timers inativos

    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    VITE_API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"

    # Admin padrão criado automaticamente na primeira migration (RF-44)
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_FULL_NAME: str = "Administrador"


settings = Settings()
