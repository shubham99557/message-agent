"""
Central Approved ActTrident Product-Claims Registry.
Enforces non-negotiable truthfulness rule 3.5:
Every outreach message must use only approved and current product descriptions.
Never invent capabilities, certifications, customer references, pricing, or unverified offers.
"""
from typing import Dict, List, Any

# Central approved product capabilities
APPROVED_PRODUCT_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "runtime_workspace_protection": {
        "title": "Runtime Workspace Protection",
        "description": "Non-intrusive runtime protection for distributed company laptops that isolates browser workspaces and prevents unauthorized corporate data exfiltration.",
        "target_audience": "Software engineering, cloud infrastructure, and IT development teams",
        "is_approved": True,
    },
    "browser_credential_isolation": {
        "title": "Zero-Trust Browser Credential Isolation",
        "description": "Safeguards cloud credentials and sensitive web sessions against session hijacking, malicious browser extensions, and unauthorized copy/paste operations.",
        "target_audience": "Companies managing sensitive client deliverables and corporate web accounts",
        "is_approved": True,
    },
    "device_posture_verification": {
        "title": "Centralized Device Posture Verification",
        "description": "Continuous compliance verification ensuring that all laptops accessing company resources meet verified security health baselines.",
        "target_audience": "Hybrid and remote engineering workforces with 5+ company-managed laptops",
        "is_approved": True,
    },
}

# Central approved evaluation program details
APPROVED_EVALUATION_OFFER = {
    "program_name": "ActTrident 90-Day Free Product Evaluation",
    "duration_days": 90,
    "eligibility_requirement": "Eligible technology and business organizations managing a minimum verified fleet of 5 company laptops",
    "cost": "Free / zero-obligation evaluation with full technical support",
    "commitment": "Zero obligation, technical onboarding, and posture assessment",
    "is_approved": True,
}

# Disallowed claims (strictly prohibited from entering outreach copy)
DISALLOWED_CLAIMS: List[str] = [
    "100% hack-proof",
    "unbreakable security",
    "guaranteed compliance with zero effort",
    "military grade encryption",
    "instant zero-day immunity",
    "unlimited free trial for everyone",
    "official partner of Google/Microsoft/Apple (unless verified)",
    "certified SOC2 Type II / ISO 27001 (unless verified corporate certificate provided)",
]


def get_approved_claims_summary() -> str:
    """Returns a consolidated summary of approved product claims for AI prompts."""
    from app.core.config import settings
    caps = "\n".join([
        f"- {c['title']}: {c['description']}"
        for c in APPROVED_PRODUCT_CAPABILITIES.values()
        if c.get("is_approved")
    ])
    allow_eval = getattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", False)
    eval_text = ""
    if allow_eval and APPROVED_EVALUATION_OFFER.get("is_approved"):
        eval_text = (
            f"\n\nApproved Evaluation Program:\n"
            f"- {APPROVED_EVALUATION_OFFER['program_name']}: {APPROVED_EVALUATION_OFFER['eligibility_requirement']}. {APPROVED_EVALUATION_OFFER['cost']}."
        )
    return f"Approved Capabilities:\n{caps}{eval_text}"


def validate_message_against_claims(message_text: str) -> tuple[bool, List[str]]:
    """Checks whether outreach copy contains prohibited exaggerated claims or unauthorized offers."""
    from app.core.config import settings

    violations: List[str] = []
    text_lower = message_text.lower()
    for claim in DISALLOWED_CLAIMS:
        if claim.lower() in text_lower:
            violations.append(f"Prohibited claim detected: '{claim}'")

    if not getattr(settings, "ALLOW_90_DAY_EVALUATION_OFFER", False) and "90-day" in text_lower:
        violations.append("Prohibited claim detected: 90-day evaluation offer is disabled by administrative policy")

    return len(violations) == 0, violations
