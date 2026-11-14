# ActTrident AI Outreach Agent - Gmail & SMTP Setup Guide

This guide details how to configure outbound email dispatch for the ActTrident B2B outreach platform using either Google Workspace SMTP (recommended for fast setup) or the Google Workspace Gmail API.

---

## 1. Option A: Google Workspace SMTP (App Password) - Recommended

### Step 1: Enable 2-Step Verification
1. Sign in to your ActTrident Google Workspace account (e.g. `outreach@acttrident.ai`).
2. Navigate to **Google Account Settings** > **Security**.
3. Under *How you sign in to Google*, ensure **2-Step Verification** is turned ON.

### Step 2: Generate an App Password
1. Search for **App Passwords** in your Google Account Security tab.
2. Under *Select app*, select **Mail**. Under *Select device*, select **Custom (ActTrident Platform)**.
3. Click **Generate**.
4. Google will display a 16-character password (e.g., `abcd efgh ijkl mnop`). Copy this password without spaces.

### Step 3: Configure Environment Variables or Integrations Tab
In your `.env` file or in the **Integrations** tab of the dashboard:
```bash
EMAIL_PROVIDER="smtp"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="outreach@acttrident.ai"
SMTP_PASSWORD="your16characterapppassword"
SMTP_FROM_NAME="ActTrident Business Development"
SMTP_FROM_EMAIL="outreach@acttrident.ai"
SMTP_USE_TLS=true
```

---

## 2. Option B: Google Cloud Gmail API (OAuth 2.0 / Service Account)

### Step 1: Create a Project in Google Cloud Console
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project: `acttrident-outreach`.
3. Enable the **Gmail API** under *APIs & Services* > *Library*.

### Step 2: Configure OAuth Consent Screen & Scopes
1. Go to **OAuth consent screen**.
2. Select **Internal** (if restricted to `acttrident.ai` domain) or **External**.
3. Add the scope: `https://www.googleapis.com/auth/gmail.send`.

### Step 3: Create OAuth Client ID
1. Navigate to **Credentials** > **Create Credentials** > **OAuth client ID**.
2. Application type: **Web application**.
3. Download the credentials JSON and place it in the secure backend directory.

---

## 3. Deliverability Best Practices (SPF, DKIM & DMARC)

To ensure messages from `acttrident.ai` reach the primary inbox and prevent spam filtering:
- **SPF**: Add `v=spf1 include:_spf.google.com ~all` to your DNS TXT records.
- **DKIM**: Generate a 2048-bit DKIM key in Google Admin Console and publish the TXT record in your DNS.
- **DMARC**: Publish `v=DMARC1; p=quarantine; rua=mailto:dmarc@acttrident.ai` in your DNS.
- **Rate Limits**: The ActTrident platform enforces a conservative default daily limit of **50 emails per day** to protect domain reputation.
