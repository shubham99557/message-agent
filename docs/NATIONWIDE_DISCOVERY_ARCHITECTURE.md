# ActTrident Nationwide Business Discovery Architecture

## 1. Executive Summary

The ActTrident Business Discovery Engine is an enterprise-grade prospecting subsystem designed to discover, extract, deduplicate, and qualify technology-enabled companies across India. Unlike legacy implementations restricted to four regional cities, the modern engine provides comprehensive nationwide discovery coverage spanning all 28 States and 8 Union Territories, standard geopolitical zones, and Tier 1, 2, and 3 technology corridors.

---

## 2. Architectural Blueprint

```
+-----------------------------------------------------------------------------------+
|                        React / TypeScript Frontend UI                             |
|  - Scope Selector (City / State / All India)                                      |
|  - Debounced Autocomplete Input (350ms with AbortController cancellation)         |
|  - 12 Canonical Business Categories + Custom Keyword Filter                       |
|  - Preserved Target Presets (Siliguri, Gangtok, Patna, Bhagalpur, Tier 1 Metros)  |
|  - Modular Provider Status Pills, Pagination Controls, and Sort Controls          |
+-----------------------------------------------------------------------------------+
                                        |  HTTP REST API
                                        v
+-----------------------------------------------------------------------------------+
|                     FastAPI Discovery Router & Services                           |
|  - GET  /api/v1/discovery/locations/states                                        |
|  - GET  /api/v1/discovery/locations/regions                                       |
|  - GET  /api/v1/discovery/locations/presets                                       |
|  - GET  /api/v1/discovery/locations/suggest (Debounced Autocomplete)              |
|  - POST /api/v1/discovery/search-paginated (Nationwide Multi-Region Engine)       |
|  - POST /api/v1/discovery/crawl-website (SSRF-Safe Crawler)                       |
|  - POST /api/v1/discovery/upload-csv (Batch Import with Line-Level Attribution)   |
+-----------------------------------------------------------------------------------+
                                        |
               +------------------------+------------------------+
               |                                                 |
               v                                                 v
+-----------------------------+               +-------------------------------------+
|  Canonical Location Engine  |               |     Modular Provider Registry       |
|  - 28 States & 8 UTs        |               |  - OpenStreetMap Nominatim Adapter  |
|  - 6 Geopolitical Regions   |               |  - Tavily Search Adapter            |
|  - Tier 1/2/3 Metros & Hubs |               |  - SerpAPI Google Search Adapter    |
|  - Balanced Search Batches  |               |  - CSV Parser with Line Provenance  |
+-----------------------------+               +-------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                  Deduplication, Evidence & SSRF Security Engine                   |
|  - Deduplication by (Canonical Name, Normalized Website, Normalized City)         |
|  - Strict Non-Fabrication: Device fleet count marked 'Unknown — Pending Audit'    |
|  - SSRF Guard: IPv4/IPv6 private IP, loopback, link-local, cloud metadata blocked |
|  - Redirect Hops Re-validation & Memory-capped HTML Streaming                     |
|  - Quarantine: Demo fixtures strictly isolated with is_demo=True in non-prod only |
+-----------------------------------------------------------------------------------+
```

---

## 3. Location Directory & Scope Semantics

### 3.1 Search Scopes
1. **`city` (Specific Hub):** Queries target city (e.g. `Siliguri`, `Bengaluru`, `Patna`) combined with state and industry filters.
2. **`state` (Statewide Search):** Queries business clusters across the selected State or Union Territory without collapsing into a single city.
3. **`country` (All India Nationwide):**
   - **Never converts `All` into `Siliguri`** or any hardcoded default.
   - Splits nationwide discovery into balanced geographic search batches across major economic corridors:
     - *Batch 1:* Major Metros (Bengaluru, Hyderabad, Pune, Mumbai, Delhi NCR, Chennai, Kolkata).
     - *Batch 2:* Regional Commercial Hubs (Siliguri, Gangtok, Patna, Bhagalpur, Indore, Bhubaneswar, Kochi, Jaipur).
   - Deduplicates matches and aggregates results with transparent coverage reporting.

### 3.2 Canonical State & Regional Coverage
- **Northern Region:** Delhi, Haryana, Punjab, Rajasthan, Uttar Pradesh, Himachal Pradesh, Uttarakhand, Jammu & Kashmir, Ladakh, Chandigarh.
- **Southern Region:** Karnataka, Telangana, Tamil Nadu, Andhra Pradesh, Kerala, Puducherry, Lakshadweep.
- **Eastern Region:** West Bengal, Bihar, Jharkhand, Odisha, Andaman & Nicobar Islands.
- **Western Region:** Maharashtra, Gujarat, Goa, Dadra & Nagar Haveli and Daman & Diu.
- **Central Region:** Madhya Pradesh, Chhattisgarh.
- **North-Eastern Region:** Sikkim, Assam, Meghalaya, Manipur, Mizoram, Nagaland, Tripura, Arunachal Pradesh.

### 3.3 Preserved Regional Presets
The system maintains dedicated saved filter presets for one-click access:
- **ActTrident Core Focus:** Siliguri, Gangtok, Patna, Bhagalpur.
- **Tier 1 Tech Metros:** Bengaluru, Hyderabad, Pune, Mumbai, Delhi, Gurugram, Noida, Chennai.
- **Eastern India Commercial Hubs:** Kolkata, Patna, Bhubaneswar, Ranchi, Siliguri, Bhagalpur.
- **North-Eastern Economic Corridor:** Gangtok, Guwahati, Shillong, Siliguri, Agartala.

---

## 4. Business Categories & Targeting

The engine supports 12 standardized enterprise and technology categories:
1. Software Development & SaaS
2. IT Services & Cloud Hosting
3. Digital Marketing & Web Design
4. BPO, KPO & Call Centres
5. IT Consulting & System Integration
6. Educational Institutions & Universities
7. Computer Training & Skill Development Centers
8. Hospitals & Healthcare Organisations
9. Financial Services, FinTech & Banking
10. Manufacturing & Industrial Enterprises
11. Corporate & Regional Enterprise Offices
12. E-Commerce & Retail Technology
13. *Custom Category / Free-form Keywords*

---

## 5. Security & Truthfulness Safeguards

1. **Managed Laptop Fleet Verification Guard:**
   - ActTrident targets companies managing at least 5 company-owned laptops.
   - External discovery snippets never fabricate device counts; newly discovered records are tagged `laptop_count_verified=None` with `has_verified_5_plus_laptops=False`.
   - Companies without verified device evidence are blocked from entering active live campaigns.
2. **SSRF Hardening on Website Crawler:**
   - Blocks private IP spaces (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `::1`, `fc00::/7`).
   - Blocks cloud metadata endpoints (`169.254.169.254`, `fd00:ec2::254`, `metadata.google.internal`).
   - Resolves both IPv4 and IPv6 via dual-stack `getaddrinfo`.
   - Manually inspects every 3xx redirect hop; relative URLs are resolved and verified against the SSRF filter before fetching.
   - Caps responses at 50KB to eliminate memory exhaustion vulnerabilities.
3. **Quarantine of Demo Fixtures:**
   - Demo fixtures (`.example.com`, `.example.org`) are never returned in `ENVIRONMENT=production`.
   - In non-production, they are strictly tagged `is_demo=True` and `verification_status="demo_fixture"`.
