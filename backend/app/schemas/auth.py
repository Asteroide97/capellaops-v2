from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import EmpresaSummary, MembershipSummary, UserSummary


class RegisterStartRequest(BaseModel):
    empresa_nombre: str = Field(min_length=2, max_length=160)
    nombre_completo: str = Field(min_length=2, max_length=160)
    email: EmailStr
    country_code: str = Field(min_length=2, max_length=8)
    phone_number: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    plan_code: str = Field(default="basico")
    recaptcha_token: str | None = Field(default=None, max_length=4096)


class RegisterStartResponse(BaseModel):
    ok: bool
    message: str
    pending_id: str
    masked_phone: str
    cooldown_seconds: int


class RegisterVerifyRequest(BaseModel):
    pending_id: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    empresa_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserSummary
    empresa: EmpresaSummary
    membership: MembershipSummary
