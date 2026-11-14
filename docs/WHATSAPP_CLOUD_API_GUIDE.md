# ActTrident AI Outreach Agent - Meta WhatsApp Cloud API Setup Guide

This guide provides instructions for configuring the **official Meta WhatsApp Business Cloud API** for ActTrident B2B messaging while adhering to Meta policies and privacy regulations.

---

## 1. Compliance Architecture & Consent Rules

> [!IMPORTANT]
> The ActTrident platform enforces strict consent verification before any automated message can be sent:
> - Never send unsolicited promotional WhatsApp messages to scraped or publicly listed phone numbers.
> - Documented permission is mandatory for automated Meta Cloud API delivery (`opted_in` status).
> - If a company has a public WhatsApp number without documented consent, the platform automatically produces a compliant **Click-to-Chat (`https://wa.me/...`)** link for one-to-one manual outreach.

---

## 2. Meta Business Manager & Cloud API Setup

### Step 1: Register on Meta for Developers
1. Log in to [Meta for Developers](https://developers.facebook.com/).
2. Click **My Apps** > **Create App**.
3. Select **Business** as the app type and name it `ActTrident Outreach Engine`.

### Step 2: Add the WhatsApp Product
1. On the App Dashboard, find **WhatsApp** and click **Set Up**.
2. Select or create your **Meta Business Account (WABA)**.
3. Meta will provide a test business phone number, a **Phone Number ID**, and a temporary 24-hour token.

### Step 3: Generate a Permanent System User Token
1. Go to [Meta Business Settings](https://business.facebook.com/settings).
2. Under **Users** > **System Users**, click **Add**.
3. Role: **Admin**.
4. Click **Generate New Token**.
5. Select your ActTrident App and select permissions:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
6. Copy the resulting permanent token (`EAAB...`).

---

## 3. Registering Pre-Approved Meta Templates

In the **WhatsApp Manager** > **Message Templates**, submit the two standard ActTrident templates:

### Template 1: `acttrident_intro_utility_v1`
- **Category**: Utility
- **Language**: English (`en`)
- **Header**: ActTrident Workspace Protection
- **Body**:
  ```text
  Hello {{1}}, this is ActTrident (https://acttrident.ai/). We are connecting regarding your business laptop management in {{2}}. Eligible teams with 5+ managed devices qualify for our proposed 90-day evaluation program. Would you like a brief demonstration?
  ```
- **Footer**: Reply STOP to opt out

### Template 2: `acttrident_eval_notice_v1`
- **Category**: Utility
- **Language**: English (`en`)
- **Header**: 90-Day Free Evaluation Notice
- **Body**:
  ```text
  Dear {{1}}, following up on your request for ActTrident workspace protection for {{2}}. Your 90-day evaluation setup is ready for scheduling. Please reply to select a time.
  ```
- **Footer**: Reply STOP to opt out

---

## 4. Configuring Webhook Callback

1. In the Meta App Dashboard under WhatsApp > **Configuration**:
   - **Callback URL**: `https://your-domain.com/api/v1/whatsapp/webhook`
   - **Verify Token**: `acttrident_meta_webhook_secret_2026`
2. Under Webhook Fields, subscribe to:
   - `messages` (inbound replies)
   - `message_template_status_update` (template approvals)
