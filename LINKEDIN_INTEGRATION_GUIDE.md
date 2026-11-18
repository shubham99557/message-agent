# ActTrident AI Sales Outreach Agent — LinkedIn Integration Guide

## 1. Strict Compliance & Anti-Ban Policy
ActTrident integrates with LinkedIn **exclusively through Official LinkedIn OAuth 2.0 and authorized LinkedIn APIs**.

ActTrident **strictly prohibits and never implements**:
- Collecting or storing LinkedIn account passwords
- Extracting browser session cookies (`li_at`, `JSESSIONID`)
- Headless browser automation, DOM clickers, or unauthorized profile scraping
- Automated mass connection requests or unapproved 1:1 DM bots

Violating LinkedIn's User Agreement risks permanent account suspension. ActTrident protects your sales team by enforcing official API permissions and compliant human-assisted workflows.

---

## 2. Official LinkedIn API Permission Tiers (Honest Capability Matrix)

| Capability | Standard LinkedIn OAuth 2.0 App (`openid profile email`) | Approved LinkedIn Partner / Sales Navigator API |
| :--- | :---: | :---: |
| Verify Sales Rep Identity via OAuth 2.0 | **Supported** | **Supported** |
| Store Fernet-Encrypted OAuth Tokens | **Supported** | **Supported** |
| Draft Personalized Connection Notes (≤300 chars) & DMs (≤1900 chars) | **Supported** | **Supported** |
| Mandatory Human Approval + Content-Hash Integrity | **Supported** | **Supported** |
| Compliant Human-Assisted Handoff (`ready_for_manual_send` → `manually_sent_confirmed`) | **Supported (Default)** | **Supported** |
| Automated Direct 1:1 Message Dispatch via REST API | **Not Permitted by LinkedIn** | **Supported** (requires `LINKEDIN_MESSAGING_API_APPROVED=true` + Partner Endpoint) |

> **Truthfulness Guarantee**: When `LINKEDIN_MESSAGING_API_APPROVED=false` (default), ActTrident **never** simulates an API send or fabricates a `provider_message_id`. Approved messages transition cleanly to `ready_for_manual_send` with a copy-ready message and direct profile link so the human sales rep sends it natively inside LinkedIn and clicks **Confirm Manual Send** to log it to the CRM and Audit Log.

---

## 3. Setting Up Official LinkedIn OAuth 2.0

1. Go to the [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps) and create a new app associated with your ActTrident Company Page.
2. Under **Products**, enable **Sign In with LinkedIn using OpenID Connect** (grants `openid`, `profile`, `email`).
3. Under **Auth → OAuth 2.0 settings**, add your Authorized Redirect URL:
   - Local development: `http://localhost:8000/api/v1/integrations/linkedin/oauth/callback`
   - Production: `https://api.your-domain.com/api/v1/integrations/linkedin/oauth/callback`
4. Copy your **Client ID** and **Client Secret** into your backend `.env` file (never commit secrets to Git):

```env
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/v1/integrations/linkedin/oauth/callback
LINKEDIN_API_SCOPES=openid profile email

# Keep false unless LinkedIn has formally approved your organization for Partner Messaging API access
LINKEDIN_MESSAGING_API_APPROVED=false
LINKEDIN_PARTNER_MESSAGING_ENDPOINT=
```

5. In the ActTrident UI, navigate to **Integrations → LinkedIn (Official OAuth 2.0)** and click **Connect LinkedIn (OAuth 2.0)** as an `admin` or `manager`.
6. OAuth access tokens are stored encrypted at rest using Fernet (`CREDENTIAL_ENCRYPTION_KEY`) in `channel_connections` and are never exposed in API responses or logs.

---

## 4. LinkedIn Outreach Workflow
1. **Draft**: Open **LinkedIn Outreach**, choose a target company, verify the `https://www.linkedin.com/in/...` URL, pick `Connection Note (300 char max)` or `Direct Message`, and create a draft.
2. **Human Approval**: An `admin` or `manager` reviews and approves the draft (recording an immutable `ApprovalRecord` with SHA-256 `content_hash`). Any edit to an approved draft automatically invalidates approval.
3. **Dispatch / Handoff**:
   - **Standard mode**: Click **Prepare Manual Handoff**, copy the approved message, open the recipient's LinkedIn profile, send natively inside LinkedIn, and click **Confirm Manual Send** to update CRM pipeline status (`contacted`) and write an `AuditLog` entry.
   - **Approved Partner API mode**: Dispatches via the configured Partner REST endpoint with an idempotency key and stores the real returned `provider_message_id`.
