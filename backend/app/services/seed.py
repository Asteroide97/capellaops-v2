from sqlalchemy.orm import Session

from app.core.catalog import MODULE_DEFINITIONS, PLAN_CATALOG
from app.models import Empresa, EmpresaModulo, Plan


PLAN_SEED_DATA = {
    "basico": {
        "name": "Basico",
        "description": "Inventario para operacion esencial.",
        "max_usuarios": 2,
        "max_almacenes": 1,
        "max_facturas_mensuales": 20,
        "productos_ilimitados": True,
        "ventas_ilimitadas": True,
    },
    "pro": {
        "name": "Pro",
        "description": "Inventario, POS y facturacion marcada como pendiente.",
        "max_usuarios": 3,
        "max_almacenes": 3,
        "max_facturas_mensuales": 50,
        "productos_ilimitados": True,
        "ventas_ilimitadas": True,
    },
    "total": {
        "name": "Total",
        "description": "Inventario, POS, CRM y gestion de proyectos.",
        "max_usuarios": 4,
        "max_almacenes": None,
        "max_facturas_mensuales": None,
        "productos_ilimitados": True,
        "ventas_ilimitadas": True,
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
            plan.max_usuarios = config["max_usuarios"]
            plan.max_almacenes = config["max_almacenes"]
            plan.max_facturas_mensuales = config["max_facturas_mensuales"]
            plan.productos_ilimitados = config["productos_ilimitados"]
            plan.ventas_ilimitadas = config["ventas_ilimitadas"]
        else:
            db.add(
                Plan(
                    code=plan_code,
                    name=config["name"],
                    description=config["description"],
                    modules=modules,
                    max_usuarios=config["max_usuarios"],
                    max_almacenes=config["max_almacenes"],
                    max_facturas_mensuales=config["max_facturas_mensuales"],
                    productos_ilimitados=config["productos_ilimitados"],
                    ventas_ilimitadas=config["ventas_ilimitadas"],
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
            notes="Creado automaticamente a partir del plan asignado.",
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
            existing.notes = "Actualizado automaticamente a partir del plan asignado."
            continue

        empresa.modules.append(
            EmpresaModulo(
                empresa_id=empresa.id,
                module_name=module_name,
                is_enabled=is_enabled,
                notes="Creado automaticamente a partir del plan asignado.",
            )
        )
