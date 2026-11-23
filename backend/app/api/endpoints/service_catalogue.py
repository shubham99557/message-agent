from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, require_role
from app.models.user import User
from app.schemas.service_catalogue import (
    ServiceCatalogueResponse,
    ServiceCatalogueCreate,
    ServiceCatalogueUpdate,
    ServiceMatchResult
)
from app.services import service_catalogue_service

router = APIRouter()


@router.get("", response_model=List[ServiceCatalogueResponse])
def list_services(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves all ActTrident service catalogue items."""
    return service_catalogue_service.get_services(db, active_only=active_only)


@router.get("/{service_id}", response_model=ServiceCatalogueResponse)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves a single service catalogue item by ID."""
    svc = service_catalogue_service.get_service_by_id(db, service_id)
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )
    return svc


@router.post("", response_model=ServiceCatalogueResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    item_in: ServiceCatalogueCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """Creates a new service catalogue item (Admin only)."""
    existing = service_catalogue_service.get_service_by_code(db, item_in.service_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service code '{item_in.service_code}' already exists"
        )
    return service_catalogue_service.create_service(db, item_in)


@router.put("/{service_id}", response_model=ServiceCatalogueResponse)
def update_service(
    service_id: int,
    item_in: ServiceCatalogueUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """Updates an existing service catalogue item (Admin only)."""
    svc = service_catalogue_service.update_service(db, service_id, item_in)
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )
    return svc


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(["admin"]))
):
    """Deletes a service catalogue item (Admin only)."""
    success = service_catalogue_service.delete_service(db, service_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with ID {service_id} not found"
        )
    return None


@router.post("/match", response_model=ServiceMatchResult)
def match_service(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Evaluates a company profile and returns the most suitable ActTrident service with rationale."""
    result = service_catalogue_service.match_service_for_company(payload, db=db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active services found in catalogue"
        )
    return result
