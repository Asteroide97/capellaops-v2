from datetime import datetime, timezone

from app.core.catalog import ACTIVE_COMPANY_STATUSES, MODULE_DEFINITIONS, PLAN_CATALOG
from app.models import Empresa, Usuario
from app.models.mixins import utcnow
from app.schemas.module import ModuleItem


def can_access_company(empresa: Empresa, *, now: datetime | None = None) -> bool:
    if empresa.access_status not in ACTIVE_COMPANY_STATUSES:
        return False
    if empresa.access_status != "trial":
        return True

    end = empresa.trial_ends_at
    if end is None:
        return False
    # SQLite drops tzinfo; trial instants are stored/interpreted as UTC.
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    current = now if now is not None else utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return end > current


def can_access_module(user: Usuario, empresa: Empresa, module_name: str, *, now: datetime | None = None) -> bool:
    if not user.is_active:
        return False

    if module_name == "superadmin":
        return user.is_superadmin

    if not can_access_company(empresa, now=now):
        return False

    plan_modules = set(PLAN_CATALOG.get(empresa.plan_code, []))
    if module_name not in plan_modules:
        return False

    company_overrides = {module.module_name: module for module in empresa.modules}
    override = company_overrides.get(module_name)
    if override and not override.is_enabled:
        return False

    if module_name == "billing_pending":
        return user.is_superadmin

    return True


def build_module_payload(user: Usuario, empresa: Empresa) -> list[ModuleItem]:
    modules: list[ModuleItem] = []
    plan_modules = PLAN_CATALOG.get(empresa.plan_code, [])
    now = utcnow()

    for module_name in plan_modules:
        definition = MODULE_DEFINITIONS[module_name]
        has_access = can_access_module(user, empresa, module_name, now=now)
        is_pending = module_name == "billing_pending"
        modules.append(
            ModuleItem(
                name=module_name,
                label=definition["label"],
                route=definition["route"] if has_access else None,
                description=definition["description"],
                enabled=has_access,
                pending=is_pending,
                visible_in_sidebar=True,
                superadmin_only=is_pending,
                reason=(
                    "Pendiente para clientes. Sin operaciones fiscales habilitadas."
                    if is_pending and not user.is_superadmin
                    else "La empresa no tiene acceso operativo a este módulo."
                    if not has_access
                    else None
                ),
            )
        )

    if user.is_superadmin:
        definition = MODULE_DEFINITIONS["superadmin"]
        modules.append(
            ModuleItem(
                name="superadmin",
                label=definition["label"],
                route=definition["route"],
                description=definition["description"],
                enabled=True,
                pending=False,
                visible_in_sidebar=True,
                superadmin_only=True,
            )
        )

    return modules

