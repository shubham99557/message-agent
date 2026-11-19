# ActTrident AI Sales Outreach Agent — LinkedIn API Policy & Limitations

## 1. Compliance Statement & Anti-Ban Policy
ActTrident operates in strict adherence to LinkedIn's User Agreement and API Terms of Service.

### Prohibited Techniques (Never Used)
- **Zero Browser Automation:** No headless browser scripts (Puppeteer, Selenium, Playwright) navigating LinkedIn user accounts.
- **Zero Cookie Extraction:** No extraction or storage of session cookies (`li_at`, `JSESSIONID`).
- **Zero Credential Collection:** The application never requests, stores, or inputs LinkedIn passwords.
- **Zero Mass Scraping:** No automated scraping of private profiles or connections.

Using unauthorized automation risks permanent personal and company account bans. ActTrident protects your team by using official APIs and honest human-in-the-loop workflows.

---

## 2. Capability Matrix by Permission Tier

| Capability | Standard OAuth 2.0 (`openid profile email`) | Approved LinkedIn Partner / Messaging API |
| :--- | :---: | :---: |
| Authenticate Sales Rep Identity | **Supported** | **Supported** |
| Store Encrypted OAuth Tokens (AES-256) | **Supported** | **Supported** |
| AI Draft: Connection Notes (≤300 chars) | **Supported** | **Supported** |
| AI Draft: Direct InMail / Messages (≤1900 chars) | **Supported** | **Supported** |
| Mandatory Human Approval & Content Hash | **Supported** | **Supported** |
| Compliant Manual Handoff Workflow | **Supported (Default)** | **Supported** |
| Automated 1:1 REST API Dispatch | **Not Permitted by LinkedIn** | **Supported** (requires Partner Approval) |

---

## 3. Compliant Manual Handoff Workflow

When `LINKEDIN_MESSAGING_API_APPROVED=false` (standard configuration):

1. **AI Generation:** The system drafts a tailored connection note (strictly capped at 300 characters) or conversation starter based on verified business research and the 90-Day Free Product Evaluation.
2. **Human Approval:** An admin or manager reviews and approves the draft in the Approval Queue.
3. **Manual Handoff:**
   - In the **LinkedIn Outreach** view, the approved draft transitions to `ready_for_manual_send`.
   - The salesperson clicks **Open Profile & Copy Note**.
   - The salesperson pastes the message and sends it natively from their authenticated personal LinkedIn account.
4. **Audit & CRM Confirmation:**
   - The salesperson clicks **Confirm Manual Send**.
   - The system transitions the draft to `manually_sent_confirmed`, logs an audit record, and updates the CRM lead status to `contacted`.

---

## 4. Enabling Automated Partner Messaging API

If your organization obtains formal approval from LinkedIn for the Partner Messaging API:

1. Configure in `.env`:
   ```ini
   LINKEDIN_MESSAGING_API_APPROVED=true
   LINKEDIN_PARTNER_MESSAGING_ENDPOINT=https://api.linkedin.com/v2/messages
   ```
2. Once enabled, approved messages can be dispatched directly via the authorized partner endpoint.
