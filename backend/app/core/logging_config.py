import contextvars
import json
import logging
import re
from datetime import datetime, timezone

# Correlation ID propagated per HTTP request or background task
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Regex patterns to prevent secrets, tokens, or passwords from ever appearing in logs
SECRET_REDACTION_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r'("(?:password|secret|api_key|access_token|refresh_token|encrypted_value|authorization)"\s*:\s*")[^"]+(")', re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"((?:password|secret|api_key|token)=)[^\s&]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"enc:v1:[A-Za-z0-9_\-=]+"), "enc:v1:[REDACTED]"),
]


def redact_sensitive_text(text: str) -> str:
    if not text:
        return text
    sanitized = str(text)
    for pattern, replacement in SECRET_REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class StructuredJsonFormatter(logging.Formatter):
    """Formats application logs as structured JSON with correlation IDs and secret redaction."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_ctx.get("-"),
            "message": redact_sensitive_text(record.getMessage()),
        }
        if record.exc_info:
            log_obj["exception"] = redact_sensitive_text(self.formatException(record.exc_info))
        return json.dumps(log_obj, default=str)


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configures root logger with structured JSON output and secret redaction."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if not any(isinstance(h.formatter, StructuredJsonFormatter) for h in root_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJsonFormatter())
        root_logger.handlers = [handler]
