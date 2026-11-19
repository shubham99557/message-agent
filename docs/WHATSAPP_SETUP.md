# Meta WhatsApp Cloud API Setup & Compliance Guide

**API Version**: Meta Graph API v19.0+  
**Adapter Implementation**: `app.integrations.whatsapp_adapter.WhatsAppChannelAdapter`  
**Compliance Standard**: Meta WhatsApp Business Messaging Policy & India TRAI Telecom Commercial Communications Customer Preference Regulations (TCCCPR)

---

## 1. Overview & Operational Modes

ActTrident integrates with the Meta WhatsApp Cloud API to deliver personalized introductory notifications to verified business decision makers and handle instant replies via webhooks.

### Operational Modes:
1. **Live Production Mode**: Active when valid `META_WA_ACCESS_TOKEN`, `META_WA_PHONE_NUMBER_ID`, `META_WA_APP_SECRET`, and `META_WABA_ID` are configured. Communicates directly with `https://graph.facebook.com/v19.0/`. Outbound messages receive genuine `wamid` message IDs and update delivery receipts.
2. **Sandbox / Simulation Mode**: Enabled when credentials are unconfigured or in test mode. Messages are flagged with status `simulated`, generating a mock provider ID (`sim-wamid-<timestamp>`) and storing the rendered payload without hitting Meta's servers.

---

## 2. Meta for Developers Account & App Creation

### Step 1: Create a Meta for Developers Account
1. Visit [developers.facebook.com](https://developers.facebook.com/) and register or log in.
2. Link your Meta account to your verified business organization in Meta Business Manager.

### Step 2: Create a Business App
1. Go to **My Apps > Create App**.
2. Select **Other** as the use case, click Next.
3. Select **Business** as the app type.
4. App Name: `ActTrident Sales Automation`.
5. Link to your **Meta Business Account**.
6. Click **Create app**.

### Step 3: Add WhatsApp Product
1. On the App Dashboard, locate **WhatsApp** and click **Set up**.
2. Review the API Getting Started screen.
3. Meta provisions a complimentary **Test Phone Number** and assigns:
   - **Phone number ID**
   - **WhatsApp Business Account (WABA) ID**
   - **Temporary 24-hour access token**

---

## 3. Generating a Permanent System User Token

Temporary developer tokens expire every 24 hours. For automated production campaigns:

1. Open [Meta Business Settings](https://business.facebook.com/settings).
2. Under **Users**, select **System Users**.
3. Click **Add**, name the user `acttrident-backend-worker`, and select role **Admin**.
4. Click **Add Assets**:
   - Assign your **WhatsApp Business Account** with **Full control (Manage WhatsApp Business Account)**.
5. Click **Generate New Token**:
   - Select your ActTrident App.
   - Token expiration: **Never** (Permanent).
   - Scopes required:
     - `whatsapp_business_messaging`
     - `whatsapp_business_management`
6. Copy and store the resulting access token securely.

---

## 4. Message Template Creation & Approval

Under WhatsApp policy, **cold outreach or businesses initiating conversation outside the 24-hour customer care window MUST use Meta-approved message templates**. Freeform messaging is prohibited for initial contact.

### Required Template: `acttrident_eval_intro_v1`
1. In Meta Business Manager, navigate to **WhatsApp Manager > Message Templates**.
2. Click **Create Template**:
   - **Category**: `MARKETING`
   - **Name**: `acttrident_eval_intro_v1`
   - **Language**: `English (US)` (`en_US`)
3. **Template Body**:
   ```text
   Hello {{1}},

   We noticed {{2}} has an active engineering and digital team in {{3}}. 

   ActTrident is offering a complimentary 90-day evaluation of our workspace security and laptop protection platform for teams with 5+ managed devices.

   Would you be open to reviewing a brief overview for your team?

   Reply STOP to unsubscribe at any time.
   ```
4. **Variables**:
   - `{{1}}`: Decision Maker Name (e.g. "Amitabh")
   - `{{2}}`: Company Name (e.g. "Siliguri Infotech")
   - `{{3}}`: Target City (e.g. "Siliguri")
5. Submit for review (typically approved by Meta within 5 to 30 minutes).

---

## 5. Webhook Setup & Signature Verification

ActTrident receives real-time delivery status updates (`sent`, `delivered`, `read`) and prospect replies via the WhatsApp Webhook.

### Webhook Configuration:
1. In App Dashboard, go to **WhatsApp > Configuration**.
2. In the **Webhook** section, click **Edit**:
   - **Callback URL**: `https://your-domain.com/api/v1/whatsapp/webhook`
   - **Verify Token**: Set a secure secret matching `META_WA_VERIFY_TOKEN` (e.g. `trident-wa-webhook-sec-99557`).
3. Click **Verify and Save**.
4. In **Webhook fields**, click **Manage** and subscribe to:
   - `messages` (Inbound customer messages, text replies, and button clicks)

### Cryptographic HMAC-SHA256 Signature Validation:
- Every inbound webhook payload sent by Meta includes the header:
  ```http
  X-Hub-Signature-256: sha256=4f5d6e7f8...
  ```
- ActTrident validates this header against your `META_WA_APP_SECRET` using `app.core.security.verify_meta_webhook_signature()`.
- If the signature is missing or does not match the payload digest, ActTrident immediately returns `HTTP 403 Forbidden` to prevent spoofing.

---

## 6. Automated Opt-Out & Stop Compliance

1. **Keyword Detection**: The webhook listener inspects all incoming text replies for mandatory opt-out keywords:
   - `STOP`, `UNSUBSCRIBE`, `CANCEL`, `OPT OUT`, `REMOVE ME`
2. **Immediate Execution**: When detected:
   - The prospect's phone number is added to the global suppression table (`handle_opt_out(db, identifier=phone, channel='whatsapp')`).
   - The associated CRM lead status transitions to `opted_out`.
   - All pending WhatsApp outbox dispatches for that number are cancelled.
   - An automated single-message confirmation is returned acknowledging the opt-out.

---

## 7. Environment Variables Reference

Add the following keys to your production environment:

```env
# Meta WhatsApp Cloud API Configuration
META_WA_PHONE_NUMBER_ID=109283746591823
META_WA_ACCESS_TOKEN=EAABwzL1...[System User Permanent Token]
META_WA_VERIFY_TOKEN=trident-wa-webhook-sec-99557
META_WA_APP_SECRET=a1b2c3d4e5f60718293a4b5c6d7e8f90
META_WABA_ID=981273019283746
```
