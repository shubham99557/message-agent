"""
Phase 4A Read-Only DNS Authentication Preflight Service (SPF, DKIM, DMARC).

Inspects TXT records via dnspython, parses actual policy directives,
and reports errors, warnings, and actionable recommendations.
Never modifies DNS records and never treats mere record presence as valid.
"""
import re
from typing import Any, Callable, Dict, List, Optional

import dns.exception
import dns.resolver


def default_txt_lookup(qname: str) -> List[str]:
    """Queries live DNS TXT records in read-only mode using dnspython."""
    try:
        answers = dns.resolver.resolve(qname, "TXT", lifetime=5.0)
        records: List[str] = []
        for rdata in answers:
            # Join multi-string TXT chunks per RFC 7208
            chunks = [s.decode("utf-8", errors="replace") if isinstance(s, bytes) else str(s) for s in rdata.strings]
            records.append("".join(chunks))
        return records
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []


def check_spf(domain: str, lookup_fn: Callable[[str], List[str]] = default_txt_lookup) -> Dict[str, Any]:
    txt_records = lookup_fn(domain)
    spf_records = [r.strip() for r in txt_records if r.strip().lower().startswith("v=spf1")]

    errors: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []
    parsed_policy: Dict[str, Any] = {}

    if not spf_records:
        errors.append(f"No SPF (v=spf1) TXT record found for {domain}.")
        recommendations.append(f"Publish a single TXT record on {domain}: 'v=spf1 include:<your-provider> -all'.")
        return {
            "found": False,
            "valid": False,
            "records": [],
            "parsed_policy": parsed_policy,
            "errors": errors,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    if len(spf_records) > 1:
        errors.append(f"Multiple SPF records found ({len(spf_records)}); RFC 7208 treats this as PermError.")
        recommendations.append("Merge all SPF mechanisms into a single v=spf1 TXT record.")

    primary = spf_records[0]
    tokens = primary.split()
    includes = [t.split(":", 1)[1] for t in tokens if t.lower().startswith("include:") and ":" in t]
    all_mech = next((t.lower() for t in tokens if t.lower() in ("-all", "~all", "?all", "+all")), None)
    parsed_policy = {"raw": primary, "includes": includes, "all_mechanism": all_mech}

    if all_mech == "+all":
        errors.append("SPF ends with '+all', allowing any server worldwide to spoof this domain.")
        recommendations.append("Replace '+all' with '-all' (hard fail) or '~all' (soft fail).")
    elif all_mech == "?all":
        warnings.append("SPF ends with '?all' (neutral), providing no spoofing protection.")
        recommendations.append("Change '?all' to '~all' or '-all'.")
    elif all_mech == "~all":
        warnings.append("SPF uses '~all' (softfail). Consider '-all' once all legitimate senders are confirmed.")
    elif all_mech is None and "redirect=" not in primary.lower():
        warnings.append("SPF record has no explicit 'all' or 'redirect=' mechanism.")
        recommendations.append("Add '-all' or '~all' at the end of the SPF record.")

    return {
        "found": True,
        "valid": len(errors) == 0,
        "records": spf_records,
        "parsed_policy": parsed_policy,
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def check_dkim(domain: str, selector: str = "default", lookup_fn: Callable[[str], List[str]] = default_txt_lookup) -> Dict[str, Any]:
    clean_sel = (selector or "default").strip()
    qname = f"{clean_sel}._domainkey.{domain}"
    txt_records = lookup_fn(qname)

    errors: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []
    parsed_policy: Dict[str, Any] = {"selector": clean_sel, "query_name": qname}

    if not txt_records:
        errors.append(f"No DKIM TXT record found at {qname}.")
        recommendations.append(f"Generate a 2048-bit DKIM keypair with your email provider and publish TXT record at {qname}.")
        return {
            "found": False,
            "valid": False,
            "records": [],
            "parsed_policy": parsed_policy,
            "errors": errors,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    primary = txt_records[0].strip()
    tags = {}
    for part in primary.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            tags[k.strip().lower()] = v.strip()

    parsed_policy.update({"version": tags.get("v"), "key_type": tags.get("k", "rsa"), "has_public_key": bool(tags.get("p"))})

    if "p" not in tags:
        errors.append("DKIM record is missing the 'p=' public key tag.")
    elif tags["p"] == "":
        errors.append("DKIM public key 'p=' is empty (key has been revoked per RFC 6376).")
        recommendations.append(f"Publish an active DKIM public key at {qname} or switch to an active selector.")
    elif len(tags["p"]) < 128:
        warnings.append("DKIM public key appears shorter than 1024/2048-bit standard; verify 2048-bit key length.")

    return {
        "found": True,
        "valid": len(errors) == 0,
        "records": txt_records,
        "parsed_policy": parsed_policy,
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def check_dmarc(domain: str, lookup_fn: Callable[[str], List[str]] = default_txt_lookup) -> Dict[str, Any]:
    qname = f"_dmarc.{domain}"
    txt_records = lookup_fn(qname)
    dmarc_records = [r.strip() for r in txt_records if r.strip().lower().startswith("v=dmarc1")]

    errors: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []
    parsed_policy: Dict[str, Any] = {"query_name": qname}

    if not dmarc_records:
        errors.append(f"No DMARC (v=DMARC1) TXT record found at {qname}.")
        recommendations.append(f"Publish TXT at {qname}: 'v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain}; pct=100'.")
        return {
            "found": False,
            "valid": False,
            "records": [],
            "parsed_policy": parsed_policy,
            "errors": errors,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    if len(dmarc_records) > 1:
        errors.append(f"Multiple DMARC records found ({len(dmarc_records)}) at {qname}.")

    primary = dmarc_records[0]
    tags = {}
    for part in primary.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            tags[k.strip().lower()] = v.strip()

    policy = (tags.get("p") or "").lower()
    rua = tags.get("rua")
    pct = tags.get("pct", "100")
    parsed_policy.update({"policy": policy, "rua": rua, "pct": pct, "sp": tags.get("sp")})

    if policy not in ("none", "quarantine", "reject"):
        errors.append(f"DMARC record is missing a valid 'p=' policy (found: '{policy}').")
    elif policy == "none":
        warnings.append("DMARC policy is 'p=none' (monitoring only; does not block spoofing).")
        recommendations.append("Advance DMARC policy from 'p=none' to 'p=quarantine' and then 'p=reject' after reviewing reports.")

    if not rua:
        warnings.append("DMARC record has no 'rua=' aggregate reporting URI.")
        recommendations.append(f"Add 'rua=mailto:dmarc@{domain}' to receive delivery/alignment reports.")

    return {
        "found": True,
        "valid": len(errors) == 0,
        "records": dmarc_records,
        "parsed_policy": parsed_policy,
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def run_domain_auth_preflight(
    domain: str,
    dkim_selector: str = "resend",
    lookup_fn: Callable[[str], List[str]] = default_txt_lookup,
) -> Dict[str, Any]:
    clean_domain = (domain or "").strip().lower().lstrip("@")
    if not clean_domain or not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", clean_domain):
        raise ValueError(f"Invalid domain for DNS preflight check: '{domain}'")

    spf = check_spf(clean_domain, lookup_fn=lookup_fn)
    dkim = check_dkim(clean_domain, selector=dkim_selector, lookup_fn=lookup_fn)
    dmarc = check_dmarc(clean_domain, lookup_fn=lookup_fn)

    all_errors = spf["errors"] + dkim["errors"] + dmarc["errors"]
    all_warnings = spf["warnings"] + dkim["warnings"] + dmarc["warnings"]
    overall_ready = spf["valid"] and dkim["valid"] and dmarc["valid"]

    resend_guidance = {
        "provider": "resend",
        "domain_verified_in_resend": False,
        "required_records_from_resend_dashboard": [
            {
                "type": "TXT",
                "host": f"{dkim_selector}._domainkey.{clean_domain}",
                "purpose": "Resend DKIM public key (obtain exact 'p=' value from Resend Dashboard -> Domains)",
            },
            {
                "type": "TXT",
                "host": f"send.{clean_domain}",
                "purpose": "Resend Return-Path SPF record (e.g. 'v=spf1 include:amazonses.com ~all' from Resend Dashboard)",
            },
            {
                "type": "MX",
                "host": f"send.{clean_domain}",
                "purpose": "Resend bounce feedback MX record (exact priority/target from Resend Dashboard)",
            },
            {
                "type": "TXT",
                "host": f"_dmarc.{clean_domain}",
                "purpose": "DMARC alignment policy ('v=DMARC1; p=quarantine;' or stricter)",
            },
        ],
        "note": "Do not assume selector 'default' for Resend; verify the exact selector and records in the Resend Dashboard.",
    }

    return {
        "domain": clean_domain,
        "dkim_selector": dkim_selector,
        "read_only": True,
        "overall_ready": overall_ready,
        "spf": spf,
        "dkim": dkim,
        "dmarc": dmarc,
        "resend_guidance": resend_guidance,
        "errors_count": len(all_errors),
        "warnings_count": len(all_warnings),
    }
