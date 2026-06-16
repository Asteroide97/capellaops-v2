from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import EmpresaSummary, MembershipSummary, UserSummary


class RegisterStartRequest(BaseModel):
    empresa_nombre: str = Field(min_length=2, max_length=160)
    empresa_razon_social: str | None = Field(default=None, max_length=180)
    empresa_rfc: str | None = Field(default=None, max_length=32)
    empresa_giro: str | None = Field(default=None, max_length=120)
    empresa_telefono: str | None = Field(default=None, max_length=40)
    empresa_email_contacto: EmailStr | None = None
    empresa_pais: str | None = Field(default=None, max_length=80)
    empresa_estado: str | None = Field(default=None, max_length=80)
    empresa_ciudad: str | None = Field(default=None, max_length=80)
    empresa_direccion: str | None = Field(default=None, max_length=500)
    nombre_completo: str = Field(min_length=2, max_length=160)
    email: EmailStr
    country_code: str = Field(min_length=2, max_length=8)
    phone_number: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    plan_code: str = Field(default="basico")
    recaptcha_token: str | None = Field(default=None, max_length=4096)

    @field_validator("empresa_email_contacto", mode="before")
    @classmethod
    def normalize_contact_email(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


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


class PasswordResetStartRequest(BaseModel):
    email: EmailStr
    phone: str = Field(min_length=8, max_length=32)


class PasswordResetGenericResponse(BaseModel):
    ok: bool
    message: str


class PasswordResetVerifyRequest(BaseModel):
    email: EmailStr
    phone: str = Field(min_length=8, max_length=32)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordResetVerifyResponse(BaseModel):
    reset_token: str
    expires_in_minutes: int


class PasswordResetCompleteRequest(BaseModel):
    reset_token: str = Field(min_length=16, max_length=255)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetCompleteResponse(BaseModel):
    ok: bool
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserSummary
    empresa: EmpresaSummary
    membership: MembershipSummary
