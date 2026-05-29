# Capella Ops V2

Monorepo para un SaaS multiempresa con Azure SQL, FastAPI y React + Vite.

## Estado actual

- Core multiempresa operativo
- Registro con reCAPTCHA v3 y Twilio Verify SMS
- Onboarding obligatorio del primer almacén
- Portal Superadmin operativo
- Inventario Shell operativo con navegación lateral desplegable
- Inventario Fase 1.2 operativo
- Compras Fase 1 operativa dentro del dominio de Inventario
- POS Fase 1 operativo
- Dashboard operativo en `Inventario > Resumen`

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

- `GET /inventory/summary`
- `GET /inventory/warehouses`
- `GET /inventory/warehouses/{id}`
- `POST /inventory/warehouses`
- `PUT /inventory/warehouses/{id}`
- `GET /inventory/materials`
- `POST /inventory/materials/image-upload`
- `GET /inventory/materials/{id}`
- `POST /inventory/materials`
- `POST /inventory/materials/{id}/create-requisition`
- `PUT /inventory/materials/{id}`
- `GET /inventory/stock`
- `GET /inventory/movements`
- `POST /inventory/movements`
- `POST /inventory/movements/bulk`
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
- `POST /inventory/requisitions/{id}/create-purchase-order`
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

La navegación de Inventario vive en el sidebar lateral desplegable. El layout interno ya no muestra una barra horizontal duplicada.

Subrutas visibles:

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

Las primeras nueve secciones ya están conectadas a datos reales o flujos operativos. Las últimas cuatro siguen como placeholder documentado para fases posteriores.

## Dashboard de Resumen

`GET /inventory/summary` construye un dashboard operativo calculado desde `existencias` y `movimientos_inventario`, sin duplicar la verdad del stock en `Material`.

### Métricas incluidas

- KPIs:
  - `materiales_bajo_stock`
  - `ordenes_compra_pendientes`
  - `requisiciones_pendientes`
  - `total_materiales`
- Indicadores:
  - `valor_inventario`
  - `costo_reposicion`
  - `ajustes_mes`
  - `merma_mes`
- Listas:
  - `productos_core`
  - `baja_rotacion`
  - `materiales_bajo_stock`
  - `alertas`

### Reglas del resumen

- El stock global se calcula como la suma de `existencias` por material.
- `Material.stock_actual` no existe como fuente de verdad.
- `valor_inventario` usa `stock_total * costo_promedio_actual`, con fallback a `costo_unitario`.
- `costo_reposicion` estima el faltante contra `stock_minimo`.
- `merma_mes` queda en `0` hasta implementar clasificación formal de merma.

### Pendientes del dashboard

- Escaneo QR o código de barras real
- Notificaciones persistentes
- Envío automático de alertas por email
- Merma formal
- Reportes avanzados

## Conexiones de Inventario

### POS -> Inventario

- La venta pagada crea una salida por cada renglon.
- La cancelacion crea entradas inversas y devuelve stock.
- Cada `VentaDetalle` guarda `movimiento_inventario_id`.
- El flujo valida stock suficiente y no permite stock negativo.

### Compras -> Inventario

- La recepcion de OC crea movimientos `entrada`.
- Soporta recepcion parcial y total.
- Actualiza `cantidad_recibida`.
- Cambia estatus a `recibida_parcial` o `recibida`.

### Requisicion -> Orden de compra

- `POST /inventory/requisitions/{id}/create-purchase-order`
- Solo opera con requisiciones `aprobada`.
- Requiere `proveedor_id` y `almacen_destino_id`.
- Crea la OC en `borrador`, copia detalles y calcula totales en backend.
- Guarda `requisiciones.orden_compra_id` para evitar duplicados.
- La requisicion se mantiene `aprobada` hasta que la OC avance en compras.

### Bajo stock -> requisicion sugerida

- `POST /inventory/materials/{id}/create-requisition`
- Calcula stock total desde `existencias`.
- Sugiere cantidad usando `stock_minimo` y `stock_maximo`.
- Usa `proveedor_principal_id` como sugerencia cuando existe.
- Bloquea duplicados si ya existe una requisicion pendiente para el material.

### Proveedor -> Material

- `Material.proveedor_principal_id` se valida contra la misma empresa.
- Los responses de materiales incluyen nombre y RFC del proveedor principal cuando existe.

### Movimientos -> PM placeholder

- Los movimientos bulk aceptan `es_proyecto`, `proyecto_id` y `proyecto_nombre_snapshot`.
- Kardex y movimientos muestran la referencia de proyecto cuando se captura.
- No existe FK real a PM en esta fase.

### Pendientes de conexiones

- CRMProveedorMaterial
- PM real con FK
- Notificaciones persistentes
- Email de bajo stock
- Acavike
- Tiendanube
- Facturacion via POS / CFDI

## Inventario Fase 1.2

- Todo dato de inventario se guarda con `empresa_id`.
- Todo endpoint de inventario valida autenticación, contexto de empresa y acceso al módulo `inventory`.
- La verdad del stock vive en `existencias` + `movimientos_inventario`.
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

## Inventario UX/UI Parity

- Se adopta `Inter` como tipografia global del frontend para acercar la jerarquia visual al estilo SaaS de V1.
- El sidebar pasa a usar iconografia consistente con `lucide-react`, con Inventario desplegable y subrutas visibles con icono propio.
- Se elimina la base visual perla/beige y se adopta una base blanca con sombras suaves, bordes neutros y superficies limpias.
- Se agrega `GET /inventory/materials` con búsqueda por `sku`, `nombre`, `categoria`, `subcategoria` y `codigo_barras`.
- Se agrega `POST /inventory/movements/bulk` para registrar entradas, salidas y ajustes multi-artículo en una sola transacción.
- `Material` ahora soporta `imagen_url`, `imagenes_extra_json` como texto JSON, `codigo_barras`, `subcategoria`, `stock_maximo`, `ubicacion_texto`, `proveedor_principal_id`, `lead_time_dias` y `costo_promedio_actual`.
- `Proveedor` ahora soporta `razon_social` y `rfc`.
- El stock actual visible en materiales y dashboard sigue calculándose desde `existencias` y `movimientos_inventario`. No se introduce `Material.stock_actual` como fuente de verdad.
- Se rediseñan visualmente `Inventario > Resumen`, `Materiales`, `Movimientos`, `Kardex` y `Proveedores` con una base de UI consistente para operación diaria.
- La navegación del módulo Inventario queda centralizada en el sidebar lateral desplegable. No se reintroduce navegación horizontal interna.
- Se unifican cards, tablas, modales, botones, inputs y badges bajo una misma capa visual del módulo Inventario.

### Flujo operativo agregado

- Materiales:
  - Alta y edición por modal.
  - Carga de imagen principal desde archivo, galería o cámara cuando el navegador la soporta.
  - Búsqueda por SKU y código de barras.
  - `imagen_url` sigue siendo el campo persistido y se alimenta desde upload.
  - Exportación CSV client-side de la vista actual.
  - Categoría obligatoria y proveedor principal opcional.
- Movimientos:
  - Carrito multi-artículo.
  - Búsqueda manual por SKU, nombre o código de barras.
  - Evidencia fotográfica por URL.
  - Campos operativos: motivo, entregado por, recibido por, documento y referencia.
  - Vinculación preparatoria con proyectos mediante `es_proyecto`, `proyecto_id` y `proyecto_nombre_snapshot`.
  - Snapshot de costo unitario y costo promedio por movimiento.
- Kardex:
  - Vista auditada con filtros, badges y tabla densa.
  - Muestra entrada, salida, balance, costo snapshot, valor inventario y usuario cuando el backend lo entrega.
- Proveedores:
  - Vista operativa con RFC, razón social y modal de edición rediseñado.

### Pendientes de esta capa

- Robustecer el escaneo por cámara para más navegadores y escenarios de producción; hoy depende de permisos, soporte del navegador y HTTPS.
- Importación backend de Excel/CSV para materiales. En esta fase queda solo placeholder en UI.
- FK real a PM/Proyectos cuando el módulo PM exista.
- Costo promedio ponderado formal.
- Estados borrador/cancelado para movimientos manuales base.

## SKU, código de barras y escáner

- `SKU` es obligatorio por material y sigue siendo único por empresa.
- `codigo_barras` es opcional, pero cuando existe se valida como único por empresa.
- La búsqueda general de materiales ya soporta `sku`, `codigo_barras` y `nombre`.
- Se agrega `GET /inventory/materials/lookup?code=...` para búsqueda exacta por escáner sobre `sku` o `codigo_barras`.
- El lookup exacto devuelve el material, `stock_total` y `stock_por_almacen`.
- Los lectores USB funcionan como teclado:
  - Materiales: Enter ejecuta búsqueda/lookup.
  - Movimientos: Enter busca por código y agrega al carrito multi-artículo.
  - Resumen: Enter consulta el material exacto.
  - POS: Enter filtra por código y, si hay una sola coincidencia, agrega al carrito.
- Se agrega escáner por cámara en navegador compatible usando `@zxing/browser`.
- La cámara funciona en celular o computadora si el navegador soporta `getUserMedia`.
- En producción la cámara requiere HTTPS.
- Si no hay permisos o no existe cámara disponible, la UI permite captura manual del código.
- Integración actual:
  - Materiales: escanear/buscar y capturar SKU o código de barras en el modal.
  - Movimientos: escanear/agregar material exacto al carrito.
  - Resumen: escaneo rápido con resultado operativo y stock por almacén.
  - POS: búsqueda por `codigo_barras` en catálogo y escaneo básico para agregar si hay coincidencia única.

### Pendientes del escáner

- Escaneo por cámara depende del navegador, permisos y HTTPS en producción.
- No existe importación backend Excel/CSV.
- PM sigue usando `proyecto_id` / `proyecto_nombre_snapshot` sin FK real.

## Imágenes de materiales

- Las imágenes no se guardan en SQL.
- `Material.imagen_url` guarda la URL final de la imagen principal.
- `POST /inventory/materials/image-upload` recibe `multipart/form-data`, valida formato/tamaño y sube la imagen a Azure Blob Storage.
- El modal de `Nuevo Material` permite:
  - tomar foto desde celular o navegador compatible
  - elegir imagen desde galería o archivos
  - previsualizar la imagen antes de guardar
  - quitar la imagen antes de guardar
- Variables requeridas en backend:
  - `AZURE_STORAGE_CONNECTION_STRING`
  - `AZURE_STORAGE_CONTAINER`
  - `AZURE_STORAGE_PUBLIC_BASE_URL` si se requiere URL pública personalizada

### Pendientes de imágenes

- Imágenes adicionales
- Compresión automática
- Borrado físico del blob al quitar o reemplazar una imagen
- Thumbnails

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
9. Confirmar que el inventario aumenta en el almacén destino.

### Alcance actual

- Proveedores: CRUD básico con filtros y paginación.
- Requisiciones: borrador, detalles, envío, aprobación, rechazo, cancelación y creación de OC vinculada.
- Órdenes de compra: borrador, detalles, emisión y recepción parcial o total.
- Recepción conectada a inventario: implementada.

### Pendientes de Compras

- Cancelación avanzada de órdenes emitidas
- Historial formal de recepciones por documento
- Cuentas por pagar
- Integración fiscal

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
