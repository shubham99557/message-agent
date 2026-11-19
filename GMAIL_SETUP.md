# ActTrident AI Sales Outreach Agent — Gmail OAuth 2.0 Production Setup Guide

## 1. Overview
The ActTrident Gmail Integration uses official Google OAuth 2.0 with offline access to dispatch approved outbound sales outreach and synchronize prospect replies and bounce events.

---

## 2. Google Cloud Console Configuration

### 2.1 Project & API Activation
1. Sign in to [Google Cloud Console](https://console.cloud.google.com/).
2. Select or create your Google Cloud Project (e.g., `acttrident-sales-prod`).
3. Navigate to **APIs & Services** → **Library**.
4. Search for **Gmail API** and click **Enable**.

### 2.2 OAuth Consent Screen
1. Navigate to **APIs & Services** → **OAuth consent screen**.
2. Select User Type:
   - **Internal** (Recommended if outreach mailbox is hosted on ActTrident Google Workspace).
   - **External** (Requires Google App Verification if sending to general public mailboxes).
3. App Information:
   - App Name: `ActTrident Sales Automation`
   - User Support Email: `outreach@acttrident.ai`
   - Developer Contact Email: `security@acttrident.ai`
4. Minimum Required Scopes:
   - `https://www.googleapis.com/auth/gmail.send` (Send messages on your behalf)
   - `https://www.googleapis.com/auth/gmail.readonly` (Read incoming replies and bounce notices)
   - `https://www.googleapis.com/auth/userinfo.email` (Identify authenticated sender mailbox)
5. Save and continue. For External apps in testing status, add authorized team mailboxes to **Test Users**.

### 2.3 OAuth 2.0 Credentials
1. Navigate to **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **OAuth client ID**.
3. Application Type: **Web application**.
4. Name: `ActTrident Outreach Backend`.
5. Authorized Redirect URIs:
   - Development: `http://localhost:8000/api/v1/integrations/gmail/oauth/callback`
   - Staging: `https://staging.acttrident.ai/api/v1/integrations/gmail/oauth/callback`
   - Production: `https://outreach.acttrident.ai/api/v1/integrations/gmail/oauth/callback`
6. Click **Create**. Copy the generated `Client ID` and `Client Secret`.

---

## 3. Environment Variable Configuration

Add the credentials to your host `.env` file (never commit secrets to version control):

```ini
EMAIL_PROVIDER=gmail
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REDIRECT_URI=https://outreach.acttrident.ai/api/v1/integrations/gmail/oauth/callback
```

---

## 4. Operator Connection Walkthrough

1. Open the ActTrident Dashboard at `https://outreach.acttrident.ai/`.
2. Sign in with your Administrator or Manager account.
3. In the sidebar, navigate to **Integrations**.
4. Locate the **Gmail API (Google OAuth 2.0)** card.
5. Click **Connect Gmail (OAuth 2.0)**:
   - You will be redirected to Google's OAuth consent screen.
   - Confirm permissions for your sender mailbox (e.g. `outreach@acttrident.ai`).
6. Upon redirect, the backend:
   - Verifies the HMAC CSRF state token.
   - Exchanges the authorization code for access and refresh tokens.
   - Encrypts tokens using AES-256 Fernet at rest in the database.
   - Updates the channel status to `connected`.

---

## 5. Inbox Reply & Bounce Polling

- **Automatic Polling:** Celery Beat periodically triggers `task_gmail_reply_sync` every 5 minutes (`gmail-reply-sync-poller`).
- **Manual Trigger:** In **Integrations**, click **Sync Replies** to poll immediately.
- **Bounce Deduplication:** The synchronizer checks existing `EmailEvent` records by provider message ID, preventing duplicate bounce registrations.
- **Unsubscribe Actions:** If an incoming email reply is classified as `Unsubscribe` or `Complaint`, the contact is immediately added to the global suppression list and future dispatches are blocked.

---

## 6. Disconnecting & Revoking Access

1. Navigate to **Integrations** → **Gmail API**.
2. Click **Disconnect**:
   - The backend sends a revocation request to `oauth2.googleapis.com/revoke`.
   - Stored access and refresh tokens are wiped from the database.
   - Channel status transitions to `disconnected`.
