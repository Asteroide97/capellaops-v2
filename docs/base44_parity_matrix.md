# Matriz de Paridad Base44 vs CapellaOpsV2

## Introduccion

Base44 se usa como referencia funcional e historica, pero CapellaOpsV2 se reconstruye limpio con FastAPI, React, Azure SQL, SQLAlchemy y Alembic. La meta no es copiar implementacion, sino cubrir la misma capacidad operativa o documentar con claridad que queda fuera de cada fase.

Cuando exista duda, el estado debe quedarse en `Parcial` o `Pendiente`. No se marca algo como `Implementado` si no existe claramente hoy en V2.

## Estados validos

- `Implementado`
- `Parcial`
- `Pendiente`
- `Congelado`
- `No aplica todavia`

## Matriz principal

| Area | Funcionalidad Base44 | Estado en V2 | Prioridad | Fase objetivo | Notas | Riesgo si falta |
| --- | --- | --- | --- | --- | --- | --- |
| Core | Multiempresa por tenant | Implementado | Critica | Core actual | Aislamiento por `empresa_id` y contexto activo. | Fuga de datos entre clientes. |
| Core | Auth de usuarios | Implementado | Critica | Core actual | JWT propio, `/me`, login y registro. | Accesos no controlados. |
| Core | Roles por empresa | Parcial | Alta | Core hardening | Existe `EmpresaUsuario`, pero la matriz fina de permisos todavia no cubre todos los dominios futuros. | Sobreacceso o permisos inconsistentes. |
| Core | Planes comerciales | Implementado | Critica | Core actual | `basico`, `pro`, `total`. | Acceso comercial incorrecto. |
| Core | Trial | Implementado | Alta | Core actual | Trial de 15 dias. | Onboarding comercial incompleto. |
| Core | Modulos por plan | Implementado | Critica | Core actual | Acceso centralizado con `/modules` y `can_access_module`. | Clientes viendo modulos no contratados. |
| Core | Superadmin | Implementado | Alta | Core actual | Portal, cambio de acceso, overview e impersonacion. | Falta de control operativo central. |
| Core | Auditoria | Parcial | Alta | Core hardening | `AuditLog` ya cubre acciones importantes, pero no toda la plataforma futura. | Trazabilidad insuficiente. |
| Core | Impersonacion | Implementado | Alta | Core actual | Soporta token corto y bloqueo de `/superadmin` cuando hay impersonacion. | Soporte operativo limitado. |
| Inventario | Navegacion estructurada del modulo | Implementado | Alta | Inventario Shell | Sidebar lateral desplegable con subrutas. | Crecimiento desordenado del modulo. |
| Inventario | UX/UI Inventario estilo V1 | Parcial | Alta | Inventario UX/UI Parity | `Resumen`, `Materiales`, `Movimientos`, `Kardex` y `Proveedores` ya comparten una base visual mas operativa. | Experiencia inconsistente frente a V1. |
| Inventario | Resumen / Dashboard de inventario | Implementado | Alta | Inventario Resumen | Dashboard operativo con KPIs, indicadores, alertas y listas calculadas. | Operacion sin visibilidad ejecutiva. |
| Inventario | Smart SKU Search | Pendiente | Media | Inventario F2 | En Resumen queda placeholder; la busqueda inteligente real no esta conectada todavia. | Localizacion lenta de materiales. |
| Inventario | Materiales / productos | Parcial | Critica | Inventario F1.1 | Existe catalogo base con SKU, categoria, unidad, costo, precio y stock minimo. | Catalogo insuficiente para operacion avanzada. |
| Inventario | Materiales UX avanzado | Parcial | Alta | Inventario UX/UI Parity | La tabla, filtros y modal de materiales ya se acercan al flujo operativo de V1. | Operacion de catalogo todavia menos madura que la referencia. |
| Inventario | Materiales con campos avanzados | Parcial | Alta | Inventario UX / F2 | Existen imagen URL, codigo de barras, subcategoria, stock maximo, ubicacion, proveedor principal, lead time y costo promedio actual. | Escalabilidad limitada del catalogo. |
| Inventario | Materiales con imagen | Parcial | Media | Inventario UX | Se soporta `imagen_url` y lista adicional serializada como texto JSON. | Catalogo menos legible en operacion. |
| Inventario | Azure Blob para imagenes y evidencias | Pendiente | Media | Inventario F2 | En V2 solo se guardan URLs. | Evidencias e imagenes dependen de gestion manual externa. |
| Inventario | SKU unico por empresa | Implementado | Alta | Inventario F1 | Constraint y validacion backend existentes. | Duplicidad de catalogo. |
| Inventario | Limites de SKU por plan | Pendiente | Media | Comercial / Inventario F3 | No existe politica de cupos por plan. | Comercializacion y control de uso incompletos. |
| Inventario | Existencias por almacen | Implementado | Critica | Inventario F1 | `existencias` es fuente primaria por almacen y material. | Stock por ubicacion inconsistente. |
| Inventario | Fuente de verdad de stock en movimientos + existencias | Implementado | Critica | Inventario actual | No se usa `Material.stock_actual` como verdad. El stock global se calcula por suma. | Desincronizacion de stock. |
| Inventario | Movimientos de inventario | Implementado | Critica | Inventario F1 | Entradas, salidas y ajustes auditables. | No hay trazabilidad de stock. |
| Inventario | Movimientos multi-articulo / carrito | Implementado | Alta | Inventario UX | Existe `POST /inventory/movements/bulk` con aplicacion transaccional por multiples lineas. | Operacion lenta para recepciones amplias. |
| Inventario | Movimientos multi-articulo UX | Parcial | Alta | Inventario UX/UI Parity | El modal multi-articulo y la tabla ya tienen flujo operativo mas cercano a V1. | Operacion todavia menos robusta que la referencia. |
| Inventario | Movimientos con estatus borrador / confirmado / cancelado | Parcial | Media | Inventario F2 | El movimiento base se persiste como `confirmado`; no existe todavia flujo documental manual de borrador/cancelacion. | Menor control documental antes de impactar stock. |
| Inventario | Evidencia fotografica en entradas | Parcial | Baja | Inventario UX | Se soporta `evidencia_url`, pero no almacenamiento real ni adjuntos binarios. | Soporte debil de recepciones sensibles. |
| Inventario | Responsables en salidas | Parcial | Media | Inventario UX / F2 | Ya existen campos manuales `entregado_por` y `recibido_por`. | Ambiguedad en consumos o mermas. |
| Inventario | Vinculacion de salidas a proyectos | Parcial | Media | Inventario / PM F2 | Ya existen `es_proyecto`, `proyecto_id` y `proyecto_nombre_snapshot` sin FK real a PM. | Consumo sin centro de costo operativo. |
| Inventario | Kardex | Implementado | Alta | Inventario F1 | Consulta por material y almacen ya existe. | Dificil auditar cambios. |
| Inventario | Kardex inmutable con snapshots | Parcial | Alta | Inventario UX / F2 | Los movimientos no se editan y ya guardan snapshots de costo, pero todavia no existe costeo historico completo. | Auditoria historica incompleta. |
| Inventario | Kardex visual extendido | Parcial | Media | Inventario UX/UI Parity | La vista ya muestra filtros, balance, costo, valor, usuario y proyecto cuando existen. | Auditoria operativa menos clara que V1. |
| Inventario | Costo promedio ponderado | Pendiente | Alta | Inventario Costos F2 | Hoy se usa `costo_unitario` o `costo_promedio_actual` sin motor formal de promedio ponderado. | Costeo inexacto para analisis avanzado. |
| Inventario | Stock bajo | Implementado | Alta | Inventario F1.1 | Disponible en backend y frontend. | Quiebres de stock no detectados. |
| Inventario | Alertas automaticas | Parcial | Alta | Inventario Resumen | El dashboard calcula alertas, pero no existen procesos persistentes ni envio automatico. | Reaccion tardia a riesgos operativos. |
| Inventario | Requisiciones automaticas por bajo stock | Parcial | Alta | Compras / Inventario F2 | Existe generacion sugerida manual desde Materiales y Resumen; no hay disparo automatico ni reglas programadas por empresa. | Reposicion tardia si nadie atiende la sugerencia. |
| Inventario | Reportes avanzados | Pendiente | Media | Inventario F3 | Solo existe placeholder y resumen operativo basico. | Operacion sin analitica profunda. |
| Inventario | FIFO / lotes | Pendiente | Alta | Inventario F3 | No existen lotes ni reglas FIFO. | Riesgo operativo y de trazabilidad. |
| Inventario | Series / caducidades | Pendiente | Alta | Inventario F3 | No existe control por serie o fecha. | Trazabilidad limitada. |
| Inventario | Clasificacion ABC | Pendiente | Media | Inventario F3 | No implementado. | Priorizacion operativa deficiente. |
| Inventario | Conteos fisicos | Implementado | Alta | Inventario F1.2 | Borrador, detalle, aplicacion y cancelacion de borrador. | Diferencias no controladas. |
| Inventario | Conteos ciclicos | Pendiente | Media | Inventario F3 | Existe conteo manual, pero no politica ciclica programada. | Conteo reactivo en vez de preventivo. |
| Inventario | Transferencias / traspasos | Parcial | Alta | Inventario F1.2 | Flujo borrador-confirmacion-cancelacion de borrador. La reversa de confirmadas sigue pendiente. | Reubicacion incompleta en incidentes. |
| Inventario | Safety stock | Pendiente | Media | Inventario F3 | No existe campo o regla dedicada. | Politica de abastecimiento incompleta. |
| Inventario | Reorder point | Pendiente | Media | Inventario F3 | No existe umbral formal de reorden. | Reposicion tardia. |
| Inventario | Min / max | Parcial | Media | Inventario F3 | Existen `stock_minimo` y `stock_maximo`, pero no politica completa por producto. | Reposicion poco precisa. |
| Inventario | Politicas por producto | Pendiente | Media | Inventario F3 | No implementado. | Gestion homogenea donde deberia ser diferenciada. |
| Inventario | Configuracion avanzada de inventario | Pendiente | Media | Inventario F3 | No existe modulo/configuracion dedicada. | Menor adaptabilidad operativa. |
| Inventario | Notificaciones | Parcial | Media | Inventario F3 | El resumen calcula alertas, pero no existen notificaciones persistentes ni reglas configurables por empresa. | Alertas visibles solo si alguien entra al dashboard. |
| Inventario | Importacion CSV / Excel | Pendiente | Alta | Inventario F2 | Solo existe placeholder/documentacion en frontend. | Altas masivas lentas. |
| Inventario | Exportacion CSV | Parcial | Media | Inventario UX | Materiales ya permite exportacion simple client-side de la vista actual. | Dificil explotar datos fuera del sistema. |
| Inventario | Edicion masiva | Pendiente | Media | Inventario F2 | No implementado. | Mantenimiento lento del catalogo. |
| Inventario | Codigo de barras / QR | Parcial | Media | Inventario UX | Los materiales ya guardan `codigo_barras` y la busqueda manual o por lector USB queda soportada. | Operacion lenta en piso si no hay lector o captura asistida. |
| Inventario | Escaneo QR / codigo de barras por camara | Pendiente | Media | Inventario F2 | En frontend quedan placeholders manuales; aun no existe integracion con camara. | Operacion lenta en piso. |
| Inventario | Proveedores | Parcial | Alta | Compras F1 + UX | CRUD operativo con RFC, razon social y vista mas usable. | Compras sin directorio base. |
| Inventario | Proveedor principal en Material | Implementado | Alta | Inventario UX / Compras F1 | `Material.proveedor_principal_id` ya se valida por empresa y se expone con nombre y RFC cuando existe. | Materiales sin referencia clara de abastecimiento. |
| Inventario | Proveedores UX avanzado | Parcial | Media | Inventario UX/UI Parity | La vista y modal de proveedores ya se acercan a V1. | Experiencia de compras todavia menos madura que la referencia. |
| Inventario | Requisiciones | Parcial | Alta | Compras F1 | Borrador, envio, aprobacion, rechazo, cancelacion y sugerencia desde bajo stock. `surtida` aun no tiene flujo completo. | Solicitudes internas incompletas. |
| Inventario | Requisicion -> orden de compra | Implementado | Alta | Compras F1 | Una requisicion aprobada ya puede crear una OC en borrador con detalles copiados y enlace persistido para evitar duplicados. | Flujo compras-inventario fragmentado. |
| Inventario | Ordenes de compra | Parcial | Alta | Compras F1 | Borrador, detalle, emision, recepcion y creacion desde requisicion. Faltan cancelaciones avanzadas e historial formal de recepciones. | Compras operables pero aun limitadas. |
| Inventario | Recepcion de compras conectada a inventario | Implementado | Alta | Compras F1 | La recepcion crea entradas y aumenta existencias. | Stock no conectado al documento fuente. |
| Inventario | Conexion con POS | Implementado | Critica | POS F1 | POS ya descuenta inventario automaticamente y la cancelacion devuelve stock. | Ventas sin salida automatica. |
| Inventario | Conexion con compras | Parcial | Alta | Compras F1 | La recepcion ya impacta stock y ahora existe enlace requisicion -> OC; faltan automatismos mas amplios y cierre documental completo. | Flujo compra-inventario incompleto. |
| Inventario | Conexion con PM / proyectos | Parcial | Media | PM F2 | Movimientos y kardex ya aceptan referencia manual de proyecto sin FK real ni modulo PM activo. | Consumo sin trazabilidad fuerte por proyecto. |
| Inventario | Proyectos | Pendiente | Media | Inventario / PM F2 | Placeholder de UI solamente. | Ruta vacia frente a alcance esperado. |
| Inventario | Equipos | Pendiente | Media | Inventario F2 | Placeholder de UI solamente. | Activos sin control. |
| Inventario | Ordenes de trabajo | Pendiente | Media | Inventario F2 | Placeholder de UI solamente. | Operacion de campo sin trazabilidad. |
| Inventario | Reportes | Pendiente | Media | Inventario F2 | Placeholder de UI solamente. | Falta de visibilidad consolidada. |
| Integraciones | Acavike B2B | Pendiente | Alta | Integraciones F2 | No implementado. | Catalogo y stock desconectados del canal externo. |
| Integraciones | Tiendanube | Pendiente | Media | Integraciones F2 | No implementado. | Canal e-commerce aislado. |
| Integraciones | Sincronizacion de catalogo | Pendiente | Alta | Integraciones F2 | No implementado. | Datos duplicados o desactualizados. |
| Integraciones | Sincronizacion de stock | Pendiente | Alta | Integraciones F2 | No implementado. | Sobreventa o stock incorrecto fuera del sistema. |
| Integraciones | Canales externos | Pendiente | Media | Integraciones F3 | No implementado. | Escalabilidad comercial limitada. |
| Integraciones | Webhooks futuros | Pendiente | Media | Integraciones F2 | No implementado. | Integraciones manuales o fragiles. |
| POS | Punto de venta | Parcial | Critica | POS F1 | Venta base, catalogo, ticket basico y cancelacion basica ya existen. | Operacion de mostrador incompleta frente al alcance final. |
| POS | Carrito | Implementado | Alta | POS F1 | Carrito funcional en frontend. | Flujo de cobro incompleto. |
| POS | Ventas | Implementado | Critica | POS F1 | Venta persistida y calculada en backend. | Sin transacciones comerciales reales. |
| POS | Metodos de pago | Parcial | Alta | POS F2 | Existe metodo simple; pagos mixtos completos siguen pendientes. | Cobro limitado en escenarios reales. |
| POS | Tickets | Parcial | Media | POS F2 | Ticket basico disponible; version imprimible formal pendiente. | Cierre comercial debil. |
| POS | Corte de caja | Pendiente | Alta | POS F2 | No implementado. | Riesgo operativo y financiero. |
| POS | Salida automatica de inventario | Implementado | Critica | POS F1 | Cada venta pagada genera salida de inventario. | Stock falso despues de vender. |
| POS | Venta pendiente / cancelacion | Parcial | Alta | POS F2 | Existe cancelacion basica; venta pendiente formal sigue pendiente. | Caja rigida para escenarios reales. |
| POS | Facturacion via POS | Pendiente | Alta | Facturacion F2 | No implementado. | Venta desconectada del CFDI. |
| Facturacion | CFDI 4.0 | Congelado | Critica | Facturacion futura | Fuera de esta etapa. | No se puede facturar fiscalmente. |
| Facturacion | Factura.com | Congelado | Alta | Facturacion futura | Fuera de esta etapa. | Sin integracion fiscal. |
| Facturacion | CSD | Congelado | Alta | Facturacion futura | Fuera de esta etapa. | No se puede timbrar. |
| Facturacion | Timbrado | Congelado | Critica | Facturacion futura | Fuera de esta etapa. | Sin emision fiscal valida. |
| Facturacion | Cancelacion fiscal | Congelado | Alta | Facturacion futura | No implementado. | Flujo fiscal incompleto. |
| Facturacion | Logs fiscales | Congelado | Media | Facturacion futura | No implementado. | Soporte fiscal dificil. |
| Facturacion | Sandbox | Congelado | Media | Facturacion futura | No implementado. | Riesgo al probar integraciones futuras. |
| Facturacion | Facturacion pendiente / bloqueada en V2 | Implementado | Alta | Core actual | Existe solo como modulo bloqueado para clientes. | Expectativa erronea si no se comunica bien. |
| Facturacion | Factura global futura | Pendiente | Media | Facturacion F3 | No implementado. | Alcance fiscal incompleto. |
| Facturacion | Nota de credito futura | Pendiente | Media | Facturacion F3 | No implementado. | Postventa incompleta. |
| CRM | Clientes | Pendiente | Alta | CRM F1 | No implementado. | Base comercial central inexistente. |
| CRM | Oportunidades | Pendiente | Media | CRM F1 | No implementado. | Embudo comercial vacio. |
| CRM | Actividades | Pendiente | Media | CRM F1 | No implementado. | Seguimiento comercial debil. |
| CRM | Seguimiento | Pendiente | Media | CRM F1 | No implementado. | Oportunidades sin continuidad. |
| CRM | Cobranza | Pendiente | Alta | CRM / Finanzas F2 | No implementado. | Recuperacion de pagos deficiente. |
| CRM | Cuentas por pagar / cobrar | Pendiente | Alta | CRM / Finanzas F2 | No implementado. | Control financiero parcial. |
| CRM | CRMProveedorMaterial | Pendiente | Media | CRM / Compras F2 | La vinculacion comercial proveedor-material sigue manual via `proveedor_principal_id`. | Analitica comercial limitada sobre abastecimiento. |
| CRM | Automatizaciones | Pendiente | Media | CRM F3 | No implementado. | Trabajo manual repetitivo. |
| CRM | Logs de automatizacion | Pendiente | Media | CRM F3 | No implementado. | Automatizaciones sin trazabilidad. |
| PM | Proyectos | Pendiente | Alta | PM F1 | No implementado. | Sin gestion formal de ejecucion. |
| PM | Tareas | Pendiente | Alta | PM F1 | No implementado. | Seguimiento operativo incompleto. |
| PM | Tiempos | Pendiente | Media | PM F2 | No implementado. | Productividad opaca. |
| PM | Costos por usuario / rol | Pendiente | Media | PM F2 | No implementado. | Rentabilidad dificil de medir. |
| PM | Materiales usados en proyecto | Pendiente | Alta | PM F2 | No implementado. | Consumo sin centro de costo. |
| PM | Documentos | Pendiente | Media | PM F2 | No implementado. | Informacion dispersa. |
| PM | Portal externo | Pendiente | Baja | PM F3 | No implementado. | Experiencia limitada para clientes externos. |
| PM | Snapshots comerciales | Pendiente | Media | PM F3 | No implementado. | Se pierde contexto comercial en ejecucion. |
| PM | Relacion con ventas / facturas / cobranza | Pendiente | Alta | PM F3 | No implementado. | Flujo comercial-operativo desconectado. |
| QA / Admin | Paginas QA | Pendiente | Media | Admin F2 | No implementado. | Validacion mas lenta. |
| QA / Admin | Diagnosticos | Parcial | Media | Admin F1 | Ya existen utilidades como `debug_db`, pero no portal formal. | Soporte tecnico mas manual. |
| QA / Admin | Logs | Parcial | Alta | Admin F1 | Hay audit logs y logs tecnicos, sin observabilidad integral todavia. | Investigacion lenta de incidentes. |
| QA / Admin | Health checks | Implementado | Alta | Core actual | `/health` ya existe. | Menor visibilidad de disponibilidad. |
| QA / Admin | Herramientas de superadmin | Implementado | Alta | Core actual | Empresas, usuarios, overview, cambios de acceso e impersonacion ya existen. | Operacion central limitada. |

## Regla de desarrollo futuro

Cada nuevo prompt de desarrollo debe respetar esta matriz. Si una funcionalidad ya existia en Base44, CapellaOpsV2 debe incluirla, reemplazarla por una alternativa superior o documentar explicitamente por que se omite.
