import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

VALID_ROLES = {"admin", "manager", "sales_rep"}


def _validate_strong_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    return password


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str
    role: Optional[str] = "sales_rep"  # Note: self-registration ignores role and enforces sales_rep

    @field_validator("password")
    @classmethod
    def check_password_policy(cls, v: str) -> str:
        return _validate_strong_password(v)


class AdminUserCreate(UserBase):
    password: str
    role: str = "sales_rep"  # admin, sales_rep, manager

    @field_validator("password")
    @classmethod
    def check_password_policy(cls, v: str) -> str:
        return _validate_strong_password(v)

    @field_validator("role")
    @classmethod
    def check_role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role must be one of {sorted(VALID_ROLES)}")
        return v


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def check_role_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role must be one of {sorted(VALID_ROLES)}")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    tv: Optional[int] = None
    exp: Optional[int] = None
