import os
import json
from typing import List, Annotated, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    PROJECT_NAME: str = "ActTrident AI Outreach Agent"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # development, test, production

    # JWT Security & Encryption at Rest
    SECRET_KEY: str = os.getenv("SECRET_KEY", "acttrident-dev-secret-key-replace-in-env-at-least-32-chars")
    CREDENTIAL_ENCRYPTION_KEY: str = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 min lifetime
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))  # 14 days

    # Outbound Rate Limits (per minute)
    OUTBOUND_RATE_LIMIT_EMAIL_PER_MIN: int = int(os.getenv("OUTBOUND_RATE_LIMIT_EMAIL_PER_MIN", "30"))
    OUTBOUND_RATE_LIMIT_WA_PER_MIN: int = int(os.getenv("OUTBOUND_RATE_LIMIT_WA_PER_MIN", "10"))

    # Product Claims & Offer Guards
    ALLOW_90_DAY_EVALUATION_OFFER: bool = os.getenv("ALLOW_90_DAY_EVALUATION_OFFER", "false").lower() in ("true", "1", "yes")
    ALLOW_DESKTOP_SQLITE: bool = os.getenv("ALLOW_DESKTOP_SQLITE", "false").lower() in ("true", "1", "yes")

    # Live Outreach Safety Gate (Default: False — fail-closed)
    LIVE_SEND_ENABLED: bool = os.getenv("LIVE_SEND_ENABLED", "false").lower() in ("true", "1", "yes")

    # Initial Admin Bootstrap (from environment only; never hardcoded in source)
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./acttrident.db")

    # Local Desktop Storage Directory (%LOCALAPPDATA%\ActTrident)
    LOCAL_APP_DATA_DIR: str = os.getenv(
        "LOCAL_APP_DATA_DIR",
        os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "ActTrident")
    )

    # Redis & Distributed Celery Task Queue
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    USE_LOCAL_WORKER: bool = os.getenv("USE_LOCAL_WORKER", "true").lower() in ("true", "1", "yes")

    # Local-First AI Configuration (Default: Ollama)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "ollama")  # ollama, mock, gemini, openai
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "llama3.2:latest")

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
    GMAIL_REDIRECT_URI: str = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/gmail/oauth/callback")
    GMAIL_REFRESH_TOKEN: str = os.getenv("GMAIL_REFRESH_TOKEN", "")
    GMAIL_ACCESS_TOKEN: str = os.getenv("GMAIL_ACCESS_TOKEN", "")

    # WhatsApp Cloud API (Meta Official)
    WHATSAPP_ENABLED: bool = os.getenv("WHATSAPP_ENABLED", "true").lower() == "true"
    ENFORCE_TRAI_CURFEW: bool = os.getenv("ENFORCE_TRAI_CURFEW", "true").lower() in ("true", "1", "yes")
    META_WA_ACCESS_TOKEN: str = os.getenv("META_WA_ACCESS_TOKEN", "")
    META_WA_PHONE_NUMBER_ID: str = os.getenv("META_WA_PHONE_NUMBER_ID", "")
    META_WA_BUSINESS_ACCOUNT_ID: str = os.getenv("META_WA_BUSINESS_ACCOUNT_ID", "")
    META_WA_VERIFY_TOKEN: str = os.getenv("META_WA_VERIFY_TOKEN", "acttrident_meta_webhook_secret_2026")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")  # Used for HMAC-SHA256 signature verification

    # LinkedIn Official OAuth 2.0 / Authorized Partner API (NEVER password/cookie scraping)
    LINKEDIN_CLIENT_ID: str = os.getenv("LINKEDIN_CLIENT_ID", "")
    LINKEDIN_CLIENT_SECRET: str = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    LINKEDIN_REDIRECT_URI: str = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/linkedin/oauth/callback")
    LINKEDIN_API_SCOPES: str = os.getenv("LINKEDIN_API_SCOPES", "openid profile email")
    LINKEDIN_MESSAGING_API_APPROVED: bool = os.getenv("LINKEDIN_MESSAGING_API_APPROVED", "false").lower() == "true"
    LINKEDIN_PARTNER_MESSAGING_ENDPOINT: str = os.getenv("LINKEDIN_PARTNER_MESSAGING_ENDPOINT", "")

    # Conservative Safety & Sending Limits
    DEFAULT_DAILY_EMAIL_LIMIT: int = int(os.getenv("DEFAULT_DAILY_EMAIL_LIMIT", "50"))
    DEFAULT_DAILY_WHATSAPP_LIMIT: int = int(os.getenv("DEFAULT_DAILY_WHATSAPP_LIMIT", "20"))
    REQUIRE_HUMAN_APPROVAL: bool = True

    # Search & Real Discovery Providers (hybrid, serpapi, tavily, catalog)
    SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "hybrid")
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    ENABLE_OPENSTREETMAP_DISCOVERY: bool = True
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
        """Validates that production/staging environments never run with insecure defaults or wildcards."""
        env = self.ENVIRONMENT.lower()
        if env in ("production", "staging"):
            if "replace-in-env" in self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError("CRITICAL SECURITY ERROR: Production SECRET_KEY must be a unique key of at least 32 characters.")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("CRITICAL SECURITY ERROR: Wildcard CORS is strictly forbidden in production.")
        if env == "production":
            if not self.CREDENTIAL_ENCRYPTION_KEY or len(self.CREDENTIAL_ENCRYPTION_KEY.strip()) < 16:
                raise ValueError("CRITICAL SECURITY ERROR: Production requires CREDENTIAL_ENCRYPTION_KEY (at least 16 characters).")
            if self.DATABASE_URL.lower().startswith("sqlite") and not self.ALLOW_DESKTOP_SQLITE:
                raise ValueError("CRITICAL SECURITY ERROR: SQLite is forbidden in production; configure PostgreSQL DATABASE_URL.")
            if self.WHATSAPP_ENABLED and (self.META_WA_ACCESS_TOKEN or "").strip():
                if not (self.META_APP_SECRET or "").strip():
                    raise ValueError("CRITICAL SECURITY ERROR: Production WhatsApp Cloud API requires META_APP_SECRET for HMAC verification.")
                if (self.META_WA_VERIFY_TOKEN or "").strip() in ("", "acttrident_meta_webhook_secret_2026"):
                    raise ValueError("CRITICAL SECURITY ERROR: Production META_WA_VERIFY_TOKEN must not use the default development token.")
            known_insecure_defaults = {
                "AdminPassword2026!",
                "SalesPassword2026!",
                "ManagerPassword2026!",
                "Password123!",
                "SecurePassword123!",
                "AdminPassword123!",
            }
            if self.INITIAL_ADMIN_PASSWORD and self.INITIAL_ADMIN_PASSWORD in known_insecure_defaults:
                raise ValueError("CRITICAL SECURITY ERROR: INITIAL_ADMIN_PASSWORD must not use a known default development password in production.")


settings = Settings()
# Execute check on startup
settings.validate_production_security()
