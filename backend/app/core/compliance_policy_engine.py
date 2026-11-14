import re
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.security import compute_content_hash, is_safe_external_url, sanitize_untrusted_text
from app.models.activity import SuppressionList
from app.core.audit import record_audit_log

logger = logging.getLogger(__name__)


class PolicyViolationError(ValueError):
    """Raised when an action violates ActTrident compliance, truthfulness, or safety policies."""
    def __init__(self, policy_rule: str, detail: str):
        super().__init__(f"Compliance Policy Violation [{policy_rule}]: {detail}")
        self.policy_rule = policy_rule
        self.detail = detail


# Forbidden deceptive phrases and fabricated attack allegations
FORBIDDEN_ATTACK_CLAIMS = [
    r"you(?:'ve| have)? suffered a (?:cyberattack|breach|ransomware|hack|data leak)",
    r"we detected (?:a breach|malware|compromise|infection) (?:on|in) your (?:network|systems|laptops)",
    r"your (?:network|domain|systems) (?:is|are) compromised",
    r"urgent security alert regarding your breach",
    r"confidential incident report for your company"
]

FORBIDDEN_PRODUCT_CLAIMS = [
    r"100%\s+unhackable",
    r"guarantee(?:s|d)?\s+zero\s+breaches",
    r"impossible to breach",
    r"certified\s+invulnerable",
]


class CompliancePolicyEngine:
    """
    Centralized automated policy interceptor enforcing:
    1. Truthfulness in marketing & outreach (no fabricated breaches or security alerts)
    2. Zero invented ActTrident product claims
    3. Strict laptop count evidence separation
    4. Mandatory human approval & immutable content hashing
    5. Immediate suppression list enforcement
    6. SSRF and prompt injection protection
    """

    @classmethod
    def validate_outreach_text(cls, subject: str, body: str, db: Optional[Session] = None, user_id: Optional[int] = None) -> None:
        combined = f"{subject}\n{body}".lower()

        # 1. Check for fabricated attack claims against prospect
        for pattern in FORBIDDEN_ATTACK_CLAIMS:
            if re.search(pattern, combined, re.IGNORECASE):
                msg = "Outreach messages must NEVER allege that a prospect company suffered a cyberattack or security breach without verified factual evidence."
                if db and user_id:
                    record_audit_log(db, "policy_violation_blocked", "outreach_content", "draft", user_id, {"rule": "NO_FABRICATED_BREACHES", "detail": msg})
                raise PolicyViolationError("NO_FABRICATED_BREACHES", msg)

        # 2. Check for deceptive security guarantees
        for pattern in FORBIDDEN_PRODUCT_CLAIMS:
            if re.search(pattern, combined, re.IGNORECASE):
                msg = "ActTrident features must never be described with impossible guarantees like '100% unhackable' or 'zero breaches guaranteed'."
                if db and user_id:
                    record_audit_log(db, "policy_violation_blocked", "outreach_content", "draft", user_id, {"rule": "NO_DECEPTIVE_GUARANTEES", "detail": msg})
                raise PolicyViolationError("NO_DECEPTIVE_GUARANTEES", msg)

    @classmethod
    def validate_laptop_evidence(cls, count: Optional[int], evidence: Optional[str]) -> bool:
        """
        Guarantees that a company is never labeled as having 5+ laptops without corroborated evidence.
        Returns True if legitimately verified, False otherwise.
        """
        if count is None:
            return False
        if count >= 5 and (not evidence or evidence.strip().lower() in ["none", "unknown", "n/a"]):
            raise PolicyViolationError(
                "VERIFIED_DEVICE_EVIDENCE_REQUIRED",
                f"Cannot certify company with {count} laptops without documented public evidence or company confirmation."
            )
        return count >= 5 and bool(evidence)

    @classmethod
    def validate_dispatch_authorization(cls, draft, db: Session) -> None:
        """Validates human approval, content hash, and suppression list before any transmission."""
        # Check human approval
        if getattr(draft, "approval_status", None) != "approved":
            raise PolicyViolationError("APPROVAL_REQUIRED", "Message has not been approved by an authorized manager.")

        # Check content hash
        current_hash = compute_content_hash([draft.subject, getattr(draft, "body_text", "")])
        if not getattr(draft, "approved_content_hash", None) or current_hash != draft.approved_content_hash:
            raise PolicyViolationError("CONTENT_TAMPERING_DETECTED", "Approved content hash mismatch. Content was modified post-approval.")

        # Check suppression
        recipient = getattr(draft, "recipient_email", None) or getattr(draft, "recipient_phone", None)
        if recipient:
            clean_rec = recipient.strip().lower()
            suppressed = db.query(SuppressionList).filter(SuppressionList.identifier == clean_rec).first()
            if suppressed:
                raise PolicyViolationError("SUPPRESSION_LIST_ENFORCED", f"Recipient {recipient} is on the suppression list: {suppressed.reason}")

    @classmethod
    def validate_url(cls, url: str) -> None:
        """Validates that a URL is a safe public target and blocks SSRF."""
        if not is_safe_external_url(url):
            raise PolicyViolationError("SSRF_ATTEMPT_BLOCKED", f"The URL {url} targets an internal, loopback, or non-permitted network destination.")
