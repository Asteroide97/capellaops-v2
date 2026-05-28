# Matriz de Paridad Base44 vs CapellaOpsV2

## Introducción

Base44 se usará como referencia funcional e histórica, pero CapellaOpsV2 se reconstruye limpio con FastAPI, React, Azure SQL, SQLAlchemy y Alembic. La intención no es copiar implementación, sino asegurar paridad real de capacidades o documentar con claridad qué queda fuera de cada fase.

Cuando exista duda, el estado debe quedarse en `Parcial` o `Pendiente`. No se marca algo como `Implementado` si no existe claramente hoy en V2.

## Estados válidos

- `Implementado`
- `Parcial`
- `Pendiente`
- `Congelado`
- `No aplica todavía`

## Matriz principal

| Área | Funcionalidad Base44 | Estado en V2 | Prioridad | Fase objetivo | Notas | Riesgo si falta |
| --- | --- | --- | --- | --- | --- | --- |
| Core | Multiempresa por tenant | Implementado | Crítica | Core actual | Aislamiento por `empresa_id` y contexto activo. | Fuga de datos entre clientes. |
| Core | Auth de usuarios | Implementado | Crítica | Core actual | JWT propio, `/me`, login y registro. | Accesos no controlados. |
| Core | Roles por empresa | Parcial | Alta | Core hardening | Existe `EmpresaUsuario`, pero la matriz fina de permisos todavía no cubre todos los dominios futuros. | Sobreacceso o permisos inconsistentes. |
| Core | Planes comerciales | Implementado | Crítica | Core actual | `basico`, `pro`, `total`. | Acceso comercial incorrecto. |
| Core | Trial | Implementado | Alta | Core actual | Trial de 15 días. | Onboarding comercial incompleto. |
| Core | Módulos por plan | Implementado | Crítica | Core actual | Acceso centralizado con `/modules` y `can_access_module`. | Clientes viendo módulos no contratados. |
| Core | Superadmin | Implementado | Alta | Core actual | Portal, cambio de acceso, overview e impersonación. | Falta de control operativo central. |
| Core | Auditoría | Parcial | Alta | Core hardening | `AuditLog` ya cubre acciones importantes, pero no toda la plataforma futura. | Trazabilidad insuficiente. |
| Core | Impersonación | Implementado | Alta | Core actual | Soporta token corto y bloqueo de `/superadmin` cuando hay impersonación. | Soporte operativo limitado. |
| Inventario | Navegación estructurada del módulo | Implementado | Alta | Inventario Shell | Sidebar lateral desplegable con subrutas. La barra horizontal interna se elimina en esta fase. | Crecimiento desordenado del módulo. |
| Inventario | UX/UI Inventario estilo V1 | Parcial | Alta | Inventario UX/UI Parity | `Resumen`, `Materiales`, `Movimientos`, `Kardex` y `Proveedores` ya adoptan una base visual blanca, más densa y operativa. Falta extender el mismo nivel al resto del módulo. | Experiencia inconsistente frente a V1. |
| Inventario | Resumen / Dashboard de inventario | Implementado | Alta | Inventario Resumen | Dashboard operativo con KPIs, indicadores, alertas y listas calculadas. | Operación sin visibilidad ejecutiva. |
| Inventario | Smart SKU Search | Pendiente | Media | Inventario F2 | En Resumen queda placeholder; la búsqueda inteligente real no está conectada todavía. | Localización lenta de materiales. |
| Inventario | Materiales / productos | Parcial | Crítica | Inventario F1.1 | Existe catálogo base con SKU, categoría, unidad, costo, precio y stock mínimo. | Catálogo insuficiente para operación avanzada. |
| Inventario | Materiales UX avanzado | Parcial | Alta | Inventario UX/UI Parity | La tabla, filtros y modal de materiales ya se acercan al flujo operativo de V1. Siguen pendientes importación backend, acciones masivas y escaneo por cámara. | Operación de catálogo todavía menos madura que la referencia. |
| Inventario | Materiales con campos avanzados | Parcial | Alta | Inventario UX/F2 | Ya existen imagen URL, código de barras, subcategoría, stock máximo, ubicación, proveedor principal, lead time y costo promedio actual. Siguen pendientes políticas más profundas y costeo formal. | Escalabilidad limitada del catálogo. |
| Inventario | Materiales con imagen | Parcial | Media | Inventario UX | Se soporta `imagen_url` y lista adicional serializada como texto JSON. La subida real a Blob y gestión de archivos siguen pendientes. | Catálogo menos legible en operación. |
| Inventario | Azure Blob para imágenes y evidencias | Pendiente | Media | Inventario F2 | En V2 solo se guardan URLs. No hay carga binaria ni integración con Blob en esta fase. | Evidencias e imágenes dependen de gestión manual externa. |
| Inventario | SKU único por empresa | Implementado | Alta | Inventario F1 | Constraint y validación backend existentes. | Duplicidad de catálogo. |
| Inventario | Límites de SKU por plan | Pendiente | Media | Comercial / Inventario F3 | No existe política de cupos por plan. | Comercialización y control de uso incompletos. |
| Inventario | Existencias por almacén | Implementado | Crítica | Inventario F1 | `existencias` es fuente primaria por almacén y material. | Stock por ubicación inconsistente. |
| Inventario | Fuente de verdad de stock en movimientos + existencias | Implementado | Crítica | Inventario actual | No se usa `Material.stock_actual` como verdad. El stock global se calcula por suma. | Desincronización de stock. |
| Inventario | Movimientos de inventario | Implementado | Crítica | Inventario F1 | Entradas, salidas y ajustes auditables. | No hay trazabilidad de stock. |
| Inventario | Movimientos multi-artículo / carrito | Implementado | Alta | Inventario UX | Existe `POST /inventory/movements/bulk` con aplicación transaccional por múltiples líneas. No hay documento maestro persistente separado todavía. | Operación lenta para recepciones amplias. |
| Inventario | Movimientos multi-artículo UX | Parcial | Alta | Inventario UX/UI Parity | El modal multi-artículo y la tabla ya tienen flujo operativo más cercano a V1. Siguen pendientes estados documentales completos y mayor profundidad de evidencias. | Operación todavía menos robusta que la referencia. |
| Inventario | Movimientos con estatus borrador / confirmado / cancelado | Parcial | Media | Inventario F2 | El movimiento base se persiste como `confirmado`; no existe todavía flujo documental manual de borrador/cancelación. | Menor control documental antes de impactar stock. |
| Inventario | Evidencia fotográfica en entradas | Parcial | Baja | Inventario UX | Se soporta `evidencia_url`, pero no almacenamiento real ni adjuntos binarios. | Soporte débil de recepciones sensibles. |
| Inventario | Responsables en salidas | Parcial | Media | Inventario UX / F2 | Ya existen campos manuales `entregado_por` y `recibido_por`, pero falta flujo más estricto de responsables por documento. | Ambigüedad en consumos o mermas. |
| Inventario | Vinculación de salidas a proyectos | Parcial | Media | Inventario / PM F2 | Ya existen `es_proyecto`, `proyecto_id` y `proyecto_nombre_snapshot` como preparación sin FK real a PM. | Consumo sin centro de costo operativo. |
| Inventario | Kardex | Implementado | Alta | Inventario F1 | Consulta por material y almacén ya existe. | Difícil auditar cambios. |
| Inventario | Kardex inmutable con snapshots | Parcial | Alta | Inventario UX / F2 | Los movimientos no se editan y ya guardan snapshots de costo, pero todavía no existe un documento maestro formal ni costeo histórico completo. | Auditoría histórica incompleta. |
| Inventario | Kardex visual extendido | Parcial | Media | Inventario UX/UI Parity | La vista ya muestra filtros, balance, costo, valor, usuario y proyecto cuando existen. Faltan más capas de costeo avanzado y exportación formal. | Auditoría operativa menos clara que V1. |
| Inventario | Costo promedio ponderado | Pendiente | Alta | Inventario Costos F2 | Hoy se usa `costo_unitario` del material. | Costeo inexacto para análisis avanzado. |
| Inventario | Stock bajo | Implementado | Alta | Inventario F1.1 | Disponible en backend y frontend. | Quiebres de stock no detectados. |
| Inventario | Alertas automáticas | Parcial | Alta | Inventario Resumen | El dashboard calcula alertas, pero no existen procesos persistentes ni envío automático. | Reacción tardía a riesgos operativos. |
| Inventario | Requisiciones automáticas por bajo stock | Pendiente | Alta | Compras / Inventario F2 | No existe generación automática. | Reposición manual y tardía. |
| Inventario | Reportes avanzados | Pendiente | Media | Inventario F3 | Solo existe placeholder y resumen operativo básico. | Operación sin analítica profunda. |
| Inventario | FIFO / lotes | Pendiente | Alta | Inventario F3 | No existen lotes ni reglas FIFO. | Riesgo operativo y de trazabilidad. |
| Inventario | Series / caducidades | Pendiente | Alta | Inventario F3 | No existe control por serie o fecha. | Trazabilidad limitada. |
| Inventario | Clasificación ABC | Pendiente | Media | Inventario F3 | No implementado. | Priorización operativa deficiente. |
| Inventario | Conteos físicos | Implementado | Alta | Inventario F1.2 | Borrador, detalle, aplicación y cancelación de borrador. | Diferencias no controladas. |
| Inventario | Conteos cíclicos | Pendiente | Media | Inventario F3 | Existe conteo manual, pero no política cíclica programada. | Conteo reactivo en vez de preventivo. |
| Inventario | Transferencias / traspasos | Parcial | Alta | Inventario F1.2 | Flujo borrador-confirmación-cancelación de borrador. La reversa de confirmadas sigue pendiente. | Reubicación incompleta en incidentes. |
| Inventario | Safety stock | Pendiente | Media | Inventario F3 | No existe campo o regla dedicada. | Política de abastecimiento incompleta. |
| Inventario | Reorder point | Pendiente | Media | Inventario F3 | No existe umbral formal de reorden. | Reposición tardía. |
| Inventario | Min / max | Parcial | Media | Inventario F3 | Solo existe `stock_minimo`; no hay máximo ni política completa. | Reposición parcial y poco precisa. |
| Inventario | Políticas por producto | Pendiente | Media | Inventario F3 | No implementado. | Gestión homogénea donde debería ser diferenciada. |
| Inventario | Configuración avanzada de inventario | Pendiente | Media | Inventario F3 | No existe módulo/configuración dedicada. | Menor adaptabilidad operativa. |
| Inventario | Notificaciones | Pendiente | Media | Inventario F3 | No hay notificaciones persistentes. | Alertas no salen del dashboard. |
| Inventario | Importación CSV / Excel | Pendiente | Alta | Inventario F2 | Solo existe placeholder/documentación en frontend. No hay backend operativo de importación en esta fase. | Altas masivas lentas. |
| Inventario | Exportación CSV | Parcial | Media | Inventario UX | Materiales ya permite exportación simple client-side de la vista actual. Falta exportación backend y para otros submódulos. | Difícil explotar datos fuera del sistema. |
| Inventario | Edición masiva | Pendiente | Media | Inventario F2 | No implementado. | Mantenimiento lento del catálogo. |
| Inventario | Código de barras / QR | Parcial | Media | Inventario UX | Los materiales ya guardan `codigo_barras` y la búsqueda manual o por lector USB queda soportada. Falta captura por cámara y automatización adicional. | Operación lenta en piso si no hay lector o captura asistida. |
| Inventario | Escaneo QR / código de barras por cámara | Pendiente | Media | Inventario F2 | En frontend quedan placeholders manuales; aún no existe integración con cámara. | Operación lenta en piso. |
| Inventario | Proveedores | Parcial | Alta | Compras F1 + UX | CRUD operativo con RFC, razón social y vista más usable. Falta homologación comercial más profunda e importación masiva. | Compras sin directorio base. |
| Inventario | Proveedores UX avanzado | Parcial | Media | Inventario UX/UI Parity | La vista y modal de proveedores ya se acercan a V1, pero siguen sin búsqueda avanzada, exportación y anexos. | Experiencia de compras todavía menos madura que la referencia. |
| Inventario | Requisiciones | Parcial | Alta | Compras F1 | Borrador, envío, aprobación, rechazo y cancelación. `surtida` aún no tiene flujo completo. | Solicitudes internas incompletas. |
| Inventario | Órdenes de compra | Parcial | Alta | Compras F1 | Borrador, detalle, emisión y recepción. Faltan cancelaciones avanzadas e historial formal de recepciones. | Compras operables pero aún limitadas. |
| Inventario | Recepción de compras conectada a inventario | Implementado | Alta | Compras F1 | La recepción crea entradas y aumenta existencias. | Stock no conectado al documento fuente. |
| Inventario | Conexión con POS | Implementado | Crítica | POS F1 | POS ya descuenta inventario automáticamente. | Ventas sin salida automática. |
| Inventario | Conexión con compras | Parcial | Alta | Compras F1 | La recepción ya impacta stock; faltan automatismos y mayor cierre operativo. | Flujo compra-inventario incompleto. |
| Inventario | Conexión con PM / proyectos | Pendiente | Media | PM F2 | No implementado. | Consumo sin trazabilidad por proyecto. |
| Inventario | Proyectos | Pendiente | Media | Inventario / PM F2 | Placeholder de UI solamente. | Ruta vacía frente a alcance esperado. |
| Inventario | Equipos | Pendiente | Media | Inventario F2 | Placeholder de UI solamente. | Activos sin control. |
| Inventario | Órdenes de trabajo | Pendiente | Media | Inventario F2 | Placeholder de UI solamente. | Operación de campo sin trazabilidad. |
| Inventario | Reportes | Pendiente | Media | Inventario F2 | Placeholder de UI solamente. | Falta de visibilidad consolidada. |
| Integraciones | Acavike B2B | Pendiente | Alta | Integraciones F2 | No implementado. | Catálogo y stock desconectados del canal externo. |
| Integraciones | Tiendanube | Pendiente | Media | Integraciones F2 | No implementado. | Canal e-commerce aislado. |
| Integraciones | Sincronización de catálogo | Pendiente | Alta | Integraciones F2 | No implementado. | Datos duplicados o desactualizados. |
| Integraciones | Sincronización de stock | Pendiente | Alta | Integraciones F2 | No implementado. | Sobreventa o stock incorrecto fuera del sistema. |
| Integraciones | Canales externos | Pendiente | Media | Integraciones F3 | No implementado. | Escalabilidad comercial limitada. |
| Integraciones | Webhooks futuros | Pendiente | Media | Integraciones F2 | No implementado. | Integraciones manuales o frágiles. |
| POS | Punto de venta | Parcial | Crítica | POS F1 | Venta base, catálogo, ticket básico y cancelación básica ya existen. | Operación de mostrador incompleta frente al alcance final. |
| POS | Carrito | Implementado | Alta | POS F1 | Carrito funcional en frontend. | Flujo de cobro incompleto. |
| POS | Ventas | Implementado | Crítica | POS F1 | Venta persistida y calculada en backend. | Sin transacciones comerciales reales. |
| POS | Métodos de pago | Parcial | Alta | POS F2 | Existe método simple; pagos mixtos completos siguen pendientes. | Cobro limitado en escenarios reales. |
| POS | Tickets | Parcial | Media | POS F2 | Ticket básico disponible; versión imprimible formal pendiente. | Cierre comercial débil. |
| POS | Corte de caja | Pendiente | Alta | POS F2 | No implementado. | Riesgo operativo y financiero. |
| POS | Salida automática de inventario | Implementado | Crítica | POS F1 | Cada venta paga genera salida de inventario. | Stock falso después de vender. |
| POS | Venta pendiente / cancelación | Parcial | Alta | POS F2 | Existe cancelación básica; venta pendiente formal sigue pendiente. | Caja rígida para escenarios reales. |
| POS | Conexión futura con facturación | Pendiente | Alta | Facturación F2 | No implementado. | Venta desconectada del CFDI. |
| Facturación | CFDI 4.0 | Congelado | Crítica | Facturación futura | Fuera de esta etapa. | No se puede facturar fiscalmente. |
| Facturación | Factura.com | Congelado | Alta | Facturación futura | Fuera de esta etapa. | Sin integración fiscal. |
| Facturación | CSD | Congelado | Alta | Facturación futura | Fuera de esta etapa. | No se puede timbrar. |
| Facturación | Timbrado | Congelado | Crítica | Facturación futura | Fuera de esta etapa. | Sin emisión fiscal válida. |
| Facturación | Cancelación fiscal | Congelado | Alta | Facturación futura | No implementado. | Flujo fiscal incompleto. |
| Facturación | Logs fiscales | Congelado | Media | Facturación futura | No implementado. | Soporte fiscal difícil. |
| Facturación | Sandbox | Congelado | Media | Facturación futura | No implementado. | Riesgo al probar integraciones futuras. |
| Facturación | Facturación pendiente / bloqueada en V2 | Implementado | Alta | Core actual | Existe solo como módulo bloqueado para clientes. | Expectativa errónea si no se comunica bien. |
| Facturación | Factura global futura | Pendiente | Media | Facturación F3 | No implementado. | Alcance fiscal incompleto. |
| Facturación | Nota de crédito futura | Pendiente | Media | Facturación F3 | No implementado. | Postventa incompleta. |
| CRM | Clientes | Pendiente | Alta | CRM F1 | No implementado. | Base comercial central inexistente. |
| CRM | Oportunidades | Pendiente | Media | CRM F1 | No implementado. | Embudo comercial vacío. |
| CRM | Actividades | Pendiente | Media | CRM F1 | No implementado. | Seguimiento comercial débil. |
| CRM | Seguimiento | Pendiente | Media | CRM F1 | No implementado. | Oportunidades sin continuidad. |
| CRM | Cobranza | Pendiente | Alta | CRM / Finanzas F2 | No implementado. | Recuperación de pagos deficiente. |
| CRM | Cuentas por pagar / cobrar | Pendiente | Alta | CRM / Finanzas F2 | No implementado. | Control financiero parcial. |
| CRM | Automatizaciones | Pendiente | Media | CRM F3 | No implementado. | Trabajo manual repetitivo. |
| CRM | Logs de automatización | Pendiente | Media | CRM F3 | No implementado. | Automatizaciones sin trazabilidad. |
| PM | Proyectos | Pendiente | Alta | PM F1 | No implementado. | Sin gestión formal de ejecución. |
| PM | Tareas | Pendiente | Alta | PM F1 | No implementado. | Seguimiento operativo incompleto. |
| PM | Tiempos | Pendiente | Media | PM F2 | No implementado. | Productividad opaca. |
| PM | Costos por usuario / rol | Pendiente | Media | PM F2 | No implementado. | Rentabilidad difícil de medir. |
| PM | Materiales usados en proyecto | Pendiente | Alta | PM F2 | No implementado. | Consumo sin centro de costo. |
| PM | Documentos | Pendiente | Media | PM F2 | No implementado. | Información dispersa. |
| PM | Portal externo | Pendiente | Baja | PM F3 | No implementado. | Experiencia limitada para clientes externos. |
| PM | Snapshots comerciales | Pendiente | Media | PM F3 | No implementado. | Se pierde contexto comercial en ejecución. |
| PM | Relación con ventas / facturas / cobranza | Pendiente | Alta | PM F3 | No implementado. | Flujo comercial-operativo desconectado. |
| QA / Admin | Páginas QA | Pendiente | Media | Admin F2 | No implementado. | Validación más lenta. |
| QA / Admin | Diagnósticos | Parcial | Media | Admin F1 | Ya existen utilidades como `debug_db`, pero no portal formal. | Soporte técnico más manual. |
| QA / Admin | Logs | Parcial | Alta | Admin F1 | Hay audit logs y logs técnicos, sin observabilidad integral todavía. | Investigación lenta de incidentes. |
| QA / Admin | Health checks | Implementado | Alta | Core actual | `/health` ya existe. | Menor visibilidad de disponibilidad. |
| QA / Admin | Herramientas de superadmin | Implementado | Alta | Core actual | Empresas, usuarios, overview, cambios de acceso e impersonación ya existen. | Operación central limitada. |

## Regla de desarrollo futuro

Cada nuevo prompt de desarrollo debe respetar esta matriz. Si una funcionalidad ya existía en Base44, CapellaOpsV2 debe incluirla, reemplazarla por una alternativa superior o documentar explícitamente por qué se omite.
