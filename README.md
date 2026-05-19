# Capella Ops V2

Monorepo para un SaaS multiempresa con Azure SQL, FastAPI y React + Vite.

## Estado actual

- Core multiempresa operativo
- Registro con reCAPTCHA v3 y Twilio Verify SMS
- Onboarding obligatorio de primer almacén
- Portal Superadmin operativo
- Inventario Shell operativo con navegación lateral desplegable
- Inventario Fase 1.2 operativo
- Compras Fase 1 operativa dentro del dominio de Inventario
- POS Fase 1 operativo

## Stack

- Frontend: React + Vite
- Backend: FastAPI
- Base de datos objetivo: Azure SQL
- ORM: SQLAlchemy
- Migraciones: Alembic
- Auth: JWT propio
- Verificación de teléfono: Twilio Verify SMS
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

4. Sembrar datos base:

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

- Si omites `--confirm`, el script solo muestra lo que haría y no escribe cambios.
- El script solo cambia `usuarios.is_superadmin`.
- El script no toca `empresa_usuarios`, empresas, planes ni módulos.

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

## Variables relevantes

### Backend

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

### Frontend

- `VITE_API_URL`
- `VITE_RECAPTCHA_SITE_KEY`

## Base de datos

- Producción: usar Azure SQL mediante `DATABASE_URL` o variables `AZURE_SQL_*`.
- Alembic toma la URL resuelta desde `backend/.env`.
- Si no se configura Azure SQL, el backend puede caer en SQLite local solo para smoke tests rápidos.
- Para aplicar cambios de esquema, ejecutar `alembic upgrade head`.

## Endpoints incluidos

### Core

- `GET /health`
- `POST /auth/register/start`
- `POST /auth/register/verify`
- `POST /auth/login`
- `GET /me`
- `GET /modules`

### Onboarding de inventario

- `GET /inventory/onboarding-status`
- `POST /inventory/first-warehouse`

### Inventario base

- `GET /inventory/warehouses`
- `GET /inventory/warehouses/{id}`
- `POST /inventory/warehouses`
- `PUT /inventory/warehouses/{id}`
- `GET /inventory/materials`
- `GET /inventory/materials/{id}`
- `POST /inventory/materials`
- `PUT /inventory/materials/{id}`
- `GET /inventory/stock`
- `GET /inventory/movements`
- `POST /inventory/movements`
- `GET /inventory/materials/{id}/kardex`

### Traspasos y conteos

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

### Compras Fase 1

- `GET /inventory/suppliers`
- `POST /inventory/suppliers`
- `GET /inventory/suppliers/{id}`
- `PUT /inventory/suppliers/{id}`
- `GET /inventory/requisitions`
- `POST /inventory/requisitions`
- `GET /inventory/requisitions/{id}`
- `PUT /inventory/requisitions/{id}`
- `POST /inventory/requisitions/{id}/details`
- `PUT /inventory/requisitions/{id}/details/{detail_id}`
- `DELETE /inventory/requisitions/{id}/details/{detail_id}`
- `POST /inventory/requisitions/{id}/submit`
- `POST /inventory/requisitions/{id}/approve`
- `POST /inventory/requisitions/{id}/reject`
- `POST /inventory/requisitions/{id}/cancel`
- `GET /inventory/purchase-orders`
- `POST /inventory/purchase-orders`
- `GET /inventory/purchase-orders/{id}`
- `PUT /inventory/purchase-orders/{id}`
- `POST /inventory/purchase-orders/{id}/details`
- `PUT /inventory/purchase-orders/{id}/details/{detail_id}`
- `DELETE /inventory/purchase-orders/{id}/details/{detail_id}`
- `POST /inventory/purchase-orders/{id}/issue`
- `POST /inventory/purchase-orders/{id}/receive`

### POS Fase 1

- `GET /pos/catalog`
- `GET /pos/sales`
- `GET /pos/sales/{id}`
- `POST /pos/sales`
- `POST /pos/sales/{id}/cancel`
- `GET /pos/ticket/{id}`

### Superadmin

- `GET /superadmin/overview`
- `GET /superadmin/companies`
- `GET /superadmin/companies/{id}`
- `PATCH /superadmin/companies/{id}/access`
- `GET /superadmin/users`
- `GET /superadmin/users/{id}`
- `POST /superadmin/impersonate`
- `GET /superadmin/audit-logs`

## Flujo de registro

1. `POST /auth/register/start`
   Valida reCAPTCHA, verifica que correo y teléfono no existan, crea o actualiza `PendingRegistration` y envía un código por SMS con Twilio Verify.
2. `POST /auth/register/verify`
   Verifica el código de 6 dígitos por SMS y solo entonces crea `Empresa`, `Usuario`, `EmpresaUsuario`, `EmpresaModulo` y `AuditLog`.

## Onboarding obligatorio de inventario

1. Si la empresa no tiene almacenes activos y el usuario no es superadmin, la app fuerza el setup inicial.
2. `GET /inventory/onboarding-status`
   Indica si la empresa debe crear su primer almacén.
3. `POST /inventory/first-warehouse`
   Crea el primer almacén y desbloquea el dashboard normal.

## Inventario Shell

La navegación lateral de Inventario ya es desplegable y expone estas subrutas:

- `Resumen`
- `Almacenes`
- `Materiales`
- `Movimientos`
- `Kardex`
- `Traspasos`
- `Proveedores`
- `Órdenes de compra`
- `Requisiciones`
- `Proyectos`
- `Equipos`
- `Órdenes de trabajo`
- `Reportes`

Las primeras nueve secciones ya están conectadas a datos reales o a flujos operativos de esta fase. Las últimas cuatro quedan como placeholder documentado para fases posteriores.

## Inventario Fase 1.2

- Todo dato de inventario se guarda con `empresa_id`.
- Todo endpoint de inventario valida autenticación, contexto de empresa y acceso al módulo `inventory`.
- La verdad del stock vive en `existencias` + `movimientos_inventario`.
- `Material` no guarda `stock_actual` como fuente principal.
- No se permite stock negativo.
- Cada movimiento crea un registro auditable.
- Los listados devuelven `items`, `total`, `limit` y `offset`.
- Se agregaron filtros y paginación para almacenes, materiales, existencias y movimientos.
- Se agregaron transferencias entre almacenes con confirmación transaccional.
- Se agregaron conteos físicos con snapshot de sistema y ajustes auditables al aplicar.

### Reglas operativas

- Tipos de movimiento: `entrada`, `salida`, `ajuste`
- No se implementa reversa de transferencias confirmadas en esta fase.
- No se implementa reversa de conteos aplicados en esta fase.

## Compras Fase 1

- Todo endpoint de compras corre dentro del dominio `/inventory`.
- Todo endpoint valida autenticación, empresa actual y acceso al módulo `inventory`.
- Proveedores, requisiciones y órdenes de compra quedan aislados por `empresa_id`.
- La recepción de órdenes de compra crea movimientos `entrada` y aumenta existencias en el almacén destino.

### Flujo básico

1. Crear proveedor.
2. Crear requisición en borrador.
3. Agregar detalles a la requisición.
4. Enviar y aprobar la requisición.
5. Crear orden de compra en borrador.
6. Agregar materiales y costos.
7. Emitir la orden.
8. Recibir parcial o total.
9. Confirmar que el inventario aumentó en el almacén destino.

### Alcance actual

- Proveedores: CRUD básico con filtros y paginación.
- Requisiciones: borrador, detalles, envío, aprobación, rechazo y cancelación.
- Órdenes de compra: borrador, detalles, emisión y recepción parcial o total.
- Recepción conectada a inventario: implementada.

### Pendientes de Compras

- Relación automática requisición → orden de compra.
- Cancelación avanzada de órdenes emitidas.
- Historial formal de recepciones por documento.
- Cuentas por pagar.
- Integración fiscal.

## POS Fase 1

- Todo endpoint POS valida autenticación, contexto de empresa y acceso al módulo `pos`.
- Toda venta se calcula en backend.
- Toda venta pagada descuenta inventario automáticamente.
- Existe ticket básico y cancelación básica con retorno de stock.

### Pendientes POS

- Corte de caja
- Pagos mixtos formales
- Descuentos avanzados
- Ticket imprimible formal
- Conexión con facturación fiscal

## Placeholders actuales

Estas vistas ya aparecen en el shell de Inventario, pero siguen reservadas para fases posteriores:

- `Proyectos`
- `Equipos`
- `Órdenes de trabajo`
- `Reportes`

## Notas

- No se usa Base44 ni SDKs relacionados.
- No se implementa factura.com, CFDI, timbrado, CSD ni Stripe en este estado del proyecto.
