import pytest
from app.core.compliance_policy_engine import CompliancePolicyEngine, PolicyViolationError


def test_compliance_blocks_fabricated_breach_claims():
    """Verify that outreach falsely claiming a company suffered a breach is rejected."""
    bad_subject = "Urgent Security Alert regarding your breach"
    bad_body = "Hello Amitabh, we detected a breach in your network yesterday and want to offer ActTrident."

    with pytest.raises(PolicyViolationError) as exc_info:
        CompliancePolicyEngine.validate_outreach_text(bad_subject, bad_body)
    assert "NO_FABRICATED_BREACHES" in str(exc_info.value)


def test_compliance_blocks_impossible_guarantees():
    """Verify that claims like '100% unhackable' are blocked."""
    subject = "ActTrident Product Overview"
    body = "Our platform guarantees zero breaches and makes your browser 100% unhackable."

    with pytest.raises(PolicyViolationError) as exc_info:
        CompliancePolicyEngine.validate_outreach_text(subject, body)
    assert "NO_DECEPTIVE_GUARANTEES" in str(exc_info.value)


def test_compliance_requires_laptop_evidence():
    """Verify that labeling a company with 5+ laptops without evidence is blocked."""
    with pytest.raises(PolicyViolationError) as exc_info:
        CompliancePolicyEngine.validate_laptop_evidence(count=12, evidence="Unknown")
    assert "VERIFIED_DEVICE_EVIDENCE_REQUIRED" in str(exc_info.value)

    # Valid documented evidence passes
    assert CompliancePolicyEngine.validate_laptop_evidence(
        count=12,
        evidence="MCA filing audits 12 company-issued Dell Latitude laptops"
    ) is True


def test_compliance_blocks_ssrf_urls():
    """Verify that SSRF target URLs are blocked by the policy engine."""
    with pytest.raises(PolicyViolationError) as exc_info:
        CompliancePolicyEngine.validate_url("http://127.0.0.1:8000/api/v1/auth")
    assert "SSRF_ATTEMPT_BLOCKED" in str(exc_info.value)

    with pytest.raises(PolicyViolationError) as exc_info:
        CompliancePolicyEngine.validate_url("http://169.254.169.254/latest/meta-data")
    assert "SSRF_ATTEMPT_BLOCKED" in str(exc_info.value)
