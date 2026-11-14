from fastapi import APIRouter
from app.api.endpoints import (
    auth, companies, crm, discovery, qualification,
    research, emails, approvals, campaigns, whatsapp, replies,
    analytics, settings
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(companies.router, prefix="/companies", tags=["Companies & Leads"])
api_router.include_router(crm.router, prefix="/crm", tags=["CRM Pipeline"])
api_router.include_router(discovery.router, prefix="/discovery", tags=["Discovery"])
api_router.include_router(qualification.router, prefix="/qualification", tags=["AI Qualification"])
api_router.include_router(research.router, prefix="/research", tags=["AI Research Agent"])
api_router.include_router(emails.router, prefix="/emails", tags=["AI Email Outreach"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["Human Approval Queue"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["WhatsApp Cloud API"])
api_router.include_router(replies.router, prefix="/replies", tags=["Inbox & AI Reply Classification"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & Reporting"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings & Audit Logs"])
