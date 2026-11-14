import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "ActTrident AI Outreach Agent"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "acttrident-super-secret-production-key-change-in-env-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./acttrident.db")

    # AI Configuration (gemini, openai, anthropic, mock)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "gemini-1.5-pro")

    # Email Settings (SMTP / Gmail)
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "mock")  # smtp, gmail, mock
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "ActTrident Business Development")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "outreach@acttrident.ai")
    SMTP_USE_TLS: bool = True

    # WhatsApp Cloud API (Meta Official)
    WHATSAPP_ENABLED: bool = os.getenv("WHATSAPP_ENABLED", "true").lower() == "true"
    META_WA_ACCESS_TOKEN: str = os.getenv("META_WA_ACCESS_TOKEN", "")
    META_WA_PHONE_NUMBER_ID: str = os.getenv("META_WA_PHONE_NUMBER_ID", "")
    META_WA_BUSINESS_ACCOUNT_ID: str = os.getenv("META_WA_BUSINESS_ACCOUNT_ID", "")
    META_WA_VERIFY_TOKEN: str = os.getenv("META_WA_VERIFY_TOKEN", "acttrident_meta_webhook_secret_2026")

    # Conservative Safety & Sending Limits
    DEFAULT_DAILY_EMAIL_LIMIT: int = int(os.getenv("DEFAULT_DAILY_EMAIL_LIMIT", "50"))
    DEFAULT_DAILY_WHATSAPP_LIMIT: int = int(os.getenv("DEFAULT_DAILY_WHATSAPP_LIMIT", "20"))
    REQUIRE_HUMAN_APPROVAL: bool = True

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
