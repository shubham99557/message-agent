import json
import logging
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.job import BackgroundTaskRecord, DeadLetterTask
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _record_task_start(db, task_id: str, category: str, payload: dict) -> BackgroundTaskRecord:
    record = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.task_id == task_id).first()
    if not record:
        record = BackgroundTaskRecord(
            task_id=task_id,
            category=category,
            payload_json=json.dumps(payload, default=str),
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db.add(record)
    else:
        record.status = "running"
        record.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


def _record_task_success(db, task_id: str, result: Any):
    record = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.task_id == task_id).first()
    if record:
        record.status = "completed"
        record.result_json = json.dumps(result, default=str)
        record.completed_at = datetime.now(timezone.utc)
        db.commit()


def _record_task_failure(db, task_id: str, category: str, payload: dict, exc: Exception, retry_count: int, max_retries: int):
    record = db.query(BackgroundTaskRecord).filter(BackgroundTaskRecord.task_id == task_id).first()
    is_exhausted = retry_count >= max_retries
    if record:
        record.retry_count = retry_count
        record.error_message = str(exc)
        if is_exhausted:
            record.status = "dead_letter"
            record.completed_at = datetime.now(timezone.utc)
        else:
            record.status = "retrying"
        db.commit()

    if is_exhausted:
        dlq = DeadLetterTask(
            task_id=task_id,
            category=category,
            idempotency_key=record.idempotency_key if record else None,
            payload_json=json.dumps(payload, default=str),
            final_error=str(exc),
            retries_exhausted=retry_count,
            failed_at=datetime.now(timezone.utc)
        )
        db.add(dlq)
        db.commit()


def execute_task_logic(category: str, payload: Dict[str, Any], db) -> Dict[str, Any]:
    """Pure business logic dispatch for the 13 task categories."""
    if category == "company_discovery":
        from app.services.discovery_service import search_public_company_directory
        from app.services.company_service import create_company, find_duplicate_company
        from app.integrations.discovery_adapters import is_demo_domain
        from app.schemas.research import DiscoveryQuery
        from app.schemas.company import CompanyCreate

        cities = payload.get("cities") or ["Siliguri", "Gangtok", "Patna", "Bhagalpur"]
        created = 0
        skipped_demo = 0
        for city in cities:
            # Strictly exclude demo fixtures from autonomous background discovery!
            items = search_public_company_directory(DiscoveryQuery(city=city, include_demo=False))
            for item in items:
                if item.is_demo or is_demo_domain(item.website) or is_demo_domain(item.public_email):
                    skipped_demo += 1
                    continue
                existing = find_duplicate_company(db, name=item.name, website=item.website, email=item.public_email)
                if not existing:
                    create_company(
                        db,
                        CompanyCreate(
                            name=item.name,
                            website=item.website,
                            city=item.city,
                            state=item.state,
                            industry=item.industry,
                            description=item.description,
                            public_email=item.public_email,
                            public_phone=item.public_phone,
                            public_whatsapp=item.public_whatsapp,
                            linkedin_url=item.linkedin_url,
                            employee_count_min=item.employee_count_min,
                            employee_count_max=item.employee_count_max,
                            employee_size_evidence=item.employee_size_evidence,
                            laptop_count_verified=item.laptop_count_verified,
                            laptop_count_evidence=item.laptop_count_evidence,
                            source_url=item.source_url,
                            source_notes=f"Background discovery ({item.source_type})",
                            is_demo=False,
                        ),
                    )
                    created += 1
        return {
            "discovered_cities": cities,
            "new_companies_created": created,
            "skipped_demo_fixtures": skipped_demo,
        }

    elif category == "company_enrichment":
        from app.models.company import Company
        company_id = payload.get("company_id")
        comp = db.query(Company).filter(Company.id == company_id).first()
        if not comp:
            return {"status": "not_found", "company_id": company_id}
        comp.date_last_verified = datetime.now(timezone.utc)
        db.commit()
        return {"company_id": comp.id, "name": comp.name, "enriched": True}

    elif category == "website_research":
        import asyncio
        from app.models.company import Company
        from app.services.research_service import generate_company_research_report
        company_id = payload.get("company_id")
        comp = db.query(Company).filter(Company.id == company_id).first()
        if not comp:
            return {"error": f"Company {company_id} not found"}
        research = asyncio.run(generate_company_research_report(db, comp))
        return {"company_id": comp.id, "research_id": research.id, "summary": research.summary}

    elif category == "lead_qualification":
        from app.models.company import Company
        from app.services.qualification_service import qualify_company
        recheck_stale = payload.get("recheck_stale_only", False)
        company_id = payload.get("company_id")
        if company_id:
            comp = db.query(Company).filter(Company.id == company_id).first()
            if comp:
                qual = qualify_company(db, comp)
                return {"company_id": comp.id, "status": qual.status, "score": qual.score}
            return {"error": f"Company {company_id} not found"}
        
        # Batch qualification
        query = db.query(Company)
        if recheck_stale:
            stale_threshold = datetime.now(timezone.utc) - timedelta(days=30)
            query = query.filter((Company.date_last_verified == None) | (Company.date_last_verified < stale_threshold))
        companies = query.limit(50).all()
        results = []
        for c in companies:
            q = qualify_company(db, c)
            results.append({"id": c.id, "name": c.name, "status": q.status, "score": q.score})
        return {"rechecked_count": len(results), "qualifications": results}

    elif category == "email_generation":
        from app.models.company import Company
        from app.services.email_generator_service import generate_email_draft
        company_id = payload.get("company_id")
        campaign_id = payload.get("campaign_id")
        style = payload.get("style", "Friendly professional")
        comp = db.query(Company).filter(Company.id == company_id).first()
        if not comp:
            return {"error": f"Company {company_id} not found"}
        draft = generate_email_draft(db=db, company=comp, campaign_id=campaign_id, tone=style)
        return {"draft_id": draft.id, "subject": draft.subject, "status": draft.approval_status}

    elif category == "whatsapp_generation":
        from app.models.company import Company
        from app.schemas.whatsapp import WhatsAppDraftRequest
        from app.services.whatsapp_service import create_whatsapp_message, seed_default_meta_templates
        company_id = payload.get("company_id")
        comp = db.query(Company).filter(Company.id == company_id).first()
        if not comp:
            return {"error": f"Company {company_id} not found"}
        seed_default_meta_templates(db)
        req = WhatsAppDraftRequest(
            company_id=comp.id,
            template_name=payload.get("template_name", "acttrident_intro_utility_v1"),
            recipient_phone=payload.get("recipient_phone") or comp.public_whatsapp or comp.public_phone,
            parameters=payload.get("parameters") or {"1": comp.decision_maker_name or "Team", "2": comp.city}
        )
        draft = create_whatsapp_message(db, comp, req)
        return {"whatsapp_id": draft.id, "status": draft.approval_status}

    elif category == "email_dispatch":
        from app.models.email import EmailDraft
        from app.services.email_sender_service import send_approved_email
        draft_id = payload.get("draft_id")
        draft = db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
        if not draft:
            return {"error": f"Draft {draft_id} not found"}

        actor_user_id = payload.get("user_id") or draft.approved_by_id or 1
        result = send_approved_email(db=db, draft_id=draft.id, user_id=actor_user_id)
        if result.status == "rate_limited":
            raise RuntimeError(result.message or "Email dispatch rate limit reached, retrying with backoff")
        return {"draft_id": draft_id, "result": result.model_dump()}

    elif category == "whatsapp_dispatch":
        from app.models.whatsapp import WhatsAppMessage
        from app.services.whatsapp_service import send_approved_whatsapp_message
        message_id = payload.get("message_id")
        msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
        if not msg:
            return {"error": f"Message {message_id} not found"}

        actor_user_id = payload.get("user_id") or msg.approved_by_id or 1
        success, detail = send_approved_whatsapp_message(db=db, message_id=msg.id, user_id=actor_user_id)
        if not success and "rate limit" in (detail or "").lower():
            raise RuntimeError(detail)
        return {"message_id": message_id, "success": success, "detail": detail}

    elif category == "reply_ingestion":
        from app.services.reply_classifier_service import ingest_inbound_reply
        reply = ingest_inbound_reply(
            db=db,
            channel=payload.get("channel", "email"),
            sender_identifier=payload.get("sender", "unknown@example.com"),
            recipient_identifier=payload.get("recipient", "outreach@acttrident.ai"),
            subject=payload.get("subject"),
            message_body=payload.get("body", "")
        )
        return {"reply_id": reply.id, "channel": reply.channel, "classification": reply.classification}

    elif category == "reply_classification":
        from app.models.reply import Reply
        from app.services.reply_classifier_service import classify_reply_text
        reply_id = payload.get("reply_id")
        reply = db.query(Reply).filter(Reply.id == reply_id).first()
        if not reply:
            return {"error": f"Reply {reply_id} not found"}
        classification, confidence, reason, suggested, is_neg = classify_reply_text(reply.message_body)
        reply.classification = classification
        reply.classification_confidence = confidence
        reply.classification_reason = reason
        reply.suggested_response = suggested
        reply.is_negotiation = is_neg
        db.commit()
        return {"reply_id": reply_id, "classification": classification, "confidence": confidence}

    elif category == "crm_update":
        from app.models.lead import Lead, PIPELINE_STATUSES
        lead_id = payload.get("lead_id")
        new_status = payload.get("new_status")
        notes = payload.get("notes")
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return {"error": f"Lead {lead_id} not found"}
        if new_status and new_status in PIPELINE_STATUSES:
            lead.pipeline_status = new_status
        if notes:
            lead.notes = f"{(lead.notes or '')}\n{notes}".strip()
        lead.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"lead_id": lead.id, "status": lead.pipeline_status}

    elif category == "followup_scheduling":
        from app.services.followup_service import process_autonomous_followups
        return process_autonomous_followups(db)

    elif category == "daily_reporting":
        from app.services.analytics_service import generate_daily_operational_digest
        digest = generate_daily_operational_digest(db)
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "metrics": digest["summary"], "digest": digest}

    elif category == "outbox_dispatch":
        from app.services.orchestration_service import process_outbox_batch
        return process_outbox_batch(
            db=db,
            user_id=int(payload.get("user_id", 1)),
            limit=int(payload.get("limit", 20)),
        )

    elif category == "gmail_reply_sync":
        from app.integrations.gmail_adapter import get_active_gmail_connection, sync_gmail_replies
        conn = get_active_gmail_connection(db)
        if not conn or conn.status != "connected":
            return {"status": "skipped_disconnected", "synced_replies": 0, "bounces_recorded": 0}
        return sync_gmail_replies(
            db=db,
            connection=conn,
            max_results=int(payload.get("max_results", 25)),
        )

    else:
        raise ValueError(f"Unknown task category: {category}")


def _execute_with_retry(task_self, category: str, task_uuid: str, payload: dict):
    """Template execution handler with backoff, retry, and DLQ tracking."""
    db = SessionLocal()
    task_id = task_uuid or (task_self.request.id if task_self else str(time.time()))
    retry_count = task_self.request.retries if task_self and hasattr(task_self.request, "retries") else 0
    max_retries = 3

    try:
        _record_task_start(db, task_id, category, payload)
        result = execute_task_logic(category, payload, db)
        _record_task_success(db, task_id, result)
        return result
    except Exception as exc:
        logger.error(f"Task {category} (id={task_id}) failed: {exc}", exc_info=True)
        _record_task_failure(db, task_id, category, payload, exc, retry_count, max_retries)
        if task_self and retry_count < max_retries:
            # Exponential backoff with jitter
            countdown = int(min(300, (2 ** retry_count) * 10 + random.uniform(1, 5)))
            raise task_self.retry(exc=exc, countdown=countdown)
        raise exc
    finally:
        db.close()


# Define Celery Tasks for all 13 categories
@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_company_discovery")
def task_company_discovery(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "company_discovery", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_company_enrichment")
def task_company_enrichment(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "company_enrichment", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_website_research")
def task_website_research(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "website_research", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_lead_qualification")
def task_lead_qualification(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "lead_qualification", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_email_generation")
def task_email_generation(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "email_generation", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_whatsapp_generation")
def task_whatsapp_generation(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "whatsapp_generation", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_email_dispatch")
def task_email_dispatch(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "email_dispatch", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_whatsapp_dispatch")
def task_whatsapp_dispatch(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "whatsapp_dispatch", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_reply_ingestion")
def task_reply_ingestion(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "reply_ingestion", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_reply_classification")
def task_reply_classification(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "reply_classification", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_crm_update")
def task_crm_update(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "crm_update", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_followup_scheduling")
def task_followup_scheduling(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "followup_scheduling", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_daily_reporting")
def task_daily_reporting(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "daily_reporting", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_outbox_dispatch")
def task_outbox_dispatch(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "outbox_dispatch", task_uuid, payload or {})

@celery_app.task(bind=True, max_retries=3, name="app.worker.tasks.task_gmail_reply_sync")
def task_gmail_reply_sync(self, payload=None, task_uuid=None):
    return _execute_with_retry(self, "gmail_reply_sync", task_uuid, payload or {})


CATEGORY_TO_TASK = {
    "company_discovery": task_company_discovery,
    "company_enrichment": task_company_enrichment,
    "website_research": task_website_research,
    "lead_qualification": task_lead_qualification,
    "email_generation": task_email_generation,
    "whatsapp_generation": task_whatsapp_generation,
    "email_dispatch": task_email_dispatch,
    "whatsapp_dispatch": task_whatsapp_dispatch,
    "reply_ingestion": task_reply_ingestion,
    "reply_classification": task_reply_classification,
    "crm_update": task_crm_update,
    "followup_scheduling": task_followup_scheduling,
    "daily_reporting": task_daily_reporting,
    "outbox_dispatch": task_outbox_dispatch,
    "gmail_reply_sync": task_gmail_reply_sync,
}


def dispatch_celery_task(category: str, task_uuid: str, payload: dict):
    """Dispatches asynchronous Celery task using configured routing."""
    task_func = CATEGORY_TO_TASK.get(category)
    if not task_func:
        raise ValueError(f"No task handler registered for category {category}")
    return task_func.apply_async(args=[payload, task_uuid], task_id=task_uuid)
