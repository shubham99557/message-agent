import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user import User, RefreshToken
from app.schemas.auth import UserCreate, VALID_ROLES
from app.core.security import (
    get_password_hash,
    verify_password,
    generate_refresh_token_string,
    hash_token
)
from app.core.config import settings

logger = logging.getLogger(__name__)

KNOWN_INSECURE_DEFAULT_PASSWORDS = {
    "AdminPassword2026!",
    "SalesPassword2026!",
    "ManagerPassword2026!",
    "Password123!",
    "SecurePassword123!",
    "AdminPassword123!",
}


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_in: UserCreate, role: str = "sales_rep") -> User:
    safe_role = role if role in VALID_ROLES else "sales_rep"
    if settings.ENVIRONMENT.lower() == "production" and user_in.password in KNOWN_INSECURE_DEFAULT_PASSWORDS:
        raise ValueError("Known development default passwords are not permitted in production.")
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email.lower().strip(),
        hashed_password=hashed_password,
        full_name=user_in.full_name.strip(),
        role=safe_role,
        is_active=True,
        token_version=1
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if settings.ENVIRONMENT.lower() == "production" and password in KNOWN_INSECURE_DEFAULT_PASSWORDS:
        logger.warning(f"Production security block: Rejected login for '{email}' using known default password.")
        return None
    return user


def change_user_password(db: Session, user_id: int, old_password: str, new_password: str) -> User:
    """Securely rotates user password, increments token_version and invalidates active sessions."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("User not found.")
    if not verify_password(old_password, user.hashed_password):
        raise ValueError("Current password verification failed.")
    if len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters long.")
    if settings.ENVIRONMENT.lower() == "production" and new_password in KNOWN_INSECURE_DEFAULT_PASSWORDS:
        raise ValueError("Known development default passwords are not permitted in production.")

    user.hashed_password = get_password_hash(new_password)
    revoke_user_refresh_tokens(db, user_id)
    db.commit()
    db.refresh(user)
    return user


def issue_refresh_token(db: Session, user_id: int) -> Tuple[str, RefreshToken]:
    """Generates a secure random refresh token and persists its SHA-256 hash in the database."""
    raw_token = generate_refresh_token_string()
    token_hashed = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_entity = RefreshToken(
        user_id=user_id,
        token_hash=token_hashed,
        expires_at=expires_at
    )
    db.add(refresh_entity)
    db.commit()
    db.refresh(refresh_entity)
    return raw_token, refresh_entity


def rotate_refresh_token(db: Session, raw_token: str) -> Optional[Tuple[User, str]]:
    """Validates an incoming refresh token, revokes it, and issues a new cryptographically rotated token."""
    token_hashed = hash_token(raw_token)
    token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hashed).first()

    if not token_record:
        logger.warning("Attempted refresh with nonexistent token hash.")
        return None

    if not token_record.is_active:
        logger.warning(f"Attempted reuse or expired refresh token for user_id={token_record.user_id}.")
        return None

    user = token_record.user
    if not user or not user.is_active:
        return None

    now = datetime.now(timezone.utc)
    token_record.revoked_at = now

    new_raw_token = generate_refresh_token_string()
    new_token_hash = hash_token(new_raw_token)
    token_record.replaced_by_hash = new_token_hash

    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_token_record)
    db.commit()

    return user, new_raw_token


def revoke_user_refresh_tokens(db: Session, user_id: int) -> int:
    """Revokes all active refresh tokens and increments token_version to invalidate active JWTs."""
    now = datetime.now(timezone.utc)
    tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None)
    ).all()
    count = 0
    for t in tokens:
        t.revoked_at = now
        count += 1

    user = get_user_by_id(db, user_id)
    if user:
        user.token_version = (user.token_version or 1) + 1

    db.commit()
    return count


def set_user_active_status(db: Session, user_id: int, is_active: bool) -> Optional[User]:
    """Activates or deactivates a user account and immediately revokes all active sessions."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = is_active
    user.token_version = (user.token_version or 1) + 1
    if not is_active:
        revoke_user_refresh_tokens(db, user_id)
    else:
        db.commit()
    db.refresh(user)
    return user


def update_user_role(db: Session, user_id: int, new_role: str) -> Optional[User]:
    """Updates a user's RBAC role and rotates token_version so stale JWT claims are invalidated."""
    if new_role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{new_role}'.")
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.role = new_role
    user.token_version = (user.token_version or 1) + 1
    db.commit()
    db.refresh(user)
    return user


def seed_default_admin(db: Session) -> Optional[User]:
    """
    Seeds initial administrator strictly in non-production environments from environment variables.
    Automatic production admin seeding is forbidden — use scripts/provision_admin.py instead.
    """
    if settings.ENVIRONMENT.lower() == "production":
        logger.info("Automatic admin seeding skipped in production environment.")
        return None

    admin_email = (settings.INITIAL_ADMIN_EMAIL or "").strip()
    admin_password = (settings.INITIAL_ADMIN_PASSWORD or "").strip()

    if not admin_email or not admin_password:
        return None

    admin = get_user_by_email(db, admin_email)
    if not admin:
        admin_create = UserCreate(
            email=admin_email,
            password=admin_password,
            full_name="ActTrident Admin",
            role="admin"
        )
        return create_user(db, admin_create, role="admin")
    return admin
