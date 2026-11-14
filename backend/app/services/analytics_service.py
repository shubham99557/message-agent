from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.company import Company
from app.models.lead import Lead, Meeting, Trial, Customer
from app.models.email import EmailDraft, EmailEvent
from app.models.reply import Reply
from app.models.activity import SuppressionList
from app.models.campaign import Campaign
from app.schemas.analytics import FunnelMetrics, CityBreakdownItem, CampaignPerformanceSummary


def calculate_funnel_metrics(db: Session, campaign_id: Optional[int] = None) -> FunnelMetrics:
    # 1. Total companies researched
    comp_query = db.query(Company)
    total_companies = comp_query.count()

    # 2. Qualified leads
    qualified_leads = db.query(Company).filter(
        Company.qualification_status.in_(["High priority", "Medium priority"])
    ).count()

    # 3. Email counts
    draft_query = db.query(EmailDraft)
    if campaign_id:
        draft_query = draft_query.filter(EmailDraft.campaign_id == campaign_id)

    emails_drafted = draft_query.count()
    emails_approved = draft_query.filter(EmailDraft.approval_status.in_(["approved", "sent", "simulated"])).count()
    
    # Strictly sent or simulated test dispatches (never count drafted, queued, or rejected!)
    emails_sent = draft_query.filter(EmailDraft.approval_status.in_(["sent", "simulated"])).count()

    # Events
    emails_delivered = db.query(EmailEvent).filter(EmailEvent.event_type == "delivered").count()
    bounces = db.query(EmailEvent).filter(EmailEvent.event_type.in_(["bounced", "complaint"])).count()

    # 4. Inbound replies
    replies_count = db.query(Reply).count()
    interested_count = db.query(Reply).filter(
        Reply.classification.in_(["interested", "requests_demonstration", "requests_pricing"])
    ).count()

    # 5. Pipeline Stages
    meetings_booked = db.query(Meeting).count()
    demos_completed = db.query(Meeting).filter(Meeting.status == "completed").count()
    trials_started = db.query(Trial).count()
    paid_conversions = db.query(Customer).count()
    opt_outs = db.query(SuppressionList).count()

    # Authentic Denominators
    qual_rate = (qualified_leads / total_companies * 100) if total_companies > 0 else 0.0
    appr_rate = (emails_approved / emails_drafted * 100) if emails_drafted > 0 else 0.0
    deliv_rate = (emails_delivered / emails_sent * 100) if emails_sent > 0 else 0.0
    reply_rate = (replies_count / emails_sent * 100) if emails_sent > 0 else 0.0
    interest_rate = (interested_count / replies_count * 100) if replies_count > 0 else 0.0
    trial_rate = (trials_started / emails_sent * 100) if emails_sent > 0 else 0.0
    customer_rate = (paid_conversions / emails_sent * 100) if emails_sent > 0 else 0.0

    return FunnelMetrics(
        total_companies_researched=total_companies,
        qualified_leads=qualified_leads,
        emails_drafted=emails_drafted,
        emails_approved=emails_approved,
        emails_sent=emails_sent,
        emails_delivered=emails_delivered,
        bounces=bounces,
        replies_received=replies_count,
        interested_prospects=interested_count,
        meetings_booked=meetings_booked,
        demos_completed=demos_completed,
        trials_started=trials_started,
        paid_conversions=paid_conversions,
        opt_outs=opt_outs,
        qualification_rate=round(qual_rate, 1),
        approval_rate=round(appr_rate, 1),
        delivery_rate=round(deliv_rate, 1),
        reply_rate=round(reply_rate, 1),
        interest_rate=round(interest_rate, 1),
        trial_conversion_rate=round(trial_rate, 1),
        customer_conversion_rate=round(customer_rate, 1)
    )


def calculate_city_breakdown(db: Session) -> List[CityBreakdownItem]:
    cities = ["Siliguri", "Gangtok", "Patna", "Bhagalpur"]
    breakdowns = []

    for city in cities:
        c_count = db.query(Company).filter(Company.city.ilike(f"%{city}%")).count()
        laptop_count = db.query(Company).filter(
            Company.city.ilike(f"%{city}%"),
            Company.has_verified_5_plus_laptops == True
        ).count()
        
        sent = db.query(EmailDraft).join(Company).filter(
            Company.city.ilike(f"%{city}%"),
            EmailDraft.approval_status == "sent"
        ).count()

        replies = db.query(Reply).join(Company).filter(
            Company.city.ilike(f"%{city}%")
        ).count()

        trials = db.query(Trial).join(Lead).join(Company).filter(
            Company.city.ilike(f"%{city}%")
        ).count()

        breakdowns.append(CityBreakdownItem(
            city=city,
            companies_count=c_count,
            verified_5_plus_laptops_count=laptop_count,
            sent_count=sent,
            replies_count=replies,
            trials_count=trials
        ))

    return breakdowns


def calculate_campaign_performances(db: Session) -> List[CampaignPerformanceSummary]:
    campaigns = db.query(Campaign).all()
    summaries = []

    for camp in campaigns:
        recipients_count = len(camp.recipients)
        drafted = db.query(EmailDraft).filter(EmailDraft.campaign_id == camp.id).count()
        approved = db.query(EmailDraft).filter(
            EmailDraft.campaign_id == camp.id,
            EmailDraft.approval_status == "approved"
        ).count()
        sent = db.query(EmailDraft).filter(
            EmailDraft.campaign_id == camp.id,
            EmailDraft.approval_status == "sent"
        ).count()
        delivered = db.query(EmailEvent).join(EmailDraft).filter(
            EmailDraft.campaign_id == camp.id,
            EmailEvent.event_type == "delivered"
        ).count()

        trials = db.query(Trial).join(Lead).join(Company).join(EmailDraft).filter(
            EmailDraft.campaign_id == camp.id
        ).count()

        conv_rate = (trials / sent * 100) if sent > 0 else 0.0

        summaries.append(CampaignPerformanceSummary(
            campaign_id=camp.id,
            campaign_name=camp.name,
            target_city=camp.target_city,
            recipients_count=recipients_count,
            drafted=drafted,
            approved=approved,
            sent=sent,
            delivered=delivered,
            replies=0,
            trials=trials,
            conversion_rate=round(conv_rate, 1)
        ))

    return summaries


def generate_daily_operational_digest(db: Session) -> dict:
    """Generates comprehensive daily digest with exact metrics across all modules."""
    from datetime import datetime, timezone
    from app.models.job import BackgroundTaskRecord, DeadLetterTask
    from app.models.whatsapp import WhatsAppMessage
    from app.core.config import settings

    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Pipeline & Volume
    funnel = calculate_funnel_metrics(db)
    city_breakdown = calculate_city_breakdown(db)

    # 2. Email & WhatsApp Dispatches (Real vs Simulated)
    emails_sent_real = db.query(EmailDraft).filter(EmailDraft.approval_status == "sent").count()
    emails_simulated = db.query(EmailDraft).filter(EmailDraft.approval_status == "simulated").count()
    wa_sent_real = db.query(WhatsAppMessage).filter(WhatsAppMessage.status == "sent").count()
    wa_simulated = db.query(WhatsAppMessage).filter(WhatsAppMessage.status == "simulated").count()

    # 3. Replies by Category (all 10 classes)
    reply_counts_by_cat = {}
    reply_rows = db.query(Reply.classification, func.count(Reply.id)).group_by(Reply.classification).all()
    for cat, count in reply_rows:
        reply_counts_by_cat[cat] = count

    # 4. Job Engine Health & DLQ
    dlq_count = db.query(DeadLetterTask).filter(DeadLetterTask.requeued == False).count()
    failed_tasks_today = db.query(BackgroundTaskRecord).filter(
        BackgroundTaskRecord.created_at >= today_start,
        BackgroundTaskRecord.status == "failed"
    ).count()

    return {
        "report_date": today_start.strftime("%Y-%m-%d"),
        "timezone": settings.TIMEZONE,
        "generated_at": now_utc.isoformat(),
        "summary": {
            "total_companies_discovered": funnel.total_companies_researched,
            "qualified_leads": funnel.qualified_leads,
            "qualification_rate_percent": funnel.qualification_rate,
            "emails_drafted": funnel.emails_drafted,
            "emails_approved": funnel.emails_approved,
            "emails_dispatched_real": emails_sent_real,
            "emails_dispatched_simulated": emails_simulated,
            "whatsapp_dispatched_real": wa_sent_real,
            "whatsapp_dispatched_simulated": wa_simulated,
            "replies_received": funnel.replies_received,
            "meetings_booked": funnel.meetings_booked,
            "evaluation_programs_started": funnel.trials_started,
            "customer_conversions": funnel.paid_conversions,
            "opt_outs": funnel.opt_outs
        },
        "replies_breakdown": reply_counts_by_cat,
        "worker_health": {
            "failed_tasks_today": failed_tasks_today,
            "unresolved_dead_letters": dlq_count,
            "status": "healthy" if dlq_count == 0 else "action_required"
        },
        "city_breakdown": [item.model_dump() for item in city_breakdown]
    }
