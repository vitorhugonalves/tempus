from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    SECRET_KEY: str
    SESSION_TTL_SECONDS: int = 28800

    DATABASE_URL: str

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TIMER_TTL_SECONDS: int = 86400

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    FRONTEND_URL: str = "http://localhost:5173"

    ADMIN_EMAIL: str
    ADMIN_FULL_NAME: str = "Administrador"

    @property
    def smtp_enabled(self) -> bool:
        """Retorna True somente se as credenciais SMTP estão completas."""
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)


settings = Settings()
