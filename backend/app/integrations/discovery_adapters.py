import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
import httpx

from app.core.config import settings
from app.core.security import is_safe_external_url, sanitize_untrusted_text
from app.schemas.research import DiscoveryQuery, DiscoveredCompanyItem

logger = logging.getLogger(__name__)

DEMO_DOMAIN_SUFFIXES = (".example.com", ".example.org", ".example.net", ".invalid", ".test")

# Phone & Email regex for snippet contact discovery
INDIAN_PHONE_REGEX = re.compile(
    r'(?:\+?91[\s.-]?)?(?:[6-9]\d{9}|0\d{2,4}[\s.-]?\d{6,8})'
)
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
)
INVALID_EMAIL_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf', '.js', '.css',
    '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.ico'
)

# Directory aggregators that should NEVER be recorded as official company websites
DIRECTORY_AGGREGATOR_DOMAINS = {
    "justdial.com", "indiamart.com", "sulekha.com", "tradeindia.com",
    "zaubacorp.com", "linkedin.com", "glassdoor.co.in", "glassdoor.com",
    "facebook.com", "instagram.com", "yellowpages.in", "quikr.com",
    "magicbricks.com", "99acres.com", "shiksha.com", "collegedunia.com",
    "wikipedia.org", "youtube.com", "twitter.com", "x.com"
}

# Explicit non-commercial / public facility patterns to strictly reject across all providers
EXCLUDED_FACILITY_PATTERNS = [
    "post office", "head post", "sub post", "dak ghar", "speed post",
    "police", "thana", "outpost", "traffic outpost", "patrol",
    "institute of technology", "college", "university", "polytechnic", "vidyalaya",
    "shiksha", "school", "academy", "madrasa", "campus",
    "hospital", "swasthya", "clinic", "dispensary", "nursing home", "health centre",
    "court", "nyayalaya", "bar association", "tribunal",
    "collectorate", "municipality", "panchayat", "vidhan", "sahayata kendra",
    "kendra", "prashasan", "administrative office", "tehsil", "block development",
    "department of", "ministry of", "barrage office", "irrigation office", "pwd office",
    "railway station", "bus terminus", "bus stand", "toll plaza",
    "temple", "mandir", "masjid", "mosque", "church", "gurudwara", "ashram",
    "airconditioning", "air conditioning", "ac repair", "surgical", "pathology",
    "laboratory", "lab solutions", "diagnostic", "jeweller", "jewel", "sweets", "restaurant", "hotel"
]


def is_demo_domain(value: Optional[str]) -> bool:
    """Returns True if a website URL or email address belongs to RFC 2606 example/test domains."""
    if not value:
        return False
    raw = value.strip().lower()
    host = raw
    if "@" in raw and "://" not in raw:
        host = raw.split("@", 1)[1]
    elif "://" in raw:
        host = (urlparse(raw).hostname or "").lower()
    host = host.split(":")[0]
    return host in ("example.com", "example.org", "example.net") or any(host.endswith(s) for s in DEMO_DOMAIN_SUFFIXES)


class DiscoverySourceAdapter(ABC):
    """Modular base interface for permitted public business discovery data sources."""

    name: str
    source_type: str
    is_demo_source: bool = False

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def search(
        self,
        query: DiscoveryQuery,
        limit: int = 10,
        http_client: Optional[httpx.Client] = None,
    ) -> List[DiscoveredCompanyItem]:
        pass


_nominatim_lock = threading.Lock()
_last_nominatim_call = 0.0


def _throttle_nominatim(min_interval: float = 1.0) -> None:
    """Enforces strict 1 req/sec policy required by OpenStreetMap Nominatim Usage Policy."""
    global _last_nominatim_call
    with _nominatim_lock:
        now = time.time()
        elapsed = now - _last_nominatim_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_nominatim_call = time.time()


class OpenStreetMapPublicAdapter(DiscoverySourceAdapter):
    """
    Queries public OpenStreetMap Nominatim open-data directory for offices and technology
    companies in target cities without bypassing access controls or inventing missing facts.
    """
    name = "openstreetmap_nominatim"
    source_type = "openstreetmap_public"
    is_demo_source = False

    def is_configured(self) -> bool:
        return bool(getattr(settings, "ENABLE_OPENSTREETMAP_DISCOVERY", True))

    def search(
        self,
        query: DiscoveryQuery,
        limit: int = 8,
        http_client: Optional[httpx.Client] = None,
    ) -> List[DiscoveredCompanyItem]:
        city = (query.city or "").strip()
        is_all_india = city.lower() in ("all", "all india", "") or query.scope == "country"

        candidate_queries = []
        candidate_terms: List[str] = []
        if query.query and query.query.strip():
            candidate_terms.append(query.query.strip())
        if query.industry and query.industry.strip() not in ("All", "all", "Business / Technology"):
            candidate_terms.append(query.industry.strip())

        ind_lower = (query.industry or "").lower()
        if any(k in ind_lower for k in ["soft", "it", "tech", "computer", "cloud", "digital"]):
            # Use targeted B2B commercial phrases rather than generic "office" or standalone "technology"
            # which mistakenly pull in post offices, educational institutes, and government facilities
            candidate_terms.extend([
                "software company",
                "infotech",
                "IT services company",
                "computer software",
                "technology company",
                "technologies",
                "IT solutions",
                "software development",
                "digital agency",
                "computer solution",
                "digital hub",
                "solutions",
                "computer"
            ])
        else:
            candidate_terms.extend(["commercial enterprise", "private limited company", "corporate office", "business services"])

        seen_terms = set()
        terms_to_try: List[str] = []
        for t in candidate_terms:
            t_clean = t.strip()
            if t_clean.lower() not in seen_terms:
                seen_terms.add(t_clean.lower())
                terms_to_try.append(t_clean)

        close_client = http_client is None
        client = http_client or httpx.Client(timeout=8.0)
        items: List[DiscoveredCompanyItem] = []
        seen_names = set()

        EXCLUDED_OSM_CLASSES = ("highway", "boundary", "landuse", "leisure", "natural", "waterway", "railway", "aeroway", "tourism")
        EXCLUDED_OSM_TYPES = (
            "road", "residential", "service", "administrative", "track",
            "post_office", "school", "college", "university", "kindergarten",
            "police", "courthouse", "townhall", "fire_station", "prison",
            "hospital", "clinic", "pharmacy", "doctors", "dentist",
            "place_of_worship", "bank", "atm", "fuel", "parking", "bus_station",
            "government", "political_party", "ngo"
        )

        try:
            for term in terms_to_try:
                if len(items) >= limit:
                    break
                if is_all_india:
                    search_q = f"{term} India"
                elif query.state and not city:
                    search_q = f"{term} {query.state} India"
                else:
                    search_q = f"{term} {city} {query.state or ''} India".strip()

                _throttle_nominatim(1.0)
                try:
                    resp = client.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={"q": search_q, "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": min(limit * 2, 20)},
                        headers={"User-Agent": "ActTrident-B2B-Discovery/2.0 (https://acttrident.ai)"},
                    )
                    if resp.status_code != 200:
                        continue
                    now = datetime.now(timezone.utc)
                    for place in resp.json() or []:
                        place_class = place.get("class", "")
                        place_type = place.get("type", "")
                        if place_class in EXCLUDED_OSM_CLASSES or place_type in EXCLUDED_OSM_TYPES:
                            continue

                        display = place.get("name") or (place.get("display_name") or "").split(",")[0].strip()
                        if not display or display.lower() in seen_names:
                            continue

                        disp_lower = (place.get("display_name") or display).lower()
                        # Strict relevance filter: reject educational institutes, public post offices, and government services
                        if any(pattern in disp_lower for pattern in EXCLUDED_FACILITY_PATTERNS):
                            continue

                        # Geographic validation: if specific city requested, ensure display or address matches city
                        addr = place.get("address") or {}
                        extracted_city = addr.get("city") or addr.get("town") or addr.get("municipality") or (city if not is_all_india else "India")
                        extracted_state = addr.get("state") or query.state

                        if city and not is_all_india:
                            city_matched = (
                                city.lower() in disp_lower
                                or city.lower() in (addr.get("city") or "").lower()
                                or city.lower() in (addr.get("town") or "").lower()
                                or city.lower() in (addr.get("municipality") or "").lower()
                                or city.lower() in (addr.get("suburb") or "").lower()
                                or city.lower() in (addr.get("county") or "").lower()
                            )
                            if not city_matched:
                                continue
                            # Canonicalize city name to the queried target city
                            extracted_city = city

                        seen_names.add(display.lower())

                        extra = place.get("extratags") or {}
                        website = extra.get("website") or extra.get("contact:website")
                        if website and not website.startswith(("http://", "https://")):
                            website = f"https://{website}"
                        if website and not is_safe_external_url(website):
                            website = None

                        osm_type = place.get("osm_type", "node")
                        osm_id = place.get("osm_id", "")
                        osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_id else "https://www.openstreetmap.org/"
                        addr_text = sanitize_untrusted_text((place.get("display_name") or "")[:250])

                        osm_prov = [
                            {
                                "field_name": "company_name",
                                "field_value": display,
                                "source_url": osm_url,
                                "source_type": self.source_type,
                                "retrieval_timestamp": now.isoformat(),
                                "verification_status": "publicly_listed",
                                "confidence_score": 0.85,
                                "evidence_snippet": f"Physical directory listing in OpenStreetMap: {addr_text}",
                            }
                        ]
                        if addr_text:
                            osm_prov.append({
                                "field_name": "business_address",
                                "field_value": addr_text,
                                "source_url": osm_url,
                                "source_type": self.source_type,
                                "retrieval_timestamp": now.isoformat(),
                                "verification_status": "publicly_listed",
                                "confidence_score": 0.90,
                                "evidence_snippet": f"Geocoded physical business address: {addr_text}",
                            })

                        items.append(DiscoveredCompanyItem(
                            name=sanitize_untrusted_text(display[:120]),
                            website=website,
                            city=extracted_city,
                            state=extracted_state,
                            country=addr.get("country", "India"),
                            industry=query.industry or extra.get("office") or "Software Development",
                            description=sanitize_untrusted_text((place.get("display_name") or "")[:300]),
                            business_address=addr_text,
                            public_email=extra.get("email") or extra.get("contact:email"),
                            public_phone=extra.get("phone") or extra.get("contact:phone"),
                            laptop_count_verified=None,  # Never fabricate device count!
                            laptop_count_evidence="Unknown — pending verification",
                            employee_size_evidence="Unknown — pending verification",
                            source_url=website or osm_url,
                            source_type=self.source_type,
                            is_demo=False,
                            verification_status="unverified",
                            confidence_level=0.75,
                            retrieval_timestamp=now,
                            provenance_sources=osm_prov,
                        ))
                        if len(items) >= limit:
                            break
                except Exception as ex:
                    logger.debug(f"OSM term query '{search_q}' notice: {ex}")
        except Exception as exc:
            logger.debug(f"OpenStreetMap discovery request skipped/failed: {exc}")
        finally:
            if close_client:
                client.close()
        return items


class TavilyDiscoveryAdapter(DiscoverySourceAdapter):
    """Permitted Search API adapter using Tavily Search when TAVILY_API_KEY is configured."""
    name = "tavily_search"
    source_type = "tavily_search"
    is_demo_source = False

    def is_configured(self) -> bool:
        return bool((settings.TAVILY_API_KEY or "").strip())

    def search(
        self,
        query: DiscoveryQuery,
        limit: int = 8,
        http_client: Optional[httpx.Client] = None,
    ) -> List[DiscoveredCompanyItem]:
        if not self.is_configured():
            return []
        city = (query.city or "").strip()
        is_all_india = city.lower() in ("all", "all india", "") or query.scope == "country"
        ind = (query.industry or "software IT services").strip()
        kw = (query.query or "").strip()

        neg_terms = "-college -university -school -hospital -police -post_office -institute -campus"
        if is_all_india:
            q = f"{kw} {ind} companies in India official website contact {neg_terms}".strip()
            result_city = "India"
        elif query.state and not city:
            q = f"{kw} {ind} companies in {query.state} India official website contact {neg_terms}".strip()
            result_city = query.state
        else:
            q = f"{kw} {ind} companies in {city} {query.state or ''} India official website contact {neg_terms}".strip()
            result_city = city or "India"

        close_client = http_client is None
        client = http_client or httpx.Client(timeout=10.0)
        items: List[DiscoveredCompanyItem] = []
        try:
            resp = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.TAVILY_API_KEY.strip(),
                    "query": q,
                    "search_depth": "basic",
                    "max_results": limit * 2,
                },
            )
            if resp.status_code != 200:
                return []
            now = datetime.now(timezone.utc)
            seen_names = set()
            for r in (resp.json().get("results") or []):
                url = r.get("url", "")
                if not url or not is_safe_external_url(url) or is_demo_domain(url):
                    continue
                raw_title = r.get("title") or ""
                snippet = r.get("content") or ""
                text_to_check = f"{raw_title} {snippet}".lower()

                # Filter out excluded facilities
                if any(pat in text_to_check for pat in EXCLUDED_FACILITY_PATTERNS):
                    continue

                title = raw_title.split(" - ")[0].split(" | ")[0].strip()
                if not title or title.lower() in seen_names:
                    continue
                seen_names.add(title.lower())

                # Check if URL belongs to an aggregator directory
                parsed_host = (urlparse(url).hostname or "").lower()
                is_aggregator = any(parsed_host == agg or parsed_host.endswith(f".{agg}") for agg in DIRECTORY_AGGREGATOR_DOMAINS)

                official_web = None if is_aggregator else url
                src_type = "business_directory" if is_aggregator else self.source_type
                contact_page = url if ("/contact" in url.lower() or "/about" in url.lower()) and not is_aggregator else None

                # Extract emails and phone numbers from snippet
                snippet_emails = [
                    em.lower() for em in EMAIL_REGEX.findall(snippet)
                    if not any(em.lower().endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS) and not is_demo_domain(em)
                ]
                snippet_phones = [ph.strip() for ph in INDIAN_PHONE_REGEX.findall(snippet) if len(re.sub(r'[\s.-]', '', ph)) >= 10]

                email_found = snippet_emails[0] if snippet_emails else None
                phone_found = snippet_phones[0] if snippet_phones else None

                provenance = [{
                    "field_name": "company_name",
                    "field_value": title,
                    "source_url": url,
                    "source_type": src_type,
                    "retrieval_timestamp": now.isoformat(),
                    "verification_status": "publicly_listed",
                    "confidence_score": 0.80,
                    "evidence_snippet": f"Discovered via Tavily search: {snippet[:200]}",
                }]

                if email_found:
                    provenance.append({
                        "field_name": "public_email",
                        "field_value": email_found,
                        "source_url": url,
                        "source_type": src_type,
                        "retrieval_timestamp": now.isoformat(),
                        "verification_status": "publicly_listed",
                        "confidence_score": 0.85,
                        "evidence_snippet": f"Found public email in Tavily snippet: {email_found}",
                    })

                if phone_found:
                    provenance.append({
                        "field_name": "public_phone",
                        "field_value": phone_found,
                        "source_url": url,
                        "source_type": src_type,
                        "retrieval_timestamp": now.isoformat(),
                        "verification_status": "publicly_listed",
                        "confidence_score": 0.80,
                        "evidence_snippet": f"Found public phone in Tavily snippet: {phone_found}",
                    })

                items.append(DiscoveredCompanyItem(
                    name=sanitize_untrusted_text(title[:120]),
                    website=official_web,
                    city=result_city,
                    state=query.state,
                    country=query.country or "India",
                    industry=query.industry or "Technology Services",
                    description=sanitize_untrusted_text(snippet[:300]),
                    public_email=email_found,
                    email_verification_status="publicly_listed" if email_found else "not_found",
                    public_phone=phone_found,
                    phone_verification_status="publicly_listed" if phone_found else "not_found",
                    contact_page_url=contact_page,
                    laptop_count_verified=None,
                    laptop_count_evidence="Unknown — pending verification",
                    employee_size_evidence="Unknown — pending verification",
                    source_url=url,
                    source_type=src_type,
                    is_demo=False,
                    verification_status="partially_verified" if official_web else "unverified",
                    confidence_level=0.80 if official_web else 0.65,
                    retrieval_timestamp=now,
                    provenance_sources=provenance,
                ))
                if len(items) >= limit:
                    break
        except Exception as exc:
            logger.warning(f"Tavily search adapter error: {exc}")
        finally:
            if close_client:
                client.close()
        return items


class SerpApiDiscoveryAdapter(DiscoverySourceAdapter):
    """Permitted Search API adapter using SerpAPI when SERPAPI_API_KEY is configured."""
    name = "serpapi_search"
    source_type = "serpapi_search"
    is_demo_source = False

    def is_configured(self) -> bool:
        return bool((settings.SERPAPI_API_KEY or "").strip())

    def search(
        self,
        query: DiscoveryQuery,
        limit: int = 8,
        http_client: Optional[httpx.Client] = None,
    ) -> List[DiscoveredCompanyItem]:
        if not self.is_configured():
            return []
        city = (query.city or "").strip()
        is_all_india = city.lower() in ("all", "all india", "") or query.scope == "country"
        ind = (query.industry or "software IT services").strip()
        kw = (query.query or "").strip()

        neg_terms = "-college -university -school -hospital -police -post_office -institute -campus"
        if is_all_india:
            q = f"{kw} {ind} companies in India {neg_terms}".strip()
            result_city = "India"
        elif query.state and not city:
            q = f"{kw} {ind} companies in {query.state} India {neg_terms}".strip()
            result_city = query.state
        else:
            q = f"{kw} {ind} companies in {city} {query.state or ''} India {neg_terms}".strip()
            result_city = city or "India"

        close_client = http_client is None
        client = http_client or httpx.Client(timeout=10.0)
        items: List[DiscoveredCompanyItem] = []
        try:
            resp = client.get(
                "https://serpapi.com/search.json",
                params={"api_key": settings.SERPAPI_API_KEY.strip(), "q": q, "engine": "google", "num": limit * 2},
            )
            if resp.status_code != 200:
                return []
            now = datetime.now(timezone.utc)
            seen_names = set()
            for org in (resp.json().get("organic_results") or []):
                link = org.get("link", "")
                if not link or not is_safe_external_url(link) or is_demo_domain(link):
                    continue
                raw_title = org.get("title") or ""
                snippet = org.get("snippet") or ""
                text_to_check = f"{raw_title} {snippet}".lower()

                if any(pat in text_to_check for pat in EXCLUDED_FACILITY_PATTERNS):
                    continue

                title = raw_title.split(" - ")[0].split(" | ")[0].strip()
                if not title or title.lower() in seen_names:
                    continue
                seen_names.add(title.lower())

                parsed_host = (urlparse(link).hostname or "").lower()
                is_aggregator = any(parsed_host == agg or parsed_host.endswith(f".{agg}") for agg in DIRECTORY_AGGREGATOR_DOMAINS)

                official_web = None if is_aggregator else link
                src_type = "business_directory" if is_aggregator else self.source_type
                contact_page = link if ("/contact" in link.lower() or "/about" in link.lower()) and not is_aggregator else None

                items.append(DiscoveredCompanyItem(
                    name=sanitize_untrusted_text(title[:120]),
                    website=official_web,
                    city=result_city,
                    state=query.state,
                    country=query.country or "India",
                    industry=query.industry or "Technology Services",
                    description=sanitize_untrusted_text(snippet[:300]),
                    contact_page_url=contact_page,
                    laptop_count_verified=None,
                    laptop_count_evidence="Unknown — pending verification",
                    employee_size_evidence="Unknown — pending verification",
                    source_url=link,
                    source_type=src_type,
                    is_demo=False,
                    verification_status="partially_verified" if official_web else "unverified",
                    confidence_level=0.80 if official_web else 0.65,
                    retrieval_timestamp=now,
                ))
                if len(items) >= limit:
                    break
        except Exception as exc:
            logger.warning(f"SerpAPI search adapter error: {exc}")
        finally:
            if close_client:
                client.close()
        return items


def list_discovery_source_statuses() -> List[Dict[str, Any]]:
    """Reports honest configuration status of every modular discovery source adapter."""
    adapters: List[DiscoverySourceAdapter] = [
        TavilyDiscoveryAdapter(),
        SerpApiDiscoveryAdapter(),
        OpenStreetMapPublicAdapter(),
    ]
    meta = {
        "tavily_search": ("Tavily Search API", "Permitted live web search via TAVILY_API_KEY"),
        "serpapi_search": ("SerpAPI Search", "Permitted Google business search via SERPAPI_API_KEY"),
        "openstreetmap_nominatim": ("OpenStreetMap Open Data", "Public Nominatim business directory"),
    }
    return [
        {
            "name": a.name,
            "label": meta.get(a.name, (a.name, ""))[0],
            "description": meta.get(a.name, (a.name, ""))[1],
            "source_type": a.source_type,
            "configured": a.is_configured(),
            "is_demo_source": a.is_demo_source,
        }
        for a in adapters
    ]
