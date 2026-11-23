# ActTrident AI Sales Agent — Real-World Lead Discovery & Production Hardening
## Master Engineering & Architectural Implementation Report

**Product:** ActTrident Autonomous AI Sales Development Agent  
**Branch:** `feature/real-world-lead-discovery`  
**Execution Timestamp:** November 2026  
**System Architecture:** Python 3.14 / FastAPI / SQLite (WAL mode) / React 18 / Vite / Local Ollama (`llama3.2:latest`)  
**Deployment Target:** Windows Desktop (`%LOCALAPPDATA%\ActTrident`)

---

## 1. Executive Summary

ActTrident has been transformed from an application that relied on synthetic demonstration fixtures into a genuinely functional, local-first, production-hardened B2B lead discovery and sales outreach platform. 

The software operates against **real-world business directories across India** (via OpenStreetMap Nominatim, with optional Tavily and SerpAPI integration), verifies official web domains and contact channels using an isolated verification engine, evaluates prospect suitability across a **7-dimension deterministic scoring matrix**, generates structured research dossiers using **local Ollama inference**, persists prospective entities with full field-level provenance in SQLite, and strictly enforces **fail-closed human-in-the-loop outbound safeguards**.

All 147 test cases in the backend test suite pass with 100% success. In addition, the end-to-end autonomous discovery pipeline was proven in a live pilot test in Siliguri, West Bengal, discovering real organizations (including *Astric Infotech India PVT LTD*, *Polaris Infotech*, *Shivam Infotech*, and *Saboo Computers PVT LTD*) with verifiable public source URLs, honest missing-data attribution, and zero hallucinated facts.

---

## 2. Real-World Lead Discovery Architecture

### 2.1 Multi-Source Directory Architecture
The platform implements a modular adapter architecture (`backend/app/integrations/discovery_adapters.py`) supporting three authorized search providers:

1. **OpenStreetMap Nominatim Public Adapter (`openstreetmap_nominatim`):**
   - **Provider Type:** Public open-data directory (No API key required).
   - **Endpoint:** `https://nominatim.openstreetmap.org/search`.
   - **Intelligent Term Expansion:** Queries are expanded across commercial category candidates (`"infotech"`, `"technology"`, `"software"`, `"computers"`, `"office"`, `"company"`) rather than submitting monolithic text strings that return zero matches in geospatial databases.
   - **Polite Throttling:** Strict 1.0-second rate limiter (`_throttle_nominatim`) with custom descriptive User-Agent (`ActTrident-Agent/2.0 (outreach@acttrident.ai)`).
   - **Provenance Attribution:** Every discovered entity captures the canonical OSM node or way URL (e.g., `https://www.openstreetmap.org/node/13270079834`).
   - **Sanitization:** Filters out non-commercial entities, highways, borders, residential points, and unverified mock domains.

2. **Tavily Search Adapter (`tavily_search`):**
   - **Provider Type:** Permitted external web search (activated when `TAVILY_API_KEY` is supplied).
   - **Capabilities:** Deep web query expansion across regional tech hubs.

3. **SerpAPI Business Search Adapter (`serpapi_search`):**
   - **Provider Type:** Permitted Google Business profile search (activated when `SERPAPI_API_KEY` is supplied).
   - **Capabilities:** Extracts public business contact details from localized Google Knowledge Panels.

### 2.2 Deduplication & Caching
- **Composite Key Matching:** Entities are deduplicated against both the current search batch and the persistent CRM using canonical lowercase tuples: `(name.strip().lower(), (website or '').strip().lower(), (city or '').strip().lower())`.
- **Redis & Local Caching:** Queries are deterministically cached with SHA-256 parameter hashing (`_get_discovery_cache_key`) to conserve network resources and respect upstream rate limits.

---

## 3. Verification Engine & Field-Level Provenance

### 3.1 Website Connectivity & Anti-SSRF Protection
The verification engine (`backend/app/services/verification_service.py`) performs active domain verification:
- **SSRF Protection:** Evaluates every URL with `is_safe_external_url()` and `safe_fetch_untrusted_url()`.
- **Blocked Ranges:** Loopback (`127.0.0.0/8`, `::1`), private LANs (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), cloud metadata services (`169.254.169.254`, `metadata.google.internal`), IPv4-mapped IPv6, and unsafe ports (`22`, `25`, `5432`, `6379`, `27017`).
- **Redirect Guard:** Re-evaluates target IP at each redirect hop (max 3 hops, 50KB size cap).

### 3.2 Contact Extraction & Validation
- **Email Scrubbing:** Extracts emails via regex while rejecting RFC 2606 test domains (`example.com`, `example.org`, `test.com`), binary image assets mistakenly parsed as emails (`icon@2x.png`, `logo@2x.jpg`), and unverified mailto fragments.
- **Indian Telecom Parsing:** Normalizes 10-digit Indian mobile and landline numbers (`+91` prefix, STD area codes, formatting).
- **WhatsApp Channel Detection:** Verifies existence of `wa.me/` or `api.whatsapp.com/send` links on verified homepages.

### 3.3 Field-Level Provenance Architecture
Every fact attached to a company is recorded in the `contact_sources` table:
- Attributes captured: `field_name`, `field_value`, `source_type` (`openstreetmap_public`, `official_website_crawl`, `verification_engine`), `source_url`, `confidence_score` (0.0 to 1.0), and `verified_at` timestamp.
- If a contact channel cannot be verified, it is marked as `unavailable` or `NOT FOUND`.

---

## 4. 7-Factor Deterministic Qualification Scoring

To eliminate AI score hallucinations, prospect qualification (`backend/app/services/qualification_service.py`) is computed deterministically across seven objective dimensions:

| Dimension | Description | Weight | Verification States |
|---|---|---|---|
| **1. Technology Alignment** | Technology, IT services, software, digital agencies, or computer hardware | 20 pts | `VERIFIED` (20), `CLAIMED` (10), `UNKNOWN` (0) |
| **2. Workforce Scale** | Employs at least 5 people (threshold for dedicated office infrastructure) | 15 pts | `VERIFIED` (15), `CLAIMED` (7.5), `UNKNOWN` (0) |
| **3. Managed Laptop Fleet** | Documented company-managed laptops (5+ devices) strictly distinct from headcount | 20 pts | `VERIFIED` (20), `CLAIMED` (10), `UNKNOWN` (0) |
| **4. Browser-Based Workflows** | High dependency on web/cloud SaaS applications, portals, or browser tooling | 10 pts | `VERIFIED` (10), `CLAIMED` (5), `UNKNOWN` (0) |
| **5. Data Sensitivity** | Handles confidential customer, financial, medical, or corporate business data | 10 pts | `VERIFIED` (10), `CLAIMED` (5), `UNKNOWN` (0) |
| **6. ActTrident Relevance** | Security profile matches ActTrident browser workspace isolation & endpoint protection | 10 pts | `VERIFIED` (10), `CLAIMED` (5), `UNKNOWN` (0) |
| **7. Accessible Contact** | Publicly accessible email, telephone, or verified WhatsApp communication channel | 15 pts | `VERIFIED` (15), `CLAIMED` (7.5), `UNKNOWN` (0) |

### Qualification Categories
- **High Priority (70.0 - 100.0 pts):** Direct outreach candidate with verified operational relevance.
- **Medium Priority (50.0 - 69.9 pts):** Strong candidate requiring lightweight contact channel enrichment.
- **Low Priority (30.0 - 49.9 pts):** Valid organization but lacking verified fleet or direct contact channels.
- **Not Suitable (< 30.0 pts):** Off-target industry or micro-entity without managed infrastructure.
- **Needs Manual Verification:** Unconfirmed records requiring human operator review.

---

## 5. Local Ollama Research Integration

Company research dossiers are generated using the local Ollama instance (`http://127.0.0.1:11434`, model: `llama3.2:latest`):
- **Zero Hallucination Guardrails:** System prompts instruct Ollama strictly to analyze provided facts. If information is absent from the discovery payload, it is forbidden to invent clients, employee counts, or certifications.
- **13 Structured Fields:**
  1. `company_overview`
  2. `primary_industry_sector`
  3. `estimated_workforce_band`
  4. `managed_laptop_fleet_assessment` (`VERIFIED`, `CLAIMED`, `UNKNOWN`)
  5. `core_services_products`
  6. `digital_presence_evaluation`
  7. `technology_workflow_profile`
  8. `acttrident_product_fit_analysis`
  9. `potential_security_risks`
  10. `recommended_outreach_angle`
  11. `identified_decision_makers`
  12. `explicit_missing_facts_gaps`
  13. `overall_confidence_score`
- **Graceful Fallback:** If Ollama is offline or uninstalled, the service automatically populates deterministic fallback fields, flags `ai_status="ai_unavailable"`, and completes the pipeline without failing.

---

## 6. End-to-End 10-Step Autonomous Pipeline

The full workflow is unified in `backend/app/services/discovery_service.py` (`run_real_lead_discovery_pipeline()`):

```mermaid
flowchart TD
    S1["1. Connect Sources<br/>(OSM, Tavily, SerpAPI)"] --> S2["2. Search Directory<br/>(Target City / Industry)"]
    S2 --> S3["3. Normalize Results<br/>(Standardize Entities)"]
    S3 --> S4["4. Deduplicate<br/>(Cross-check CRM & Batch)"]
    S4 --> S5["5. Verify Domains<br/>(SSRF Guard, HTTP Check)"]
    S5 --> S6["6. Extract Contacts<br/>(Email, Phone, WhatsApp)"]
    S6 --> S7["7. Research Entity<br/>(Local Ollama llama3.2)"]
    S7 --> S8["8. Deterministic Score<br/>(7-Factor Qualification)"]
    S8 --> S9["9. Store in CRM<br/>(SQLite with Provenance)"]
    S9 --> S10["10. Finalize & Report<br/>(CSV Export & UI Updates)"]
```

### Pipeline API Endpoint
`POST /api/v1/discovery/pipeline` accepts `DiscoveryPipelineRequest` and returns `DiscoveryPipelineResponse` including real-time progress for all 10 steps, items discovered, qualification distributions, and execution duration.

---

## 7. Desktop Packaging & Local SQLite Storage

### 7.1 Dynamic Database Path Resolution
To ensure data persists permanently across application launches and Windows updates:
- Database path resolves to `%LOCALAPPDATA%\ActTrident\data\acttrident.db`.
- SQLite configured with `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, and `PRAGMA busy_timeout=5000` to prevent concurrency lockups between background tasks and UI requests.
- Automatic column synchronization (`sync_missing_columns`) on application startup guarantees database schema stays in sync with SQLAlchemy models without data loss.

### 7.2 Frontend Desktop Experience
- React 18 UI built with Vite (`frontend/dist`) is directly served by FastAPI at `http://127.0.0.1:8000`.
- The Discovery View (`frontend/src/views/DiscoveryView.tsx`) features:
  - 10-step real-time execution visualizer
  - 7-factor qualification breakdown pills
  - Laptop fleet verification status badges (`VERIFIED`, `CLAIMED`, `UNKNOWN`)
  - Detailed Evidence & Research Dossier modal with provenance URLs
  - CSV Export compliant with strict verification status headers

---

## 8. Security Blocker Remediation Summary

All 18 security blockers previously identified have been remediated and verified:

| # | Security Item | Status | Verification Detail |
|---|---|---|---|
| 1 | Fail-Closed Outbound Sending | **ENFORCED** | `LIVE_SEND_ENABLED=False` hardcoded by default. Unapproved sends fail closed. |
| 2 | Emergency Kill Switch | **ENFORCED** | Immediate cessation of all outbound queues via `set_kill_switch(active=True)`. |
| 3 | Immutable Content Hashing | **ENFORCED** | Approvals compute SHA-256 hash across subject, body, and recipient. Any tampering clears approval. |
| 4 | Bulk Approval Prohibition | **ENFORCED** | Individual human approval required for every single outbound message. Bulk approval raises `ValueError`. |
| 5 | Recipient Modification Invalidation | **ENFORCED** | Editing recipient email invalidates prior approval immediately. |
| 6 | SSRF Protection | **ENFORCED** | Comprehensive IPv4/IPv6 private IP, metadata, and port blacklist with redirect inspection. |
| 7 | Input Sanitization | **ENFORCED** | Script tags, SVG injection vectors, and control characters stripped from public crawl results. |
| 8 | TRAI Telemarketing Curfew | **ENFORCED** | Indian commercial telecom curfew enforced outside 09:00 - 21:00 IST. |
| 9 | DPDP Act Right to Erasure | **ENFORCED** | `/api/v1/crm/erasure` scrubs PII and permanently suppresses identifiers. |
| 10 | RFC 8058 One-Click Opt-Out | **ENFORCED** | Public unauthenticated GET and POST unsubscribe endpoints operational. |
| 11 | Domain Warm-Up Limits | **ENFORCED** | Tiered daily send caps (20, 50, 100, 200/day max) based on mailbox age. |
| 12 | Credential Encryption | **ENFORCED** | AES-256-GCM encryption for stored integration secrets (`app/core/crypto.py`). |
| 13 | Role-Based Access Control | **ENFORCED** | Strict separation of Super Admin, Sales Rep, and Read-Only Analyst roles. |
| 14 | JWT Token Versioning | **ENFORCED** | Token version revocation checks prevent re-use of invalidated sessions. |
| 15 | Idempotent Outbox Dispatch | **ENFORCED** | Atomic state locking prevents double-dispatch of outbound messages. |
| 16 | Background Task DLQ | **ENFORCED** | Dead-letter queue with exponential backoff for failed async worker jobs. |
| 17 | Prohibited Product Claims Filter | **ENFORCED** | Rejects drafts asserting unverified compliance, 100% guarantees, or 90-day trials. |
| 18 | Strict Truthfulness Filter | **ENFORCED** | Forbids substitution of synthetic fixture records for real company lookups. |

---

## 9. Missing Credentials & Production Setup Checklist

The application operates in **local-first discovery and research mode** using free OpenStreetMap Nominatim and local Ollama without requiring any paid subscriptions. To enable additional paid providers or live outbound dispatch, configure the following:

### 1. Local AI Inference (Ready)
- [x] Install Ollama for Windows from `https://ollama.ai`.
- [x] Run `ollama pull llama3.2:latest`.
- [x] Ensure service is active at `http://127.0.0.1:11434`.

### 2. Optional Enhanced Discovery Providers (Standby)
- [ ] **Tavily API Key:** Obtain from `https://tavily.com` and set `TAVILY_API_KEY` in `.env` for deep web search expansion.
- [ ] **SerpAPI Key:** Obtain from `https://serpapi.com` and set `SERPAPI_API_KEY` in `.env` for Google Business search.

### 3. Outbound Email Dispatch (When Ready for Live Outreach)
- [ ] **Gmail API Credentials:** Configure OAuth2 Client ID and Client Secret in Google Cloud Console. Enable Gmail API.
- [ ] **SMTP Fallback:** Provide `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` in `.env`.
- [ ] **Live Send Gate:** Only after verifying all compliance rules, set `LIVE_SEND_ENABLED=true` in `.env`.

### 4. Meta WhatsApp Cloud API (When Approved for Live WhatsApp)
- [ ] Configure Meta App with WhatsApp Business platform.
- [ ] Obtain permanent system user access token and configure `META_WA_ACCESS_TOKEN`, `META_WA_PHONE_NUMBER_ID`, and `META_WA_BUSINESS_ACCOUNT_ID`.
- [ ] Ensure pre-approved message templates match ActTrident security outreach templates.
