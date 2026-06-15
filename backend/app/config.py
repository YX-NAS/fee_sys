from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://fee_user:fee_password@localhost:5432/fee_sys"

    # Redis
    REDIS_URL: str = "redis://:redis_password@localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change_me_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption (for webhook URLs)
    ENCRYPTION_KEY: str = ""

    # First admin
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_EMAIL: str = "admin@example.com"
    FIRST_ADMIN_PASSWORD: str = "admin123"

    # App
    APP_TITLE: str = "费用管理系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # AI cost monitoring
    AI_MONITOR_ADMIN_ONLY: bool = True
    AI_GATEWAY_DEFAULT_RATE_LIMIT: int = 60
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    AI_PROVIDER_TIMEOUT_SECONDS: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
