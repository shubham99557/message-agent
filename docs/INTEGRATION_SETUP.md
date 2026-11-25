# ActTrident External Integration Setup Guide

**Integrations Covered**: Google Workspace (Gmail API), Meta WhatsApp Cloud API, LinkedIn Integration, AI & Discovery Providers  
**Operational Modes**: Live External Production Mode vs. Safe Local/Staging Simulation Mode

---

## 1. Google Workspace / Gmail API Setup

### Scopes Required:
- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.modify`

### Step 1: Create GCP Project & Enable Gmail API
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create project `ActTrident Outreach Agent`.
3. In **APIs & Services > Library**, search for and enable **Gmail API**.

### Step 2: Configure OAuth Consent Screen & Scopes
1. Go to **APIs & Services > OAuth consent screen**.
2. For business Google Workspace accounts, select **Internal** (avoids public app verification).
3. Add scopes: `gmail.send`, `gmail.readonly`, `gmail.modify`.

### Step 3: Create Credentials & Obtain Refresh Token
1. Go to **Credentials > Create Credentials > OAuth client ID**.
2. Select **Web application** (or **Desktop app** for CLI token generation).
3. Use [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground) with your Client ID and Client Secret to exchange the authorization code for a long-lived **Refresh Token**.

### Step 4: Configure Environment Variables
```env
GMAIL_CLIENT_ID=1092837465-abcdefghijklmn.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-SecretClientKeyHere12345
GMAIL_REFRESH_TOKEN=1//04abcdefghijkLMNOPQRSTUV-WXYZ
GMAIL_SENDER_EMAIL=outreach@acttrident.com
```

> **Simulation Fallback**: If these variables are omitted, ActTrident automatically runs in **simulated mode**, recording `sim-gmail-...` provider receipts without making external calls.

---

## 2. Meta WhatsApp Cloud API Setup

### Requirements:
- Meta for Developers Business App.
- Permanent System User Token with `whatsapp_business_messaging` scope.
- Meta-approved template `acttrident_eval_intro_v1`.

### Step 1: Create Meta App & Enable WhatsApp
1. Visit [developers.facebook.com](https://developers.facebook.com/).
2. Create an app of type **Business** named `ActTrident Sales Automation`.
3. Add the **WhatsApp** product.
4. Record your **Phone Number ID** and **WhatsApp Business Account (WABA) ID**.

### Step 2: Generate Permanent System User Token
1. In [Meta Business Settings](https://business.facebook.com/settings), go to **Users > System Users**.
2. Create an admin system user `acttrident-backend-worker`.
3. Click **Add Assets** and assign your WhatsApp account with full permissions.
4. Click **Generate New Token**, select permissions `whatsapp_business_messaging` and `whatsapp_business_management`, and choose expiration **Never**.

### Step 3: Submit Message Template for Meta Approval
In **WhatsApp Manager > Message Templates**, create template `acttrident_eval_intro_v1`:
```text
Hello {{1}},

We noticed {{2}} has an active engineering and digital team in {{3}}. 

ActTrident is offering a complimentary 90-day evaluation of our workspace security and laptop protection platform for teams with 5+ managed devices.

Would you be open to reviewing a brief overview for your team?

Reply STOP to unsubscribe at any time.
```

### Step 4: Webhook Configuration
1. Under **WhatsApp > Configuration**, configure:
   - **Callback URL**: `https://sales.acttrident.com/api/v1/whatsapp/webhook`
   - **Verify Token**: Set a secure string matching `META_WA_VERIFY_TOKEN`.
2. Subscribe to the `messages` webhook field.

### Step 5: Configure Environment Variables
```env
META_WA_PHONE_NUMBER_ID=109283746591823
META_WA_ACCESS_TOKEN=EAABwzL1...[Permanent System User Token]
META_WA_VERIFY_TOKEN=trident-wa-webhook-sec-99557
META_WA_APP_SECRET=a1b2c3d4e5f60718293a4b5c6d7e8f90
META_WABA_ID=981273019283746
```

> **Simulation Fallback**: If Meta credentials are not provided, ActTrident operates in **safe sandbox mode**, generating `sim-wamid-...` receipts and recording payloads locally.

---

## 3. LinkedIn Compliant Integration Setup

### Policy Notice:
Under LinkedIn Developer Terms of Service, **direct unattended 1:1 InMail/Messaging automation is restricted** and third-party scraping via browser extensions or headless Puppeteer sessions is **strictly prohibited**.

### Compliant Manual Handoff Architecture:
ActTrident implements a fully compliant, semi-automated workflow:
1. **AI Drafting**: Generates personalized connection notes strictly capped at **300 characters** (LinkedIn maximum limit).
2. **Manager Approval**: Drafts are reviewed in the Approval Queue and hashed.
3. **Operator Handoff**: The representative opens `LinkedInView`, clicks **"Copy Message"**, clicks **"Open Profile"** (opens prospect's LinkedIn profile in browser), pastes the text, and clicks **"Mark as Sent"**.
4. **Zero Account Ban Risk**: Guarantees complete compliance with LinkedIn terms without risking account restrictions.

---

## 4. AI & Discovery Providers Setup (Optional)

### Google Gemini API (Personalized Drafting):
```env
GEMINI_API_KEY=AIzaSy...[Your Gemini API Key]
```
*Fallback: If omitted, ActTrident uses verified static template builders with local fact injection.*

### Tavily / SerpApi (Live Web Discovery):
```env
TAVILY_API_KEY=tvly-...[Your Tavily API Key]
SERPAPI_API_KEY=...[Your SerpApi Key]
```
*Fallback: If omitted, ActTrident uses the comprehensive verified discovery catalog for Siliguri, Gangtok, Patna, and Bhagalpur.*
