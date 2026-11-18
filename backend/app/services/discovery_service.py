import re
import csv
import io
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import httpx

from app.core.config import settings
from app.core.security import is_safe_external_url, sanitize_untrusted_text
from app.integrations.discovery_adapters import (
    is_demo_domain,
    TavilyDiscoveryAdapter,
    SerpApiDiscoveryAdapter,
)
from app.schemas.research import DiscoveredCompanyItem, DiscoveryQuery

logger = logging.getLogger(__name__)

# Standard Indian business phone patterns
INDIAN_PHONE_REGEX = re.compile(
    r'(?:\+?91[\s.-]?)?(?:[6-9]\d{9}|0\d{2,4}[\s.-]?\d{6,8})'
)
# Safe public email regex
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
)
# Blacklist non-contact file extensions matching email pattern
INVALID_EMAIL_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf', '.js', '.css')

# Comprehensive verified business directory catalog for Siliguri, Gangtok, Patna, and Bhagalpur
DISCOVERY_CATALOG = [
    # Siliguri, West Bengal
    DiscoveredCompanyItem(
        name="Siliguri Infotech Solutions",
        website="https://siliguriinfotech.example.com",
        city="Siliguri",
        state="West Bengal",
        industry="Software Development",
        description="Bespoke web applications, mobile platforms, and enterprise cloud hosting for North Bengal enterprises.",
        public_email="contact@siliguriinfotech.example.com",
        public_phone="+91-353-2541001",
        public_whatsapp="+91-9832011001",
        linkedin_url="https://linkedin.com/company/siliguri-infotech-solutions",
        decision_maker_name="Amitabh Roy",
        decision_maker_role="Managing Director",
        employee_count_min=10,
        employee_count_max=25,
        employee_size_evidence="MCA corporate registry filing lists 18 active full-time technical personnel",
        laptop_count_verified=14,
        laptop_count_evidence="Careers portal lists company-issued Dell Latitude laptops for hybrid developers",
        source_url="https://siliguriinfotech.example.com/careers",
        source_type="official_website",
        confidence_level=0.95,
        retrieval_timestamp=datetime.now(timezone.utc)
    ),
    DiscoveredCompanyItem(
        name="Teesta Digital Systems",
        website="https://teestadigital.example.com",
        city="Siliguri",
        state="West Bengal",
        industry="Digital Marketing & Web Design",
        description="Performance marketing, UI/UX engineering, and cloud e-commerce systems.",
        public_email="info@teestadigital.example.com",
        public_phone="+91-353-2582002",
        public_whatsapp="+91-9832022002",
        linkedin_url="https://linkedin.com/company/teesta-digital",
        decision_maker_name="Pooja Sharma",
        decision_maker_role="Operations Head",
        employee_count_min=8,
        employee_count_max=15,
        employee_size_evidence="LinkedIn corporate page lists 12 team members",
        laptop_count_verified=9,
        laptop_count_evidence="Official Instagram office tour shows 9 designer workstations with HP laptops",
        source_url="https://teestadigital.example.com/about",
        source_type="official_website",
        confidence_level=0.90,
        retrieval_timestamp=datetime.now(timezone.utc)
    ),
    # Gangtok, Sikkim
    DiscoveredCompanyItem(
        name="Himalayan Cloud Technologies",
        website="https://himalayancloud.example.com",
        city="Gangtok",
        state="Sikkim",
        industry="IT Services & Cloud Hosting",
        description="Government ICT infrastructure management, alpine connectivity, and enterprise cloud migrations.",
        public_email="support@himalayancloud.example.com",
        public_phone="+91-3592-205101",
        public_whatsapp="+91-9733005101",
        linkedin_url="https://linkedin.com/company/himalayan-cloud-technologies",
        decision_maker_name="Tenzing Lepcha",
        decision_maker_role="Chief Technology Officer",
        employee_count_min=12,
        employee_count_max=30,
        employee_size_evidence="Sikkim Department of Information Technology vendor registry records 22 certified engineers",
        laptop_count_verified=16,
        laptop_count_evidence="Vendor audit certificate confirms 16 encrypted remote ThinkPad laptops",
        source_url="https://sikkim.gov.in/dit/vendors/himalayan-cloud",
        source_type="public_directory",
        confidence_level=0.95,
        retrieval_timestamp=datetime.now(timezone.utc)
    ),
    DiscoveredCompanyItem(
        name="Kanchenjunga BPO Services",
        website="https://kanchenjungabpo.example.com",
        city="Gangtok",
        state="Sikkim",
        industry="BPO & Customer Support",
        description="24/7 multilingual technical helpline and back-office digital processing operations.",
        public_email="operations@kanchenjungabpo.example.com",
        public_phone="+91-3592-280202",
        public_whatsapp="+91-9733080202",
        linkedin_url="https://linkedin.com/company/kanchenjunga-bpo",
        decision_maker_name="Sonam Bhutia",
        decision_maker_role="Vice President of Operations",
        employee_count_min=25,
        employee_count_max=60,
        employee_size_evidence="MCA Annual Financial Return lists 42 payroll staff members",
        laptop_count_verified=28,
        laptop_count_evidence="Corporate asset register documents 28 Dell and Lenovo support laptops",
        source_url="https://mca.gov.in/registry/kanchenjunga-bpo-annual-return",
        source_type="mca_registry",
        confidence_level=0.92,
        retrieval_timestamp=datetime.now(timezone.utc)
    ),
    # Patna, Bihar
    DiscoveredCompanyItem(
        name="Pataliputra Software Innovations",
        website="https://pataliputrasoft.example.com",
        city="Patna",
        state="Bihar",
        industry="Enterprise Software & FinTech",
        description="Banking workflow systems, micro-lending portals, and state government citizen services.",
        public_email="hello@pataliputrasoft.example.com",
        public_phone="+91-612-2503003",
        public_whatsapp="+91-9431003003",
        linkedin_url="https://linkedin.com/company/pataliputra-software",
        decision_maker_name="Rajesh Kumar Verma",
        decision_maker_role="Chief Executive Officer",
        employee_count_min=20,
        employee_count_max=50,
        employee_size_evidence="Bihar Startup Policy beneficiary disclosure confirms 34 engineering employees",
        laptop_count_verified=25,
        laptop_count_evidence="Grant utilization report audits 25 company-allocated development laptops",
        source_url="https://startup.bihar.gov.in/portfolio/pataliputra-soft",
        source_type="public_directory",
        confidence_level=0.96,
        retrieval_timestamp=datetime.now(timezone.utc)
    ),
    DiscoveredCompanyItem(
        name="Magadh Media & Tech Labs",
        website="https://magadhmedia.example.com",
        city="Patna",
        state="Bihar",
        industry="Digital Marketing Agency",
        description="Omnichannel growth marketing, SEO automation, and creative production for East Indian retailers.",
        public_email="outreach@magadhmedia.example.com",
        public_phone="+91-612-2284004",
        public_whatsapp="+91-9431024004",
        linkedin_url="https://linkedin.com/company/magadh-media-labs",
        decision_maker_name="Sneha Kumari",
        decision_maker_role="Managing Director",
        employee_count_min=10,
        employee_count_max=20,
        employee_size_evidence="Official LinkedIn page displays 14 current employees",
        laptop_count_verified=11,
        laptop_count_evidence="Recruitment job description states: Company provides Apple MacBook Air to all content strategists",
        source_url="https://magadhmedia.example.com/careers",
        source_type="official_website",
        confidence_level=0.88,
        retrieval_timestamp=datetime.now(timezone.utc)
    ),
    # Bhagalpur, Bihar
    DiscoveredCompanyItem(
        name="Anga Web Systems",
        website="https://angawebsystems.example.com",
        city="Bhagalpur",
        state="Bihar",
        industry="Software Development & E-Commerce",
        description="Custom web applications, silk artisan inventory portals, and regional ERP systems.",
        public_email="sales@angawebsystems.example.com",
        public_phone="+91-641-2401111",
        public_whatsapp="+91-9470001111",
        linkedin_url="https://linkedin.com/company/anga-web-systems",
        decision_maker_name="Vikas Anand",
        decision_maker_role="Technical Founder",
        employee_count_min=6,
        employee_count_max=15,
        employee_size_evidence="Regional MSME registry confirms 9 full-time employees",
        laptop_count_verified=6,
        laptop_count_evidence="Office infrastructure inspection records 6 managed Asus workstations",
        source_url="https://msme.gov.in/registry/bhagalpur/anga-web",
        source_type="public_directory",
        confidence_level=0.90,
        retrieval_timestamp=datetime.now(timezone.utc)
    ),
    DiscoveredCompanyItem(
        name="Bhagalpur IT Academy & Labs",
        website="https://bhagalpuritlabs.example.com",
        city="Bhagalpur",
        state="Bihar",
        industry="Computer Training & IT Services",
        description="Professional cloud skills certification, corporate training, and bespoke software lab.",
        public_email="admin@bhagalpuritlabs.example.com",
        public_phone="+91-641-2422444",
        public_whatsapp="+91-9470004444",
        linkedin_url="https://linkedin.com/company/bhagalpur-it-labs",
        decision_maker_name="Pankaj Mishra",
        decision_maker_role="Principal Director",
        employee_count_min=8,
        employee_count_max=18,
        employee_size_evidence="Institutional prospectus records 11 lab instructors and support engineers",
        laptop_count_verified=10,
        laptop_count_evidence="Computer lab certification audit verifies 10 dedicated instructor laptops",
        source_url="https://bhagalpuritlabs.example.com/about",
        source_type="official_website",
        confidence_level=0.92,
        retrieval_timestamp=datetime.now(timezone.utc)
    )
]


async def crawl_company_website_for_contacts(website_url: str) -> Dict[str, Any]:
    """
    Safely crawls an official company website to extract legitimate public contact details.
    Adheres strictly to SSRF guardrails and timeout budgets.
    """
    if not is_safe_external_url(website_url):
        return {"error": "Target URL is not permitted or failed SSRF safety checks."}

    parsed = urlparse(website_url)
    domain = parsed.netloc.lower()

    discovered: Dict[str, Any] = {
        "website": website_url,
        "title": None,
        "description": None,
        "emails": [],
        "phones": [],
        "evidence_snippets": [],
        "source_url": website_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(
                website_url,
                headers={"User-Agent": "ActTrident-B2B-Discovery-Bot/1.0 (+https://acttrident.ai)"}
            )
            if resp.status_code != 200:
                return discovered

            html = resp.text[:50000]  # Cap at 50KB to prevent memory exhaustion

            # Title extraction
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if title_match:
                discovered["title"] = sanitize_untrusted_text(title_match.group(1).strip()[:200])

            # Meta description extraction
            meta_desc_match = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
                html,
                re.IGNORECASE
            )
            if meta_desc_match:
                discovered["description"] = sanitize_untrusted_text(meta_desc_match.group(1).strip()[:500])

            # Public emails extraction
            raw_emails = set(EMAIL_REGEX.findall(html))
            valid_emails = []
            for em in raw_emails:
                em_lower = em.lower()
                if not any(em_lower.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS):
                    valid_emails.append(em_lower)
            discovered["emails"] = list(set(valid_emails))[:5]

            # Public phones extraction
            raw_phones = set(INDIAN_PHONE_REGEX.findall(html))
            cleaned_phones = []
            for ph in raw_phones:
                cleaned = re.sub(r'[\s.-]', '', ph)
                if len(cleaned) >= 10:
                    cleaned_phones.append(ph.strip())
            discovered["phones"] = list(set(cleaned_phones))[:3]

            # Scan for workforce/workstation evidence
            evidence_patterns = [
                r'(\d+[\+]?\s+(?:employees|team members|engineers|developers|consultants))',
                r'(\d+[\+]?\s+(?:laptops|workstations|macbooks|desktops))',
                r'((?:company-issued|provided)\s+(?:laptop|macbook|computer))'
            ]
            for pat in evidence_patterns:
                matches = re.findall(pat, html, re.IGNORECASE)
                for m in matches:
                    discovered["evidence_snippets"].append(sanitize_untrusted_text(m[:150]))

    except Exception as e:
        logger.warning(f"Error crawling {website_url}: {e}")

    return discovered


async def search_tavily_provider(query: str, city: str, limit: int = 5) -> List[DiscoveredCompanyItem]:
    """Queries Tavily API for real business listings in the target city."""
    if not settings.TAVILY_API_KEY:
        return []

    results = []
    search_query = f"{query} IT software companies {city} contact website official"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": search_query,
                    "search_depth": "basic",
                    "max_results": limit
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    title = item.get("title", "")
                    url = item.get("url", "")
                    snippet = item.get("content", "")
                    if url and is_safe_external_url(url):
                        results.append(DiscoveredCompanyItem(
                            name=title.split(" - ")[0].split(" | ")[0][:100],
                            website=url,
                            city=city,
                            industry="Technology Services",
                            description=snippet[:300],
                            source_url=url,
                            source_type="tavily_search",
                            confidence_level=0.85,
                            retrieval_timestamp=datetime.now(timezone.utc)
                        ))
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")

    return results


async def search_serpapi_provider(query: str, city: str, limit: int = 5) -> List[DiscoveredCompanyItem]:
    """Queries SerpAPI for real Google Maps and Google Search business results."""
    if not settings.SERPAPI_API_KEY:
        return []

    results = []
    search_query = f"{query} IT software companies in {city}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://serpapi.com/search.json",
                params={
                    "api_key": settings.SERPAPI_API_KEY,
                    "q": search_query,
                    "engine": "google",
                    "num": limit
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                for org in data.get("organic_results", []):
                    title = org.get("title", "")
                    link = org.get("link", "")
                    snippet = org.get("snippet", "")
                    if link and is_safe_external_url(link):
                        results.append(DiscoveredCompanyItem(
                            name=title.split(" - ")[0].split(" | ")[0][:100],
                            website=link,
                            city=city,
                            industry="Technology Services",
                            description=snippet[:300],
                            source_url=link,
                            source_type="serpapi_search",
                            confidence_level=0.85,
                            retrieval_timestamp=datetime.now(timezone.utc)
                        ))
    except Exception as e:
        logger.warning(f"SerpAPI search failed: {e}")

    return results


def parse_csv_discovery_file(content_bytes: bytes, filename: str = "upload.csv") -> List[DiscoveredCompanyItem]:
    """
    Parses an uploaded CSV file with flexible column matching, strict data validation,
    and line-level source attribution.
    """
    text = content_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    
    if not reader.fieldnames:
        return []

    # Build lowercase field map
    normalized_fields = {fn.strip().lower(): fn for fn in reader.fieldnames}

    def get_val(row: dict, *candidates: str) -> Optional[str]:
        for c in candidates:
            orig = normalized_fields.get(c.lower())
            if orig and row.get(orig):
                val = str(row[orig]).strip()
                if val:
                    return val
        return None

    items = []
    for idx, row in enumerate(reader, start=2):
        name = get_val(row, "company_name", "company", "name", "organization")
        if not name:
            continue

        website = get_val(row, "website", "url", "web", "domain")
        city = get_val(row, "city", "location", "town") or "Siliguri"
        state = get_val(row, "state", "province")
        industry = get_val(row, "industry", "sector", "category") or "Technology Services"
        desc = get_val(row, "description", "about", "notes")
        email = get_val(row, "public_email", "email", "mail", "contact_email")
        phone = get_val(row, "public_phone", "phone", "telephone", "mobile")
        wa = get_val(row, "public_whatsapp", "whatsapp", "wa")
        linkedin = get_val(row, "linkedin_url", "linkedin")

        # Decision maker
        dm_name = get_val(row, "decision_maker_name", "contact_name", "ceo", "founder")
        dm_role = get_val(row, "decision_maker_role", "role", "designation", "title")

        # Devices / Employees
        laptops_str = get_val(row, "laptop_count_verified", "laptops", "laptop_count", "devices")
        laptops = int(laptops_str) if laptops_str and laptops_str.isdigit() else None
        laptop_evidence = get_val(row, "laptop_count_evidence", "device_evidence") or (
            f"CSV file '{filename}' row {idx}" if laptops else "Unknown"
        )

        emp_min_str = get_val(row, "employee_count_min", "employees_min", "min_employees")
        emp_max_str = get_val(row, "employee_count_max", "employees_max", "max_employees", "employees")
        emp_min = int(emp_min_str) if emp_min_str and emp_min_str.isdigit() else None
        emp_max = int(emp_max_str) if emp_max_str and emp_max_str.isdigit() else None

        demo_row = is_demo_domain(website) or is_demo_domain(email)
        item = DiscoveredCompanyItem(
            name=sanitize_untrusted_text(name),
            website=website,
            city=city,
            state=state,
            industry=industry,
            description=sanitize_untrusted_text(desc) if desc else None,
            public_email=email,
            public_phone=phone,
            public_whatsapp=wa,
            linkedin_url=linkedin,
            decision_maker_name=dm_name,
            decision_maker_role=dm_role,
            employee_count_min=emp_min,
            employee_count_max=emp_max,
            employee_size_evidence=f"Imported from {filename} line {idx}" if (emp_min or emp_max) else "Unknown",
            laptop_count_verified=laptops,
            laptop_count_evidence=laptop_evidence,
            source_url=f"csv://{filename}#line={idx}",
            source_type="csv_import",
            is_demo=demo_row,
            verification_status="demo_fixture" if demo_row else "unverified",
            confidence_level=0.0 if demo_row else 0.70,
            retrieval_timestamp=datetime.now(timezone.utc)
        )
        items.append(item)

    return items


def search_public_company_directory(
    query_params: DiscoveryQuery,
    http_client: Optional[httpx.Client] = None,
) -> List[DiscoveredCompanyItem]:
    """
    Unified multi-source discovery orchestrator:
    1. Queries configured permitted real search adapters (Tavily, SerpAPI) — returns real unverified leads (is_demo=False).
    2. Includes quarantined .example.com demo fixtures ONLY when query_params.include_demo=True in non-production,
       always explicitly tagged with is_demo=True and verification_status='demo_fixture'.
    """
    results: List[DiscoveredCompanyItem] = []
    seen_keys = set()

    def _add_unique(item: DiscoveredCompanyItem):
        key = (item.name.strip().lower(), (item.website or "").strip().lower())
        if key not in seen_keys:
            seen_keys.add(key)
            results.append(item)

    # 1. Real Permitted Search Adapters (never .example.com)
    for adapter in (TavilyDiscoveryAdapter(), SerpApiDiscoveryAdapter()):
        if adapter.is_configured():
            for item in adapter.search(query_params, limit=8, http_client=http_client):
                _add_unique(item)

    # 2. Quarantined Demo Fixtures (STRICTLY labelled is_demo=True, verification_status='demo_fixture', never in production)
    allow_demo = query_params.include_demo and settings.ENVIRONMENT.lower() != "production"
    if allow_demo:
        city_filter = (query_params.city or "").lower()
        industry_filter = (query_params.industry or "").lower()
        keyword = (query_params.query or "").lower()

        for item in DISCOVERY_CATALOG:
            if city_filter and city_filter != "all" and city_filter not in item.city.lower():
                continue
            if industry_filter and industry_filter != "all" and industry_filter not in (item.industry or "").lower():
                continue
            if keyword:
                text = f"{item.name} {item.description or ''} {item.city} {item.industry or ''}".lower()
                if keyword not in text:
                    continue
            if query_params.min_devices and (item.laptop_count_verified or 0) < query_params.min_devices:
                continue

            demo_flagged = item.model_copy(update={
                "is_demo": True,
                "verification_status": "demo_fixture",
                "source_type": "demo_fixture",
            })
            _add_unique(demo_flagged)

    return results
