# ActTrident AI Outreach Agent - Business Development User Manual

Welcome to the **ActTrident AI Outreach Agent** platform. This manual guides business development representatives and sales managers through discovering prospective businesses, qualifying leads, managing multi-channel outreach, and tracking 90-day product evaluation trials.

---

## 1. Initial Login & Executive Dashboard

1. Navigate to the web application at `http://localhost:5173`.
2. Sign in with your corporate credentials provisioned by your system administrator (or via `backend/scripts/provision_admin.py` during deployment). Default credentials are intentionally removed from documentation to uphold enterprise security.
3. The **Executive Dashboard** displays:
   - Researched accounts, qualified leads, approved drafts, dispatched emails, inbound replies, and active 90-day evaluations.
   - Target markets overview: **Siliguri**, **Gangtok**, **Patna**, and **Bhagalpur**.
   - B2B conversion pipeline with non-inflated authentic denominators.

---

## 2. Company Lead Discovery (Module A)

1. Select **Discover Companies** from the sidebar.
2. Filter by target city (Siliguri, Gangtok, Patna, Bhagalpur), industry, and minimum verified devices (5+ laptops).
3. Review company profile, verified laptops count, evidence citation, and official source URL.
4. Click **Add Lead** to import the company into your active database.
5. Alternatively, use the **Batch Import via CSV** tool at the top to upload company spreadsheets with automated deduplication and source logging.

---

## 3. Lead Database & Contact Sources (Module A & B)

1. Navigate to **Lead Database**.
2. View and search all imported companies.
3. Every piece of contact information (email, phone, WhatsApp) links to a verified source URL and verification timestamp.
4. Export the current dataset at any time via the **Export CSV** button.

---

## 4. AI Research & 7-Factor Qualification (Module B & C)

1. Navigate to **AI Research**.
2. Select a target account from the dropdown.
3. The system presents:
   - **7-Factor Qualification Score (0-100)**: Evaluates technology alignment, 5+ workforce, managed laptop evidence, browser workflows, customer data handling, ActTrident fit, and accessible channels.
   - **Compliance Note**: Explains the strict separation between employee count and verified laptop count.
   - **Company Research Report**: A concise summary of services, likely technology requirements, recommended outreach angle, and relevant decision-maker role.
4. Click **Re-run 7-Factor Qualification** or click **Draft Outreach Email** to proceed.

---

## 5. AI Personalized Email Outreach (Module D)

1. Navigate to **Email Outreach**.
2. Choose a company and select from 5 tones:
   - **Friendly professional**: Warm, collaborative, value-driven.
   - **Formal**: Traditional executive structure.
   - **Technical**: Emphasizes endpoint posture and browser isolation.
   - **Short introductory**: Crisp overview.
   - **Follow-up**: Polite sequence check-in.
3. Add optional custom notes.
4. Click **Generate AI Email Draft**.
5. Inspect the generated 8-part message presenting the ActTrident proposed 90-day evaluation.
6. Edit the text inline, view Plain Text / HTML, and click **Save Draft**.
7. Drafts automatically queue into the **Approval Queue** in `draft` status.

---

## 6. Official Meta WhatsApp Outreach (Module E)

1. Navigate to **WhatsApp Outreach**.
2. Select target account and approved Meta template (`acttrident_intro_utility_v1` or `acttrident_eval_notice_v1`).
3. **Consent Enforcement**:
   - If documented consent exists (`opted_in`), you can generate a draft for human approval and Meta Cloud API dispatch.
   - If the contact is unconsented, the system will block automated Cloud API sending and provide an official **Click-to-Chat (`https://wa.me/...`)** link for manual conversation.
4. Use **Record Valid Consent** to document verified permissions (form submission, business card handover).

---

## 7. Mandatory Human Approval Queue (Module F)

1. Navigate to **Approval Queue**.
2. Review all pending messages awaiting outbound dispatch.
3. For each message, review recipient, contact source, consent status, and text.
4. Available Actions:
   - **Approve**: Marks draft as approved and ready for sending.
   - **Edit**: Modify subject or body inline before approving.
   - **Reject**: Rejects message with an audit reason.
   - **Skip**: Defers message.
   - **Approve Selected**: Bulk-approves selected drafts.
5. Once approved, click **Send Now** to dispatch via the configured provider.

---

## 8. Campaigns Management (Module G)

1. Navigate to **Campaigns**.
2. Create geographic campaigns (e.g., *Siliguri IT Companies Campaign*, *Sikkim Technology Companies Campaign*).
3. Set conservative daily limits (default 50 emails/day, 20 WhatsApp/day).
4. Click **Batch Generate Drafts** to draft emails for all campaign recipients in `draft` mode.
5. After human review in the Approval Queue, return to Campaigns and click **Send Approved**.

---

## 9. Inbound Inbox & 10-Class Reply Classifier (Module I)

1. Navigate to **Inbox & Replies**.
2. Incoming replies are classified into 10 categories:
   - `interested`, `requests_demonstration`, `requests_pricing`, `wants_more_information`, `wants_a_callback`, `potential_partnership`, `wrong_contact`, `out_of_office`, `not_interested`, `unsubscribe`.
3. The AI suggests appropriate follow-up responses.
4. **Negotiation Rule**: Replies involving demo requests or pricing require explicit human approval before being sent.
5. Any `unsubscribe` or `not_interested` response automatically adds the recipient to the **Global Suppression List** and halts follow-ups.

---

## 10. 16-Stage CRM Sales Pipeline (Module H)

1. Navigate to **CRM Pipeline**.
2. Move leads through the 16 pipeline stages:
   `new` -> `researching` -> `qualified` -> `draft_ready` -> `awaiting_approval` -> `contacted` -> `replied` -> `interested` -> `meeting_scheduled` -> `demo_completed` -> `trial_offered` -> `trial_activated` -> `converted`.
3. Schedule demo meetings via **Demo**.
4. Activate the **90-Day Free Product Evaluation** for prospects with 5+ managed laptops via **+ Activate 90-Day Trial**.
5. Manually trigger opt-outs using the **Ban** icon if requested by a prospect.

---

## 11. Analytics, Integrations & Settings (Modules J & Security)

- **Analytics**: Real conversion funnel with true denominators, regional city comparisons, and campaign performance summaries.
- **Integrations**: Enter Gemini API keys, SMTP credentials, or Meta WhatsApp Business Cloud API access tokens.
- **Settings**: View the immutable security audit trail and review suppressed email addresses and phone numbers.
