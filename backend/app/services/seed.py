from sqlalchemy.orm import Session

from app.core.catalog import MODULE_DEFINITIONS, PLAN_CATALOG
from app.models import Empresa, EmpresaModulo, Plan


PLAN_SEED_DATA = {
    "basico": {
        "name": "Básico",
        "description": "Inventario para operación esencial.",
    },
    "pro": {
        "name": "Pro",
        "description": "Inventario, POS y facturación marcada como pendiente.",
    },
    "total": {
        "name": "Total",
        "description": "Inventario, POS, CRM y gestión de proyectos.",
    },
}


def seed_default_plans(db: Session) -> None:
    for plan_code, config in PLAN_SEED_DATA.items():
        plan = db.get(Plan, plan_code)
        modules = PLAN_CATALOG[plan_code]
        if plan:
            plan.name = config["name"]
            plan.description = config["description"]
            plan.modules = modules
        else:
            db.add(
                Plan(
                    code=plan_code,
                    name=config["name"],
                    description=config["description"],
                    modules=modules,
                )
            )
    db.commit()


def build_company_modules(plan_code: str, empresa_id: str) -> list[EmpresaModulo]:
    plan_modules = set(PLAN_CATALOG.get(plan_code, []))
    module_names = [name for name in MODULE_DEFINITIONS if name != "superadmin"]
    return [
        EmpresaModulo(
            empresa_id=empresa_id,
            module_name=module_name,
            is_enabled=module_name in plan_modules,
            notes="Creado automáticamente a partir del plan asignado.",
        )
        for module_name in module_names
    ]


def sync_company_modules(empresa: Empresa, plan_code: str) -> None:
    plan_modules = set(PLAN_CATALOG.get(plan_code, []))
    module_names = [name for name in MODULE_DEFINITIONS if name != "superadmin"]
    module_map = {module.module_name: module for module in empresa.modules}

    for module_name in module_names:
        is_enabled = module_name in plan_modules
        existing = module_map.get(module_name)
        if existing:
            existing.is_enabled = is_enabled
            existing.notes = "Actualizado automÃ¡ticamente a partir del plan asignado."
            continue

        empresa.modules.append(
            EmpresaModulo(
                empresa_id=empresa.id,
                module_name=module_name,
                is_enabled=is_enabled,
                notes="Creado automÃ¡ticamente a partir del plan asignado.",
            )
        )
