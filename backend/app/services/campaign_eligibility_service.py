"""
Campaign lead eligibility and cross-campaign contact guard.

One place decides whether a company may be added to (or emailed from) a campaign, so
the "Add Companies" picker, the add-recipients API and the send pipeline all agree.

Rules (each failing rule yields a machine code + human-readable reason):
  demo_fixture            Demo / fixture companies are never outreach targets.
  no_email                No usable email (contact, public or decision-maker).
  suppressed              Email is on the global suppression list (opted out / bounced).
  already_in_campaign     Already a recipient of this campaign.
  in_other_campaign       Already a recipient of another campaign that is not finished.
  recently_contacted      Emailed or WhatsApp'd (for real, not simulated) in the last 30 days.
  unverified_fleet        Live campaign requires verified 5+ laptops (pre-existing rule).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.activity import SuppressionList
from app.models.campaign import Campaign, CampaignRecipient, CampaignLeadSource
from app.models.company import Company, CompanyContact
from app.models.email import EmailDraft
from app.models.whatsapp import WhatsAppMessage

RECENT_CONTACT_WINDOW_DAYS = 30

# Campaigns in these states no longer contact anyone, so they don't block other campaigns.
FINISHED_CAMPAIGN_STATUSES = ("completed", "failed", "stopped")

# Draft states that mean an email actually left (or is leaving) the system.
# "simulated" is excluded on purpose: nothing was delivered.
CONTACTED_EMAIL_STATUSES = ("sending", "sent", "delivered", "bounced")
CONTACTED_WHATSAPP_STATUSES = ("sent",)


@dataclass
class LeadEligibility:
    company_id: int
    eligible: bool = True
    reasons: List[Dict[str, str]] = field(default_factory=list)

    ignored: frozenset = frozenset()

    def block(self, code: str, message: str) -> None:
        if code in self.ignored:
            return
        self.eligible = False
        self.reasons.append({"code": code, "message": message})


def company_email(company: Company, contacts: Optional[List[CompanyContact]] = None) -> Optional[str]:
    """
    The address a campaign draft will actually use. Campaign recipients are added without a
    contact_id, so the email generator falls back to public_email, then decision_maker_email.
    (`contacts` is accepted for API compatibility but intentionally not used.)
    """
    for value in (company.public_email, company.decision_maker_email):
        if value and value.strip():
            return value.strip()
    return None


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evaluate_lead_eligibility(
    db: Session,
    campaign: Campaign,
    companies: Iterable[Company],
    now: Optional[datetime] = None,
    ignore: Iterable[str] = (),
) -> Dict[int, LeadEligibility]:
    """
    Evaluates every company against the campaign rules using batched queries.
    `ignore` lists rule codes the caller does not enforce (e.g. the multi-channel
    autonomous agent ignores "no_email" because it can still reach a lead on WhatsApp).
    """
    ignore = set(ignore)
    companies = list(companies)
    if not companies:
        return {}
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RECENT_CONTACT_WINDOW_DAYS)
    ids = [c.id for c in companies]

    emails = {c.id: company_email(c) for c in companies}
    lowered = {e.lower() for e in emails.values() if e}

    suppressed = set()
    if lowered:
        suppressed = {
            row.identifier.lower()
            for row in db.query(SuppressionList.identifier)
            .filter(func.lower(SuppressionList.identifier).in_(lowered))
            .all()
        }

    # Memberships in this and other campaigns
    in_this = set()
    in_other: Dict[int, str] = {}
    for rec, camp in (
        db.query(CampaignRecipient, Campaign)
        .join(Campaign, Campaign.id == CampaignRecipient.campaign_id)
        .filter(CampaignRecipient.company_id.in_(ids))
        .all()
    ):
        if camp.id == campaign.id:
            in_this.add(rec.company_id)
        elif camp.status not in FINISHED_CAMPAIGN_STATUSES:
            in_other.setdefault(rec.company_id, camp.name)

    # Real outreach within the window, by company or by the same email address
    recent: Dict[int, datetime] = {}
    email_filters = [EmailDraft.company_id.in_(ids)]
    if lowered:
        email_filters.append(func.lower(EmailDraft.recipient_email).in_(lowered))
    for d in (
        db.query(EmailDraft)
        .filter(
            or_(*email_filters),
            EmailDraft.approval_status.in_(CONTACTED_EMAIL_STATUSES),
        )
        .all()
    ):
        # A send stuck in "sending" (crash mid-dispatch) is never reset, so it is bounded
        # by the same window via updated_at instead of blocking the company forever.
        when = _as_aware(d.sent_at) or _as_aware(d.updated_at)
        if when is None or when < cutoff:
            continue
        targets = {d.company_id}
        if d.recipient_email:
            low = d.recipient_email.strip().lower()
            targets |= {cid for cid, e in emails.items() if e and e.lower() == low}
        for cid in targets:
            if cid in emails:
                recent[cid] = max(recent.get(cid, when or now), when or now)

    for m in (
        db.query(WhatsAppMessage)
        .filter(
            WhatsAppMessage.company_id.in_(ids),
            WhatsAppMessage.approval_status.in_(CONTACTED_WHATSAPP_STATUSES),
            WhatsAppMessage.sent_at.isnot(None),
        )
        .all()
    ):
        when = _as_aware(m.sent_at)
        if when and when >= cutoff:
            recent[m.company_id] = max(recent.get(m.company_id, when), when)

    live_requires_verified = (
        campaign.status in ("active", "running") and (campaign.min_devices or 0) >= 5
    )

    results: Dict[int, LeadEligibility] = {}
    for c in companies:
        r = LeadEligibility(company_id=c.id, ignored=frozenset(ignore))
        if c.is_demo or c.verification_status == "demo_fixture":
            r.block("demo_fixture", "Demo fixture company: cannot be added to campaigns.")
        email = emails.get(c.id)
        if not email:
            r.block("no_email", "No email address on file.")
        elif email.lower() in suppressed:
            r.block("suppressed", f"{email} has opted out or bounced (suppression list).")
        if c.id in in_this:
            r.block("already_in_campaign", "Already in this campaign.")
        if c.id in in_other:
            r.block("in_other_campaign", f"Already in active campaign \"{in_other[c.id]}\".")
        if c.id in recent:
            r.block(
                "recently_contacted",
                f"Contacted on {recent[c.id].date().isoformat()} (within {RECENT_CONTACT_WINDOW_DAYS} days).",
            )
        if live_requires_verified and (not c.has_verified_5_plus_laptops or c.verification_status != "verified"):
            r.block("unverified_fleet", "Live campaign requires verified 5+ laptops (unverified fleet status).")
        results[c.id] = r
    return results


def find_recent_contact_conflict(db: Session, draft: EmailDraft, now: Optional[datetime] = None) -> Optional[str]:
    """
    Send-time guard for campaign emails: returns a reason string if the same company or
    email address already got a real email in the last 30 days from a *different* campaign
    or from outside any campaign, or is being sent one right now.

    Drafts with no campaign (manual one-offs, the follow-up cadence) are not blocked here:
    follow-ups are intentionally sent 3-5 days after the first touch and are human-approved.
    Repeat emails within the same campaign are likewise allowed.
    """
    if not draft.campaign_id:
        return None
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RECENT_CONTACT_WINDOW_DAYS)
    filters = [EmailDraft.company_id == draft.company_id]
    if draft.recipient_email and draft.recipient_email.strip():
        filters.append(func.lower(EmailDraft.recipient_email) == draft.recipient_email.strip().lower())

    for other in (
        db.query(EmailDraft)
        .filter(
            EmailDraft.id != draft.id,
            or_(EmailDraft.campaign_id.is_(None), EmailDraft.campaign_id != draft.campaign_id),
            or_(*filters),
            EmailDraft.approval_status.in_(CONTACTED_EMAIL_STATUSES),
        )
        .all()
    ):
        when = _as_aware(other.sent_at) or _as_aware(other.updated_at)
        if when is None or when < cutoff:
            continue
        if other.approval_status == "sending":
            return f"Another email to this company is being sent from another campaign (draft #{other.id})."
        return (
            f"This company was already emailed on {when.date().isoformat()} (draft #{other.id}"
            f"{', campaign #' + str(other.campaign_id) if other.campaign_id else ''}); "
            f"{RECENT_CONTACT_WINDOW_DAYS}-day cooldown applies."
        )
    return None


def link_leads_to_campaign(
    db: Session,
    campaign_id: Optional[int],
    company_ids: Iterable[int],
    source: str = "discovery_pipeline",
    discovery_run_id: Optional[int] = None,
) -> int:
    """Records that these companies were discovered for a campaign. Idempotent; commits."""
    if not campaign_id:
        return 0
    ids = {cid for cid in company_ids if cid}
    if not ids or not db.query(Campaign.id).filter(Campaign.id == campaign_id).first():
        return 0
    existing = {
        row.company_id
        for row in db.query(CampaignLeadSource.company_id)
        .filter(CampaignLeadSource.campaign_id == campaign_id, CampaignLeadSource.company_id.in_(ids))
        .all()
    }
    new_rows = [
        CampaignLeadSource(campaign_id=campaign_id, company_id=cid, source=source, discovery_run_id=discovery_run_id)
        for cid in ids - existing
    ]
    for row in new_rows:
        db.add(row)
    if discovery_run_id and existing:
        db.query(CampaignLeadSource).filter(
            CampaignLeadSource.campaign_id == campaign_id,
            CampaignLeadSource.company_id.in_(existing),
            CampaignLeadSource.discovery_run_id.is_(None),
        ).update({"discovery_run_id": discovery_run_id}, synchronize_session=False)
    db.commit()
    return len(new_rows)
