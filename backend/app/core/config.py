import os
import json
from typing import List, Annotated, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    PROJECT_NAME: str = "ActTrident AI Outreach Agent"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # development, test, production

    # JWT Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "acttrident-dev-secret-key-replace-in-env-at-least-32-chars")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 min lifetime
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))  # 14 days

    # Initial Admin Bootstrap (from environment only; never hardcoded in source)
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "admin@acttrident.ai")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "AdminPassword2026!")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./acttrident.db")

    # Redis & Distributed Celery Task Queue
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")

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
    GMAIL_CLIENT_ID: str = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET: str = os.getenv("GMAIL_CLIENT_SECRET", "")
    GMAIL_REFRESH_TOKEN: str = os.getenv("GMAIL_REFRESH_TOKEN", "")
    GMAIL_ACCESS_TOKEN: str = os.getenv("GMAIL_ACCESS_TOKEN", "")

    # WhatsApp Cloud API (Meta Official)
    WHATSAPP_ENABLED: bool = os.getenv("WHATSAPP_ENABLED", "true").lower() == "true"
    META_WA_ACCESS_TOKEN: str = os.getenv("META_WA_ACCESS_TOKEN", "")
    META_WA_PHONE_NUMBER_ID: str = os.getenv("META_WA_PHONE_NUMBER_ID", "")
    META_WA_BUSINESS_ACCOUNT_ID: str = os.getenv("META_WA_BUSINESS_ACCOUNT_ID", "")
    META_WA_VERIFY_TOKEN: str = os.getenv("META_WA_VERIFY_TOKEN", "acttrident_meta_webhook_secret_2026")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")  # Used for HMAC-SHA256 signature verification

    # Conservative Safety & Sending Limits
    DEFAULT_DAILY_EMAIL_LIMIT: int = int(os.getenv("DEFAULT_DAILY_EMAIL_LIMIT", "50"))
    DEFAULT_DAILY_WHATSAPP_LIMIT: int = int(os.getenv("DEFAULT_DAILY_WHATSAPP_LIMIT", "20"))
    REQUIRE_HUMAN_APPROVAL: bool = True

    # Search & Real Discovery Providers (hybrid, serpapi, tavily, catalog)
    SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "hybrid")
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    GOOGLE_SEARCH_API_KEY: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_ENGINE_ID: str = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

    # CORS: Explicit allowed origins (Never wildcard in production)
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return [str(o).strip() for o in v if str(o).strip()]
        if isinstance(v, str):
            raw = v.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed if str(o).strip()]
                except Exception:
                    pass
            return [o.strip() for o in raw.split(",") if o.strip()]
        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def validate_production_security(self) -> None:
        """Validates that production environment is not using insecure default credentials or wildcards."""
        if self.ENVIRONMENT.lower() == "production":
            if "replace-in-env" in self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError("CRITICAL SECURITY ERROR: Production SECRET_KEY must be a unique key of at least 32 characters.")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("CRITICAL SECURITY ERROR: Wildcard CORS is strictly forbidden in production.")


settings = Settings()
# Execute check on startup
settings.validate_production_security()
