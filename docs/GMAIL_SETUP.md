# Gmail OAuth 2.0 Integration & Setup Guide

**Provider**: Google Workspace / Gmail API v1  
**Scopes Required**:  
- `https://www.googleapis.com/auth/gmail.send` (Deliver approved cold outreach)  
- `https://www.googleapis.com/auth/gmail.readonly` (Synchronize replies and bounce notifications)  
- `https://www.googleapis.com/auth/gmail.modify` (Label and archive processed sales communications)

---

## 1. Overview & Operational Modes

ActTrident interfaces with Google Workspace to dispatch personalized outreach emails from verified sales representative accounts, synchronize prospect replies into the CRM inbox, and detect non-delivery bounce reports.

### Operational Modes:
1. **Live Production Mode**: Enabled when `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, and `GMAIL_SENDER_EMAIL` are valid and authorized. The adapter sends emails directly via `https://gmail.googleapis.com/gmail/v1/users/me/messages/send`.
2. **Simulated Sandbox Mode**: Enabled automatically when credentials are absent or contain placeholder values. Outbound messages are recorded with status `simulated`, generating a mock provider ID (`sim-gmail-<timestamp>`) and storing headers without initiating external HTTP traffic. **Simulated messages are strictly segregated in analytics.**

---

## 2. Google Cloud Platform Configuration

### Step 1: Create or Select GCP Project
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named `ActTrident Sales Outreach`.
3. Note your **Project ID**.

### Step 2: Enable the Gmail API
1. In the GCP Navigation Menu, select **APIs & Services > Library**.
2. Search for **Gmail API**.
3. Click **Enable**.

### Step 3: Configure the OAuth Consent Screen
1. Go to **APIs & Services > OAuth consent screen**.
2. **User Type**:
   - If using Google Workspace (recommended for business outreach), select **Internal**. This restricts authorization to your domain and avoids public verification requirements.
   - If using a standard Google account during staging, select **External** and add your sender email to the **Test Users** list.
3. Fill in the App Name: `ActTrident Outreach Agent`.
4. Add User Support Email and Developer Contact Information.
5. In **Scopes for Google APIs**, click **Add or Remove Scopes** and select:
   - `.../auth/gmail.send`
   - `.../auth/gmail.readonly`
   - `.../auth/gmail.modify`
6. Save and continue.

### Step 4: Create OAuth 2.0 Credentials
1. Navigate to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. **Application type**: Select **Web application** (or **Desktop app** for initial headless CLI token generation).
4. Name: `ActTrident Backend Integration`.
5. Authorized redirect URIs:
   - `https://developers.google.com/oauthplayground` (for rapid token generation)
   - Or your production callback URL: `https://your-domain.com/api/v1/integrations/gmail/callback`
6. Click **Create**.
7. Securely record your **Client ID** and **Client Secret**.

---

## 3. Obtaining the Refresh Token

To enable unattended background dispatch and Celery Beat synchronization, obtain a long-lived OAuth 2.0 Refresh Token.

### Using OAuth 2.0 Playground:
1. Open [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground).
2. Click the gear icon (Settings) in the top right:
   - Check **Use your own OAuth credentials**.
   - Enter your **OAuth Client ID** and **OAuth Client Secret**.
3. In **Step 1 (Select & authorize APIs)**, paste the three Gmail scopes:
   ```
   https://www.googleapis.com/auth/gmail.send
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/gmail.modify
   ```
4. Click **Authorize APIs** and log in with your designated sender email (e.g. `outreach@acttrident.com`).
5. In **Step 2 (Exchange authorization code for tokens)**, click **Exchange authorization code for tokens**.
6. Copy the resulting **Refresh token**.

---

## 4. Production Environment Configuration

Inject the obtained credentials into your production environment (`.env` or Docker secrets):

```env
# Google Workspace / Gmail Configuration
GMAIL_CLIENT_ID=1092837465-abcdefghijklmn.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-SecretClientKeyHere12345
GMAIL_REFRESH_TOKEN=1//04abcdefghijkLMNOPQRSTUV-WXYZ
GMAIL_SENDER_EMAIL=outreach@acttrident.com

# Symmetric Fernet Key for DB Token Encryption (Generate with cryptography.fernet.Fernet.generate_key())
ENCRYPTION_KEY=z8Yx7w6v5u4t3s2r1q0pONMLKJIHGFEDCBA=
```

---

## 5. Token Encryption & Storage Architecture

- When stored in the `integrations` table, sensitive credentials (`client_secret`, `refresh_token`) are encrypted with AES-128-CBC / HMAC-SHA256 via `cryptography.fernet.Fernet`.
- During application startup, `app.integrations.gmail_adapter.GmailAdapter` initializes with the decrypted credentials.
- The adapter automatically handles access token refreshes when the 3600-second Google token expires, catching HTTP 401 errors and rotating tokens in memory.

---

## 6. Reply Synchronization & Bounce Deduplication

1. **Celery Beat Polling**: Every 300 seconds (5 minutes), `sync-gmail-inbox-replies` polls the Gmail API:
   - Queries `q="is:unread -from:me"` to fetch new inbound messages.
   - Extracts `Message-ID`, `In-Reply-To`, and `References` headers to thread replies back to original cold outreach drafts.
   - Categorizes reply intent using NLP classification (Positive, Meeting Request, Opt-out, Technical Question, Not Interested).
2. **Bounce Handling**:
   - Queries `q="from:mailer-daemon@googlemail.com OR subject:Delivery Status Notification"`
   - Parses the recipient email address and failure code (550, 554, etc.).
   - Marks the prospect's lead status as `bounced` and appends to the suppression registry.
   - **Deduplication**: Records the Gmail message ID in `EmailSendAttempt` so subsequent synchronization cycles do not inflate bounce counts.
