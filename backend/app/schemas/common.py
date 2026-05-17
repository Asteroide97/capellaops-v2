from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserSummary(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_superadmin: bool


class EmpresaSummary(BaseModel):
    id: str
    name: str
    slug: str
    plan_code: str
    access_status: str
    trial_ends_at: datetime


class MembershipSummary(BaseModel):
    role: str


class MeResponse(BaseModel):
    user: UserSummary
    empresa: EmpresaSummary
    membership: MembershipSummary
    empresas: list[EmpresaSummary]

