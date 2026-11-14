from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.analytics import FunnelMetrics, CityBreakdownItem, CampaignPerformanceSummary
from app.services.analytics_service import (
    calculate_funnel_metrics,
    calculate_city_breakdown,
    calculate_campaign_performances
)

router = APIRouter()


@router.get("/dashboard", response_model=FunnelMetrics)
def get_dashboard_analytics(
    campaign_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return calculate_funnel_metrics(db, campaign_id=campaign_id)


@router.get("/cities", response_model=List[CityBreakdownItem])
def get_city_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return calculate_city_breakdown(db)


@router.get("/campaigns", response_model=List[CampaignPerformanceSummary])
def get_campaigns_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return calculate_campaign_performances(db)
