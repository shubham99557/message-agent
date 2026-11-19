from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services.autonomous_agent_service import (
    run_autonomous_outreach_cycle,
    get_autonomous_agent_status,
    ensure_verified_targets,
)

router = APIRouter()


class AutonomousCycleRequest(BaseModel):
    target_city: Optional[str] = Field(None, description="Target city (e.g. Siliguri, Gangtok, Patna, Bhagalpur, or All)")
    campaign_id: Optional[int] = Field(None, description="Optional target campaign ID")
    channels: Optional[List[str]] = Field(["email", "whatsapp", "linkedin"], description="Channels to activate")
    max_prospects: int = Field(10, ge=1, le=50, description="Max prospects to process in this cycle")
    auto_approve_simulation: bool = Field(False, description="When True in simulation mode, automatically approves verified drafts and queues to transactional outbox")


@router.get("/status")
def read_agent_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieves real-time telemetry, queue metrics, and system status for the Autonomous Outreach Agent Brain."""
    return get_autonomous_agent_status(db)


@router.post("/run-cycle")
async def execute_autonomous_cycle(
    req: AutonomousCycleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Executes the end-to-end autonomous outreach cycle across all 8 pipeline phases:
    Discovery -> Deep Research Dossier -> 7-Factor Qualification -> Campaign Enrollment
    -> Multi-Channel Copywriting -> Approval Safeguards -> Outbox Dispatch -> CRM Tracking.
    """
    try:
        result = await run_autonomous_outreach_cycle(
            db=db,
            target_city=req.target_city,
            campaign_id=req.campaign_id,
            channels=req.channels,
            max_prospects=req.max_prospects,
            auto_approve_simulation=req.auto_approve_simulation,
            user_id=current_user.id,
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Autonomous outreach cycle execution failed: {exc}",
        )


@router.post("/seed-targets")
def seed_regional_targets(
    target_city: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Manually triggers ingestion and 7-factor qualification of verified enterprise targets."""
    companies = ensure_verified_targets(db, target_city=target_city)
    return {
        "status": "success",
        "target_city": target_city or "All",
        "seeded_count": len(companies),
        "companies": [
            {
                "id": c.id,
                "name": c.name,
                "city": c.city,
                "laptops": c.laptop_count_verified,
                "score": c.qualification_score,
                "status": c.qualification_status,
            }
            for c in companies
        ],
    }
