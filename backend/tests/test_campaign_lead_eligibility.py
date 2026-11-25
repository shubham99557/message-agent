"""Campaign lead picker: eligibility filtering, partial adds, discovery scoping, cross-campaign guard."""
from datetime import datetime, timedelta, timezone

from app.models.activity import SuppressionList
from app.models.campaign import CampaignLeadSource
from app.models.company import Company
from app.models.email import EmailDraft
from app.services.campaign_eligibility_service import find_recent_contact_conflict


def _mail(local):
    return local + chr(64) + "leadtest.in"


def _company(db, name, email="", **kw):
    c = Company(name=name, city="Siliguri", public_email=email or None, is_demo=kw.pop("is_demo", False), **kw)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _campaign(client, headers, name):
    res = client.post("/api/v1/campaigns", json={"name": name, "objective": "Test", "target_city": "Siliguri"}, headers=headers)
    assert res.status_code == 201
    return res.json()["id"]


def _sent_draft(db, company, campaign_id, days_ago, email=None):
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    d = EmailDraft(
        campaign_id=campaign_id, company_id=company.id, recipient_email=email or company.public_email,
        subject="Hi", body_html="<p>Hi</p>", body_text="Hi", approval_status="sent", sent_at=when,
    )
    db.add(d)
    db.commit()
    return d


def _codes(item):
    return {r["code"] for r in item["reasons"]}


def test_candidates_scope_and_blocked_reasons(client, admin_auth_headers, db_session):
    camp_a = _campaign(client, admin_auth_headers, "Campaign A")
    camp_b = _campaign(client, admin_auth_headers, "Campaign B")

    good = _company(db_session, "Good Co", _mail("good"))
    no_email = _company(db_session, "No Email Co")
    demo = _company(db_session, "Demo Co", _mail("demo"), is_demo=True)
    opted_out = _company(db_session, "Opted Out Co", _mail("optout"))
    db_session.add(SuppressionList(identifier=_mail("optout"), reason="unsubscribe"))
    in_b = _company(db_session, "In B Co", _mail("inb"))
    recent = _company(db_session, "Recent Co", _mail("recent"))
    old = _company(db_session, "Old Contact Co", _mail("old"))
    other_discovery = _company(db_session, "Found By B Co", _mail("foundb"))
    db_session.commit()

    for c in (good, no_email, demo, opted_out, in_b, recent, old):
        db_session.add(CampaignLeadSource(campaign_id=camp_a, company_id=c.id))
    db_session.add(CampaignLeadSource(campaign_id=camp_b, company_id=other_discovery.id))
    db_session.commit()

    r_b = client.post(f"/api/v1/campaigns/{camp_b}/recipients", json={"company_ids": [in_b.id]}, headers=admin_auth_headers)
    assert r_b.status_code == 200, r_b.text
    _sent_draft(db_session, recent, None, days_ago=5)
    _sent_draft(db_session, old, None, days_ago=45)

    res = client.get(f"/api/v1/campaigns/{camp_a}/candidates?scope=campaign", headers=admin_auth_headers)
    assert res.status_code == 200
    body = res.json()
    by_name = {i["name"]: i for i in body["items"]}

    # Only Campaign A's discoveries; demo companies never listed
    assert "Found By B Co" not in by_name
    assert "Demo Co" not in by_name
    assert body["campaign_lead_count"] == 7

    assert by_name["Good Co"]["eligible"] is True
    assert by_name["Old Contact Co"]["eligible"] is True  # outside 30-day window
    assert _codes(by_name["No Email Co"]) == {"no_email"}
    assert _codes(by_name["Opted Out Co"]) == {"suppressed"}
    assert _codes(by_name["In B Co"]) == {"in_other_campaign"}
    assert _codes(by_name["Recent Co"]) == {"recently_contacted"}
    assert body["eligible_total"] == 2

    # scope=all includes other campaigns' discoveries and flags which are "ours"
    all_items = {i["name"]: i for i in client.get(f"/api/v1/campaigns/{camp_a}/candidates?scope=all", headers=admin_auth_headers).json()["items"]}
    assert all_items["Found By B Co"]["from_this_campaign"] is False
    assert all_items["Good Co"]["from_this_campaign"] is True


def test_add_recipients_adds_good_and_skips_bad(client, admin_auth_headers, db_session):
    camp = _campaign(client, admin_auth_headers, "Partial Add")
    good1 = _company(db_session, "Good One", _mail("good1"))
    good2 = _company(db_session, "Good Two", _mail("good2"))
    bad = _company(db_session, "No Email")

    res = client.post(f"/api/v1/campaigns/{camp}/recipients", json={"company_ids": [good1.id, bad.id, good2.id]}, headers=admin_auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["added_count"] == 2
    assert body["skipped_count"] == 1
    assert body["skipped"][0]["name"] == "No Email"
    assert body["skipped"][0]["reasons"][0]["code"] == "no_email"

    # Re-adding is skipped with a reason, and nothing-added is a 400
    again = client.post(f"/api/v1/campaigns/{camp}/recipients", json={"company_ids": [good1.id]}, headers=admin_auth_headers)
    assert again.status_code == 400
    assert "Already in this campaign" in again.json()["detail"]


def test_same_company_cannot_join_two_active_campaigns(client, admin_auth_headers, db_session):
    camp_a = _campaign(client, admin_auth_headers, "First")
    camp_b = _campaign(client, admin_auth_headers, "Second")
    c = _company(db_session, "Shared Co", _mail("shared"))

    assert client.post(f"/api/v1/campaigns/{camp_a}/recipients", json={"company_ids": [c.id]}, headers=admin_auth_headers).status_code == 200
    res = client.post(f"/api/v1/campaigns/{camp_b}/recipients", json={"company_ids": [c.id]}, headers=admin_auth_headers)
    assert res.status_code == 400
    assert "First" in res.json()["detail"]

    # Once the first campaign is stopped (and never actually emailed), the company is free again
    client.post(f"/api/v1/campaigns/{camp_a}/stop", headers=admin_auth_headers)
    assert client.post(f"/api/v1/campaigns/{camp_b}/recipients", json={"company_ids": [c.id]}, headers=admin_auth_headers).status_code == 200


def test_send_time_guard_blocks_cross_campaign_email_within_30_days(client, admin_auth_headers, db_session):
    camp_a = _campaign(client, admin_auth_headers, "Guard A")
    camp_b = _campaign(client, admin_auth_headers, "Guard B")
    c = _company(db_session, "Guarded Co", _mail("guarded"))
    _sent_draft(db_session, c, camp_a, days_ago=3)

    pending = EmailDraft(
        campaign_id=camp_b, company_id=c.id, recipient_email=_mail("guarded"),
        subject="Hi again", body_html="x", body_text="x", approval_status="approved",
    )
    db_session.add(pending)
    db_session.commit()
    assert "already emailed" in (find_recent_contact_conflict(db_session, pending) or "")

    # Same email address under a different company record is also caught
    alias = _company(db_session, "Guarded Co (duplicate record)", _mail("guarded"))
    pending.company_id = alias.id
    db_session.commit()
    assert find_recent_contact_conflict(db_session, pending) is not None

    # Same-campaign follow-ups and no-campaign drafts are not blocked here
    pending.campaign_id = camp_a
    assert find_recent_contact_conflict(db_session, pending) is None
    pending.campaign_id = None
    assert find_recent_contact_conflict(db_session, pending) is None

    # Outside the window: allowed
    pending.campaign_id = camp_b
    old = db_session.query(EmailDraft).filter(EmailDraft.campaign_id == camp_a).first()
    old.sent_at = datetime.now(timezone.utc) - timedelta(days=31)
    db_session.commit()
    assert find_recent_contact_conflict(db_session, pending) is None


def test_send_endpoint_rejects_recently_contacted(client, admin_auth_headers, db_session):
    camp_a = _campaign(client, admin_auth_headers, "Send A")
    camp_b = _campaign(client, admin_auth_headers, "Send B")
    c = _company(db_session, "Send Co", _mail("send"))
    _sent_draft(db_session, c, camp_a, days_ago=1)

    d = client.post("/api/v1/emails/generate", json={"company_id": c.id, "campaign_id": camp_b}, headers=admin_auth_headers).json()
    assert client.post(f"/api/v1/approvals/approve/{d['id']}", headers=admin_auth_headers).status_code == 200
    res = client.post(f"/api/v1/emails/send/{d['id']}", headers=admin_auth_headers)
    db_session.expire_all()
    row = db_session.query(EmailDraft).filter(EmailDraft.id == d["id"]).first()
    assert row.approval_status == "rejected"
    assert "already emailed" in (row.rejection_reason or "")
    assert res.json().get("status") in ("blocked_recent_contact", None) or res.status_code >= 400


def test_discovery_import_tags_leads_for_campaign(client, admin_auth_headers, db_session):
    camp = _campaign(client, admin_auth_headers, "Discovery Tagged")
    item = {
        "name": "Tagged Discovery Co", "city": "Siliguri", "website": "https://tagged-discovery.in",
        "public_email": _mail("tagged"), "source_url": "https://tagged-discovery.in",
        "source_type": "official_website", "is_demo": False,
    }
    res = client.post("/api/v1/discovery/batch-import-summary", json={"companies": [item], "campaign_id": camp}, headers=admin_auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["linked_to_campaign"] == 1

    # Importing the same lead again (duplicate) for the same campaign is idempotent
    again = client.post("/api/v1/discovery/batch-import-summary", json={"companies": [item], "campaign_id": camp}, headers=admin_auth_headers).json()
    assert again["duplicates_skipped"] == 1 and again["linked_to_campaign"] == 0

    names = [i["name"] for i in client.get(f"/api/v1/campaigns/{camp}/candidates", headers=admin_auth_headers).json()["items"]]
    assert names == ["Tagged Discovery Co"]


def test_review_fixes_contact_email_stuck_sending_and_ignore(client, admin_auth_headers, db_session):
    from app.models.campaign import Campaign
    from app.models.company import CompanyContact
    from app.services.campaign_eligibility_service import evaluate_lead_eligibility

    camp_id = _campaign(client, admin_auth_headers, "Review Fixes")
    camp_other = _campaign(client, admin_auth_headers, "Review Other")
    camp = db_session.query(Campaign).get(camp_id)

    # 1. Only a contact-person email: a campaign draft cannot use it -> no_email
    contact_only = _company(db_session, "Contact Only Co")
    db_session.add(CompanyContact(company_id=contact_only.id, name="Asha", email=_mail("asha")))
    # decision-maker email is used by the generator -> eligible
    dm_only = _company(db_session, "DM Only Co", decision_maker_email=_mail("dm"))
    db_session.commit()

    # 2. Send stuck in "sending" for 40 days must not block forever; a fresh one does
    stuck = _company(db_session, "Stuck Co", _mail("stuck"))
    fresh = _company(db_session, "Fresh Sending Co", _mail("fresh"))
    for comp, days in ((stuck, 40), (fresh, 0)):
        d = EmailDraft(campaign_id=camp_other, company_id=comp.id, recipient_email=comp.public_email,
                       subject="s", body_html="b", body_text="b", approval_status="sending")
        db_session.add(d)
        db_session.commit()
        d.updated_at = datetime.now(timezone.utc) - timedelta(days=days)
        db_session.commit()

    v = evaluate_lead_eligibility(db_session, camp, [contact_only, dm_only, stuck, fresh])
    assert [r["code"] for r in v[contact_only.id].reasons] == ["no_email"]
    assert v[dm_only.id].eligible
    assert v[stuck.id].eligible
    assert [r["code"] for r in v[fresh.id].reasons] == ["recently_contacted"]

    # 3. ignore= lets a caller skip a rule (used by the multi-channel agent for no_email)
    v2 = evaluate_lead_eligibility(db_session, camp, [contact_only], ignore=("no_email",))
    assert v2[contact_only.id].eligible


def test_migration_0009_upgrade_and_downgrade(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    import sqlalchemy as sa
    import os

    db_file = tmp_path / "mig.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = Config(ini)
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")
    insp = sa.inspect(sa.create_engine(url))
    assert "campaign_lead_sources" in insp.get_table_names()
    assert "campaign_id" in {c["name"] for c in insp.get_columns("discovery_runs")}

    command.downgrade(cfg, "0008_phase8_production_hardening_constraints")
    insp = sa.inspect(sa.create_engine(url))
    assert "campaign_lead_sources" not in insp.get_table_names()
    assert "campaign_id" not in {c["name"] for c in insp.get_columns("discovery_runs")}

    # Re-upgrade from a real 0008 schema exercises the create-table / add-column path
    command.upgrade(cfg, "head")
    insp = sa.inspect(sa.create_engine(url))
    assert "campaign_lead_sources" in insp.get_table_names()
    assert "ix_discovery_runs_campaign_id" in {i["name"] for i in insp.get_indexes("discovery_runs")}
