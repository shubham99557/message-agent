# ActTrident AI Sales Outreach Agent — Environment Variables Reference

All configuration is loaded via Pydantic `BaseSettings` in [config.py](backend/app/core/config.py) from environment variables or a local `.env` file (gitignored).

| Variable | Required in Prod | Default | Sensitivity | Purpose |
| :--- | :---: | :--- | :---: | :--- |
| `ENVIRONMENT` | Yes | `development` | Low | `development`, `test`, or `production`. Enables fail-fast security guards in `production`. |
| `TIMEZONE` | Recommended | `Asia/Kolkata` | Low | Scheduling & IST business-hours timezone. |
| `SECRET_KEY` | **Yes** | Dev placeholder | **CRITICAL** | JWT signing & OAuth CSRF state HMAC key (≥32 chars mandatory in prod). |
| `CREDENTIAL_ENCRYPTION_KEY` | **Yes** | Empty | **CRITICAL** | Fernet encryption key for stored API keys & OAuth tokens (≥16 chars mandatory in prod). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Low | Short-lived JWT access token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `14` | Low | Rotating refresh token lifetime in days. |
| `BACKEND_CORS_ORIGINS` | **Yes** | Localhost origins | Medium | Comma-separated or JSON array of allowed origins (`*` forbidden in prod). |
| `DATABASE_URL` | **Yes** | `sqlite:///./acttrident.db` | **High** | PostgreSQL connection URL required in prod (SQLite forbidden in prod). |
| `REDIS_URL` | Yes (workers) | `redis://localhost:6379/0` | Medium | Redis connection URL for Celery broker/locks. |
| `CELERY_BROKER_URL` | Yes (workers) | `REDIS_URL` | Medium | Celery broker URL. |
| `CELERY_RESULT_BACKEND` | Yes (workers) | `REDIS_URL` | Medium | Celery result backend URL. |
| `AI_PROVIDER` | No | `mock` | Low | `mock` (offline deterministic), `gemini`, or `openai`. |
| `GEMINI_API_KEY` | If `gemini` | Empty | **High** | Official Google Gemini API key. |
| `OPENAI_API_KEY` | If `openai` | Empty | **High** | OpenAI / compatible API key. |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | Low | OpenAI-compatible API base URL. |
| `AI_MODEL_NAME` | No | `gemini-1.5-pro` | Low | Model identifier for Gemini provider. |
| `EMAIL_PROVIDER` | No | `mock` | Low | `mock` (simulation), `gmail` (OAuth 2.0), or `smtp`. |
| `GMAIL_CLIENT_ID` | If Gmail OAuth | Empty | Medium | Google Cloud OAuth 2.0 Client ID. |
| `GMAIL_CLIENT_SECRET` | If Gmail OAuth | Empty | **High** | Google Cloud OAuth 2.0 Client Secret. |
| `GMAIL_REDIRECT_URI` | If Gmail OAuth | `http://localhost:8000/api/v1/integrations/gmail/oauth/callback` | Low | Authorized Google OAuth callback URL. |
| `SMTP_HOST` / `SMTP_PORT` | If SMTP | `smtp.gmail.com` / `587` | Low | Outbound SMTP relay host & TLS port. |
| `SMTP_USER` / `SMTP_PASSWORD` | If SMTP | Empty | **High** | SMTP authentication username and App Password. |
| `SMTP_FROM_NAME` / `SMTP_FROM_EMAIL` | If SMTP | `ActTrident Business Development` / `outreach@acttrident.ai` | Low | Outbound sender identity. |
| `WHATSAPP_ENABLED` | No | `true` | Low | Enables WhatsApp Cloud API module. |
| `META_WA_ACCESS_TOKEN` | If Live WA | Empty | **High** | Meta System User permanent token. |
| `META_WA_PHONE_NUMBER_ID` | If Live WA | Empty | Medium | Meta WhatsApp Business Phone Number ID. |
| `META_WA_BUSINESS_ACCOUNT_ID` | If Live WA | Empty | Medium | Meta WABA ID (required for live template sync). |
| `META_WA_VERIFY_TOKEN` | If Live WA | Dev token | **High** | Webhook GET verification challenge token. |
| `META_APP_SECRET` | **If Live WA** | Empty | **High** | Meta App Secret for `X-Hub-Signature-256` HMAC verification. |
| `LINKEDIN_CLIENT_ID` | If LinkedIn | Empty | Medium | Official LinkedIn OAuth 2.0 Client ID. |
| `LINKEDIN_CLIENT_SECRET` | If LinkedIn | Empty | **High** | Official LinkedIn OAuth 2.0 Client Secret. |
| `LINKEDIN_REDIRECT_URI` | If LinkedIn | `http://localhost:8000/api/v1/integrations/linkedin/oauth/callback` | Low | Authorized LinkedIn OAuth callback URL. |
| `LINKEDIN_API_SCOPES` | No | `openid profile email` | Low | Least-privilege official LinkedIn scopes. |
| `LINKEDIN_MESSAGING_API_APPROVED` | No | `false` | Low | Keep `false` unless approved for LinkedIn Partner Messaging API. |
| `LINKEDIN_PARTNER_MESSAGING_ENDPOINT` | If Partner API | Empty | Medium | Official LinkedIn Partner REST messaging endpoint. |
| `TAVILY_API_KEY` | Optional | Empty | **High** | Permitted Tavily web search discovery API key. |
| `SERPAPI_API_KEY` | Optional | Empty | **High** | Permitted SerpAPI search discovery key. |
| `DEFAULT_DAILY_EMAIL_LIMIT` | No | `50` | Low | Global daily email send ceiling. |
| `DEFAULT_DAILY_WHATSAPP_LIMIT` | No | `20` | Low | Global daily WhatsApp send ceiling. |
| `OUTBOUND_RATE_LIMIT_EMAIL_PER_MIN` | No | `30` | Low | Per-minute outbound email burst limit. |
| `OUTBOUND_RATE_LIMIT_WA_PER_MIN` | No | `10` | Low | Per-minute outbound WhatsApp burst limit. |
| `REQUIRE_HUMAN_APPROVAL` | Yes | `true` | Low | Mandatory human approval safeguard (must remain `true`). |
