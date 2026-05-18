# Capella Ops V2

Monorepo inicial para un SaaS multiempresa con Azure SQL, FastAPI y React + Vite.

Estado actual:
- Core multiempresa operativo
- Registro con reCAPTCHA v3 y Twilio Verify SMS
- Inventario Fase 1 implementado
- Inventario Fase 1.2 implementado
- Onboarding obligatorio de primer almacén
- Portal Superadmin operativo

## Stack

- Frontend: React + Vite
- Backend: FastAPI
- Base de datos objetivo: Azure SQL
- ORM: SQLAlchemy
- Migraciones: Alembic
- Auth: JWT propio
- Verificacion de telefono: Twilio Verify SMS
- Antibot: reCAPTCHA validado en backend

## Estructura

```text
CapellaOpsV2/
  frontend/
  backend/
  docs/
  database/
```

## Requisitos

- Node.js 18+
- Python 3.11+
- ODBC Driver 18 for SQL Server

## Backend

1. Crear entorno virtual:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configurar variables:

```powershell
Copy-Item .env.example .env
```

3. Ejecutar migraciones:

```powershell
alembic upgrade head
```

4. Sembrar planes:

```powershell
python -m app.seed
```

5. Inspeccionar la base configurada:

```powershell
python -m app.debug_db
```

6. Levantar API:

```powershell
uvicorn app.main:app --reload
```

### Promover usuario a Superadmin

- Solo ejecutar desde `backend`.
- No exponer este flujo como endpoint.
- No usarlo desde frontend.

Promover:

```powershell
cd backend
python -m app.scripts.manage_superadmin promote --email "correo@dominio.com" --reason "Bootstrap superadmin inicial" --confirm
```

Retirar privilegios:

```powershell
cd backend
python -m app.scripts.manage_superadmin demote --email "correo@dominio.com" --reason "Retiro de privilegios superadmin" --confirm
```

Notas:

- Si omites `--confirm`, el script solo muestra lo que haria y no escribe cambios.
- El script solo cambia `usuarios.is_superadmin`.
- El script no toca `empresa_usuarios`, empresas, planes ni modulos.

### Endpoints incluidos

- `GET /health`
- `POST /auth/register/start`
- `POST /auth/register/verify`
- `POST /auth/login`
- `GET /me`
- `GET /modules`
- `GET /inventory/warehouses`
- `GET /inventory/warehouses/{id}`
- `POST /inventory/warehouses`
- `PUT /inventory/warehouses/{id}`
- `GET /inventory/onboarding-status`
- `POST /inventory/first-warehouse`
- `GET /inventory/materials`
- `GET /inventory/materials/{id}`
- `POST /inventory/materials`
- `PUT /inventory/materials/{id}`
- `GET /inventory/stock`
- `GET /inventory/movements`
- `GET /inventory/materials/{id}/kardex`
- `POST /inventory/movements`
- `GET /inventory/transfers`
- `GET /inventory/transfers/{id}`
- `POST /inventory/transfers`
- `PUT /inventory/transfers/{id}`
- `POST /inventory/transfers/{id}/details`
- `PUT /inventory/transfers/{id}/details/{detail_id}`
- `DELETE /inventory/transfers/{id}/details/{detail_id}`
- `POST /inventory/transfers/{id}/confirm`
- `POST /inventory/transfers/{id}/cancel`
- `GET /inventory/counts`
- `GET /inventory/counts/{id}`
- `POST /inventory/counts`
- `PUT /inventory/counts/{id}`
- `POST /inventory/counts/{id}/details`
- `PUT /inventory/counts/{id}/details/{detail_id}`
- `DELETE /inventory/counts/{id}/details/{detail_id}`
- `POST /inventory/counts/{id}/apply`
- `POST /inventory/counts/{id}/cancel`
- `GET /superadmin/overview`
- `GET /superadmin/companies`
- `GET /superadmin/companies/{id}`
- `PATCH /superadmin/companies/{id}/access`
- `GET /superadmin/users`
- `GET /superadmin/users/{id}`
- `POST /superadmin/impersonate`
- `GET /superadmin/audit-logs`

### Flujo de registro

1. `POST /auth/register/start`
   Valida reCAPTCHA, verifica que el correo y el telefono no existan todavia, crea o actualiza `PendingRegistration` y envia un codigo por SMS con Twilio Verify.
2. `POST /auth/register/verify`
   Verifica el codigo de 6 digitos por SMS y solo entonces crea `Empresa`, `Usuario`, `EmpresaUsuario`, `EmpresaModulo` y `AuditLog`.

### Onboarding de Inventario

1. Si la empresa no tiene almacenes activos y el usuario no es superadmin, la app fuerza el setup inicial.
2. `GET /inventory/onboarding-status`
   Indica si la empresa debe crear su primer almacén.
3. `POST /inventory/first-warehouse`
   Crea el primer almacén y desbloquea el dashboard normal.

### Variables relevantes

- `DATABASE_URL`
- `AZURE_SQL_SERVER`
- `AZURE_SQL_DATABASE`
- `AZURE_SQL_USERNAME`
- `AZURE_SQL_PASSWORD`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_VERIFY_SERVICE_SID`
- `TWILIO_VERIFY_CHANNEL`
- `VERIFY_DEV_MODE`
- `VERIFY_DEV_CODE`
- `RECAPTCHA_SECRET_KEY`
- `RECAPTCHA_MIN_SCORE`
- `RECAPTCHA_ENABLED`

## Frontend

1. Instalar dependencias:

```powershell
cd frontend
npm install
```

2. Configurar entorno:

```powershell
Copy-Item .env.example .env
```

3. Levantar Vite:

```powershell
npm run dev
```

### Variables relevantes

- `VITE_API_URL`
- `VITE_RECAPTCHA_SITE_KEY`

## Base de datos

- Produccion: usar Azure SQL mediante `DATABASE_URL` o variables `AZURE_SQL_*`.
- Alembic toma la URL resuelta desde `backend/.env`, sin depender del directorio desde donde se ejecute el comando.
- Si no se configura Azure SQL, el backend cae en SQLite local solo para smoke tests rapidos.
- Para aplicar cambios de esquema, ejecutar `alembic upgrade head`.

## Inventario Fase 1.2

- Todo dato de inventario se guarda con `empresa_id`.
- Todo endpoint de inventario valida autenticacion, contexto de empresa y acceso al modulo `inventory`.
- La verdad del stock vive en `existencias` + `movimientos_inventario`.
- `Material` no guarda `stock_actual` como fuente principal.
- No se permite stock negativo.
- Cada movimiento crea un registro auditable.
- Los listados devuelven `items`, `total`, `limit` y `offset`.
- Se agregaron filtros y paginacion para almacenes, materiales, existencias y movimientos.
- Se agregaron transferencias entre almacenes con confirmacion transaccional.
- Se agregaron conteos fisicos con snapshot de sistema y ajustes auditables al aplicar.
- Tipos de movimiento soportados:
  - `entrada`
  - `salida`
  - `ajuste`

### Endpoints operativos

- `GET /inventory/warehouses`
  Soporta `q`, `activo`, `limit`, `offset`.
- `GET /inventory/materials`
  Soporta `q`, `categoria`, `activo`, `stock_bajo`, `limit`, `offset`.
- `GET /inventory/stock`
  Soporta `almacen_id`, `material_id`, `q`, `stock_bajo`, `limit`, `offset`.
- `GET /inventory/movements`
  Soporta `almacen_id`, `material_id`, `tipo`, `fecha_desde`, `fecha_hasta`, `limit`, `offset`.
- `GET /inventory/warehouses/{id}`
  Devuelve detalle de un almacén de la empresa actual.
- `GET /inventory/materials/{id}`
  Devuelve detalle de un material de la empresa actual.
- `GET /inventory/transfers`
  Soporta `q`, `almacen_origen_id`, `almacen_destino_id`, `estatus`, `fecha_desde`, `fecha_hasta`, `limit`, `offset`.
- `GET /inventory/counts`
  Soporta `q`, `almacen_id`, `estatus`, `fecha_desde`, `fecha_hasta`, `limit`, `offset`.

### Flujo basico de transferencia

1. Crear una transferencia en borrador.
2. Seleccionar almacen origen y almacen destino.
3. Agregar materiales y cantidades.
4. Confirmar la transferencia.
5. El sistema registra una salida en origen y una entrada en destino dentro de la misma operacion.

### Flujo basico de conteo fisico

1. Crear un conteo en borrador por almacen.
2. Agregar materiales con cantidad fisica.
3. El sistema guarda la cantidad actual como snapshot.
4. Aplicar el conteo.
5. Si existe diferencia, se crea un movimiento de ajuste para dejar el stock igual a la cantidad fisica.

### Regla de reversa en esta fase

- En Inventario Fase 1.2 no se implementa reversa de transferencias confirmadas.
- En Inventario Fase 1.2 no se implementa reversa de conteos aplicados.
- Si se requiere reversa futura, debe documentarse y auditarse como una fase posterior.

### Flujo basico esperado

1. Crear un almacen.
2. Crear un material.
3. Registrar una `entrada`.
4. Consultar `GET /inventory/stock`.
5. Registrar una `salida` o un `ajuste`.
6. Consultar `GET /inventory/materials/{id}/kardex`.

## Superadmin

- Todos los endpoints `/superadmin` requieren usuario autenticado con `is_superadmin=true`.
- Un token impersonado no puede acceder al portal Superadmin.
- El portal permite:
  - ver overview operativo
  - listar empresas y usuarios
  - cambiar plan y `access_status` con razón obligatoria
  - revisar auditoría reciente
  - impersonar un usuario por 15 minutos máximo
- `Usuario.last_login_at` se actualiza en logins exitosos.

## Reglas implementadas

- Cada empresa tiene `plan_code`: `basico`, `pro` o `total`.
- Cada empresa tiene `access_status`: `trial`, `active`, `past_due`, `suspended`, `cancelled`.
- Toda empresa nueva inicia con trial de 15 dias.
- El contexto de empresa se valida desde backend mediante token y/o `X-Empresa-Id`.
- La funcion central `can_access_module(user, empresa, module_name)` gobierna acceso por plan, estado y rol.
- Facturacion existe solo como modulo pendiente y bloqueado para clientes.
- No se crea empresa hasta verificar el SMS.
- No se permiten mas de 5 intentos por codigo.
- No se permite reenviar codigo antes de 60 segundos.

## Notas

- No se usa Base44 ni SDKs relacionados.
- No se implementa `factura.com`.
- No se implementa timbrado CFDI.
- No se implementa CSD.
- Twilio Verify SMS requiere un Verify Service con canal `sms` habilitado y una cuenta/configuracion valida para envio de SMS.
