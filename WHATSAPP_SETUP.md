# ActTrident AI Sales Outreach Agent — Meta WhatsApp Cloud API Setup Guide

## 1. Overview
ActTrident integrates with the official **Meta WhatsApp Cloud API** (Graph API v20.0). It enforces:
- Explicit documented consent (`ContactConsent`) before any template message dispatch.
- Mandatory human approval for all AI-generated drafts.
- Strict parameter ordering (`{{1}}`, `{{2}}`, `{{3}}`) matching Meta-approved templates.
- HMAC-SHA256 signature verification on all incoming webhooks.
- Immediate suppression upon receiving "STOP" or unsubscribe keywords.

---

## 2. Meta Business Manager Configuration

### 2.1 Meta App & WhatsApp Product
1. Sign in to [Meta for Developers](https://developers.facebook.com/).
2. Create an App of type **Business** (e.g., `ActTrident Outreach Engine`).
3. Add the **WhatsApp** product to your app.
4. Navigate to **WhatsApp** → **API Setup**:
   - Note the **Phone Number ID** (e.g. `102938475610293`).
   - Note the **WhatsApp Business Account ID (WABA ID)** (e.g. `987654321098765`).

### 2.2 System User Permanent Access Token
1. Open [Meta Business Suite Settings](https://business.facebook.com/settings).
2. Navigate to **Users** → **System Users**.
3. Create a System User with role **Admin**.
4. Click **Generate New Token**:
   - Select your WhatsApp Business App.
   - Choose token expiration: **Never**.
   - Check permissions:
     - `whatsapp_business_messaging`
     - `whatsapp_business_management`
5. Copy the generated permanent token (`META_WA_ACCESS_TOKEN`).

### 2.3 Webhook Subscription
1. Navigate to **WhatsApp** → **Configuration** in the Meta App dashboard.
2. Callback URL:
   ```text
   https://outreach.acttrident.ai/api/v1/whatsapp/webhook
   ```
3. Verify Token:
   - Generate a strong random token string (e.g., `openssl rand -hex 24`).
   - Paste it into the Meta Webhook setup and set as `META_WA_VERIFY_TOKEN` in `.env`.
4. Click **Verify and Save**.
5. Under **Webhook Fields**, click **Manage** and subscribe to **messages**.

### 2.4 App Secret (HMAC Signature Verification)
1. Navigate to **App Settings** → **Basic**.
2. Click **Show** next to **App Secret**.
3. Copy the string and set as `META_APP_SECRET` in `.env`.

---

## 3. Environment Variables Configuration

Set these parameters in your host `.env` file:

```ini
WHATSAPP_ENABLED=true
META_WA_ACCESS_TOKEN=EAA...your_system_user_token
META_WA_PHONE_NUMBER_ID=your_phone_number_id
META_WA_BUSINESS_ACCOUNT_ID=your_waba_id
META_WA_VERIFY_TOKEN=your_secure_verify_token
META_APP_SECRET=your_meta_app_secret
DEFAULT_DAILY_WHATSAPP_LIMIT=20
OUTBOUND_RATE_LIMIT_WA_PER_MIN=10
```

---

## 4. Message Templates & Consent Policy

### 4.1 Creating Templates in Meta Business Manager
Outbound business-initiated messages outside the 24-hour customer service window must use Meta-approved templates:
1. Navigate to **WhatsApp Manager** → **Account Tools** → **Message Templates**.
2. Create template `acttrident_intro_eval`:
   - Category: **MARKETING**
   - Header: *None*
   - Body:
     ```text
     Hello {{1}}, we noticed {{2}}'s expanding technical operations in {{3}}. ActTrident offers a 90-Day Free Evaluation of our endpoint workspace security for teams with 5+ laptops. Reply YES to review evaluation details, or STOP to opt out.
     ```
3. Submit for Meta review.

### 4.2 Template Synchronization in ActTrident
1. Open the ActTrident Dashboard → **WhatsApp** view.
2. Click **Sync Meta Templates** (`POST /api/v1/whatsapp/templates/sync`).
3. The platform fetches templates from Meta Graph API, storing their actual approval status (`APPROVED`, `PENDING`, `REJECTED`).
4. Only templates with verified `APPROVED` status can be dispatched.

---

## 5. Webhook Events & Automated Actions

| Webhook Event | Payload Status | ActTrident System Action |
| :--- | :--- | :--- |
| `status: "sent"` | Sent to Meta | Draft marked `sent`, provider `wamid` stored. |
| `status: "delivered"` | Handset received | Draft marked `delivered`, delivery timestamp set. |
| `status: "read"` | Recipient viewed | Draft marked `read`. |
| `status: "failed"` | Delivery failed | Draft marked `failed`, error code logged. |
| Inbound message | Text: `"STOP"` / `"Unsubscribe"` | Contact automatically suppressed, pipeline set to `do_not_contact`. |
| Inbound message | Inbound reply text | Associated with lead in Inbox, AI classification triggered, suggested response generated. |
