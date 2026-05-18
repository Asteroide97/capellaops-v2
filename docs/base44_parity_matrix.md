# Matriz de Paridad Base44 vs CapellaOpsV2

## Introducción

Base44 se usará como referencia funcional e histórica para evitar regresiones de alcance, pero CapellaOpsV2 se está reconstruyendo limpio sobre un stack nuevo: FastAPI, React, Azure SQL, SQLAlchemy y Alembic.

La regla de esta matriz es simple: no asumir que una funcionalidad existe en V2 si no está claramente implementada hoy. Cuando exista duda, el estado se marca como `Parcial` o `Pendiente`.

## Estados válidos

- `Implementado`
- `Parcial`
- `Pendiente`
- `Congelado`
- `No aplica todavía`

## Matriz principal

| Área | Funcionalidad Base44 | Estado en V2 | Prioridad | Fase objetivo | Notas | Riesgo si falta |
| --- | --- | --- | --- | --- | --- | --- |
| Core | Multiempresa por tenant | Implementado | Crítica | Core actual | Existe separación por `empresa_id` y contexto de empresa. | Fuga de datos entre clientes. |
| Core | Auth de usuarios | Implementado | Crítica | Core actual | Login, registro y JWT propio ya existen. | Acceso no controlado a la plataforma. |
| Core | Roles | Parcial | Alta | Core hardening | Existen roles por empresa, pero la matriz de permisos aún no está expandida a todos los módulos futuros. | Permisos inconsistentes o sobreacceso. |
| Core | Planes comerciales | Implementado | Crítica | Core actual | `basico`, `pro`, `total`. | Venta y activación incorrectas por cliente. |
| Core | Trial | Implementado | Alta | Core actual | Trial de 15 días activo en flujo actual. | Onboarding comercial incompleto. |
| Core | Módulos por plan | Implementado | Crítica | Core actual | `/modules` y `can_access_module` ya gobiernan acceso. | Clientes viendo módulos no contratados. |
| Core | Superadmin | Implementado | Alta | Core actual | Portal y protección backend ya existen. | Falta de control operativo central. |
| Core | Auditoría | Parcial | Alta | Core hardening | Ya hay `AuditLog` en acciones clave, pero no toda la plataforma futura está cubierta. | Trazabilidad insuficiente. |
| Core | Impersonación | Implementado | Alta | Core actual | Ya existe con bloqueo de `/superadmin` para tokens impersonados. | Soporte operativo limitado. |
| Inventario | Almacenes | Implementado | Crítica | Inventario F1 | CRUD base y onboarding del primer almacén ya existen. | No se puede operar stock por ubicación. |
| Inventario | Materiales / productos | Parcial | Crítica | Inventario F1.1 | Existen materiales base; catálogo comercial más rico sigue pendiente. | Catálogo insuficiente para POS y compras. |
| Inventario | Existencias | Implementado | Crítica | Inventario F1 | La verdad del stock vive en existencias + movimientos. | Stock inconsistente. |
| Inventario | Movimientos | Implementado | Crítica | Inventario F1 | Entradas, salidas y ajustes ya existen. | No hay trazabilidad de stock. |
| Inventario | Kardex | Implementado | Alta | Inventario F1 | Consulta por material ya disponible. | Difícil auditar cambios de inventario. |
| Inventario | Stock bajo | Implementado | Alta | Inventario F1.1 | Disponible en listados y UI actual. | Quiebres de stock no detectados. |
| Inventario | Ajustes | Implementado | Alta | Inventario F1 | Ajuste a cantidad nueva ya disponible. | Correcciones manuales imposibles. |
| Inventario | Transferencias | Pendiente | Alta | Inventario F2 | No existe flujo entre almacenes todavía. | Operación manual y propensa a error. |
| Inventario | Conteos físicos | Pendiente | Alta | Inventario F2 | No existe módulo de conteo o conciliación. | Diferencias de inventario sin control. |
| Inventario | Importación masiva | Pendiente | Media | Inventario F2 | No existe importador de catálogo o stock. | Carga inicial lenta y manual. |
| Inventario | Lotes / series / caducidades | Pendiente | Alta | Inventario F3 | No existe trazabilidad avanzada por lote/serie. | Riesgo operativo y de cumplimiento. |
| Inventario | Conexión con POS | Pendiente | Crítica | POS F1 | POS aún no se implementa. | Ventas sin salida automática de stock. |
| Inventario | Conexión con compras | Pendiente | Alta | Compras F1 | Compras aún no existen en V2. | Entradas sin origen documental. |
| Inventario | Conexión con PM | Pendiente | Media | PM F2 | PM aún no existe en V2. | Materiales de proyecto sin trazabilidad. |
| POS | Punto de venta | Pendiente | Crítica | POS F1 | No implementado. | No hay operación de venta en mostrador. |
| POS | Carrito | Pendiente | Alta | POS F1 | No implementado. | Flujo de venta incompleto. |
| POS | Ventas | Pendiente | Crítica | POS F1 | No implementado. | Sin transacciones comerciales operables. |
| POS | Métodos de pago | Pendiente | Alta | POS F1 | No implementado. | Cobro no registrable. |
| POS | Descuentos | Pendiente | Media | POS F2 | No implementado. | Reglas comerciales limitadas. |
| POS | Tickets | Pendiente | Media | POS F1 | No implementado. | Mala experiencia de cierre de venta. |
| POS | Corte de caja | Pendiente | Alta | POS F2 | No implementado. | Riesgo financiero y operativo. |
| POS | Salida automática de inventario | Pendiente | Crítica | POS F1 | Depende de POS + movimientos de inventario. | Stock falso después de vender. |
| POS | Venta pendiente / cancelación | Pendiente | Alta | POS F2 | No implementado. | Operación rígida en caja. |
| POS | Conexión futura con facturación | Pendiente | Alta | POS F3 | Depende de facturación. | Venta desconectada del CFDI. |
| Facturación | CFDI 4.0 | Congelado | Crítica | Facturación F1 | Explicitamente fuera de alcance actual. | No se puede facturar fiscalmente. |
| Facturación | Factura.com | Congelado | Alta | Facturación F1 | Explicitamente fuera de alcance actual. | Integración fiscal no disponible. |
| Facturación | CSD | Congelado | Alta | Facturación F1 | Explicitamente fuera de alcance actual. | No se puede timbrar. |
| Facturación | Timbrado | Congelado | Crítica | Facturación F1 | No implementado por decisión actual. | Sin emisión fiscal válida. |
| Facturación | Cancelación | Congelado | Alta | Facturación F2 | No implementado. | Gestión fiscal incompleta. |
| Facturación | Logs | Congelado | Media | Facturación F1 | No existen logs específicos de CFDI todavía. | Difícil soporte fiscal. |
| Facturación | Sandbox | Congelado | Media | Facturación F1 | No implementado. | Riesgo al probar futuras integraciones. |
| Facturación | Facturación pendiente / bloqueada en V2 | Implementado | Alta | Core actual | El módulo existe solo como placeholder bloqueado para clientes. | Usuarios esperando una función no disponible. |
| Facturación | Factura global futura | Pendiente | Media | Facturación F3 | No implementado. | Alcance fiscal incompleto. |
| Facturación | Nota de crédito futura | Pendiente | Media | Facturación F3 | No implementado. | Flujo postventa incompleto. |
| CRM | Clientes | Pendiente | Alta | CRM F1 | No implementado. | No hay base comercial centralizada. |
| CRM | Oportunidades | Pendiente | Media | CRM F1 | No implementado. | Embudo comercial inexistente. |
| CRM | Actividades | Pendiente | Media | CRM F1 | No implementado. | Seguimiento comercial débil. |
| CRM | Seguimiento | Pendiente | Media | CRM F1 | No implementado. | Oportunidades sin continuidad. |
| CRM | Cobranza | Pendiente | Alta | CRM/Finanzas F2 | No implementado. | Recuperación deficiente de pagos. |
| CRM | Cuentas por pagar / cobrar | Pendiente | Alta | CRM/Finanzas F2 | No implementado. | Control financiero parcial. |
| CRM | Automatizaciones | Pendiente | Media | CRM F3 | No implementado. | Trabajo manual repetitivo. |
| CRM | Logs de automatización | Pendiente | Media | CRM F3 | No implementado. | Automatizaciones sin trazabilidad. |
| PM | Proyectos | Pendiente | Alta | PM F1 | No implementado. | Sin gestión formal de ejecución. |
| PM | Tareas | Pendiente | Alta | PM F1 | No implementado. | Seguimiento operativo incompleto. |
| PM | Tiempos | Pendiente | Media | PM F2 | No implementado. | Costeo y productividad opacos. |
| PM | Costos por usuario / rol | Pendiente | Media | PM F2 | No implementado. | Rentabilidad difícil de medir. |
| PM | Materiales usados en proyecto | Pendiente | Alta | PM F2 | Depende de inventario + PM. | Consumo no rastreado por proyecto. |
| PM | Documentos | Pendiente | Media | PM F2 | No implementado. | Información dispersa. |
| PM | Portal externo | Pendiente | Baja | PM F3 | No implementado. | Experiencia limitada para clientes externos. |
| PM | Snapshots comerciales | Pendiente | Media | PM F3 | No implementado. | Pérdida de contexto comercial en ejecución. |
| PM | Relación con ventas / facturas / cobranza | Pendiente | Alta | PM F3 | No implementado. | Flujo comercial-operativo desconectado. |
| Integraciones | Acavike B2B | Pendiente | Alta | Integraciones F1 | No implementado. | Catálogo y operación externa desconectados. |
| Integraciones | Sincronización de catálogo | Pendiente | Alta | Integraciones F1 | No implementado. | Datos duplicados o desactualizados. |
| Integraciones | Sincronización de stock | Pendiente | Alta | Integraciones F1 | No implementado. | Sobreventa o stock inconsistente. |
| Integraciones | Tiendanube | Pendiente | Media | Integraciones F2 | No implementado. | Canal e-commerce aislado. |
| Integraciones | Canales externos | Pendiente | Media | Integraciones F2 | No implementado. | Escalabilidad comercial limitada. |
| Integraciones | Webhooks futuros | Pendiente | Media | Integraciones F1 | No implementado. | Integraciones frágiles o manuales. |
| QA / Admin | Páginas QA | Pendiente | Media | Admin F2 | No existen páginas QA dedicadas hoy. | Validación operativa más lenta. |
| QA / Admin | Diagnósticos | Parcial | Media | Admin F1 | Existen utilidades como `debug_db`, pero no un portal formal de diagnóstico. | Soporte técnico más manual. |
| QA / Admin | Logs | Parcial | Alta | Admin F1 | Hay audit logs y logs técnicos, pero no una observabilidad integral. | Incidencias difíciles de investigar. |
| QA / Admin | Health checks | Implementado | Alta | Core actual | `/health` ya existe. | Menor visibilidad de disponibilidad. |
| QA / Admin | Herramientas de superadmin | Implementado | Alta | Core actual | Overview, empresas, usuarios, cambios de acceso e impersonación ya existen. | Operación central limitada. |

## Regla de desarrollo futuro

Cada nuevo prompt de desarrollo debe respetar esta matriz. Si una funcionalidad ya existía en Base44, CapellaOpsV2 debe incluirla, reemplazarla por una alternativa superior o documentar explícitamente por qué se omite.
