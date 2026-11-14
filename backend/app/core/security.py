import re
import socket
import ipaddress
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
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
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


# SSRF Guard for external URL fetching
DISALLOWED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal",
    "169.254.169.254"
}


def is_safe_external_url(url: str) -> bool:
    """Validates that a URL is a legitimate public web resource and not an SSRF attempt."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower()
        if hostname_lower in DISALLOWED_HOSTS or hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
            return False

        # Resolve IP to check for private / loopback IP spaces
        try:
            ip_info = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip_info)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                return False
        except Exception:
            # If resolution fails, treat as unresolvable / unsafe
            return False

        return True
    except Exception:
        return False


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
    """Sanitizes text retrieved from untrusted external websites to neutralize prompt injections."""
    if not content:
        return ""
    text = content[:max_chars]
    for pattern in SUSPICIOUS_PROMPT_PATTERNS:
        text = re.sub(pattern, "[FILTERED_INSTRUCTION]", text, flags=re.IGNORECASE)
    return text
