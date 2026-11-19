import logging
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


class OpenStreetMapPublicAdapter(DiscoverySourceAdapter):
    """
    Queries public OpenStreetMap Nominatim open-data directory for offices and technology
    companies in target cities without bypassing access controls or inventing missing facts.
    """
    name = "openstreetmap_nominatim"
    source_type = "openstreetmap_public"
    is_demo_source = False

    def is_configured(self) -> bool:
        return True  # Public open data (polite User-Agent required)

    def search(
        self,
        query: DiscoveryQuery,
        limit: int = 8,
        http_client: Optional[httpx.Client] = None,
    ) -> List[DiscoveredCompanyItem]:
        city = (query.city or "").strip()
        is_all_india = city.lower() in ("all", "all india", "") or query.scope == "country"
        term = (query.query or query.industry or "software IT office").strip()

        if is_all_india:
            search_q = f"{term} India"
        elif query.state and not city:
            search_q = f"{term} {query.state} India"
        else:
            search_q = f"{term} {city} {query.state or ''} India".strip()

        close_client = http_client is None
        client = http_client or httpx.Client(timeout=8.0)
        items: List[DiscoveredCompanyItem] = []
        try:
            resp = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": search_q, "format": "jsonv2", "addressdetails": 1, "extratags": 1, "limit": limit},
                headers={"User-Agent": "ActTrident-B2B-Discovery/2.0 (https://acttrident.ai)"},
            )
            if resp.status_code != 200:
                return []
            now = datetime.now(timezone.utc)
            for place in resp.json() or []:
                display = place.get("name") or (place.get("display_name") or "").split(",")[0].strip()
                if not display:
                    continue
                extra = place.get("extratags") or {}
                addr = place.get("address") or {}
                website = extra.get("website") or extra.get("contact:website")
                if website and not website.startswith(("http://", "https://")):
                    website = f"https://{website}"
                if website and not is_safe_external_url(website):
                    website = None

                osm_type = place.get("osm_type", "node")
                osm_id = place.get("osm_id", "")
                osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_id else "https://www.openstreetmap.org/"

                extracted_city = addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("state_district") or (city if not is_all_india else "India")
                extracted_state = addr.get("state") or query.state

                items.append(DiscoveredCompanyItem(
                    name=sanitize_untrusted_text(display[:120]),
                    website=website,
                    city=extracted_city,
                    state=extracted_state,
                    industry=query.industry or extra.get("office") or "Business / Technology",
                    description=sanitize_untrusted_text((place.get("display_name") or "")[:300]),
                    public_email=extra.get("email") or extra.get("contact:email"),
                    public_phone=extra.get("phone") or extra.get("contact:phone"),
                    laptop_count_verified=None,  # Never fabricate device count!
                    laptop_count_evidence="Unknown — pending verification",
                    employee_size_evidence="Unknown — pending verification",
                    source_url=website or osm_url,
                    source_type=self.source_type,
                    is_demo=False,
                    verification_status="unverified",
                    confidence_level=0.65,
                    retrieval_timestamp=now,
                ))
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

        if is_all_india:
            q = f"{kw} {ind} companies in India official website contact".strip()
            result_city = "India"
        elif query.state and not city:
            q = f"{kw} {ind} companies in {query.state} India official website contact".strip()
            result_city = query.state
        else:
            q = f"{kw} {ind} companies in {city} {query.state or ''} India official website contact".strip()
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
                    "max_results": limit,
                },
            )
            if resp.status_code != 200:
                return []
            now = datetime.now(timezone.utc)
            for r in (resp.json().get("results") or []):
                url = r.get("url", "")
                if not url or not is_safe_external_url(url) or is_demo_domain(url):
                    continue
                title = (r.get("title") or "").split(" - ")[0].split(" | ")[0].strip()
                if not title:
                    continue
                items.append(DiscoveredCompanyItem(
                    name=sanitize_untrusted_text(title[:120]),
                    website=url,
                    city=result_city,
                    state=query.state,
                    industry=query.industry or "Technology Services",
                    description=sanitize_untrusted_text((r.get("content") or "")[:300]),
                    laptop_count_verified=None,
                    laptop_count_evidence="Unknown — pending verification",
                    employee_size_evidence="Unknown — pending verification",
                    source_url=url,
                    source_type=self.source_type,
                    is_demo=False,
                    verification_status="unverified",
                    confidence_level=0.75,
                    retrieval_timestamp=now,
                ))
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

        if is_all_india:
            q = f"{kw} {ind} companies in India".strip()
            result_city = "India"
        elif query.state and not city:
            q = f"{kw} {ind} companies in {query.state} India".strip()
            result_city = query.state
        else:
            q = f"{kw} {ind} companies in {city} {query.state or ''} India".strip()
            result_city = city or "India"

        close_client = http_client is None
        client = http_client or httpx.Client(timeout=10.0)
        items: List[DiscoveredCompanyItem] = []
        try:
            resp = client.get(
                "https://serpapi.com/search.json",
                params={"api_key": settings.SERPAPI_API_KEY.strip(), "q": q, "engine": "google", "num": limit},
            )
            if resp.status_code != 200:
                return []
            now = datetime.now(timezone.utc)
            for org in (resp.json().get("organic_results") or []):
                link = org.get("link", "")
                if not link or not is_safe_external_url(link) or is_demo_domain(link):
                    continue
                title = (org.get("title") or "").split(" - ")[0].split(" | ")[0].strip()
                if not title:
                    continue
                items.append(DiscoveredCompanyItem(
                    name=sanitize_untrusted_text(title[:120]),
                    website=link,
                    city=result_city,
                    state=query.state,
                    industry=query.industry or "Technology Services",
                    description=sanitize_untrusted_text((org.get("snippet") or "")[:300]),
                    laptop_count_verified=None,
                    laptop_count_evidence="Unknown — pending verification",
                    employee_size_evidence="Unknown — pending verification",
                    source_url=link,
                    source_type=self.source_type,
                    is_demo=False,
                    verification_status="unverified",
                    confidence_level=0.75,
                    retrieval_timestamp=now,
                ))
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
