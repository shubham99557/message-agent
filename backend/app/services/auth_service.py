from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserCreate
from app.core.security import get_password_hash, verify_password


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email.lower().strip(),
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        role=user_in.role or "sales_rep"
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


def seed_default_admin(db: Session) -> User:
    admin = get_user_by_email(db, "admin@acttrident.ai")
    if not admin:
        admin_create = UserCreate(
            email="admin@acttrident.ai",
            password="AdminPassword2026!",
            full_name="ActTrident Admin",
            role="admin"
        )
        return create_user(db, admin_create)
    return admin
