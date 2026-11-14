import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user import User, RefreshToken
from app.schemas.auth import UserCreate
from app.core.security import (
    get_password_hash,
    verify_password,
    generate_refresh_token_string,
    hash_token
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_in: UserCreate, role: str = "sales_rep") -> User:
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email.lower().strip(),
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        role=role
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

    # Revoke current token
    now = datetime.now(timezone.utc)
    token_record.revoked_at = now

    # Issue new rotated refresh token
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
    """Revokes all active refresh tokens for a user upon logout or security compromise."""
    now = datetime.now(timezone.utc)
    tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None)
    ).all()
    count = 0
    for t in tokens:
        t.revoked_at = now
        count += 1
    db.commit()
    return count


def seed_default_admin(db: Session) -> Optional[User]:
    """Seeds initial administrator strictly from environment variables without hardcoded credentials."""
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
