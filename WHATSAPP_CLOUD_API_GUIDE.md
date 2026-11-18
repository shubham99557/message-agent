# ActTrident AI Sales Agent — Official Meta WhatsApp Cloud API Guide

## 1. Architecture & Policy Guarantees
ActTrident integrates **exclusively** with the official **Meta WhatsApp Business Cloud API** (Graph API v20.0).

- **Consent First:** Publicly listed phone numbers never imply consent. Every outbound WhatsApp message requires a documented `ContactConsent(consent_status="opted_in")` record, which is **re-verified live immediately before dispatch**.
- **Human Approval & Content Hash:** Every outbound WhatsApp draft requires explicit `admin`/`manager` approval and immutable SHA-256 content hash matching.
- **Template Provenance:** Templates synchronized from Meta carry `synced_from_meta=true` and their **actual Meta approval status** (`APPROVED`, `PENDING`, `REJECTED`, `PAUSED`). Only `APPROVED` templates can be sent via Meta Cloud API, with parameters strictly validated and numerically ordered (`{{1}}`, `{{2}}`, `{{3}}`).
- **Click-to-Chat Fallback:** `wa.me/<digits>` links remain a manual user-initiated option and are never counted as sent messages.
- **Honest Simulation Mode:** Without Meta credentials, sends are marked `simulated` with `meta_message_id=null` and never reported as delivered.

---

## 2. Meta Developers Setup Checklist

1. Create or open a Meta App at [developers.facebook.com](https://developers.facebook.com/) and add the **WhatsApp** product.
2. In **WhatsApp → API Setup**, collect:
   - **Phone Number ID** → `META_WA_PHONE_NUMBER_ID`
   - **WhatsApp Business Account ID (WABA ID)** → `META_WA_BUSINESS_ACCOUNT_ID`
3. Create a permanent **System User Access Token** in Meta Business Settings with `whatsapp_business_messaging` and `whatsapp_business_management` permissions → `META_WA_ACCESS_TOKEN`.
4. Copy the **App Secret** from *App Settings → Basic* → `META_APP_SECRET` (used for mandatory `X-Hub-Signature-256` HMAC verification).
5. Configure the Webhook URL under *WhatsApp → Configuration*:
   - Callback URL: `https://<your-api-domain>/api/v1/whatsapp/webhook`
   - Verify Token: match `META_WA_VERIFY_TOKEN`
   - Subscribe to `messages` field (delivers inbound replies + `sent`/`delivered`/`read`/`failed` status events).

---

## 3. Environment Variables
```ini
WHATSAPP_ENABLED=true
META_WA_ACCESS_TOKEN=<permanent_system_user_token>
META_WA_PHONE_NUMBER_ID=<phone_number_id>
META_WA_BUSINESS_ACCOUNT_ID=<waba_id>
META_WA_VERIFY_TOKEN=<strong_random_verify_token>
META_APP_SECRET=<meta_app_secret_for_hmac_sha256>
```

---

## 4. Verification Workflow in ActTrident
1. Open **WhatsApp** in the UI as an Admin/Manager.
2. Click **Check Meta Health** (`POST /api/v1/whatsapp/health-check`) to verify live credentials and business phone quality rating.
3. Click **Sync Meta Templates** (`POST /api/v1/whatsapp/templates/sync`) to pull actual Meta template approval statuses.
4. Record documented consent for a test phone number, generate a draft, explicitly approve it, and verify status transitions (`sent` → `delivered` → `read`) and `"STOP"` opt-out suppression via signed webhooks.
