import math
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.catalog import ALLOWED_PLAN_CODES, PLAN_CATALOG
from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models import AuditLog, Empresa, EmpresaUsuario, PendingRegistration, Plan, Usuario
from app.schemas.auth import (
    LoginRequest,
    RegisterStartRequest,
    RegisterStartResponse,
    RegisterVerifyRequest,
    TokenResponse,
)
from app.schemas.common import EmpresaSummary, MembershipSummary, UserSummary
from app.services.phone import PhoneValidationError, mask_phone, normalize_phone
from app.services.recaptcha import (
    RecaptchaConfigurationError,
    RecaptchaServiceError,
    RecaptchaValidationError,
    verify_recaptcha_token,
)
from app.services.seed import build_company_modules
from app.services.twilio_verify import (
    TwilioVerifyConfigurationError,
    TwilioVerifyInvalidCodeError,
    TwilioVerifyServiceError,
    check_phone_verification,
    start_phone_verification,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "empresa"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_unique_slug(db: Session, company_name: str) -> str:
    base_slug = slugify(company_name)
    slug = base_slug
    counter = 2
    while db.scalar(select(Empresa.id).where(Empresa.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def ensure_valid_plan_code(plan_code: str) -> str:
    normalized = plan_code.strip().lower()
    if normalized not in ALLOWED_PLAN_CODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"plan_code invalido. Usa: {', '.join(sorted(ALLOWED_PLAN_CODES))}.",
        )
    return normalized


def ensure_plan_seeded(db: Session, plan_code: str) -> Plan:
    plan = db.get(Plan, plan_code)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Los planes no estan inicializados. Ejecuta el seed primero.",
        )
    return plan


def get_pending_registration(db: Session, email: str) -> PendingRegistration | None:
    return db.scalar(select(PendingRegistration).where(PendingRegistration.email == normalize_email(email)))


def get_pending_registration_by_id(db: Session, pending_id: str) -> PendingRegistration | None:
    return db.get(PendingRegistration, pending_id)


def get_pending_registration_by_phone(db: Session, phone_e164: str) -> PendingRegistration | None:
    return db.scalar(
        select(PendingRegistration).where(
            PendingRegistration.phone_e164 == phone_e164,
            PendingRegistration.status == "pending",
        )
    )


def build_token_response(user: Usuario, empresa: Empresa, membership: EmpresaUsuario) -> TokenResponse:
    access_token = create_access_token(
        subject=user.id,
        empresa_id=empresa.id,
        extra_claims={"email": user.email},
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_superadmin=user.is_superadmin,
        ),
        empresa=EmpresaSummary(
            id=empresa.id,
            name=empresa.name,
            slug=empresa.slug,
            plan_code=empresa.plan_code,
            access_status=empresa.access_status,
            trial_ends_at=empresa.trial_ends_at,
        ),
        membership=MembershipSummary(role=membership.role),
    )


@router.post("/register/start", response_model=RegisterStartResponse)
def register_start(
    payload: RegisterStartRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterStartResponse:
    settings = get_settings()
    plan_code = ensure_valid_plan_code(payload.plan_code)
    email = normalize_email(payload.email)
    try:
        normalized_phone = normalize_phone(payload.country_code, payload.phone_number)
    except PhoneValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    now = datetime.now(timezone.utc)

    try:
        verify_recaptcha_token(
            payload.recaptcha_token,
            remote_ip=request.client.host if request.client else None,
            expected_action="register_start",
        )
    except RecaptchaValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RecaptchaConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except RecaptchaServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    existing_user_by_email = db.scalar(select(Usuario.id).where(Usuario.email == email))
    if existing_user_by_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo.",
        )

    existing_user_by_phone = db.scalar(select(Usuario.id).where(Usuario.phone_e164 == normalized_phone["phone_e164"]))
    if existing_user_by_phone:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este telefono ya esta registrado.",
        )

    ensure_plan_seeded(db, plan_code)
    pending = get_pending_registration(db, email)
    pending_by_phone = get_pending_registration_by_phone(db, normalized_phone["phone_e164"])

    if pending_by_phone and (pending is None or pending_by_phone.id != pending.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este telefono ya esta registrado.",
        )

    if pending and pending.last_sent_at:
        last_sent_at = ensure_utc(pending.last_sent_at)
        seconds_since_last_send = (now - last_sent_at).total_seconds()
        cooldown = settings.pending_registration_resend_cooldown_seconds
        if seconds_since_last_send < cooldown:
            seconds_left = math.ceil(cooldown - seconds_since_last_send)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Espera {seconds_left} segundos antes de reenviar otro codigo.",
            )

    if pending is None:
        pending = PendingRegistration(
            empresa_nombre=payload.empresa_nombre.strip(),
            nombre_completo=payload.nombre_completo.strip(),
            email=email,
            country_code=normalized_phone["country_code"],
            phone_number=normalized_phone["phone_number"],
            phone_e164=normalized_phone["phone_e164"],
            password_hash=get_password_hash(payload.password),
            plan_code=plan_code,
            status="pending",
            attempts=0,
            expires_at=now + timedelta(minutes=settings.pending_registration_ttl_minutes),
            last_sent_at=now,
        )
        db.add(pending)
    else:
        pending.empresa_nombre = payload.empresa_nombre.strip()
        pending.nombre_completo = payload.nombre_completo.strip()
        pending.country_code = normalized_phone["country_code"]
        pending.phone_number = normalized_phone["phone_number"]
        pending.phone_e164 = normalized_phone["phone_e164"]
        pending.password_hash = get_password_hash(payload.password)
        pending.plan_code = plan_code
        pending.status = "pending"
        pending.attempts = 0
        pending.expires_at = now + timedelta(minutes=settings.pending_registration_ttl_minutes)
        pending.last_sent_at = now

    try:
        start_phone_verification(normalized_phone["phone_e164"])
        db.commit()
        db.refresh(pending)
    except TwilioVerifyConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except TwilioVerifyServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return RegisterStartResponse(
        ok=True,
        message="Te enviamos un codigo por SMS.",
        pending_id=pending.id,
        masked_phone=mask_phone(normalized_phone["phone_e164"], normalized_phone["country_code"]),
        cooldown_seconds=settings.pending_registration_resend_cooldown_seconds,
    )


@router.post("/register/verify", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_verify(
    payload: RegisterVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    pending = get_pending_registration_by_id(db, payload.pending_id)

    if not pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay un registro pendiente para verificar.",
        )

    if pending.status in {"cancelled", "verified"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este registro pendiente ya no se puede verificar.",
        )

    expires_at = ensure_utc(pending.expires_at)
    if expires_at <= now:
        pending.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El codigo expiro. Solicita uno nuevo.",
        )

    if pending.attempts >= settings.pending_registration_max_attempts:
        pending.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Solicita un nuevo codigo.",
        )

    if db.scalar(select(Usuario.id).where(Usuario.email == pending.email)):
        pending.status = "cancelled"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo.",
        )

    if not pending.phone_e164 or not pending.country_code or not pending.phone_number:
        pending.status = "cancelled"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este registro pendiente no tiene un telefono valido.",
        )

    if db.scalar(select(Usuario.id).where(Usuario.phone_e164 == pending.phone_e164)):
        pending.status = "cancelled"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este telefono ya esta registrado.",
        )

    try:
        is_valid_code = check_phone_verification(pending.phone_e164, payload.code)
    except TwilioVerifyInvalidCodeError as exc:
        pending.attempts += 1
        if pending.attempts >= settings.pending_registration_max_attempts:
            pending.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Solicita un nuevo codigo.",
            ) from exc
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TwilioVerifyConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except TwilioVerifyServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if not is_valid_code:
        pending.attempts += 1
        if pending.attempts >= settings.pending_registration_max_attempts:
            pending.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Solicita un nuevo codigo.",
            )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo incorrecto.",
        )

    plan = ensure_plan_seeded(db, pending.plan_code)

    empresa = Empresa(
        name=pending.empresa_nombre,
        slug=build_unique_slug(db, pending.empresa_nombre),
        plan_code=plan.code,
        access_status="trial",
        trial_ends_at=now + timedelta(days=15),
    )
    user = Usuario(
        email=pending.email,
        full_name=pending.nombre_completo,
        password_hash=pending.password_hash,
        country_code=pending.country_code,
        phone_number=pending.phone_number,
        phone_e164=pending.phone_e164,
        phone_verified_at=now,
    )
    membership = EmpresaUsuario(role="owner", empresa=empresa, usuario=user)

    db.add_all([empresa, user, membership])
    db.flush()
    db.add_all(build_company_modules(plan.code, empresa.id))

    pending.status = "verified"
    pending.attempts = 0

    db.add(
        AuditLog(
            empresa_id=empresa.id,
            usuario_id=user.id,
            action="auth.register.verify",
            entity_name="empresa",
            entity_id=empresa.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={
                "plan_code": plan.code,
                "modules": PLAN_CATALOG[plan.code],
                "masked_phone": mask_phone(pending.phone_e164, pending.country_code),
            },
        )
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo finalizar el registro porque el correo, telefono o la empresa ya existen.",
        ) from exc

    db.refresh(empresa)
    db.refresh(user)
    db.refresh(membership)
    return build_token_response(user, empresa, membership)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(
        select(Usuario)
        .options(selectinload(Usuario.memberships).selectinload(EmpresaUsuario.empresa))
        .where(Usuario.email == normalize_email(payload.email))
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contrasena incorrectos.",
        )

    memberships = [membership for membership in user.memberships if membership.empresa is not None]
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene empresas asociadas.",
        )

    selected_membership = None
    if payload.empresa_id:
        selected_membership = next(
            (membership for membership in memberships if membership.empresa_id == payload.empresa_id),
            None,
        )
        if not selected_membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario no pertenece a la empresa indicada.",
            )
    elif len(memberships) == 1:
        selected_membership = memberships[0]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar empresa_id cuando el usuario pertenece a varias empresas.",
        )

    db.add(
        AuditLog(
            empresa_id=selected_membership.empresa_id,
            usuario_id=user.id,
            action="auth.login",
            entity_name="usuario",
            entity_id=user.id,
            ip_address=request.client.host if request.client else None,
            metadata_json={"empresa_id": selected_membership.empresa_id},
        )
    )
    db.commit()

    return build_token_response(user, selected_membership.empresa, selected_membership)
