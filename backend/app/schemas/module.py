from pydantic import BaseModel


class ModuleItem(BaseModel):
    name: str
    label: str
    route: str | None = None
    description: str
    enabled: bool
    pending: bool
    visible_in_sidebar: bool
    superadmin_only: bool
    reason: str | None = None


class ModulesResponse(BaseModel):
    empresa_id: str
    modules: list[ModuleItem]

