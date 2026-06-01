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
- PM Core Fase 1 operativo
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
- `GET /company/users`
- `POST /company/users/invite`
- `PATCH /company/users/{empresa_usuario_id}`
- `POST /company/users/{empresa_usuario_id}/deactivate`
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
- `POST /inventory/purchase-orders/{id}/cancel`
- `POST /inventory/purchase-orders/{id}/receive`

### POS Fase 1

- `GET /pos/catalog`
- `GET /pos/sales`
- `GET /pos/sales/{id}`
- `POST /pos/sales`
- `POST /pos/sales/{id}/cancel`
- `GET /pos/ticket/{id}`

### PM Core Fase 1

- `GET /pm/config`
- `GET /pm/dashboard`
- `GET /pm/projects`
- `POST /pm/projects`
- `GET /pm/projects/{project_id}`
- `PUT /pm/projects/{project_id}`
- `POST /pm/projects/{project_id}/deactivate`
- `GET /pm/projects/{project_id}/members`
- `POST /pm/projects/{project_id}/members`
- `POST /pm/projects/{project_id}/members/{member_id}/deactivate`
- `GET /pm/projects/{project_id}/tasks`
- `POST /pm/projects/{project_id}/tasks`
- `GET /pm/tasks/{task_id}`
- `PUT /pm/tasks/{task_id}`
- `POST /pm/tasks/{task_id}/deactivate`
- `POST /pm/tasks/{task_id}/subtasks`
- `PUT /pm/subtasks/{subtask_id}`
- `POST /pm/tasks/{task_id}/checklist`
- `PUT /pm/checklist/{item_id}`
- `POST /pm/projects/{project_id}/comments`
- `POST /pm/tasks/{task_id}/comments`

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

## Empresa, usuarios y limites por plan

- El registro crea una `Empresa` real y el usuario inicial queda vinculado como `owner`.
- El registro no crea almacenes automaticamente.
- El onboarding posterior crea el primer almacen y ahora respeta el limite del plan.
- Los usuarios adicionales se vinculan a la empresa existente por `EmpresaUsuario`.
- Los planes controlan:
  - modulos
  - `max_usuarios`
  - `max_almacenes`
  - `max_facturas_mensuales`
- `null` significa ilimitado.
- `productos_ilimitados` y `ventas_ilimitadas` quedan preparados en el modelo del plan.
- `/me` devuelve:
  - empresa activa con datos ampliados
  - rol del usuario
  - limites actuales de usuarios y almacenes
  - modulos operativos
- Endpoints de usuarios de empresa:
  - `GET /company/users`
  - `POST /company/users/invite`
  - `PATCH /company/users/{empresa_usuario_id}`
  - `POST /company/users/{empresa_usuario_id}/deactivate`
- Flujo actual de usuarios:
  - si el correo ya existe, se vincula a la empresa
  - si ya pertenece a la empresa, responde `already_member`
  - si no existe, se registra una invitacion pendiente
- La pantalla `Empresa > Usuarios` ahora muestra:
  - resumen visual de cupo del plan
  - miembros activos y pendientes
  - modal de invitacion
  - cambio de rol
  - desactivacion y reactivacion
- El envio real de email de invitacion sigue pendiente.

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
- Opera con requisiciones `aprobada` o `parcial`.
- Requiere `proveedor_id` y `almacen_destino_id`.
- Crea la OC en `borrador`, copia solo cantidades pendientes y calcula totales en backend.
- Guarda `requisiciones.orden_compra_id` para evitar duplicados.
- La requisicion pasa a `convertida_a_oc` cuando queda vinculada.

### Requisiciones operativas

- Estados operativos:
  - `borrador`
  - `enviada`
  - `aprobada`
  - `parcial`
  - `surtida`
  - `convertida_a_oc`
  - `rechazada`
  - `cancelada`
- Flujo general:
  - una requisicion se crea en `borrador`
  - puede enviarse para aprobacion
  - una requisicion `aprobada` o `parcial` puede surtirse desde inventario o convertirse en OC
- Surtido desde inventario:
  - `POST /inventory/requisitions/{id}/fulfill`
  - valida stock por almacen
  - no permite surtir mas que la cantidad pendiente
  - crea movimientos `salida` y descuenta existencias en una sola transaccion
  - actualiza `cantidad_surtida` por renglon
  - cambia la requisicion a `parcial` o `surtida`
- Requisicion para proyecto:
  - soporta `es_proyecto`, `proyecto_id` y `proyecto_nombre_snapshot`
  - los movimientos de surtido heredan esa referencia para que Kardex y Movimientos muestren el proyecto
  - la conexion con PM es preparatoria; no existe consumo formal de PM en esta fase
- Trazabilidad:
  - el surtido queda rastreable por `movimientos_inventario`
  - la OC vinculada queda visible desde la requisicion
- Pendientes:
  - aprobacion avanzada por rol
  - consumo formal PM
  - requisiciones automaticas desde PM
  - historial formal de surtidos
  - email y notificaciones

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

## PM Core Fase 1

- El modulo PM ya vive en `/pm` y queda habilitado solo para empresas con el modulo `pm` activo.
- El acceso se valida con contexto multiempresa por `empresa_id` y `can_access_module`.
- Si la empresa tiene PM habilitado pero aun no tiene configuracion, `GET /pm/config` crea `EmpresaPMConfig` con defaults seguros.

### Incluye en esta fase

- Configuracion PM por empresa:
  - `pm_enabled`
  - `pm_tareas_enabled`
  - `pm_materiales_enabled`
  - `pm_tiempo_enabled`
  - `pm_templates_enabled`
  - `pm_comercial_enabled`
  - `pm_portal_enabled`
- CRUD base de proyectos
- Miembros de proyecto
- CRUD base de tareas
- Subtareas simples
- Checklist simple
- Comentarios de proyecto y de tarea
- Dashboard PM basico
- UI inicial:
  - `Gestion de Proyectos` dashboard
  - listado de proyectos
  - detalle de proyecto con tabs
  - kanban simple por estatus

### Modelos principales

- `EmpresaPMConfig`
- `PMProyecto`
- `PMProyectoMiembro`
- `PMTarea`
- `PMSubtarea`
- `PMChecklistItem`
- `PMComentario`

### Reglas operativas

- Todo filtra por `empresa_id`.
- No se confia en `empresa_id` enviado por frontend.
- Los proyectos usan `activo=false` para desactivacion logica.
- `PMProyecto.codigo` es unico por empresa cuando se captura.
- El avance de proyecto se recalcula desde sus tareas activas:
  - tareas completadas / tareas activas * 100
- Si no hay tareas activas, el proyecto conserva su `porcentaje_avance` manual.
- Al completar una tarea se llena `fecha_completada` si no existe.

### Dashboard PM

`GET /pm/dashboard` devuelve:

- `proyectos_activos`
- `proyectos_atrasados`
- `tareas_vencidas`
- `tareas_pendientes`
- `tareas_en_progreso`
- `tareas_completadas`
- distribucion de proyectos por estatus
- distribucion de tareas por estatus
- proximos vencimientos de proyectos y tareas

### Pendientes de PM

- Materiales PM reales
- Reservas y consumos de inventario
- Tiempos, costos y tarifas
- Portal externo y documentos reales
- Gantt y calendario
- Ruta critica
- Aprobaciones
- Snapshots y automatizaciones
- Vinculos comerciales con ventas, facturas y cobranza

## PM Fase 2 - Materiales y consumo de inventario

- El proyecto ya puede planear materiales, generar requisiciones y acumular consumo real a partir de inventario.
- La integracion se mantiene transaccional y multiempresa por `empresa_id`.
- El stock sigue viviendo solo en `existencias` + `movimientos_inventario`.
- Mantenimiento queda explicitamente fuera del alcance actual de V2.

### Incluye en esta fase

- Plan de materiales por proyecto:
  - `GET /pm/projects/{project_id}/materials`
  - `POST /pm/projects/{project_id}/materials/plan`
  - `PUT /pm/projects/{project_id}/materials/plan/{plan_id}`
  - `POST /pm/projects/{project_id}/materials/plan/{plan_id}/deactivate`
- Costos de materiales por proyecto:
  - `GET /pm/projects/{project_id}/costs`
- Requisicion desde proyecto:
  - `POST /pm/projects/{project_id}/materials/create-requisition`
- Resumen extendido en dashboard PM:
  - costo estimado de materiales
  - costo real de materiales
  - variacion de materiales
  - proyectos con mayor costo de materiales
  - proyectos sobre presupuesto de materiales

### Modelos principales de PM Fase 2

- `PMProyectoMaterialPlan`
- `PMProyectoMaterialConsumo`
- `PMProyectoCostoResumen`

### Reglas operativas

- Los materiales planeados no modifican stock.
- El consumo real no se captura directo desde PM; se genera desde inventario.
- El consumo real se crea automaticamente cuando:
  - se surte una requisicion de proyecto con `proyecto_id`
  - se registra una salida manual de inventario por `movements/bulk` con `proyecto_id`
- Si solo existe `proyecto_nombre_snapshot` sin `proyecto_id`, la trazabilidad queda en movimientos, pero no se crea consumo formal PM.
- `PMProyectoMaterialConsumo` evita duplicados por `movimiento_id`.
- Los costos reales usan snapshots del movimiento y luego actualizan `PMProyectoCostoResumen`.

### Pendientes de PM Fase 2

- Reservas formales de stock
- Bloqueo de stock reservado
- Compras directas desde PM
- Horas y costos laborales
- Presupuesto / APU basico
- Portal cliente
- Gantt
- Aprobaciones
- Vinculos comerciales
- Cualquier funcionalidad de mantenimiento

## PM Fase 3 - Horas, tarifas y costo laboral

- PM ya puede registrar horas por proyecto y tarea.
- PM ya puede configurar tarifas por usuario y por rol.
- Cada registro de horas guarda snapshot de:
  - tarifa aplicada
  - costo total
  - fuente de tarifa
- El costo total del proyecto ahora suma:
  - materiales reales
  - horas reales
- Mantenimiento sigue fuera del alcance actual.

### Endpoints principales de PM Fase 3

- Registro de horas:
  - `GET /pm/projects/{project_id}/time-entries`
  - `POST /pm/projects/{project_id}/time-entries`
  - `PUT /pm/time-entries/{time_entry_id}`
  - `POST /pm/time-entries/{time_entry_id}/deactivate`
- Tarifas por usuario:
  - `GET /pm/rates/users`
  - `POST /pm/rates/users`
  - `PUT /pm/rates/users/{rate_id}`
  - `POST /pm/rates/users/{rate_id}/deactivate`
- Tarifas por rol:
  - `GET /pm/rates/roles`
  - `POST /pm/rates/roles`
  - `PUT /pm/rates/roles/{rate_id}`
  - `POST /pm/rates/roles/{rate_id}/deactivate`
- Costos:
  - `GET /pm/projects/{project_id}/costs`
  - `POST /pm/projects/{project_id}/costs/refresh`

### Reglas operativas de PM Fase 3

- La tarifa se resuelve primero por usuario.
- Si no existe tarifa por usuario, se busca tarifa por rol.
- Si no existe ninguna tarifa vigente, el registro se guarda con costo `0` y `fuente_tarifa='sin_tarifa'`.
- Cambios posteriores de tarifa no modifican registros historicos.
- `costo_total_real` del proyecto se calcula como `costo_materiales_real + costo_horas_real`.
- `variacion_presupuesto` se calcula como `presupuesto_estimado - costo_total_real`.

### Pendientes de PM Fase 3

- Aprobaciones de horas
- Nomina
- Facturacion por horas
- Presupuestos detallados / APU
- Portal cliente
- Gantt

## PM Fase 4 - Presupuestos, partidas y APU básico

- PM ya puede manejar presupuesto detallado por proyecto sin tocar inventario ni costos reales históricos.
- Cada proyecto puede tener:
  - presupuesto activo
  - capítulos y partidas
  - APU básico por partida
  - indirectos
  - comparativo contra costo real acumulado
- Mantenimiento sigue fuera del alcance actual.

### Incluye en esta fase

- Presupuesto del proyecto:
  - `GET /pm/projects/{project_id}/budget`
  - `POST /pm/projects/{project_id}/budget`
  - `PUT /pm/budgets/{budget_id}`
  - `POST /pm/budgets/{budget_id}/approve`
  - `POST /pm/budgets/{budget_id}/cancel`
  - `POST /pm/projects/{project_id}/budget/refresh`
- Comparativo presupuesto vs real:
  - `GET /pm/projects/{project_id}/budget-vs-actual`
- Partidas:
  - `POST /pm/budgets/{budget_id}/items`
  - `PUT /pm/budget-items/{item_id}`
  - `POST /pm/budget-items/{item_id}/deactivate`
- APU de materiales:
  - `POST /pm/budget-items/{item_id}/materials`
  - `PUT /pm/budget-item-materials/{component_id}`
  - `POST /pm/budget-item-materials/{component_id}/deactivate`
- APU de mano de obra:
  - `POST /pm/budget-items/{item_id}/labor`
  - `PUT /pm/budget-item-labor/{component_id}`
  - `POST /pm/budget-item-labor/{component_id}/deactivate`
- Indirectos:
  - `POST /pm/budgets/{budget_id}/indirects`
  - `PUT /pm/budget-indirects/{indirect_id}`
  - `POST /pm/budget-indirects/{indirect_id}/deactivate`

### Reglas operativas de PM Fase 4

- El presupuesto detallado no crea facturas ni cobranza.
- El presupuesto detallado no afecta inventario ni stock.
- Los totales se calculan siempre en backend.
- Cada partida calcula:
  - costo unitario
  - precio unitario
  - subtotal costo
  - subtotal venta
- El APU básico integra:
  - materiales estimados por partida
  - mano de obra estimada por partida
  - indirectos a nivel presupuesto
- El comparativo usa:
  - costo real de materiales
  - costo real de horas
  - costo total real del proyecto
- El Project Workspace ya integra la vista `Presupuesto` dentro del detalle del proyecto.

### Modelos principales de PM Fase 4

- `PMPresupuesto`
- `PMPresupuestoPartida`
- `PMPresupuestoPartidaMaterial`
- `PMPresupuestoPartidaManoObra`
- `PMPresupuestoIndirecto`

### Pendientes de PM Fase 4

- Estados de pago y estimaciones formales
- Facturación y cobranza
- Aprobaciones complejas de presupuesto
- Versionado avanzado y sustitución formal de presupuestos
- Integración contable
- Portal cliente
- Gantt editable
- Cualquier funcionalidad de mantenimiento

## PM UX tipo Project Workspace

- El detalle de proyecto en `/pm/projects/:id` ya opera como un workspace de proyecto más denso y menos fragmentado.
- La vista principal ahora se organiza por:
  - `Vista general`
  - `Plan de trabajo`
  - `Kanban`
  - `Presupuesto`
  - `Materiales`
  - `Tiempo y costos`
  - `Comentarios`
  - `Documentos`
- `Plan de trabajo` combina:
  - tabla de tareas
  - línea de tiempo tipo Gantt simple
  - panel de detalle de tarea
- El Gantt actual es solo visual:
  - sin drag & drop
  - sin dependencias
  - sin ruta crítica
  - sin edición directa sobre la barra
- `Materiales` sigue usando la integración PM ↔ Inventario de Fase 2.
- `Tiempo y costos` sigue usando el componente operativo de Fase 3 sin cambiar lógica de costos.

## PM Presupuesto UX simplificado

- La vista `Presupuesto` del Project Workspace ahora guía al usuario en cinco pasos:
  - presupuesto base
  - capítulos y partidas
  - desglose de costo
  - costos indirectos y margen
  - comparativo real
- El lenguaje principal deja de ser técnico:
  - `Desglose de costo de la partida`
  - `Materiales de la partida`
  - `Mano de obra de la partida`
  - `Costos indirectos`
- El flujo mantiene visibles las acciones clave:
  - crear presupuesto
  - agregar capítulo
  - agregar partida
  - agregar material
  - agregar mano de obra
  - agregar indirecto
  - aprobar presupuesto
  - actualizar totales
- El presupuesto puede crearse con payload mínimo seguro y, si ya existe uno activo, la vista reutiliza el existente sin error genérico.
- El comparativo sigue siendo solo económico:
  - no crea facturas
  - no afecta inventario
  - no sustituye los costos reales históricos

## PM Fase 4.5 - Prerrequisitos y dependencias de tareas

- PM ya soporta dependencias `finish_to_start` entre tareas del mismo proyecto.
- Una tarea puede quedar marcada como `Bloqueada` cuando tiene prerrequisitos activos pendientes.
- El backend impide avanzar una tarea bloqueada a:
  - `en_progreso`
  - `en_revision`
  - `completada`
- El Project Workspace muestra dependencias en:
  - plan de trabajo
  - panel de detalle de tarea
  - Gantt simple
- Kanban tambien muestra:
  - cards con bloqueo visible
  - tarea de la que depende
  - acciones para ver detalle, editar y avanzar
- La UX del plan de trabajo ahora agrega:
  - botón `Nueva tarea` sticky dentro de la vista
  - creación y edición de tarea con prerrequisitos desde el mismo modal
  - tabla y Gantt simple integrados en una sola vista operativa
  - Kanban separado como vista propia
- Queda pendiente:
  - dependencias avanzadas
  - lag real sobre fechas
  - recálculo automático
  - ruta crítica
  - drag & drop

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

## Órdenes de compra operativas

Las órdenes de compra ya siguen el flujo base:

`Requisición -> Aprobación -> OC -> Emisión -> Recepción parcial/total -> Entrada a inventario`

### Estados de OC

- `borrador`
- `emitida`
- `recibida_parcial`
- `recibida`
- `cancelada`

### Reglas actuales

- `borrador`
  - se puede editar
  - se pueden agregar o quitar renglones
  - se puede emitir
  - no afecta inventario
- `emitida`
  - permite recepción
  - ya no se edita libremente
  - no afecta inventario hasta recibir
- `recibida_parcial`
  - permite recibir faltantes
  - bloquea sobre-recepción
- `recibida`
  - cierra la orden
  - no permite recibir más
- `cancelada`
  - no permite emitir ni recibir
  - la cancelación básica solo opera si no hubo recepción previa

### Endpoints operativos

- `POST /inventory/purchase-orders`
- `POST /inventory/purchase-orders/{id}/details`
- `PUT /inventory/purchase-orders/{id}/details/{detail_id}`
- `DELETE /inventory/purchase-orders/{id}/details/{detail_id}`
- `POST /inventory/purchase-orders/{id}/issue`
- `POST /inventory/purchase-orders/{id}/cancel`
- `POST /inventory/purchase-orders/{id}/receive`

### Recepción

- soporta recepción parcial y total por renglón
- bloquea recibir más de lo pendiente
- acepta `documento_referencia` y `notas`
- crea movimientos tipo `entrada`
- aumenta `existencias`
- actualiza `cantidad_recibida` por renglón
- cambia estatus a `recibida_parcial` o `recibida`

### Trazabilidad

- la recepción queda trazada en `movimientos_inventario`
- los movimientos guardan:
  - `referencia_tipo = purchase_order_receive`
  - `referencia_id = <order_id>`
  - `documento_referencia` cuando se captura
- Kardex refleja estas entradas porque se construye desde movimientos reales

### Vínculo con requisiciones

- `POST /inventory/requisitions/{id}/create-purchase-order`
- opera con requisiciones `aprobada` o `parcial`
- crea la OC en `borrador`
- copia solo cantidades pendientes y enlaza `requisiciones.orden_compra_id`

### Pendientes de ordenes de compra

- PDF de OC
- envío por email al proveedor
- historial formal de recepciones
- cancelación avanzada con reversa de inventario
- cuentas por pagar
- adjuntos y remisiones

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
