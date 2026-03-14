from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str
    SECRET_KEY: str
    SESSION_TTL_SECONDS: int

    DATABASE_URL: str

    REDIS_URL: str
    REDIS_TIMER_TTL_SECONDS: int

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str

    FRONTEND_URL: str

    ADMIN_EMAIL: str
    ADMIN_FULL_NAME: str


settings = Settings()
