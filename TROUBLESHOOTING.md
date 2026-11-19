# ActTrident AI Sales Outreach Agent — Troubleshooting Guide

## 1. Backend Startup Fails with `CRITICAL SECURITY ERROR`
- **Cause**: Running with `ENVIRONMENT=production` while one of the fail-fast security guards is violated.
- **Fix**: Verify `.env` sets:
  1. `SECRET_KEY` (≥32 random characters, not containing `replace-in-env`)
  2. `CREDENTIAL_ENCRYPTION_KEY` (valid Fernet key or ≥16 random characters)
  3. `BACKEND_CORS_ORIGINS` (explicit origins, no `*`)
  4. `DATABASE_URL` pointing to `postgresql://...` (SQLite is forbidden in production).
  5. `META_APP_SECRET` and non-default `META_WA_VERIFY_TOKEN` if WhatsApp is enabled with access tokens.

## 2. Login Succeeds Locally, or Old Credentials Fail
- **Cause**: Production disables default admin seeding; local dev uses `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` from `.env`, or a password was changed/user deactivated.
- **Fix**: Provision or reset an admin securely via CLI:
  ```bash
  python backend/scripts/provision_admin.py --email admin@acttrident.ai --name "ActTrident Admin"
  ```

## 3. `401 Unauthorized` Immediately After Role Change, Logout, or Deactivation
- **Cause**: Working as designed — `User.token_version` increments on logout/role change/deactivation to immediately revoke active JWTs and refresh tokens.
- **Fix**: Sign in again to obtain a fresh access & refresh token pair.

## 4. `423 Locked` or `Blocked: Global Outbound Kill Switch is ACTIVE`
- **Cause**: An administrator or manager activated the **Global Emergency Outbound Kill Switch**.
- **Fix**: Navigate to **Settings → Global Emergency Outbound Kill Switch** and click **Resume Sending** (or `POST /api/v1/settings/kill-switch` with `{"active": false}`).

## 5. `409 Conflict` When Dispatching Campaign Emails
- **Cause**: The campaign status is `paused` or `stopped`.
- **Fix**: If `paused`, click **Resume** in **Campaigns**. Permanently `stopped` campaigns cannot be resumed; create a new campaign.

## 6. `429 Too Many Requests` During Outbound Send
- **Cause**: The per-minute outbound rate limit has been reached (`OUTBOUND_RATE_LIMIT_EMAIL_PER_MIN=30` or `OUTBOUND_RATE_LIMIT_WA_PER_MIN=10`).
- **Fix**: Wait 60 seconds for the sliding-window limit to reset, or dispatch messages through the asynchronous background outbox worker (`POST /campaigns/{id}/enqueue-approved`).

## 7. Gmail OAuth Shows `reauth_required`
- **Cause**: Google revoked the refresh token (`invalid_grant`) or scopes changed.
- **Fix**: Go to **Integrations → Gmail API (Google OAuth 2.0)** and click **Reconnect Gmail**.

## 8. Meta WhatsApp Webhook Returns `403 Forbidden`
- **Cause**: Missing or invalid `X-Hub-Signature-256` HMAC signature or mismatched `META_APP_SECRET`.
- **Fix**: Ensure `META_APP_SECRET` in `.env` matches the exact App Secret from Meta App Dashboard → Basic Settings.

## 9. SQLite `database is locked` During Local Alembic Migrations
- **Cause**: The local `uvicorn` backend server is holding a file lock on `acttrident.db`.
- **Fix**: Stop `uvicorn`, run `python -m alembic -c backend/alembic.ini upgrade head`, and restart `uvicorn`.

## 10. LinkedIn Outreach Shows `ready_for_manual_send` Instead of Sending Automatically
- **Cause**: Working as designed — LinkedIn restricts automated 1:1 DM APIs to approved LinkedIn Partners. Standard OAuth apps use compliant human-assisted handoff (`LINKEDIN_MESSAGING_API_APPROVED=false`) to prevent account bans.
- **Fix**: Copy the approved message, open the prospect's LinkedIn URL, send natively inside LinkedIn, and click **Confirm Manual Send** to log it to CRM.

## 11. Celery Worker / Redis Connection Errors
- **Cause**: Redis server is stopped or unreachable on the configured `REDIS_URL`.
- **Fix**: Check that Redis is running (`redis-cli ping` returns `PONG`). In Docker, verify `redis` service health:
  ```bash
  docker compose exec redis redis-cli ping
  ```

## 12. PostgreSQL Backup/Restore CLI Fails with Binary Not Found
- **Cause**: `pg_dump` or `pg_restore` is not installed on the host system or container.
- **Fix**: Inside Docker containers, `docker/Dockerfile.backend` installs `postgresql-client`. On a Windows host, ensure `C:\Program Files\PostgreSQL\18\bin` is added to your system `PATH`.
