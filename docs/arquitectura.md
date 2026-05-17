# Arquitectura base

## Multiempresa

- `Empresa` representa al tenant.
- `Usuario` representa la identidad global.
- `EmpresaUsuario` resuelve membresías por tenant.
- Toda operación protegida obtiene contexto de empresa usando JWT y `X-Empresa-Id`.

## Módulos por plan

- `basico`: `inventory`
- `pro`: `inventory`, `pos`, `billing_pending`
- `total`: `inventory`, `pos`, `billing_pending`, `crm`, `pm`

## Facturación

- El módulo fiscal existe solo como placeholder pendiente.
- Los clientes no pueden ejecutar operaciones fiscales.
- Solo superadmin puede ver la página técnica.
- No hay integración con factura.com, CFDI o CSD en esta fase.

## Seguridad

- No se confía en permisos del frontend.
- `can_access_module(user, empresa, module_name)` centraliza la decisión de acceso.
- Se registran eventos básicos de auditoría para login y registro.

