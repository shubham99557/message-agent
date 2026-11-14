# ACTTRIDENT AI OUTREACH AGENT — CREDENTIALS & ENVIRONMENT TEMPLATE

> **SECURITY NOTICE:**  
> Never commit real API keys, database passwords, or private signing secrets to version control.  
> This file provides the configuration templates and development defaults only.

---

## 1. Local Development Credentials

| Account Role | Email Identifier | Default Dev Password | Notes |
| :--- | :--- | :--- | :--- |
| **System Administrator** | `admin@acttrident.ai` | `AdminPassword2026!` | Required for user creation, DLQ management, and configuration. |
| **Sales Representative** | `sales@acttrident.ai` | `SalesPassword2026!` | Used for day-to-day company research, drafting, and CRM pipeline review. |

---

## 2. Production Environment Template (`.env.production`)

```ini
# Application Environment
ENVIRONMENT=production
TIMEZONE=Asia/Kolkata

# Core Security
# CRITICAL: Must be at least 32 cryptographically random characters
SECRET_KEY=generate_with_openssl_rand_hex_32_minimum_length_required!
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14

# Database Persistence
POSTGRES_USER=acttrident
POSTGRES_PASSWORD=replace_with_complex_pg_password
POSTGRES_DB=acttrident_db
DATABASE_URL=postgresql://acttrident:replace_with_complex_pg_password@postgres:5432/acttrident_db

# Background Job Engine & Redis Broker
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# CORS Allowed Origins (Comma separated; NO WILDCARD * IN PRODUCTION)
BACKEND_CORS_ORIGINS=https://app.acttrident.ai,https://outreach.acttrident.ai

# AI Provider Configuration (gemini, openai, or mock)
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
AI_MODEL_NAME=gemini-1.5-pro

# Search & Real Company Discovery Providers
SEARCH_PROVIDER=hybrid
TAVILY_API_KEY=your_tavily_search_api_key
SERPAPI_API_KEY=your_serpapi_key

# Email Subsystem (gmail, smtp, or mock)
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=outreach@acttrident.ai
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM_NAME=ActTrident Business Development
SMTP_FROM_EMAIL=outreach@acttrident.ai
SMTP_USE_TLS=true

# Google Gmail API OAuth2 (Optional for direct Gmail API)
GMAIL_CLIENT_ID=your_oauth_client_id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your_oauth_client_secret
GMAIL_REFRESH_TOKEN=your_oauth_refresh_token

# Meta WhatsApp Cloud API Configuration
WHATSAPP_ENABLED=true
META_WA_ACCESS_TOKEN=your_meta_system_user_token
META_WA_PHONE_NUMBER_ID=your_meta_phone_number_id
META_WA_BUSINESS_ACCOUNT_ID=your_meta_waba_id
META_WA_VERIFY_TOKEN=your_custom_webhook_verify_token
META_APP_SECRET=your_meta_app_secret_for_hmac_sha256

# Outbound Safety & Sending Caps
DEFAULT_DAILY_EMAIL_LIMIT=50
DEFAULT_DAILY_WHATSAPP_LIMIT=20
REQUIRE_HUMAN_APPROVAL=true
```
