import re
import socket
import ipaddress
import hashlib
import hmac
import secrets
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any, Tuple
import bcrypt
import jwt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


def generate_refresh_token_string() -> str:
    """Generates a cryptographically secure random token string for refresh token handling."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Computes a SHA-256 hash of a refresh token to safely persist in database."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def compute_content_hash(text_parts: List[str]) -> str:
    """Computes a canonical SHA-256 hash over message components to guarantee immutability after approval."""
    combined = "\n---\n".join((p or "").strip() for p in text_parts)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def verify_meta_hmac_signature(payload: bytes, signature_header: Optional[str], app_secret: str) -> bool:
    """Verifies that an incoming Meta WhatsApp webhook payload was signed by Meta using HMAC-SHA256."""
    if not app_secret or not signature_header:
        return False

    # Signature format: sha256=<hex_digest>
    expected_prefix = "sha256="
    if not signature_header.startswith(expected_prefix):
        return False

    received_hash = signature_header[len(expected_prefix):].strip()
    mac = hmac.new(app_secret.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
    computed_hash = mac.hexdigest()

    return hmac.compare_digest(received_hash.lower(), computed_hash.lower())


# SSRF Guard for external URL fetching
DISALLOWED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal",
    "169.254.169.254", "instance-data", "metadata"
}

DISALLOWED_TLDS = (".local", ".internal", ".localhost", ".arpa", ".test", ".example", ".invalid")

DISALLOWED_PORTS = {22, 25, 110, 143, 465, 587, 993, 995, 2375, 2376, 5432, 6379, 8000, 27017, 11211}


def is_safe_external_url(url: str) -> bool:
    """
    Validates that a URL is a legitimate public web resource and not an SSRF attempt.
    Hardens against private IP ranges, loopback, link-local, cloud metadata,
    IPv4 and IPv6 spaces, restricted ports, and internal domain patterns.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower().strip()
        if hostname_lower in DISALLOWED_HOSTS:
            return False

        if any(hostname_lower.endswith(tld) for tld in DISALLOWED_TLDS):
            return False

        port = parsed.port
        if port and port in DISALLOWED_PORTS:
            return False

        # If hostname is a literal IP address
        try:
            ip_literal = ipaddress.ip_address(hostname_lower)
            if (
                ip_literal.is_private
                or ip_literal.is_loopback
                or ip_literal.is_link_local
                or ip_literal.is_reserved
                or ip_literal.is_multicast
            ):
                return False
            # Check IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
            if isinstance(ip_literal, ipaddress.IPv6Address) and ip_literal.ipv4_mapped:
                if (
                    ip_literal.ipv4_mapped.is_private
                    or ip_literal.ipv4_mapped.is_loopback
                    or ip_literal.ipv4_mapped.is_link_local
                ):
                    return False
        except ValueError:
            # Not an IP literal, proceed to DNS resolution
            pass

        # Resolve all IPv4 and IPv6 addresses via getaddrinfo to defend against dual-stack SSRF
        try:
            addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            if not addr_info:
                return False

            for item in addr_info:
                sockaddr = item[4]
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)

                # Check private, loopback, link-local, or reserved
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_reserved
                    or ip_obj.is_multicast
                ):
                    return False

                # Check IPv4-mapped IPv6 address spaces
                if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
                    if (
                        ip_obj.ipv4_mapped.is_private
                        or ip_obj.ipv4_mapped.is_loopback
                        or ip_obj.ipv4_mapped.is_link_local
                    ):
                        return False

                # Explicit AWS/GCP/Azure link-local metadata guard
                if str(ip_obj) == "169.254.169.254" or str(ip_obj) == "fd00:ec2::254":
                    return False

        except Exception:
            # If DNS resolution fails, fail closed (unsafe)
            return False

        return True
    except Exception:
        return False


async def safe_fetch_untrusted_url(
    url: str,
    max_bytes: int = 50000,
    timeout_seconds: float = 8.0,
    max_redirects: int = 3,
    allowed_content_types: Optional[List[str]] = None
) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Safely retrieves public web content while defending against:
    - DNS rebinding & private/internal IPs
    - Redirect-based SSRF (revalidating every hop)
    - Excessive redirects
    - Oversized responses (memory exhaustion)
    - Unexpected content types (e.g. binary downloads)
    - Excessive request duration

    Returns: (success: bool, content: Optional[str], final_url: Optional[str], error_message: Optional[str])
    """
    import httpx
    from urllib.parse import urljoin

    if allowed_content_types is None:
        allowed_content_types = ["text/html", "text/plain", "application/xhtml+xml", "application/json"]

    current_url = url
    redirect_count = 0

    try:
        # Use follow_redirects=False to manually inspect every hop
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            while redirect_count <= max_redirects:
                if not is_safe_external_url(current_url):
                    return False, None, current_url, f"SSRF security check rejected destination URL: {current_url}"

                headers = {"User-Agent": "ActTrident-Outreach-Bot/2.0 (+https://acttrident.ai)"}
                resp = await client.get(current_url, headers=headers)

                # Check for 3xx redirects
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location")
                    if not location:
                        return False, None, current_url, "Redirect response missing Location header"

                    redirect_count += 1
                    if redirect_count > max_redirects:
                        return False, None, current_url, f"Exceeded maximum redirect limit ({max_redirects})"

                    # Resolve relative redirect URLs against current URL
                    current_url = urljoin(current_url, location)
                    continue

                if resp.status_code != 200:
                    return False, None, current_url, f"Remote server returned HTTP {resp.status_code}"

                # Validate content-type
                content_type = resp.headers.get("Content-Type", "").lower()
                is_allowed_type = any(act in content_type for act in allowed_content_types)
                if content_type and not is_allowed_type:
                    return False, None, current_url, f"Disallowed Content-Type '{content_type}'"

                # Cap response body size to prevent memory exhaustion
                body_text = resp.text[:max_bytes]
                return True, body_text, current_url, None

            return False, None, current_url, f"Exceeded maximum redirect hops ({max_redirects})"
    except httpx.TimeoutException:
        return False, None, current_url, f"Request timed out after {timeout_seconds}s"
    except Exception as exc:
        return False, None, current_url, f"Network error during safe fetch: {str(exc)}"


# Prompt Injection Defense: Delimit and sanitize untrusted external website content
SUSPICIOUS_PROMPT_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s*prompt",
    r"you\s+are\s+now\s+a",
    r"bypass\s+all\s+rules",
    r"disregard\s+(the\s+)?above",
    r"roleplay\s+as",
    r"developer\s+mode",
]


def sanitize_untrusted_text(content: str, max_chars: int = 4000) -> str:
    """Sanitizes text retrieved from untrusted external websites to neutralize XSS and prompt injections."""
    if not content:
        return ""
    text = content[:max_chars]
    # Strip executable HTML/script/style/iframe blocks and javascript: URIs
    text = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>", " ", text)
    text = re.sub(r"(?i)javascript\s*:", "[FILTERED_URI]", text)
    for pattern in SUSPICIOUS_PROMPT_PATTERNS:
        text = re.sub(pattern, "[FILTERED_INSTRUCTION]", text, flags=re.IGNORECASE)
    return text.strip()
