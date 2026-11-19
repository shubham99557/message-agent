# ActTrident External Provider & Infrastructure Technical Research Reference

**Document Version:** 1.0.0  
**Status:** Approved for Production Engineering  
**Scope:** Channel Integrations (Email, WhatsApp, LinkedIn), Discovery Engines (Tavily, SerpAPI, OpenStreetMap), Infrastructure (FastAPI, PostgreSQL, Redis, Celery), and Legal/Regulatory Compliance (India DPDP Act 2023, TRAI TCCCPR 2018).

---

## 1. Executive Summary

ActTrident is an AI-powered B2B sales outreach and intelligence automation platform. To guarantee enterprise reliability, regulatory safety, and zero account suspensions, every integration must adhere strictly to the provider's documented API specifications, authentication standards, rate limits, acceptable use policies, and regional legal frameworks.

This document serves as the single authoritative engineering reference for all external systems ActTrident interacts with.

---

## 2. Channel Providers

### 2.1 Google Workspace & Gmail API

#### Official Documentation
- **Gmail REST API Overview:** [https://developers.google.com/gmail/api/guides](https://developers.google.com/gmail/api/guides)
- **REST Resource: Users.messages.send:** [https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send)
- **Push Notifications (Pub/Sub):** [https://developers.google.com/gmail/api/guides/push](https://developers.google.com/gmail/api/guides/push)
- **Google API Client Libraries (Python):** [https://github.com/googleapis/google-api-python-client](https://github.com/googleapis/google-api-python-client)
- **Google Cloud OAuth Verification:** [https://support.google.com/cloud/answer/9110914](https://support.google.com/cloud/answer/9110914)

#### Capabilities & Endpoints
- `POST /gmail/v1/users/{userId}/messages/send`: Dispatches RFC 2822 base64url-encoded messages.
- `GET /gmail/v1/users/{userId}/messages`: Lists message IDs matching query filters (e.g., `in:inbox`, `after:TIMESTAMP`).
- `GET /gmail/v1/users/{userId}/messages/{id}`: Fetches message metadata and MIME payloads.
- `POST /gmail/v1/users/{userId}/watch`: Registers Cloud Pub/Sub topic for push notifications on incoming replies.
- `POST /gmail/v1/users/{userId}/stop`: Terminates active watch subscriptions.

#### Authentication & Authorization
- **Production Standard:** OAuth 2.0 Authorization Code flow with PKCE (`access_token`, `refresh_token`).
- **Required Scopes:**
  - `https://www.googleapis.com/auth/gmail.send` (Send emails on user's behalf)
  - `https://www.googleapis.com/auth/gmail.readonly` (Detect inbound prospect replies)
  - `https://www.googleapis.com/auth/userinfo.email` (Validate connected mailbox identity)
- **Fallback / Legacy:** SMTP with App Passwords (16 characters, requires 2-Step Verification enabled on Google Workspace account). Restricted by Google's ongoing deprecation of Less Secure Apps.
- **Security Assessment Requirement:** Because `gmail.send` and `gmail.readonly` are restricted scopes, commercial SaaS multi-tenant apps require Google Cloud OAuth Verification and an annual CASA Tier 2 security assessment if connecting external customer accounts.

#### Quotas, Pricing & Rate Limits
- **Cost:** Free API access included with Google Workspace / Gmail accounts.
- **Quota Units:**
  - Daily project quota: 1,000,000,000 quota units/day.
  - Per-user rate limit: 250 quota units per user per second (moving average).
  - Message send cost: 100 quota units per call.
  - Message read/get cost: 5 quota units per call.
- **Sending Limits:**
  - Google Workspace accounts: 2,000 messages/day (pooled across web UI and API).
  - Free `@gmail.com` accounts: 500 messages/day.
  - Recommended warm-up ramp: 20/day week 1, 50/day week 2, 100/day week 3, max 200/day per mailbox for cold B2B outreach to protect SPF/DKIM/DMARC domain reputation.

#### Terms of Service & Compliance Constraints
- **Unsolicited Bulk Email (UBE/Spam):** Google Workspace Acceptable Use Policy prohibits automated bulk messaging that triggers high spam complaint rates (>0.1% recommended, >0.3% triggers Google Postmaster domain penalty).
- **Mandatory Headers:** All transactional and commercial outreach must include valid `From`, `To`, `Subject`, `Message-ID`, RFC 8058 `List-Unsubscribe`, and `List-Unsubscribe-Post` headers.
- **Authentication Alignment:** Outbound sending domains must have fully aligned SPF (`v=spf1 ...`), DKIM (`v=DKIM1 ...`), and DMARC (`v=DMARC1; p=reject` or `p=quarantine`) DNS records.

#### Failure Modes & Resiliency
- `429 Too Many Requests` / `rateLimitExceeded`: Implement exponential backoff with jitter (initial delay 1.0s, multiplier 2.0, max 60s, max 5 retries).
- `401 Unauthorized` / `invalid_grant`: Refresh token expired or revoked. Mark connection as `NEEDS_REAUTH` and alert operator; do not continuously retry.
- `403 dailyLimitExceeded`: Daily mailbox sending quota exhausted. Pause campaign execution for 24 hours.

---

### 2.2 Meta WhatsApp Cloud API

#### Official Documentation
- **WhatsApp Cloud API Reference:** [https://developers.facebook.com/docs/whatsapp/cloud-api](https://developers.facebook.com/docs/whatsapp/cloud-api)
- **Cloud API Messages Endpoint:** [https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages)
- **Webhooks Setup:** [https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks)
- **WhatsApp Business Policy:** [https://www.whatsapp.com/legal/business-policy](https://www.whatsapp.com/legal/business-policy)
- **WhatsApp Business Messaging Rates:** [https://developers.facebook.com/docs/whatsapp/pricing](https://developers.facebook.com/docs/whatsapp/pricing)

#### Capabilities & Endpoints
- `POST /v22.0/{phone-number-id}/messages`: Dispatches template messages, freeform text (within 24-hour service window), interactive buttons, and media.
- `POST /v22.0/{waba-id}/message_templates`: Creates and submits message templates for Meta review.
- Webhooks: Real-time inbound payloads delivering `sent`, `delivered`, `read`, `failed`, and user text/media responses.

#### Authentication & Authorization
- **Authentication:** Meta Graph API Bearer Token.
  - Production requires a **Permanent System User Token** generated in Meta Business Manager with permissions:
    - `whatsapp_business_messaging`
    - `whatsapp_business_management`
- **Webhook Security:** Every incoming HTTP POST must verify `X-Hub-Signature-256` computed as `HMAC-SHA256(payload_body, app_secret)`. Payloads failing signature validation must be rejected with HTTP 403.

#### Quotas, Pricing & Rate Limits
- **Conversation-Based Pricing (Meta 2024/2025/2026 Model):**
  - Marketing Conversations: Variable per market (India: ~₹0.70 to ₹0.85 per conversation; US: ~$0.025 to $0.05).
  - Utility Conversations: India ~₹0.15 to ₹0.30.
  - Service Conversations: Free within 24-hour customer-initiated window.
  - 1,000 free service conversations per WhatsApp Business Account (WABA) per month.
- **Messaging Tiers:**
  - Tier 1: 1,000 unique recipients per rolling 24-hour window.
  - Tier 2: 10,000 unique recipients per 24 hours.
  - Tier 3: 100,000 unique recipients per 24 hours.
  - Tier 4: Unlimited recipients.
- **Throughput:** Standard Cloud API supports 80 messages/second (mps), upgradeable to 250 mps upon request.

#### Terms of Service & Compliance Constraints
- **STRICT PROHIBITION OF COLD / UNSOLICITED OUTREACH:** Meta WhatsApp Business Policy Section 1 requires explicit, documented opt-in prior to initiating any business-initiated message. Opt-in must clearly specify the business name and message types.
- **Pre-Approved Templates:** Only templates pre-approved by Meta can be used outside the 24-hour service window. Templates must include an explicit opt-out mechanism (e.g., "Reply STOP to unsubscribe").
- **Quality Rating:** Customer reports or blocks drop the phone number quality score (GREEN -> YELLOW -> RED). A RED rating throttles messaging tier limits automatically.

#### Failure Modes & Resiliency
- Webhook Ingestion Duplication: Meta delivers webhooks with at-least-once semantics. ActTrident must store `message_id` and idempotently deduplicate status updates.
- Template Rejection: If a campaign uses an unapproved or paused template, Meta returns error code `132000` / `132001`. ActTrident must validate template status before dispatch.
- User Block: Error code `131026` indicates recipient cannot receive messages. System must immediately mark contact as `opted_out` in CRM.

---

### 2.3 LinkedIn Integration Architecture

#### Official Documentation
- **LinkedIn Developer Portal:** [https://developer.linkedin.com/](https://developer.linkedin.com/)
- **LinkedIn Marketing Developer Platform:** [https://learn.microsoft.com/en-us/linkedin/marketing/](https://learn.microsoft.com/en-us/linkedin/marketing/)
- **LinkedIn User Agreement (Section 8.2 Dos and Don'ts):** [https://www.linkedin.com/legal/user-agreement](https://www.linkedin.com/legal/user-agreement)
- **LinkedIn API Terms of Use:** [https://legal.linkedin.com/api-terms-of-use](https://legal.linkedin.com/api-terms-of-use)

#### Capabilities & Permitted vs. Prohibited Actions
- **Permitted by Official APIs:**
  - Organization Social APIs: Post updates to company pages (`w_organization_social`).
  - Community Management APIs: Read comments and engage on corporate posts (`r_organization_social`).
  - Sponsored Messaging / InMail: Available only via official LinkedIn Enterprise Ad Partner APIs.
- **Strictly Prohibited by Section 8.2 of LinkedIn User Agreement:**
  - Automated scraping of member profiles using headless browsers (Puppeteer, Playwright, Selenium).
  - Reverse-engineered private mobile/web APIs (Voyager API).
  - Simulated human clicking or connection request bots.
  - Automated 1-to-1 direct messaging from personal user accounts.
  - Violations result in permanent member account bans and legal cease-and-desist action.

#### ActTrident Compliant Architecture
1. **Manual Workflow Handoff (Primary Mode):**
   - ActTrident AI analyzes prospect company and role, drafts high-converting personalized message copy.
   - Message is marked `ready_for_manual_send` in CRM.
   - Operator reviews copy, clicks one-click deep link to open prospect's profile, and sends manually via their authenticated personal browser session.
   - Operator clicks "Mark as Sent" in ActTrident to advance CRM state.
2. **Authorized Enterprise Partner API (Optional Enterprise Tier):**
   - Dispatches via official LinkedIn InMail Partner endpoint only when customer provides verified enterprise partner credentials (`client_id`, `client_secret`, approved developer app).

---

## 3. Real-Time Discovery Engines

### 3.1 Tavily AI Search API

#### Official Documentation
- **Tavily Documentation:** [https://docs.tavily.com/](https://docs.tavily.com/)
- **API Reference:** [https://docs.tavily.com/api-reference/search](https://docs.tavily.com/api-reference/search)

#### Capabilities & Endpoints
- `POST https://api.tavily.com/search`: Optimized for LLM agents and deep factual research.
  - Parameters: `query`, `search_depth` (`basic` or `advanced`), `include_answer`, `include_raw_content`, `include_domains`, `exclude_domains`, `max_results`.
- Output: Cleaned JSON search results with high-signal content snippets, publication dates, and LLM-synthesized summary answers.

#### Pricing & Rate Limits
- Free Tier: 1,000 search credits per month.
- Pay-as-you-go: ~$0.005 per basic search; ~$0.01 per advanced search.
- Rate Limit: 100 requests per minute on standard plans.

#### Integration Architecture
- Used for company profile enrichment, discovering executive leadership, verifying current operational status, and researching business pain points.

---

### 3.2 SerpAPI (Google Search / Google Maps)

#### Official Documentation
- **SerpAPI Overview:** [https://serpapi.com/](https://serpapi.com/)
- **Google Local / Maps API Reference:** [https://serpapi.com/google-maps-api](https://serpapi.com/google-maps-api)
- **SerpAPI Python SDK:** [https://github.com/serpapi/google-search-results-python](https://github.com/serpapi/google-search-results-python)

#### Capabilities & Endpoints
- `GET https://serpapi.com/search?engine=google_maps`: Structured local business discovery by query, coordinates (`@lat,lng,zoom`), and category.
- Output: Exact business name, verified street address, phone number, website URL, operating hours, review count, rating, and Google place ID.

#### Pricing & Rate Limits
- Free Tier: 100 searches per month.
- Paid Tiers: Developer plan $50/mo (5,000 searches); Production plan $130/mo (15,000 searches).
- Rate Limit: Up to 20 concurrent requests.

#### Terms of Service
- SerpAPI handles proxy rotation, CAPTCHA solving, and parsing infrastructure on their servers. Use of SerpAPI JSON endpoint complies with standard API consumer obligations.

---

### 3.3 OpenStreetMap / Nominatim / Overpass API

#### Official Documentation
- **Nominatim Search API:** [https://nominatim.org/release-docs/latest/api/Search/](https://nominatim.org/release-docs/latest/api/Search/)
- **Nominatim Usage Policy:** [https://operations.osmfoundation.org/policies/nominatim/](https://operations.osmfoundation.org/policies/nominatim/)
- **Overpass API Guide:** [https://wiki.openstreetmap.org/wiki/Overpass_API](https://wiki.openstreetmap.org/wiki/Overpass_API)

#### Capabilities & Endpoints
- `GET https://nominatim.openstreetmap.org/search?q={query}&format=jsonv2&addressdetails=1`: Geocodes city, district, state, and retrieves administrative boundaries.
- `POST https://overpass-api.de/api/interpreter`: Queries OpenStreetMap database for structured Point of Interest (POI) nodes and tags (e.g., `node["amenity"="hospital"]`, `node["office"="it"]`).

#### Usage Policy & Strict Requirements
- **Absolute Rate Limit:** Maximum 1 request per second (1 req/sec). Heavy hammering results in IP-level 403 Forbidden bans.
- **Mandatory User-Agent:** Requests MUST supply a valid, custom `User-Agent` header containing application identification and contact email (e.g., `User-Agent: ActTrident-SalesEngine/2.0 (contact@acttrident.com)`). Generic headers (`python-requests`, `curl`) are rejected.
- **Caching:** Identical queries must be cached locally in Redis for at least 7 days to eliminate redundant upstream calls.
- **Commercial Scale Recommendation:** For high-volume nationwide discovery (>10,000 queries/day), deploy a self-hosted Nominatim/Overpass Docker instance rather than consuming public community servers.

---

## 4. Backend Infrastructure & Core Frameworks

### 4.1 FastAPI

#### Official Documentation
- **FastAPI Documentation:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- **Pydantic v2 Settings & Validation:** [https://docs.pydantic.dev/latest/](https://docs.pydantic.dev/latest/)
- **Starlette ASGI Framework:** [https://www.starlette.io/](https://www.starlette.io/)

#### Capabilities & Patterns
- Asynchronous ASGI request handling with Uvicorn.
- Pydantic v2 schemas for bidirectional request validation, response serialization, and type safety.
- Dependency injection (`Depends`) for database sessions, authentication, and RBAC permission checks.
- OpenAPI 3.1 documentation auto-generation at `/docs` and `/redoc`.

---

### 4.2 PostgreSQL & SQLAlchemy 2.0

#### Official Documentation
- **PostgreSQL 16 Documentation:** [https://www.postgresql.org/docs/16/index.html](https://www.postgresql.org/docs/16/index.html)
- **SQLAlchemy 2.0 Documentation:** [https://docs.sqlalchemy.org/en/20/](https://docs.sqlalchemy.org/en/20/)
- **Alembic Database Migrations:** [https://alembic.sqlalchemy.org/en/latest/](https://alembic.sqlalchemy.org/en/latest/)

#### High-Availability & Concurrency Practices
- Connection Pooling: Engine configured with `pool_size=20`, `max_overflow=10`, `pool_timeout=30`, `pool_pre_ping=True` to eliminate stale connections.
- Transactional Isolation: Explicit commit/rollback blocks inside request lifecycle dependencies.
- Indexing Strategy: B-Tree indexes on `email`, `company_name`, `status`, `campaign_id`, `created_at`. Unique composite indexes on `(campaign_id, prospect_id)` for draft idempotency.

---

### 4.3 Redis & Celery

#### Official Documentation
- **Redis Documentation:** [https://redis.io/docs/latest/](https://redis.io/docs/latest/)
- **Celery Distributed Task Queue:** [https://docs.celeryq.dev/en/stable/](https://docs.celeryq.dev/en/stable/)

#### Operational Requirements
- **Redis 7.x Security:**
  - Redis running in production MUST require strong password authentication (`requirepass`).
  - Protected mode enabled; never exposed directly to public internet.
  - Dedicated Redis database numbers: DB 0 for Celery broker, DB 1 for cache and rate limiting.
- **Celery Task Guarantees:**
  - `task_acks_late=True`: Ensures tasks are only acknowledged after successful execution. If a worker dies mid-task, task is re-queued.
  - `task_reject_on_worker_lost=True`: Immediate retry on worker failure.
  - Rate Limiting: Decorator `rate_limit="20/m"` applied to outbound dispatch tasks to prevent provider threshold violations.

---

## 5. Legal, Regulatory & Compliance Frameworks

### 5.1 India Digital Personal Data Protection (DPDP) Act 2023

#### Official Documentation
- **DPDP Act 2023 Gazette Notification:** [https://www.meity.gov.in/content/digital-personal-data-protection-act-2023](https://www.meity.gov.in/content/digital-personal-data-protection-act-2023)
- **MeitY Regulatory Overview:** [https://www.meity.gov.in/](https://www.meity.gov.in/)

#### Mandatory Technical Controls
1. **Notice and Consent (Section 5 & 6):**
   - Personal data (names, personal email addresses, personal phone numbers) cannot be processed or contacted without lawful purpose and verifiable consent.
   - For B2B outreach, ActTrident must strictly prioritize publicly available business contact information and corporate email domains (`@company.com`), avoiding personal accounts (`@gmail.com`, `@yahoo.com`).
2. **Right to Withdraw Consent / Opt-Out (Section 6(4)):**
   - Every outbound communication MUST include an effortless, single-click opt-out or unsubscribe mechanism.
   - When opt-out is received, the CRM must immediately transition the contact to `opted_out` status and write to the global `suppression_list`.
   - Subsequent messaging to an opted-out contact is strictly blocked by backend database constraints.
3. **Data Principal Rights & Erasure (Section 12):**
   - ActTrident must support complete data erasure upon request ("Right to be Forgotten"). Soft-delete or full purge of personal identifiers from lead records.
4. **Data Security Safeguards (Section 8(5)):**
   - Encryption of credentials, access tokens, and sensitive business records at rest (AES-256) and in transit (TLS 1.3).
   - Penalties for significant security lapses reach up to ₹250 Crore.

---

### 5.2 Telecom Regulatory Authority of India (TRAI) TCCCPR 2018 & Commercial Communications Regulations

#### Official Documentation
- **TRAI Telecom Commercial Communications Customer Preference Regulations (TCCCPR 2018):** [https://www.trai.gov.in/telecom-commercial-communications-customer-preference-regulations-2018](https://www.trai.gov.in/telecom-commercial-communications-customer-preference-regulations-2018)
- **National Do Not Call (NDNC) / DLT Portal Requirements:** [https://www.trai.gov.in/](https://www.trai.gov.in/)

#### Mandatory Technical Controls for WhatsApp & SMS Outreach
1. **Distributed Ledger Technology (DLT) Registration:**
   - Commercial voice and SMS communications in India require enterprise registration on telecom DLT platforms (e.g., Vilpower, Jio DLT, Airtel DLT).
   - Sender IDs (Headers) and message templates must be pre-approved on DLT.
2. **National Customer Preference Register (NCPR / NDNC):**
   - Commercial communications cannot be transmitted to telephone numbers registered on the DND registry without explicit preference registration.
   - Calling or messaging unregistered or DND numbers between 9:00 PM and 9:00 AM IST is strictly prohibited.
3. **Application Enforcement in ActTrident:**
   - WhatsApp outreach validates recipient numbers against the internal DND / suppression table before invoking Meta API.
   - Outbound batch schedules enforce time-of-day guards (09:00 to 21:00 IST).

---

## 6. Synthesis: Architectural Decision Summary

| Component | Selected Approach | Key Constraint / Security Rule |
| :--- | :--- | :--- |
| **Email Outreach** | Gmail API (OAuth 2.0 PKCE) + SMTP Fallback | Strict domain warm-up (<=200/day/mailbox), RFC 8058 unsubscribe header |
| **WhatsApp Outreach** | Meta Cloud API v22.0 via System User Token | Pre-approved templates only; strict opt-in required; HMAC webhook validation |
| **LinkedIn Outreach** | Manual Workflow Handoff (Primary) | No headless browser scraping or automated private API messaging (TOS Section 8.2) |
| **Business Discovery** | Tavily API + SerpAPI Maps + Nominatim | Rate limit Nominatim to <=1 req/sec; use custom User-Agent; cache 7 days |
| **Backend & Queue** | FastAPI + PostgreSQL 16 + Redis 7 + Celery | Late task acknowledgment (`task_acks_late=True`), connection pooling, Redis auth |
| **Regulatory Safety** | DPDP 2023 & TRAI Compliance Engine | Real-time suppression check, instant opt-out processing, business hour guard (09:00-21:00 IST) |

---
*End of Technical Research Reference.*
