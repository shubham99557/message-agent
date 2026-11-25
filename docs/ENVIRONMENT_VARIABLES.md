# Environment Variables Reference

**Project**: ActTrident AI Outreach & Sales Automation  
**Classification**: Operational Configuration & Secret Dictionary

---

## 1. Core Application & Server Settings

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `ENVIRONMENT` | Yes | `development` | Runtime environment mode: `development`, `staging`, or `production`. |
| `DEBUG` | No | `False` | Enables detailed ASGI tracebacks. **Must be `False` in production**. |
| `PORT` | No | `8000` | Port for the Uvicorn ASGI server to bind. |
| `HOST` | No | `0.0.0.0` | Network interface binding. |
| `CORS_ORIGINS` | Yes | `http://localhost:5173,http://localhost:3000` | Comma-separated list of allowed browser origins for CORS requests. |

---

## 2. Security & Cryptographic Secrets

| Variable | Required | Default | Security Guidance |
|---|:---:|---|---|
| `SECRET_KEY` | **Yes (Prod)** | `dev-insecure-secret-key-...` | Minimum 32-character high-entropy secret used for HMAC-SHA256 JWT signing. |
| `ENCRYPTION_KEY` | **Yes (Prod)** | `None` (auto-derived) | 32-byte base64-encoded URL-safe key for Fernet symmetric encryption of OAuth tokens in DB. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Lifespan of short-lived JWT access tokens in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Lifespan of rotating refresh tokens in days. |

---

## 3. Database & Message Broker

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `DATABASE_URL` | **Yes** | `sqlite:///./acttrident.db` | Connection string: `postgresql://user:pass@host:5432/dbname` in production. |
| `REDIS_URL` | **Yes** | `redis://localhost:6379/0` | Redis connection URL for Celery broker, caching, and burst rate-limiting counters. |

---

## 4. Google Workspace / Gmail API

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `GMAIL_CLIENT_ID` | Optional | `None` | Google Cloud OAuth 2.0 Client ID for Gmail API v1. |
| `GMAIL_CLIENT_SECRET` | Optional | `None` | Google Cloud OAuth 2.0 Client Secret. |
| `GMAIL_REFRESH_TOKEN` | Optional | `None` | Authorized long-lived refresh token for offline email dispatch. |
| `GMAIL_SENDER_EMAIL` | Optional | `outreach@acttrident.com` | Authorized Google Workspace email address appearing in `From:` header. |

> *Note*: If Gmail credentials are not configured, ActTrident automatically runs in **simulated mode**, creating mock delivery events without sending real emails.

---

## 5. Meta WhatsApp Cloud API

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `META_WA_PHONE_NUMBER_ID` | Optional | `None` | Meta WhatsApp Cloud API Phone Number ID from App Dashboard. |
| `META_WA_ACCESS_TOKEN` | Optional | `None` | Permanent System User access token with messaging permissions. |
| `META_WA_VERIFY_TOKEN` | **Yes** | `trident-wa-webhook-sec-99557` | Webhook verification token for handshake validation. |
| `META_WA_APP_SECRET` | **Yes** | `None` | Meta App Secret used for HMAC-SHA256 payload signature validation. |
| `META_WABA_ID` | Optional | `None` | WhatsApp Business Account (WABA) ID for template status checks. |

---

## 6. LinkedIn Integration

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `LINKEDIN_CLIENT_ID` | Optional | `None` | LinkedIn Developer App Client ID. |
| `LINKEDIN_CLIENT_SECRET` | Optional | `None` | LinkedIn Developer App Client Secret. |
| `LINKEDIN_REDIRECT_URI` | Optional | `http://localhost:8000/api/v1/integrations/linkedin/callback` | OAuth redirect callback URI. |

---

## 7. AI & Discovery Providers

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `GEMINI_API_KEY` | Optional | `None` | Google Gemini API key for dynamic email and WhatsApp copy drafting. |
| `TAVILY_API_KEY` | Optional | `None` | Tavily search API key for automated lead discovery in target cities. |
| `SERPAPI_API_KEY` | Optional | `None` | SerpApi fallback search key for corporate evidence verification. |

---

## 8. Celery & Background Automation

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `CELERY_BROKER_URL` | No | Inherits `REDIS_URL` | Broker URL for Celery task queuing. |
| `CELERY_RESULT_BACKEND` | No | Inherits `REDIS_URL` | Backend URL for Celery task return values. |
| `CELERY_TASK_ALWAYS_EAGER` | No | `False` | When `True`, runs Celery tasks synchronously (used during test suites). |
