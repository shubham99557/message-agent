from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict


class FunnelMetrics(BaseModel):
    total_companies_researched: int
    qualified_leads: int
    emails_drafted: int
    emails_approved: int
    emails_queued: int = 0
    emails_accepted: int = 0
    emails_sent: int
    emails_simulated: int = 0
    emails_delivered: int
    emails_failed: int = 0
    bounces: int
    replies_received: int
    interested_prospects: int
    meetings_booked: int
    demos_completed: int
    trials_started: int
    paid_conversions: int
    opt_outs: int
    
    # Real Rates with Authentic Denominators
    qualification_rate: float       # (qualified_leads / total_companies) * 100
    approval_rate: float            # (emails_approved / emails_drafted) * 100
    delivery_rate: float            # (emails_delivered / emails_sent) * 100
    reply_rate: float               # (replies_received / emails_sent) * 100
    interest_rate: float            # (interested_prospects / replies_received) * 100
    trial_conversion_rate: float    # (trials_started / emails_sent) * 100
    customer_conversion_rate: float # (paid_conversions / emails_sent) * 100


class CityBreakdownItem(BaseModel):
    city: str
    companies_count: int
    verified_5_plus_laptops_count: int
    sent_count: int
    replies_count: int
    trials_count: int


class CampaignPerformanceSummary(BaseModel):
    campaign_id: int
    campaign_name: str
    target_city: Optional[str] = None
    recipients_count: int
    drafted: int
    approved: int
    sent: int
    delivered: int
    replies: int
    trials: int
    conversion_rate: float
