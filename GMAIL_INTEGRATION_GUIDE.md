# ActTrident AI Sales Agent — Gmail API OAuth 2.0 Integration Guide

## 1. Architecture Overview
ActTrident supports three clearly separated email dispatch modes:

| Mode | Trigger Condition | Outbound Behavior | Provider Message ID | Delivery Reporting |
| :--- | :--- | :--- | :--- | :--- |
| **Gmail API (OAuth 2.0)** *(Recommended)* | Active `ChannelConnection(channel="gmail", status="connected")` | Sends via `gmail.googleapis.com/gmail/v1/users/me/messages/send` + syncs inbox replies & bounces | Genuine Gmail `id` & `threadId` | `sent` until provider-confirmed `delivered` / `bounced` |
| **SMTP Fallback** | `EMAIL_PROVIDER=smtp` with `SMTP_USER` & `SMTP_PASSWORD` (no active Gmail OAuth) | Dispatches via STARTTLS SMTP relay | RFC 5322 `Message-ID` | Recorded as `smtp_accepted` (never falsely marked `delivered`) |
| **Mock / Simulation** | Default when no provider is connected | Local simulation only — **no external email is sent** | `None` (never fabricated) | Marked strictly as `simulated` |

---

## 2. Google Cloud Console Setup (Step-by-Step)

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or create your ActTrident project.
2. Enable the **Gmail API** under *APIs & Services → Library*.
3. Configure the **OAuth Consent Screen** (*APIs & Services → OAuth consent screen*):
   - Choose **Internal** (Google Workspace) or **External** (add your test mailbox as a Test User during verification).
   - Add **only least-privilege scopes**:
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `https://www.googleapis.com/auth/userinfo.email`
4. Create an **OAuth 2.0 Client ID** (*Credentials → Create Credentials → OAuth client ID → Web application*):
   - Add Authorized Redirect URI:
     - Local development: `http://localhost:8000/api/v1/integrations/gmail/oauth/callback`
     - Production: `https://<your-api-domain>/api/v1/integrations/gmail/oauth/callback`
5. Set the environment variables in `.env` (never commit real secrets to git):
   ```ini
   GMAIL_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=<your-client-secret>
   GMAIL_REDIRECT_URI=http://localhost:8000/api/v1/integrations/gmail/oauth/callback
   ```

---

## 3. Connecting & Verifying in ActTrident

1. Sign in as an **Admin** or **Manager**.
2. Open **Integrations** in the sidebar.
3. Under **Gmail API (Google OAuth 2.0)**, click **Connect Gmail (OAuth 2.0)**.
4. Approve the least-privilege scopes on Google's consent screen.
5. The backend verifies the HMAC-signed CSRF `state`, exchanges the authorization code, encrypts both access and refresh tokens at rest using **Fernet**, and updates connection status to `connected`.
6. Use **Sync Replies** to pull incoming replies and provider bounce notices, or **Disconnect** to revoke tokens at Google and wipe stored credentials.

---

## 4. Safety & Reliability Guarantees
- **Mandatory Human Approval:** No email can be dispatched without explicit `admin`/`manager` approval and matching SHA-256 content hash.
- **Idempotency & Race Protection:** Every approved draft version uses an atomic `approved → sending` database claim and deterministic `idempotency_key` checked against `email_send_attempts` to guarantee duplicate retries never send duplicate emails.
- **Token Expiration & Revocation:** Expired access tokens refresh automatically; revoked permissions (`invalid_grant` / HTTP 401/403) automatically mark the connection `reauth_required` with a visible UI alert.
