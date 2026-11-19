# ActTrident Platform Boundaries & Known Limitations

**Project**: ActTrident AI Sales Outreach & Automation Platform  
**Classification**: System Constraints, Platform Boundaries & Compliance Boundaries

---

## 1. External Third-Party API Credentials

### 1.1 Google Workspace / Gmail API v1
- **Constraint**: Live cold email delivery requires authorized Google Cloud Platform OAuth 2.0 credentials (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, and `GMAIL_SENDER_EMAIL`).
- **Offline / Staging Behavior**: Without these credentials, the system automatically falls back to **simulated mode**. Outbound sends record mock receipts (`sim-gmail-...`) and are segregated in analytics (`emails_simulated`), preventing accidental external delivery.
- **Operational Requirement**: A Google Workspace domain administrator must publish the internal OAuth app and complete the authorization consent flow before initiating live campaigns.

### 1.2 Meta WhatsApp Cloud API v19.0
- **Constraint**: Outbound WhatsApp messaging outside Meta's sandbox requires an active Meta Business Manager account, a verified phone number, a permanent System User Token, and an approved marketing message template (`acttrident_eval_intro_v1`).
- **Offline / Staging Behavior**: Without live credentials, the adapter operates in **sandbox simulation mode** (`sim-wamid-...`), storing payloads locally without initiating HTTP calls.
- **24-Hour Messaging Window Policy**: Under Meta policy, initial cold outreach must strictly use Meta-approved message templates. Freeform conversational messages are only permitted within the 24-hour customer care window following an inbound prospect reply.

---

## 2. LinkedIn Outreach: Policy Limitations & Safe Handoff

### 2.1 Why Full LinkedIn Automation is Prohibited
- **LinkedIn Terms of Service**: Section 8.2 of the LinkedIn User Agreement strictly prohibits headless browser scraping (Puppeteer/Playwright), session cookie extraction (`li_at`), automated connection bots, and unauthorized third-party messaging extensions.
- **Platform Risks**: Automated tools are detected by LinkedIn's behavioral monitoring systems within 24–72 hours, resulting in permanent personal profile restrictions, corporate domain blacklisting, and potential legal exposure.
- **Official InMail API**: LinkedIn's official 1:1 InMail API is restricted exclusively to approved LinkedIn Sales Navigator enterprise partners.

### 2.2 ActTrident Compliant Resolution (Operator Manual Handoff)
- ActTrident provides AI draft composition adhering strictly to LinkedIn's **300-character invitation note ceiling**.
- Drafts require managerial approval in the queue.
- The dedicated `LinkedInView` provides:
  1. **One-click "Copy Message"** (sanitized text to clipboard).
  2. **Direct "Open Profile"** (launches official LinkedIn profile in a new browser tab with active user session).
  3. **"Mark as Sent"** (records manual send confirmation, logs audit timestamp, and advances CRM lead to `contacted`).
- **Result**: **100% account safety**, zero ban risk, and complete compliance with LinkedIn policies.

---

## 3. Outreach Sending Limits & Throttling

### 3.1 Rate Limit Thresholds
To protect domain reputation and prevent spam classification:
- **Burst Rate Limit**: Maximum **10 messages per minute** across all channels.
- **Daily Email Sending Limit**: Default **50 emails per day** per campaign.
- **Daily WhatsApp Sending Limit**: Default **20 WhatsApp messages per day** per campaign.
- **Business Hours Window**: Default **09:00-18:00 IST Weekdays**. Outbox items outside this window are deferred until the next business morning.

### 3.2 Global Outbound Kill Switch
- When `global_outbound_kill_switch` is active, all outbound sending is immediately blocked (`HTTP 423 Locked`).
- Pending outbox items are held in `pending` status until the kill switch is deactivated by an administrator or manager.

---

## 4. Prospect Qualification Boundaries

- **Laptop Fleet Evidence Requirement**: ActTrident's target market is specifically B2B companies in Tier 2 and Tier 3 cities (Siliguri, Gangtok, Patna, Bhagalpur) with **5 or more company-managed laptops/workstations**.
- **Evidence Verification**: The system requires verifiable evidence (MCA registry filings, careers portal listings, or verified LinkedIn company profiles). If a company does not have documented evidence of 5+ laptops, it receives a lower qualification score and is flagged *"Needs manual verification"*, preventing automated campaign dispatch.
- **Demo Data Quarantine**: Any prospect with an `.example.com` domain or marked as a demo fixture is strictly barred from live campaigns.
