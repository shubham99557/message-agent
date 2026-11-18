# ActTrident AI Sales Outreach — Non-Technical Campaign User Guide

Welcome to the **ActTrident AI Sales Outreach & Automation Agent**. This guide walks sales representatives and account managers through launching and managing outbound B2B campaigns without technical or coding experience.

---

## The 10-Step Outreach Workflow

```
[1. Create Campaign] ➔ [2. Discover Leads] ➔ [3. Review Research] ➔ [4. Select Decision Makers] ➔
[5. Generate Outreach] ➔ [6. Human Approval] ➔ [7. Dispatch Messages] ➔ [8. Review Replies] ➔
[9. Automated Follow-Up] ➔ [10. Close in Sales CRM]
```

---

### Step 1: Create a Targeted Campaign
1. In the sidebar, click **Campaigns**.
2. Click **+ New Campaign**.
3. Fill out the targeting parameters:
   - **Campaign Name:** Descriptive name (e.g., `Siliguri IT Managed Device Outreach`).
   - **Target Geography:** Select `Siliguri`, `Gangtok`, `Patna`, or `Bhagalpur`.
   - **Target Industry:** e.g., `Software Development` or `Technology Services`.
   - **Business Type:** e.g., `IT Services & Technology`.
   - **Min Laptops Verified:** Set to `5` or higher (ActTrident device requirement).
   - **Daily Limit:** Conservative limit (e.g., 30–50 emails per day).
   - **Allowed Channels:** Select Email, WhatsApp, and/or LinkedIn.
4. Click **Create Campaign**. Your campaign starts in `Draft` status.

---

### Step 2: Discover Businesses with Device Evidence
1. Navigate to **Discovery** in the sidebar.
2. Select your target city (e.g. `Siliguri`) and click **Search Businesses**.
3. Review the discovered accounts. Each card displays:
   - Verified laptop/device fleet evidence (e.g. `Careers portal lists Dell Latitude laptops`).
   - Source attribution link.
   - Public business email, phone, and website.
4. To import a prospect into your company database, click **Import Lead**.
5. Alternatively, use **Upload CSV** to batch import your team's spreadsheet, or enter a company website URL to perform a live crawl.

---

### Step 3: Review Company Research & Qualification
1. Navigate to **Research** in the sidebar.
2. Select any company from the list to view its complete intelligence dossier:
   - Company overview and business activities.
   - Publicly available technology stack.
   - Evidence of device-management needs.
   - ActTrident 90-Day Evaluation use cases.
   - Explainable 7-factor qualification score (0.0 to 1.0).
3. If device evidence is verified, click **Mark Verified** to record analyst verification.

---

### Step 4: Add Leads to Your Campaign
1. Return to **Campaigns**.
2. On your campaign card, click **Add Leads**.
3. Check the companies you want to enroll in the campaign and click **Add Selected**.

---

### Step 5: Generate AI Outreach Drafts
1. On your campaign card, click **Generate Drafts**.
2. The AI generates personalized outreach tailored to each company's verified device count, industry, and location.
3. Every message introduces the **ActTrident 90-Day Free Product Evaluation**.
4. Generated messages are placed in `Draft` status. **No message is sent automatically.**

---

### Step 6: Review & Approve in Human Approval Queue
1. Navigate to **Approval Queue** in the sidebar.
2. Review each draft message:
   - **Approve:** Approves the draft for dispatch. Records an immutable content hash and approval timestamp.
   - **Edit:** Modify the subject or body. *Note: Editing automatically invalidates any prior approval to prevent unreviewed content from sending.*
   - **Regenerate:** Request AI re-generation with a different tone (Formal, Friendly professional, Technical, Short introductory, Follow-up).
   - **Schedule:** Pick a specific future dispatch timestamp.
   - **Reject / Skip:** Move draft out of the active queue.

---

### Step 7: Dispatch Approved Messages
1. In **Campaigns**, click **Send Approved**.
2. The system dispatches approved messages through connected channels:
   - **Email:** Dispatched via connected Gmail OAuth 2.0 or SMTP relay.
   - **WhatsApp:** Dispatched via Meta Cloud API using approved templates and verified opt-ins.
   - **LinkedIn:** Ready for manual handoff with copy-ready note and direct profile link.
3. Outbox dispatch guarantees exactly-once delivery and respects per-minute rate limits.

---

### Step 8: Manage Inbound Replies in the Inbox
1. Navigate to **Inbox** in the sidebar.
2. Incoming replies are synchronized automatically and classified into 10 categories:
   - `Interested`
   - `Meeting requested`
   - `More information requested`
   - `Not interested`
   - `Unsubscribe`
   - `Out of office`
   - `Bounce`
   - `Complaint`
   - `Other`
   - `Needs human review`
3. Click **Generate Response** to preview an AI-suggested response.
4. Review, edit if desired, and click **Approve Response**.
5. *Important:* Any reply classified as `Unsubscribe` or `Complaint` automatically suppresses future communication with that contact.

---

### Step 9: Follow-Up Sequences
- Follow-ups run automatically during business hours (**09:30–17:30 IST**, Monday–Friday).
- Follow-ups automatically stop if:
  - The prospect replies.
  - The prospect unsubscribes or complains.
  - An email bounces.
  - An operator manually pauses or stops the campaign.

---

### Step 10: Track Results in Sales CRM & Analytics
1. Navigate to **CRM Pipeline** to view accounts across 16 stages:
   - `New Lead` ➔ `Researched` ➔ `Qualified` ➔ `Contacted` ➔ `Replied` ➔ `Meeting Scheduled` ➔ `Evaluation Offered` ➔ `Evaluation Active` ➔ `Converted`.
2. Schedule meetings or activate **ActTrident 90-Day Evaluations**.
3. Click **Export CSV** to download a spreadsheet report for sales management.
4. Open **Analytics** to view campaign response rates, verified conversions, and city-by-city pipeline performance.
