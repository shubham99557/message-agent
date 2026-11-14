from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    UserCreate,
    AdminUserCreate,
    UserResponse,
    Token,
    UserLogin,
    TokenRefreshRequest
)
from app.services.auth_service import (
    create_user,
    authenticate_user,
    get_user_by_email,
    seed_default_admin,
    issue_refresh_token,
    rotate_refresh_token,
    revoke_user_refresh_tokens
)
from app.core.audit import record_audit_log

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Public self-registration strictly assigns 'sales_rep'. Administrator or Manager role assignment is forbidden."""
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )
    # Strictly enforce sales_rep role on public registration
    new_user = create_user(db, user_in, role="sales_rep")
    record_audit_log(
        db=db,
        action="public_user_registration",
        entity_type="user",
        entity_id=str(new_user.id),
        details={"email": new_user.email, "enforced_role": "sales_rep"}
    )
    return new_user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    user_in: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Admin-only endpoint to provision users with designated roles (admin, manager, sales_rep)."""
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )
    target_role = user_in.role if user_in.role in ["admin", "manager", "sales_rep"] else "sales_rep"
    new_user = create_user(db, user_in, role=target_role)
    record_audit_log(
        db=db,
        action="admin_create_user",
        entity_type="user",
        entity_id=str(new_user.id),
        user_id=current_user.id,
        details={"created_email": new_user.email, "assigned_role": target_role}
    )
    return new_user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )
    raw_refresh, _ = issue_refresh_token(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "user": user
    }


@router.post("/login/json", response_model=Token)
def login_json(credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )
    raw_refresh, _ = issue_refresh_token(db, user.id)

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "user": user
    }


@router.post("/refresh", response_model=Token)
def refresh_token_endpoint(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    """Rotates refresh token and issues a new access token and refreshed rotation token."""
    result = rotate_refresh_token(db, payload.refresh_token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked refresh token. Please re-authenticate."
        )
    user, new_raw_refresh = result

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "refresh_token": new_raw_refresh,
        "token_type": "bearer",
        "user": user
    }


@router.post("/logout")
def logout_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revokes active refresh tokens for the current user."""
    revoked_count = revoke_user_refresh_tokens(db, current_user.id)
    record_audit_log(
        db=db,
        action="user_logout",
        entity_type="user",
        entity_id=str(current_user.id),
        user_id=current_user.id,
        details={"revoked_tokens": revoked_count}
    )
    return {"status": "logged_out", "revoked_tokens": revoked_count}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserResponse], dependencies=[Depends(require_role(["admin", "manager"]))])
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(User).offset(skip).limit(limit).all()
