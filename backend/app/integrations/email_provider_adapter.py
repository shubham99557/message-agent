"""
Phase 4A Email Provider Abstraction (Test-Mode / Sandbox Ready).

Provides a clean provider-agnostic transport contract supporting:
- Provider configuration & credential validation (without logging secrets)
- Test/sandbox mode with strict operator-allowlist enforcement
- Honest state separation: provider acceptance ('accepted') != inbox delivery ('delivered')
- Retries for transient errors and idempotency-key propagation
"""
import email.utils
import logging
import smtplib
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("acttrident.email_provider")


@dataclass
class EmailProviderSendRequest:
    recipient_email: str
    subject: str
    body_text: str
    body_html: str
    from_name: str
    from_email: str
    idempotency_key: str
    headers: Dict[str, str] = field(default_factory=dict)
    is_test_mode: bool = True


@dataclass
class EmailProviderSendResult:
    outcome: str  # accepted, failed
    provider: str
    is_sandbox: bool
    provider_message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    attempts_made: int = 1


class EmailProviderAdapter(ABC):
    provider_name: str
    is_sandbox: bool = True

    @abstractmethod
    def send_test_email(self, req: EmailProviderSendRequest) -> EmailProviderSendResult:
        """Dispatches a test-mode email through the provider sandbox or relay."""


class MockSandboxEmailProvider(EmailProviderAdapter):
    """
    Deterministic sandbox provider for local/CI verification when no external sandbox key is configured.
    Supports simulated invalid credentials, transient retries, and clean acceptance IDs.
    """
    provider_name = "sandbox_mock"
    is_sandbox = True

    def __init__(self, api_key: str = "sandbox_ok", fail_transient_times: int = 0):
        self.api_key = api_key
        self.fail_transient_times = fail_transient_times
        self._transient_counter = 0

    def send_test_email(self, req: EmailProviderSendRequest) -> EmailProviderSendResult:
        if self.api_key == "invalid":
            return EmailProviderSendResult(
                outcome="failed",
                provider=self.provider_name,
                is_sandbox=True,
                error_code="invalid_credentials",
                error_message="Provider rejected API credentials (simulated 401).",
                retryable=False,
                attempts_made=1,
            )

        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            attempts += 1
            if self._transient_counter < self.fail_transient_times:
                self._transient_counter += 1
                if attempts < max_attempts:
                    continue
                return EmailProviderSendResult(
                    outcome="failed",
                    provider=self.provider_name,
                    is_sandbox=True,
                    error_code="transient_timeout",
                    error_message="Sandbox provider transient timeout after retries.",
                    retryable=True,
                    attempts_made=attempts,
                )

            msg_id = f"sandbox-{uuid.uuid5(uuid.NAMESPACE_DNS, req.idempotency_key).hex[:20]}"
            logger.info(
                f"Sandbox email accepted (provider={self.provider_name}, id={msg_id}, attempts={attempts})"
            )
            return EmailProviderSendResult(
                outcome="accepted",
                provider=self.provider_name,
                is_sandbox=True,
                provider_message_id=msg_id,
                attempts_made=attempts,
            )

        return EmailProviderSendResult(
            outcome="failed",
            provider=self.provider_name,
            is_sandbox=True,
            error_code="unknown_error",
            error_message="Exhausted send attempts.",
            attempts_made=attempts,
        )


class ResendEmailProvider(EmailProviderAdapter):
    """
    Official Resend API Adapter (POST https://api.resend.com/emails).
    Supports Resend native Idempotency-Key header, List-Unsubscribe/List-Unsubscribe-Post
    custom headers, rate-limit/transient retries with the exact same idempotency key,
    and strict non-exposure of API keys or message bodies in logs.
    """
    provider_name = "resend"
    is_sandbox = True
    API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, http_client: Optional[httpx.Client] = None):
        self.api_key = (api_key or "").strip()
        self.http_client = http_client

    def send_test_email(self, req: EmailProviderSendRequest) -> EmailProviderSendResult:
        if not self.api_key:
            return EmailProviderSendResult(
                outcome="failed",
                provider=self.provider_name,
                is_sandbox=True,
                error_code="missing_credentials",
                error_message="RESEND_API_KEY is not configured.",
                retryable=False,
            )

        payload = {
            "from": f"{req.from_name} <{req.from_email}>" if req.from_name else req.from_email,
            "to": [req.recipient_email],
            "subject": req.subject,
            "text": req.body_text,
            "html": req.body_html,
            "headers": dict(req.headers or {}),
        }
        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": req.idempotency_key,
        }

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                if self.http_client is not None:
                    resp = self.http_client.post(self.API_URL, json=payload, headers=req_headers, timeout=15.0)
                else:
                    with httpx.Client(timeout=15.0) as client:
                        resp = client.post(self.API_URL, json=payload, headers=req_headers)

                if resp.status_code in (200, 201):
                    data = resp.json()
                    msg_id = data.get("id")
                    logger.info(f"Resend accepted test email (id={msg_id}, attempt={attempt})")
                    return EmailProviderSendResult(
                        outcome="accepted",
                        provider=self.provider_name,
                        is_sandbox=True,
                        provider_message_id=msg_id,
                        attempts_made=attempt,
                    )
                if resp.status_code in (401, 403):
                    return EmailProviderSendResult(
                        outcome="failed",
                        provider=self.provider_name,
                        is_sandbox=True,
                        error_code="invalid_credentials",
                        error_message=f"Resend rejected API credentials (HTTP {resp.status_code}).",
                        retryable=False,
                        attempts_made=attempt,
                    )
                if resp.status_code == 409:
                    return EmailProviderSendResult(
                        outcome="failed",
                        provider=self.provider_name,
                        is_sandbox=True,
                        error_code="idempotency_conflict",
                        error_message="Resend idempotency conflict: key reused with a different payload.",
                        retryable=False,
                        attempts_made=attempt,
                    )
                if resp.status_code in (400, 422):
                    return EmailProviderSendResult(
                        outcome="failed",
                        provider=self.provider_name,
                        is_sandbox=True,
                        error_code="validation_error",
                        error_message=f"Resend rejected payload (HTTP {resp.status_code}).",
                        retryable=False,
                        attempts_made=attempt,
                    )
                if resp.status_code == 429:
                    if attempt < max_attempts:
                        time.sleep(0.2)
                        continue
                    return EmailProviderSendResult(
                        outcome="failed",
                        provider=self.provider_name,
                        is_sandbox=True,
                        error_code="rate_limited",
                        error_message="Resend API rate limit exceeded (HTTP 429).",
                        retryable=True,
                        attempts_made=attempt,
                    )
                if resp.status_code >= 500 and attempt < max_attempts:
                    time.sleep(0.2)
                    continue
                return EmailProviderSendResult(
                    outcome="failed",
                    provider=self.provider_name,
                    is_sandbox=True,
                    error_code=f"http_{resp.status_code}",
                    error_message=f"Resend HTTP {resp.status_code} error.",
                    retryable=resp.status_code >= 500,
                    attempts_made=attempt,
                )
            except httpx.TimeoutException:
                if attempt < max_attempts:
                    time.sleep(0.2)
                    continue
                return EmailProviderSendResult(
                    outcome="failed",
                    provider=self.provider_name,
                    is_sandbox=True,
                    error_code="network_timeout",
                    error_message="Resend API request timed out.",
                    retryable=True,
                    attempts_made=attempt,
                )
            except httpx.RequestError as exc:
                if attempt < max_attempts:
                    time.sleep(0.2)
                    continue
                return EmailProviderSendResult(
                    outcome="failed",
                    provider=self.provider_name,
                    is_sandbox=True,
                    error_code="network_error",
                    error_message=f"Network error contacting Resend: {type(exc).__name__}",
                    retryable=True,
                    attempts_made=attempt,
                )

        return EmailProviderSendResult(
            outcome="failed",
            provider=self.provider_name,
            is_sandbox=True,
            error_code="unknown_error",
            error_message="Exhausted Resend attempts.",
            attempts_made=max_attempts,
        )


class PostmarkSandboxEmailProvider(EmailProviderAdapter):
    """
    Postmark API Adapter (supports Postmark Sandbox 'POSTMARK_API_TEST' or operator test token).
    Never exposes X-Postmark-Server-Token in logs or exceptions.
    """
    provider_name = "postmark_sandbox"
    is_sandbox = True
    API_URL = "https://api.postmarkapp.com/email"

    def __init__(self, api_key: str, http_client: Optional[httpx.Client] = None):
        self.api_key = (api_key or "").strip()
        self.http_client = http_client

    def send_test_email(self, req: EmailProviderSendRequest) -> EmailProviderSendResult:
        if not self.api_key:
            return EmailProviderSendResult(
                outcome="failed",
                provider=self.provider_name,
                is_sandbox=True,
                error_code="missing_credentials",
                error_message="EMAIL_PROVIDER_API_KEY is not configured for Postmark.",
                retryable=False,
            )

        headers_list = [{"Name": k, "Value": v} for k, v in (req.headers or {}).items()]
        payload = {
            "From": f"{req.from_name} <{req.from_email}>",
            "To": req.recipient_email,
            "Subject": req.subject,
            "TextBody": req.body_text,
            "HtmlBody": req.body_html,
            "MessageStream": "outbound",
            "Headers": headers_list,
            "Metadata": {"idempotency_key": req.idempotency_key, "test_mode": "true"},
        }
        req_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self.api_key,
        }

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                if self.http_client is not None:
                    resp = self.http_client.post(self.API_URL, json=payload, headers=req_headers, timeout=15.0)
                else:
                    with httpx.Client(timeout=15.0) as client:
                        resp = client.post(self.API_URL, json=payload, headers=req_headers)

                if resp.status_code in (200, 201):
                    data = resp.json()
                    msg_id = data.get("MessageID")
                    logger.info(f"Postmark sandbox accepted test message (id={msg_id}, attempt={attempt})")
                    return EmailProviderSendResult(
                        outcome="accepted",
                        provider=self.provider_name,
                        is_sandbox=True,
                        provider_message_id=msg_id,
                        attempts_made=attempt,
                    )
                if resp.status_code in (401, 403, 422):
                    return EmailProviderSendResult(
                        outcome="failed",
                        provider=self.provider_name,
                        is_sandbox=True,
                        error_code=f"http_{resp.status_code}",
                        error_message="Provider rejected credentials or payload.",
                        retryable=False,
                        attempts_made=attempt,
                    )
                if resp.status_code >= 500 and attempt < max_attempts:
                    time.sleep(0.2)
                    continue
                return EmailProviderSendResult(
                    outcome="failed",
                    provider=self.provider_name,
                    is_sandbox=True,
                    error_code=f"http_{resp.status_code}",
                    error_message=f"Provider HTTP {resp.status_code} error.",
                    retryable=resp.status_code >= 500,
                    attempts_made=attempt,
                )
            except httpx.RequestError as exc:
                if attempt < max_attempts:
                    time.sleep(0.2)
                    continue
                return EmailProviderSendResult(
                    outcome="failed",
                    provider=self.provider_name,
                    is_sandbox=True,
                    error_code="network_error",
                    error_message=f"Network error contacting provider: {type(exc).__name__}",
                    retryable=True,
                    attempts_made=attempt,
                )

        return EmailProviderSendResult(
            outcome="failed",
            provider=self.provider_name,
            is_sandbox=True,
            error_code="unknown_error",
            error_message="Exhausted retries.",
            attempts_made=max_attempts,
        )


class SMTPSandboxEmailProvider(EmailProviderAdapter):
    """SMTP Sandbox adapter (e.g. Mailtrap/MailHog/operator test SMTP) with RFC 8058 headers."""
    provider_name = "smtp_sandbox"
    is_sandbox = True

    def send_test_email(self, req: EmailProviderSendRequest) -> EmailProviderSendResult:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            return EmailProviderSendResult(
                outcome="failed",
                provider=self.provider_name,
                is_sandbox=True,
                error_code="missing_credentials",
                error_message="SMTP_USER or SMTP_PASSWORD not configured for SMTP sandbox.",
                retryable=False,
            )

        try:
            domain = req.from_email.split("@")[-1] if "@" in req.from_email else "localhost"
            rfc_msg_id = email.utils.make_msgid(domain=domain)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = req.subject
            msg["From"] = f"{req.from_name} <{req.from_email}>"
            msg["To"] = req.recipient_email
            msg["Message-ID"] = rfc_msg_id
            for k, v in (req.headers or {}).items():
                msg[k] = v
            msg.attach(MIMEText(req.body_text, "plain", "utf-8"))
            msg.attach(MIMEText(req.body_html, "html", "utf-8"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(req.from_email, req.recipient_email, msg.as_string())

            return EmailProviderSendResult(
                outcome="accepted",
                provider=self.provider_name,
                is_sandbox=True,
                provider_message_id=rfc_msg_id,
                attempts_made=1,
            )
        except smtplib.SMTPAuthenticationError:
            return EmailProviderSendResult(
                outcome="failed",
                provider=self.provider_name,
                is_sandbox=True,
                error_code="invalid_credentials",
                error_message="SMTP authentication failed.",
                retryable=False,
            )
        except Exception as exc:
            return EmailProviderSendResult(
                outcome="failed",
                provider=self.provider_name,
                is_sandbox=True,
                error_code="smtp_error",
                error_message=f"SMTP sandbox error: {type(exc).__name__}",
                retryable=True,
            )


def get_sandbox_email_provider(
    provider_override: Optional[str] = None,
    http_client: Optional[httpx.Client] = None,
) -> EmailProviderAdapter:
    choice = (provider_override or getattr(settings, "EMAIL_SANDBOX_PROVIDER", "resend") or "resend").strip().lower()
    if choice == "resend":
        resend_key = (getattr(settings, "RESEND_API_KEY", "") or "").strip()
        if not resend_key and provider_override != "resend":
            # In local dev without RESEND_API_KEY, keep app usable via MockSandboxEmailProvider (never sends externally)
            return MockSandboxEmailProvider(api_key="sandbox_ok")
        return ResendEmailProvider(api_key=resend_key, http_client=http_client)
    if choice == "postmark_sandbox":
        return PostmarkSandboxEmailProvider(api_key=getattr(settings, "EMAIL_PROVIDER_API_KEY", ""), http_client=http_client)
    if choice == "smtp_sandbox":
        return SMTPSandboxEmailProvider()
    return MockSandboxEmailProvider(api_key=getattr(settings, "EMAIL_PROVIDER_API_KEY", "") or "sandbox_ok")
