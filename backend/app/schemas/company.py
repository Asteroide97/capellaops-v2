from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import CompanyLimitsSummary


class CompanyUserItem(BaseModel):
    id: str
    kind: str
    usuario_id: str | None = None
    email: EmailStr
    full_name: str | None = None
    role: str
    status: str
    is_active: bool
    last_login_at: datetime | None = None
    invited_by_user_id: str | None = None
    created_at: datetime


class CompanyUsersListResponse(BaseModel):
    empresa_id: str
    empresa_nombre: str
    plan_code: str
    limits: CompanyLimitsSummary
    items: list[CompanyUserItem]


class CompanyUserInviteRequest(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=160)
    role: str = Field(default="user", min_length=4, max_length=40)


class CompanyUserInviteResponse(BaseModel):
    status: str
    message: str
    item: CompanyUserItem
    limits: CompanyLimitsSummary


class CompanyUserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, min_length=4, max_length=40)
    is_active: bool | None = None


class CompanyUserDeactivateResponse(BaseModel):
    ok: bool
    message: str
    item: CompanyUserItem
    limits: CompanyLimitsSummary
