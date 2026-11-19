# ActTrident AI Sales Outreach Agent — User Manual

## 1. User Roles & Permissions
| Role | Capabilities |
| :--- | :--- |
| **Sales Rep (`sales_rep`)** | Discover/import/verify companies, run research & qualification, create Email/WhatsApp/LinkedIn drafts, manage own campaigns, log manual LinkedIn sends, manage CRM meetings & 90-day trials. |
| **Manager (`manager`)** | All Sales Rep permissions + approve/reject/dispatch Email, WhatsApp, and LinkedIn drafts, pause/resume/stop campaigns, connect Gmail/LinkedIn OAuth, sync Meta WhatsApp templates, toggle Global Kill Switch, process outbox & background jobs. |
| **Administrator (`admin`)** | All Manager permissions + create/deactivate users, change user roles, store encrypted integration secrets, disconnect OAuth accounts, inspect immutable Security Audit Logs. |

---

## 2. Step-by-Step B2B Sales Workflow (All 14 UI Views)
1. **Dashboard**: Monitor funnel conversion telemetry, active campaigns, replies, and 90-day evaluation trials.
2. **Discover Companies**:
   - View active permitted discovery adapters (`Tavily`, `SerpAPI`, `OpenStreetMap`).
   - Upload verified B2B lead lists via **Batch CSV Import** or scan a public corporate URL via the **SSRF-Protected Website Scanner**.
   - Demo fixtures (`.example.com`) are hidden by default and visibly badged `DEMO FIXTURE` — never send real outreach to demo fixtures.
3. **Lead Database**: Browse registered companies, inspect `verified` vs `unverified` vs `DEMO FIXTURE` badges, add companies manually, or export CSV.
4. **AI Research**: Review the 7-factor heuristic qualification score, verify **Missing / Unverified Information** and **Evidence Confidence**, and click **Mark Record Verified** once human verification confirms corporate evidence (including 5+ managed laptops).
5. **Email Outreach**: Generate personalized outreach drafts across 5 tones targeting ActTrident's 90-day free product evaluation. All drafts enter the Approval Queue.
6. **WhatsApp Outreach**: Check Meta Cloud API live vs simulation status, sync official Meta templates, capture documented opt-in consent, and draft template messages.
7. **LinkedIn Outreach**: Draft compliant Connection Notes (≤300 chars) or Direct Messages (≤1900 chars). After manager approval, use **Prepare Manual Handoff** to copy the approved message, open the LinkedIn profile, send natively inside LinkedIn, and click **Confirm Manual Send** to log it in CRM.
8. **Campaigns**: Create geographic campaigns (Siliguri, Gangtok, Patna, Bhagalpur), attach leads, batch-generate drafts, **Pause / Resume / Stop** campaigns at any time, and dispatch approved messages.
9. **Approval Queue**: Mandatory human review checkpoint. Managers approve, reject (with reason), skip, or edit drafts (editing an approved draft automatically invalidates approval).
10. **Inbox & Replies**: View incoming Email/WhatsApp replies classified into 10 categories (`interested`, `requests_demonstration`, `requests_pricing`, `unsubscribe`, etc.). Opt-out/STOP replies immediately add contacts to the Global Suppression List.
11. **CRM Pipeline**: Track leads through 16 stages, schedule demonstrations, and activate 90-day free evaluation trials.
12. **Analytics**: Inspect genuine conversion metrics and city breakdowns with authentic denominators.
13. **Integrations**: Connect **Gmail OAuth 2.0**, **LinkedIn OAuth 2.0**, **Meta WhatsApp Cloud API**, SMTP fallback, and AI providers (Gemini / OpenAI).
14. **Settings**: Manage users & roles, review the **Global Suppression List** and **Security Audit Trail**, and toggle the **Global Emergency Outbound Kill Switch ("Stop All Outbound Sending")** immediately if an emergency halt is ever required.
