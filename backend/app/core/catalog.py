MODULE_DEFINITIONS = {
    "inventory": {
        "label": "Inventario",
        "route": "/inventario",
        "description": "Control de existencias y movimientos.",
    },
    "pos": {
        "label": "POS",
        "route": "/pos",
        "description": "Punto de venta para cobro en mostrador.",
    },
    "crm": {
        "label": "CRM",
        "route": "/crm",
        "description": "Clientes, oportunidades y seguimiento comercial.",
    },
    "pm": {
        "label": "PM",
        "route": "/pm",
        "description": "Gestión de proyectos y tareas.",
    },
    "billing_pending": {
        "label": "Facturación pendiente",
        "route": "/facturacion-pendiente",
        "description": "Módulo fiscal reservado para implementación futura.",
    },
    "superadmin": {
        "label": "Superadmin",
        "route": "/superadmin",
        "description": "Herramientas internas de administración técnica.",
    },
}

PLAN_CATALOG = {
    "basico": ["inventory"],
    "pro": ["inventory", "pos", "billing_pending"],
    "total": ["inventory", "pos", "billing_pending", "crm", "pm"],
}

ALLOWED_PLAN_CODES = set(PLAN_CATALOG.keys())
ALLOWED_ACCESS_STATUSES = {"trial", "active", "past_due", "suspended", "cancelled"}
ACTIVE_COMPANY_STATUSES = {"trial", "active", "past_due"}

