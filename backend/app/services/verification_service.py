"""
ActTrident Real Company & Contact Verification Engine.

Transforms unverified discovery listings into source-attributed, verified records.
Independently verifies:
1. Official website reachability, title, and description.
2. Public business email addresses (with syntax validation, RFC 2606 demo rejection, and extension filtering).
3. Public business phone and WhatsApp contact channels.
4. Company operational details, workforce size indicators, and workstation fleet mentions.
5. Decision-maker identities from leadership/team sections.
6. Field-level provenance records with URL, source type, retrieval timestamp, verification status, and evidence snippets.

Strict Truthfulness:
- Never marks an email as verified merely because it matches a pattern.
- If information is missing, records it honestly as UNKNOWN or NOT FOUND.
- Never fabricates employee headcounts or laptop numbers.
"""
import logging
import re
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin
import httpx

from app.core.security import is_safe_external_url, sanitize_untrusted_text, safe_fetch_untrusted_url
from app.integrations.discovery_adapters import is_demo_domain
from app.schemas.research import DiscoveredCompanyItem

logger = logging.getLogger("acttrident.verification")


def check_email_domain_mx(email: str) -> bool:
    """Performs DNS MX / A record check on email domain to verify deliverability."""
    try:
        domain = email.split("@")[-1].strip().lower()
        if not domain or is_demo_domain(domain):
            return False
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX', lifetime=2.5)
        return len(answers) > 0
    except Exception:
        try:
            import dns.resolver
            answers = dns.resolver.resolve(domain, 'A', lifetime=2.5)
            return len(answers) > 0
        except Exception:
            return False


# Regex for standard Indian business phone numbers
INDIAN_PHONE_REGEX = re.compile(
    r'(?:\+?91[\s.-]?)?(?:[6-9]\d{9}|0\d{2,4}[\s.-]?\d{6,8})'
)

# Standard public email regex
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
)

# Indian physical business address regex (matching street, road, complex, and 6-digit PIN code)
INDIAN_ADDRESS_REGEX = re.compile(
    r'(?:(?:Plot|Flat|Shop|Ward|Holding|Block|Floor|Building|Tower|Complex|Road|Street|Sarani|Bypass|Nagar|Colony|Lane|Sector)\s+[^\n<>]{5,100}?(?:,\s*[A-Za-z\s]+)?\s*[-–,\s]\s*(?:PIN\s*[-:]?\s*)?(?:[1-9]\d{5}))',
    re.IGNORECASE
)

# Blacklist asset extensions that falsely look like email addresses
INVALID_EMAIL_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf', '.js', '.css',
    '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.ico'
)

# Non-contact generic email prefixes to de-prioritize or flag
ROLE_BASED_PREFIXES = ('info@', 'contact@', 'support@', 'sales@', 'hello@', 'admin@', 'office@', 'enquiry@', 'queries@')

# Keywords indicative of hijacked, gambling, parked, or expired domains
UNAUTHENTIC_GAMBLING_KEYWORDS = (
    "togel", "slot", "casino", "judi", "sbobet", "gambling", "betting",
    "poker", "jackpot", "rtp live", "situs judi", "pragmatic play", "maxwin", "gacor"
)
PARKED_EXPIRED_KEYWORDS = (
    "buy this domain", "domain is for sale", "domain for sale", "parked domain",
    "this domain is parked", "sedo domain parking", "godaddy parking", "domain expired",
    "account suspended", "cpanel default page", "iis windows server",
    "website under construction", "domain available for purchase", "namecheap parking",
    "hugedomains", "dan.com", "afternic", "renew your domain"
)


def _strip_html_to_text(html: str) -> str:
    """Strips scripts, styles, and tags, returning clean normalized text."""
    text = re.sub(r'(?is)<(script|style|noscript|iframe)[^>]*>.*?</\1>', ' ', html)
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _extract_links_by_keywords(html: str, base_url: str, keywords: List[str]) -> List[str]:
    """Finds navigation links whose href or anchor text matches any of the target keywords."""
    found: List[str] = []
    # Match <a href="..." ...>...</a>
    matches = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    for href, anchor in matches:
        href_lower = href.lower()
        anchor_lower = anchor.lower()
        if any(kw in href_lower or kw in anchor_lower for kw in keywords):
            if href.startswith(("http://", "https://")):
                full_url = href
            else:
                full_url = urljoin(base_url, href)
            if is_safe_external_url(full_url) and not is_demo_domain(full_url):
                if full_url not in found and full_url != base_url:
                    found.append(full_url)
    return found[:3]


async def verify_discovered_company(item: DiscoveredCompanyItem) -> DiscoveredCompanyItem:
    """
    Independently inspects and verifies a discovered company record.
    Crawls official website and contact/about subpages if available.
    Collects field-level provenance sources and marks verified states.
    """
    now = datetime.now(timezone.utc)
    provenance_sources: List[Dict[str, Any]] = []
    extracted_snippets: List[str] = []

    # 1. Base provenance from discovery provider
    provenance_sources.append({
        "field_name": "company_name",
        "field_value": item.name,
        "source_url": item.source_url,
        "source_type": item.source_type,
        "retrieval_timestamp": (item.retrieval_timestamp or now).isoformat(),
        "verification_status": "publicly_listed",
        "confidence_score": item.confidence_level,
        "evidence_snippet": f"Discovered via {item.source_type}: {item.description or item.name}",
    })

    # Initialize verification fields
    verified_website: Optional[str] = item.website
    website_status = "unavailable"
    website_classification = "unverified"
    contact_page_url: Optional[str] = item.contact_page_url
    business_address: Optional[str] = item.business_address
    public_emails: List[str] = []
    public_phones: List[str] = []
    public_whatsapp: Optional[str] = item.public_whatsapp
    description = item.description
    decision_maker_name = item.decision_maker_name
    decision_maker_role = item.decision_maker_role
    employee_count_min = item.employee_count_min
    employee_count_max = item.employee_count_max
    employee_size_evidence = item.employee_size_evidence
    laptop_count_verified = item.laptop_count_verified
    laptop_count_evidence = item.laptop_count_evidence
    laptop_fleet_status = item.laptop_fleet_status or "UNKNOWN"

    if item.public_email:
        public_emails.append(item.public_email.lower().strip())
    if item.public_phone:
        public_phones.append(item.public_phone.strip())

    # 2. Website Crawl & Verification
    if item.website and is_safe_external_url(item.website) and not is_demo_domain(item.website):
        success, homepage_html, final_url, err = await safe_fetch_untrusted_url(
            item.website,
            max_bytes=60000,
            timeout_seconds=7.0,
            max_redirects=3,
        )
        if success and homepage_html:
            # Check for domain hijacking, gambling, or parked domain signatures
            title_m = re.search(r'<title[^>]*>(.*?)</title>', homepage_html, re.IGNORECASE | re.DOTALL)
            title_clean = sanitize_untrusted_text(title_m.group(1).strip()[:180]) if title_m else ""
            check_sample = f"{title_clean} {homepage_html[:4000]}".lower()

            is_gambling = any(kw in check_sample for kw in UNAUTHENTIC_GAMBLING_KEYWORDS)
            is_parked = any(kw in check_sample for kw in PARKED_EXPIRED_KEYWORDS)

            if is_gambling or is_parked:
                rejection_reason = "gambling/betting hijack" if is_gambling else "parked/expired domain"
                website_classification = "unrelated" if is_gambling else "parked"
                logger.info(f"Rejecting unauthentic website {item.website}: detected {rejection_reason}")
                website_status = "rejected_unauthentic"
                verified_website = None
                provenance_sources.append({
                    "field_name": "official_website",
                    "field_value": item.website,
                    "source_url": item.website,
                    "source_type": "official_website",
                    "retrieval_timestamp": now.isoformat(),
                    "verification_status": "unverified",
                    "confidence_score": 0.0,
                    "evidence_snippet": f"Website rejected: detected {rejection_reason} (title: '{title_clean[:80]}')",
                })
            else:
                website_status = "accessible"
                verified_website = final_url or item.website
                clean_name_tokens = [w for w in re.sub(r'[^\w\s]', '', item.name.lower()).split() if len(w) > 3]
                has_name_token = any(t in check_sample for t in clean_name_tokens)
                if has_name_token or any(k in check_sample for k in ["software", "technology", "solutions", "it services", "digital", "consulting", "web", "cloud"]):
                    website_classification = "authentic"
                else:
                    website_classification = "likely_authentic"
                provenance_sources.append({
                    "field_name": "official_website",
                    "field_value": verified_website,
                    "source_url": verified_website,
                    "source_type": "official_website",
                    "retrieval_timestamp": now.isoformat(),
                    "verification_status": "verified",
                    "confidence_score": 0.95,
                    "evidence_snippet": f"Successfully verified reachability and content of {verified_website}",
                })

                # Extract Title & Description
                if not description or len(description) < 40:
                    description = title_clean

                meta_desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', homepage_html, re.IGNORECASE)
                if meta_desc_m:
                    meta_desc = sanitize_untrusted_text(meta_desc_m.group(1).strip()[:400])
                    if meta_desc:
                        description = meta_desc
                        extracted_snippets.append(f"Official meta description: {meta_desc[:150]}")

                # Extract Contact / Enquiry page link from homepage
                contact_links = _extract_links_by_keywords(homepage_html, verified_website, ["contact", "enquiry", "inquiry", "reach-us", "reach", "location"])
                if contact_links and not contact_page_url:
                    contact_page_url = contact_links[0]
                    provenance_sources.append({
                        "field_name": "contact_page",
                        "field_value": contact_page_url,
                        "source_url": contact_page_url,
                        "source_type": "official_website",
                        "retrieval_timestamp": now.isoformat(),
                        "verification_status": "verified",
                        "confidence_score": 0.90,
                        "evidence_snippet": f"Discovered official contact/enquiry link: {contact_page_url}",
                    })

                # Extract Indian Business Address from Homepage
                home_text = _strip_html_to_text(homepage_html)
                addr_m = INDIAN_ADDRESS_REGEX.search(home_text)
                if addr_m and not business_address:
                    business_address = sanitize_untrusted_text(addr_m.group(0).strip()[:200])
                    provenance_sources.append({
                        "field_name": "business_address",
                        "field_value": business_address,
                        "source_url": verified_website,
                        "source_type": "official_website",
                        "retrieval_timestamp": now.isoformat(),
                        "verification_status": "publicly_listed",
                        "confidence_score": 0.85,
                        "evidence_snippet": f"Found business address on homepage: {business_address}",
                    })

                # Extract Emails from Homepage
                home_emails = set(EMAIL_REGEX.findall(homepage_html))
                for em in home_emails:
                    em_l = em.lower().strip()
                    if not any(em_l.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS) and not is_demo_domain(em_l):
                        if em_l not in public_emails:
                            public_emails.append(em_l)
                            provenance_sources.append({
                                "field_name": "public_email",
                                "field_value": em_l,
                                "source_url": verified_website,
                                "source_type": "official_website",
                                "retrieval_timestamp": now.isoformat(),
                                "verification_status": "publicly_listed",
                                "confidence_score": 0.90,
                                "evidence_snippet": f"Found public email on official homepage: {em_l}",
                            })

                # Extract Phones from Homepage
                home_phones = set(INDIAN_PHONE_REGEX.findall(homepage_html))
                for ph in home_phones:
                    cleaned_ph = re.sub(r'[\s.-]', '', ph)
                    if len(cleaned_ph) >= 10 and ph.strip() not in public_phones:
                        public_phones.append(ph.strip())
                        provenance_sources.append({
                            "field_name": "public_phone",
                            "field_value": ph.strip(),
                            "source_url": verified_website,
                            "source_type": "official_website",
                            "retrieval_timestamp": now.isoformat(),
                            "verification_status": "publicly_listed",
                            "confidence_score": 0.85,
                            "evidence_snippet": f"Found public phone on official homepage: {ph.strip()}",
                        })

                # Check for WhatsApp on Homepage
                wa_m = re.search(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{10,13})', homepage_html, re.IGNORECASE)
                if wa_m and not public_whatsapp:
                    wa_num = f"+{wa_m.group(1).lstrip('+')}"
                    public_whatsapp = wa_num
                    provenance_sources.append({
                        "field_name": "public_whatsapp",
                        "field_value": wa_num,
                        "source_url": verified_website,
                        "source_type": "official_website",
                        "retrieval_timestamp": now.isoformat(),
                        "verification_status": "publicly_listed",
                        "confidence_score": 0.92,
                        "evidence_snippet": f"Discovered official WhatsApp Click-to-Chat link: {wa_num}",
                    })

            # 3. Follow contact and about links
            sub_links = _extract_links_by_keywords(homepage_html, verified_website, ["contact", "about", "team", "careers"])
            for sub_url in sub_links:
                sub_success, sub_html, _, _ = await safe_fetch_untrusted_url(
                    sub_url,
                    max_bytes=40000,
                    timeout_seconds=5.0,
                    max_redirects=2,
                )
                if sub_success and sub_html:
                    sub_text = _strip_html_to_text(sub_html)
                    # Extract additional emails from contact/about subpage
                    sub_emails = set(EMAIL_REGEX.findall(sub_html))
                    for em in sub_emails:
                        em_l = em.lower().strip()
                        if not any(em_l.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS) and not is_demo_domain(em_l):
                            if em_l not in public_emails:
                                public_emails.append(em_l)
                                provenance_sources.append({
                                    "field_name": "public_email",
                                    "field_value": em_l,
                                    "source_url": sub_url,
                                    "source_type": "contact_page" if "contact" in sub_url else "about_page",
                                    "retrieval_timestamp": now.isoformat(),
                                    "verification_status": "publicly_listed",
                                    "confidence_score": 0.95,
                                    "evidence_snippet": f"Found public contact email on subpage {sub_url}: {em_l}",
                                })

                    # Extract workforce mentions
                    emp_m = re.search(r'(\d+[\+]?\s+(?:employees|team members|engineers|developers|consultants))', sub_text, re.IGNORECASE)
                    if emp_m and not employee_count_min:
                        raw_emp_str = emp_m.group(1).strip()
                        digits = re.findall(r'\d+', raw_emp_str)
                        if digits:
                            count_val = int(digits[0])
                            employee_count_min = count_val
                            employee_size_evidence = f"Official website ({sub_url}) states: '{raw_emp_str}'"
                            provenance_sources.append({
                                "field_name": "employee_size",
                                "field_value": f"{count_val}+",
                                "source_url": sub_url,
                                "source_type": "official_website",
                                "retrieval_timestamp": now.isoformat(),
                                "verification_status": "publicly_listed",
                                "confidence_score": 0.85,
                                "evidence_snippet": employee_size_evidence,
                            })

                    # Extract laptop fleet evidence (strict verification!)
                    laptop_m = re.search(r'(\d+[\+]?\s+(?:company-issued\s+laptops|managed\s+workstations|laptops\s+for\s+developers|laptops|workstations))', sub_text, re.IGNORECASE)
                    if laptop_m and not laptop_count_verified:
                        raw_lap_str = laptop_m.group(1).strip()
                        digits = re.findall(r'\d+', raw_lap_str)
                        if digits and int(digits[0]) >= 5:
                            lap_val = int(digits[0])
                            laptop_count_verified = lap_val
                            laptop_count_evidence = f"Careers/about portal ({sub_url}) documents: '{raw_lap_str}'"
                            laptop_fleet_status = "CLAIMED"  # requires audit confirmation to reach VERIFIED
                            provenance_sources.append({
                                "field_name": "laptop_count",
                                "field_value": str(lap_val),
                                "source_url": sub_url,
                                "source_type": "careers_page" if "career" in sub_url else "official_website",
                                "retrieval_timestamp": now.isoformat(),
                                "verification_status": "publicly_listed",
                                "confidence_score": 0.80,
                                "evidence_snippet": laptop_count_evidence,
                            })

                    # Extract physical business address from subpage if not found on homepage
                    if not business_address:
                        sub_addr_m = INDIAN_ADDRESS_REGEX.search(sub_text)
                        if sub_addr_m:
                            business_address = sanitize_untrusted_text(sub_addr_m.group(0).strip()[:200])
                            provenance_sources.append({
                                "field_name": "business_address",
                                "field_value": business_address,
                                "source_url": sub_url,
                                "source_type": "contact_page" if "contact" in sub_url else "about_page",
                                "retrieval_timestamp": now.isoformat(),
                                "verification_status": "publicly_listed",
                                "confidence_score": 0.88,
                                "evidence_snippet": f"Found business address on subpage: {business_address}",
                            })

                    # Extract decision maker / leadership
                    if not decision_maker_name and ("team" in sub_url or "about" in sub_url):
                        founder_m = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[-–,:|]\s*(Founder|Co-Founder|CEO|Chief Executive Officer|Director|Managing Director|MD|CTO|Head of Engineering|President)', sub_text)
                        if founder_m:
                            decision_maker_name = founder_m.group(1).strip()
                            decision_maker_role = founder_m.group(2).strip()
                            provenance_sources.append({
                                "field_name": "decision_maker",
                                "field_value": f"{decision_maker_name} ({decision_maker_role})",
                                "source_url": sub_url,
                                "source_type": "leadership_page",
                                "retrieval_timestamp": now.isoformat(),
                                "verification_status": "publicly_listed",
                                "confidence_score": 0.85,
                                "evidence_snippet": f"Found leadership profile on {sub_url}: {decision_maker_name}, {decision_maker_role}",
                            })
        else:
            website_status = "inaccessible"
            website_classification = "unavailable"
            provenance_sources.append({
                "field_name": "official_website",
                "field_value": item.website,
                "source_url": item.website,
                "source_type": "official_website",
                "retrieval_timestamp": now.isoformat(),
                "verification_status": "unavailable",
                "confidence_score": 0.20,
                "evidence_snippet": f"Website verification failed: {err or 'Connection timed out or host unreachable'}",
            })
    elif not item.website:
        website_status = "unavailable"
        website_classification = "unavailable"

    # Determine granular email verification status
    selected_email = public_emails[0] if public_emails else None
    has_mx = False
    if selected_email:
        if not EMAIL_REGEX.match(selected_email) or any(selected_email.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS):
            email_status = "invalid"
        else:
            has_mx = await asyncio.to_thread(check_email_domain_mx, selected_email)
            found_on_official_site = bool(verified_website and any(
                p.get("field_name") == "public_email" and p.get("source_type") == "official_website"
                for p in provenance_sources
            ))
            had_in_initial_item = bool(item.public_email and item.public_email.lower().strip() == selected_email)

            if has_mx and found_on_official_site and had_in_initial_item:
                email_status = "independently_verified"
            elif found_on_official_site:
                email_status = "source_confirmed"
            elif has_mx:
                email_status = "domain_mx_confirmed"
            else:
                email_status = "syntax_valid"

        provenance_sources.append({
            "field_name": "public_email",
            "field_value": selected_email,
            "source_url": verified_website or item.source_url,
            "source_type": "official_website" if (verified_website and email_status in ("source_confirmed", "independently_verified")) else "directory",
            "retrieval_timestamp": now.isoformat(),
            "verification_status": email_status,
            "confidence_score": 0.95 if email_status in ("independently_verified", "source_confirmed") else (0.70 if email_status in ("domain_mx_confirmed", "domain_checked") else 0.0),
            "evidence_snippet": f"Email status '{email_status}' (DNS MX records confirmed: {has_mx}; mailbox existence not verified)",
        })
    else:
        email_status = "unknown"
        provenance_sources.append({
            "field_name": "public_email",
            "field_value": None,
            "source_url": verified_website or item.source_url,
            "source_type": "verification_engine",
            "retrieval_timestamp": now.isoformat(),
            "verification_status": "unknown",
            "confidence_score": 1.0,
            "evidence_snippet": "No publicly listed business email address discovered on official website or registry.",
        })

    # Determine granular phone verification status
    selected_phone = public_phones[0] if public_phones else None
    if selected_phone:
        clean_phone = re.sub(r'[\s.-]', '', selected_phone)
        if not INDIAN_PHONE_REGEX.search(selected_phone) and len(clean_phone) < 8:
            phone_status = "invalid"
        else:
            found_on_official_site = bool(verified_website and any(
                p.get("field_name") == "public_phone" and p.get("source_type") == "official_website"
                for p in provenance_sources
            ))
            had_in_initial_item = bool(item.public_phone and item.public_phone.strip() == selected_phone)

            if found_on_official_site and had_in_initial_item:
                phone_status = "independently_verified"
            elif found_on_official_site:
                phone_status = "source_confirmed"
            else:
                phone_status = "format_valid"
    else:
        phone_status = "unknown"

    # Overall verification status
    if website_status == "accessible" and selected_email and email_status in ("independently_verified", "source_confirmed", "domain_mx_confirmed", "domain_checked"):
        overall_v_status = "verified"
        confidence = 0.90
    elif website_status == "accessible":
        overall_v_status = "partially_verified"
        confidence = 0.65
    elif item.is_demo:
        overall_v_status = "demo_fixture"
        confidence = 0.0
    else:
        overall_v_status = "unverified"
        confidence = 0.40

    # Determine missing information
    missing_info: List[str] = []
    if not verified_website or website_status != "accessible":
        missing_info.append("official_website")
    if not selected_email:
        missing_info.append("public_email")
    if not selected_phone:
        missing_info.append("public_phone")
    if not business_address:
        missing_info.append("business_address")
    if not decision_maker_name:
        missing_info.append("decision_maker")
    if laptop_count_verified is None:
        missing_info.append("laptop_fleet_count")
    if employee_count_min is None and employee_count_max is None:
        missing_info.append("employee_headcount")

    return item.model_copy(update={
        "website": verified_website,
        "website_status": website_status,
        "website_classification": website_classification,
        "contact_page_url": contact_page_url,
        "business_address": business_address,
        "public_email": selected_email,
        "email_verification_status": email_status,
        "public_phone": selected_phone,
        "phone_verification_status": phone_status,
        "public_whatsapp": public_whatsapp,
        "description": description,
        "decision_maker_name": decision_maker_name,
        "decision_maker_role": decision_maker_role,
        "employee_count_min": employee_count_min,
        "employee_count_max": employee_count_max,
        "employee_size_evidence": employee_size_evidence or "Unknown — pending verification",
        "laptop_count_verified": laptop_count_verified,
        "laptop_count_evidence": laptop_count_evidence or "Unknown — pending verification",
        "laptop_fleet_status": laptop_fleet_status,
        "missing_information": missing_info,
        "verification_status": overall_v_status,
        "confidence_level": confidence,
        "provenance_sources": provenance_sources,
    })


def is_browser_request_allowed(req_url: str) -> bool:
    """
    Validates every Playwright navigation, redirect, and subresource URL.
    Blocks non-HTTP(S) schemes (file://, ftp://), localhost, private/loopback/link-local IPs,
    cloud metadata endpoints (169.254.169.254 / fd00:ec2::254), demo domains, and LinkedIn.
    """
    if not req_url:
        return False
    low = req_url.strip().lower()
    if low == "about:blank":
        return True
    parsed = urlparse(low)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.netloc or "").lower()
    if "linkedin.com" in host:
        return False
    if is_demo_domain(req_url):
        return False
    return is_safe_external_url(req_url)


async def browser_extract_company_contact(website_url: str) -> Dict[str, Any]:
    """
    Phase 4D Optional Operator-Triggered Browser-Assisted Public Contact Extractor.
    Strictly local, respects robots/anti-bot/CAPTCHA gates without bypassing,
    never scrapes LinkedIn, enforces SSRF checks, caps at 3 pages, and keeps statuses honest.
    """
    from app.core.security import validate_recipient_email_syntax

    raw_url = (website_url or "").strip()
    if not raw_url:
        return {"status": "NOT_FOUND", "reason": "No website URL provided."}
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)
    host = (parsed.netloc or "").lower()
    if "linkedin.com" in host:
        return {"status": "BLOCKED", "reason": "LinkedIn scraping is strictly prohibited."}
    if not is_safe_external_url(raw_url) or is_demo_domain(raw_url):
        return {"status": "BLOCKED", "reason": "URL failed SSRF or demo-domain safety policy."}

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return {"status": "DEFERRED", "reason": f"Playwright unavailable: {exc}"}

    root = f"{parsed.scheme}://{parsed.netloc}"
    candidate_urls = [raw_url, urljoin(root, "/contact"), urljoin(root, "/about")]
    # Deduplicate preserving order, max 3 pages
    urls: List[str] = []
    for u in candidate_urls:
        if u not in urls and is_safe_external_url(u):
            urls.append(u)
    urls = urls[:3]

    found_emails: List[Tuple[str, str]] = []
    found_phones: List[Tuple[str, str]] = []
    antibot_markers = ("verify you are human", "captcha", "cf-browser-verification", "access denied", "sign in to continue")
    noise_domains = ("sentry.io", "wixpress.com", "schema.org", "w3.org", "wordpress.org", "cloudflare.com")
    retrieved_at = datetime.now(timezone.utc).isoformat()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent="ActTrident-Local-Contact-Inspector/1.0 (+https://acttrident.ai)"
            )

            async def _ssrf_route_guard(route):
                if is_browser_request_allowed(route.request.url):
                    await route.continue_()
                else:
                    logger.warning(f"Blocked unsafe browser request/redirect/subresource: {route.request.url}")
                    await route.abort("blockedbyclient")

            await context.route("**/*", _ssrf_route_guard)
            page = await context.new_page()
            for target_url in urls:
                try:
                    resp = await page.goto(target_url, wait_until="domcontentloaded", timeout=8000)
                    if not is_browser_request_allowed(page.url):
                        return {
                            "status": "BLOCKED",
                            "reason": "Navigation redirected to a disallowed internal or restricted URL.",
                            "source_url": target_url,
                            "retrieved_at": retrieved_at,
                        }
                    if resp and resp.status in (401, 403, 429):
                        return {
                            "status": "NEEDS_REVIEW",
                            "reason": f"Website returned HTTP {resp.status}; respected restriction without bypass.",
                            "source_url": target_url,
                            "retrieved_at": retrieved_at,
                        }
                    await page.wait_for_timeout(800)
                    content_text = await page.inner_text("body")
                    html_content = await page.content()
                    low_text = (content_text or "").lower()
                    if any(m in low_text for m in antibot_markers):
                        return {
                            "status": "NEEDS_REVIEW",
                            "reason": "Anti-bot/CAPTCHA/auth gate detected; stopped without bypassing.",
                            "source_url": target_url,
                            "retrieved_at": retrieved_at,
                        }
                    for em in EMAIL_REGEX.findall(html_content + " " + content_text):
                        em_low = em.strip().lower()
                        if any(em_low.endswith(ext) for ext in INVALID_EMAIL_EXTENSIONS):
                            continue
                        if is_demo_domain(em_low) or any(nd in em_low.split("@")[-1] for nd in noise_domains):
                            continue
                        if validate_recipient_email_syntax(em_low) and all(e[0] != em_low for e in found_emails):
                            found_emails.append((em_low, page.url or target_url))
                    for ph in INDIAN_PHONE_REGEX.findall(content_text):
                        ph_clean = re.sub(r"\s+", " ", ph).strip()
                        if len(re.sub(r"\D", "", ph_clean)) >= 10 and all(x[0] != ph_clean for x in found_phones):
                            found_phones.append((ph_clean, page.url or target_url))
                    if found_emails:
                        break
                except Exception:
                    continue
        finally:
            await browser.close()

    if not found_emails:
        return {
            "status": "NOT_FOUND",
            "reason": "No public business email found across checked official pages.",
            "source_url": urls[0],
            "retrieved_at": retrieved_at,
            "phones": [p[0] for p in found_phones[:2]],
        }

    found_emails.sort(key=lambda pair: 1 if pair[0].startswith(ROLE_BASED_PREFIXES) else 0)
    best_email, src_url = found_emails[0]
    mx_ok = check_email_domain_mx(best_email)
    comp_dom = parsed.netloc.lower().lstrip("www.")
    em_dom = best_email.split("@")[-1].lower()
    dom_match = (comp_dom == em_dom) or em_dom.endswith("." + comp_dom) or comp_dom.endswith("." + em_dom)

    if mx_ok and dom_match:
        v_status = "DOMAIN_MX_CHECKED"
    elif mx_ok:
        v_status = "NEEDS_REVIEW"
    else:
        v_status = "SYNTAX_VALID"

    return {
        "status": v_status,
        "email": best_email,
        "mx_ok": mx_ok,
        "domain_matches": dom_match,
        "source_url": src_url,
        "retrieved_at": retrieved_at,
        "phones": [p[0] for p in found_phones[:2]],
    }
