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
| Core | Empresa completa | Implementado | Alta | Core hardening | `Empresa` ya guarda nombre, razon social, RFC, giro, telefono, email de contacto, ubicacion y plan. | Contexto comercial incompleto por cliente. |
| Core | Registro empresa + owner | Implementado | Critica | Core actual | El registro crea la empresa, el usuario owner y su `EmpresaUsuario`. El almacen sigue como onboarding posterior. | Onboarding confuso o tenant incompleto. |
| Core | Planes comerciales | Implementado | Critica | Core actual | `basico`, `pro`, `total`. | Acceso comercial incorrecto. |
| Core | Limites por plan | Implementado | Alta | Core hardening | Los planes ya controlan modulos, maximo de usuarios, maximo de almacenes y maximo de facturas mensuales. `null` significa ilimitado. | Sobreuso sin control comercial. |
| Core | Usuarios por empresa | Implementado | Alta | Core hardening | Los usuarios adicionales se gestionan con `EmpresaUsuario` y no crean empresas nuevas. El owner cuenta dentro del limite. | Mezcla de tenants o sobrecupo silencioso. |
| Core | Administracion de usuarios por empresa | Implementado | Alta | Core hardening | La pantalla `Empresa > Usuarios` ya muestra cupos del plan, miembros, invitaciones pendientes, cambio de rol y desactivacion/reactivacion. | Administracion operativa limitada del tenant. |
| Core | Invitaciones por email | Parcial | Media | Core hardening | Ya existe registro de invitacion pendiente y vinculacion de usuarios existentes, pero no se envia correo real todavia. | Alta manual y seguimiento incompleto. |
| Core | Almacenes por plan | Implementado | Alta | Core hardening | La creacion de almacenes y el onboarding del primer almacen respetan `max_almacenes` del plan. | Empresas operando fuera de su capacidad contratada. |
| Core | Trial | Implementado | Alta | Core actual | Trial de 15 dias. | Onboarding comercial incompleto. |
| Core | Modulos por plan | Implementado | Critica | Core actual | Acceso centralizado con `/modules` y `can_access_module`. | Clientes viendo modulos no contratados. |
| Core | Superadmin | Implementado | Alta | Core actual | Portal, cambio de acceso, overview e impersonacion. | Falta de control operativo central. |
| Core | Auditoria | Parcial | Alta | Core hardening | `AuditLog` ya cubre acciones importantes, pero no toda la plataforma futura. | Trazabilidad insuficiente. |
| Core | Impersonacion | Implementado | Alta | Core actual | Soporta token corto y bloqueo de `/superadmin` cuando hay impersonacion. | Soporte operativo limitado. |
| Inventario | Navegacion estructurada del modulo | Implementado | Alta | Inventario Shell | Sidebar lateral desplegable con subrutas. | Crecimiento desordenado del modulo. |
| Inventario | UX/UI Inventario estilo V1 | Parcial | Alta | Inventario UX/UI Parity | `Resumen`, `Materiales`, `Movimientos`, `Kardex` y `Proveedores` ya comparten una base visual mas operativa, con tipografia `Inter`, sidebar blanco y sistema de iconos consistente. | Experiencia inconsistente frente a V1. |
| Inventario | Resumen / Dashboard de inventario | Implementado | Alta | Inventario Resumen | Dashboard operativo con KPIs, indicadores, alertas y listas calculadas. | Operacion sin visibilidad ejecutiva. |
| Inventario | Smart SKU Search | Parcial | Media | Inventario F2 | Ya existe lookup exacto por `sku` / `codigo_barras`, pero no hay motor de busqueda inteligente o ranking operativo avanzado. | Localizacion lenta de materiales. |
| Inventario | Materiales / productos | Parcial | Critica | Inventario F1.1 | Existe catalogo base con SKU, categoria, unidad, costo, precio y stock minimo. | Catalogo insuficiente para operacion avanzada. |
| Inventario | Materiales UX avanzado | Parcial | Alta | Inventario UX/UI Parity | La tabla, filtros y modal de materiales ya se acercan al flujo operativo de V1, pero la experiencia aun no cubre importacion backend ni escaneo real por camara. | Operacion de catalogo todavia menos madura que la referencia. |
| Inventario | Materiales con campos avanzados | Parcial | Alta | Inventario UX / F2 | Existen imagen URL, codigo de barras, subcategoria, stock maximo, ubicacion, proveedor principal, lead time y costo promedio actual. | Escalabilidad limitada del catalogo. |
| Inventario | Materiales con imagen | Parcial | Media | Inventario UX | El modal de materiales ya permite tomar foto o elegir archivo/galeria y sube la imagen principal para persistir `imagen_url`, pero las imagenes adicionales siguen pendientes. | Catalogo menos legible en operacion. |
| Inventario | Azure Blob para imagenes y evidencias | Parcial | Media | Inventario UX | Ya existe upload de imagen principal de materiales hacia Azure Blob y se persiste solo la URL; evidencias y manejo avanzado de blobs siguen pendientes. | Evidencias e imagenes dependen de gestion manual externa. |
| Inventario | SKU unico por empresa | Implementado | Alta | Inventario F1 | Constraint y validacion backend existentes. | Duplicidad de catalogo. |
| Inventario | Limites de SKU por plan | Pendiente | Media | Comercial / Inventario F3 | No existe politica de cupos por plan. | Comercializacion y control de uso incompletos. |
| Inventario | Existencias por almacen | Implementado | Critica | Inventario F1 | `existencias` es fuente primaria por almacen y material. | Stock por ubicacion inconsistente. |
| Inventario | Fuente de verdad de stock en movimientos + existencias | Implementado | Critica | Inventario actual | No se usa `Material.stock_actual` como verdad. El stock global se calcula por suma. | Desincronizacion de stock. |
| Inventario | Movimientos de inventario | Implementado | Critica | Inventario F1 | Entradas, salidas y ajustes auditables. | No hay trazabilidad de stock. |
| Inventario | Movimientos multi-articulo / carrito | Implementado | Alta | Inventario UX | Existe `POST /inventory/movements/bulk` con aplicacion transaccional por multiples lineas. | Operacion lenta para recepciones amplias. |
| Inventario | Movimientos multi-articulo UX | Parcial | Alta | Inventario UX/UI Parity | El modal multi-articulo y la tabla ya tienen flujo operativo mas cercano a V1, aunque la experiencia sigue sin flujo documental completo de borrador/cancelacion manual. | Operacion todavia menos robusta que la referencia. |
| Inventario | Movimientos con estatus borrador / confirmado / cancelado | Parcial | Media | Inventario F2 | El movimiento base se persiste como `confirmado`; no existe todavia flujo documental manual de borrador/cancelacion. | Menor control documental antes de impactar stock. |
| Inventario | Evidencia fotografica en entradas | Parcial | Baja | Inventario UX | Se soporta `evidencia_url`, pero no almacenamiento real ni adjuntos binarios. | Soporte debil de recepciones sensibles. |
| Inventario | Responsables en salidas | Parcial | Media | Inventario UX / F2 | Ya existen campos manuales `entregado_por` y `recibido_por`. | Ambiguedad en consumos o mermas. |
| Inventario | Vinculacion de salidas a proyectos | Parcial | Media | Inventario / PM F2 | Ya existen `es_proyecto`, `proyecto_id` y `proyecto_nombre_snapshot` sin FK real a PM. | Consumo sin centro de costo operativo. |
| Inventario | Kardex | Implementado | Alta | Inventario F1 | Consulta por material y almacen ya existe. | Dificil auditar cambios. |
| Inventario | Kardex inmutable con snapshots | Parcial | Alta | Inventario UX / F2 | Los movimientos no se editan y ya guardan snapshots de costo, pero todavia no existe costeo historico completo. | Auditoria historica incompleta. |
| Inventario | Kardex visual extendido | Parcial | Media | Inventario UX/UI Parity | La vista ya muestra filtros, balance, costo, valor, usuario y proyecto cuando existen, con una presentacion mas cercana a auditoria operativa. | Auditoria operativa menos clara que V1. |
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
| Inventario | Codigo de barras / QR | Implementado | Media | Inventario UX | Cada material puede guardar `codigo_barras` opcional, con validacion unica por empresa y lookup exacto. | Operacion lenta o errores de captura si no existe identificacion clara. |
| Inventario | Busqueda por scanner USB | Implementado | Alta | Inventario UX | Los inputs de Materiales, Movimientos, Resumen y POS aceptan captura por lector USB y Enter. | Operacion lenta en piso si el lector no dispara busqueda. |
| Inventario | Escaneo QR / codigo de barras por camara | Parcial | Media | Inventario UX | Existe modal reusable con `@zxing/browser`, pero depende de permisos, HTTPS y soporte del navegador. | Operacion lenta en piso cuando la camara no esta disponible. |
| Inventario | Escaner en Materiales | Implementado | Alta | Inventario UX | Materiales permite lookup exacto por camara o USB y captura de SKU / codigo de barras en el modal. | Alta de catalogo y consulta mas lentas. |
| Inventario | Escaner en Movimientos | Implementado | Alta | Inventario UX | El modal multi-articulo permite escanear o escribir codigo exacto para agregar lineas al carrito. | Captura manual mas lenta en entradas y salidas. |
| Inventario | Escaner en Resumen | Implementado | Media | Inventario UX | El panel de control permite lookup exacto y muestra stock por almacen como resultado rapido. | Consulta lenta desde piso o supervision. |
| Inventario | Proveedores | Parcial | Alta | Compras F1 + UX | CRUD operativo con RFC, razon social y vista mas usable. | Compras sin directorio base. |
| Inventario | Proveedor principal en Material | Implementado | Alta | Inventario UX / Compras F1 | `Material.proveedor_principal_id` ya se valida por empresa y se expone con nombre y RFC cuando existe. | Materiales sin referencia clara de abastecimiento. |
| Inventario | Proveedores UX avanzado | Parcial | Media | Inventario UX/UI Parity | La vista y modal de proveedores ya se acercan a V1 y ahora comparten la misma base tipografica e iconografica del modulo. | Experiencia de compras todavia menos madura que la referencia. |
| Inventario | Requisiciones CRUD | Implementado | Alta | Compras F1 | La vista operativa ya cubre borrador, envio, aprobacion, rechazo, cancelacion, detalle y edicion segura en borrador. | Solicitudes internas desordenadas o fuera del sistema. |
| Inventario | Aprobar / rechazar requisiciones | Implementado | Alta | Compras F1 | La transicion `enviada -> aprobada/rechazada` ya opera con validaciones por empresa y auditoria basica. | Flujo de autorizacion manual y poco trazable. |
| Inventario | Requisicion -> salida inventario | Implementado | Alta | Compras F1 | `POST /inventory/requisitions/{id}/fulfill` ya surte desde inventario, descuenta existencias, crea movimientos `salida` y actualiza cantidades surtidas y pendientes. | Solicitudes aprobadas sin abastecimiento controlado. |
| Inventario | Requisicion -> orden de compra | Implementado | Alta | Compras F1 | Una requisicion aprobada ya puede crear una OC en borrador con detalles copiados y enlace persistido para evitar duplicados. | Flujo compras-inventario fragmentado. |
| Inventario | Requisicion -> PM placeholder | Parcial | Media | PM F2 | La requisicion ya soporta `es_proyecto`, `proyecto_id` y `proyecto_nombre_snapshot`, y el surtido transfiere esos datos a movimientos y kardex. | Consumo de proyecto sin integracion PM fuerte. |
| Inventario | Aprobacion avanzada por rol | Pendiente | Media | Compras F2 | No existe workflow formal multinivel ni reglas por monto, area o jerarquia. | Riesgo de aprobaciones fuera de politica. |
| Inventario | Requisiciones automaticas desde PM | Pendiente | Media | PM F3 | PM Core no genera requisiciones automaticamente; solo existe captura manual o sugerencia por bajo stock. | Planeacion de materiales desconectada de proyectos. |
| Inventario | Email / notificaciones de requisiciones | Pendiente | Media | Compras F2 | No existe motor persistente de notificaciones ni envio real de correos para requisiciones. | Seguimiento manual y tardio. |
| Inventario | OC CRUD | Implementado | Alta | Compras F1 | La pantalla y el backend ya soportan borrador, detalle, consulta y edicion segura de OC en borrador. | Compras operables pero aun limitadas. |
| Inventario | OC emision | Implementado | Alta | Compras F1 | La OC se puede emitir solo con renglones validos y cambia a `emitida` sin afectar inventario. | Flujo documental incompleto hacia proveedor. |
| Inventario | OC recepcion parcial | Implementado | Alta | Compras F1 | Ya soporta recibir cantidades parciales por renglón, actualiza pendientes y evita sobre-recepcion. | Recepciones manuales o inconsistentes. |
| Inventario | OC recepcion total | Implementado | Alta | Compras F1 | Ya cierra la orden como `recibida` cuando todo el documento fue recibido. | Cierre operativo incompleto. |
| Inventario | OC -> Inventario | Implementado | Alta | Compras F1 | La recepcion crea entradas y aumenta existencias desde backend transaccional. | Stock no conectado al documento fuente. |
| Inventario | OC -> Kardex / movimientos | Parcial | Alta | Compras F1 | La trazabilidad ya existe por `movimientos_inventario` con `purchase_order_receive`, pero aun no hay historial formal de recepciones separado. | Auditoria documental menos clara. |
| Inventario | PDF OC | Pendiente | Media | Compras F2 | No implementado. | Envio manual o externo del documento. |
| Inventario | Email proveedor | Pendiente | Media | Compras F2 | No implementado. | Seguimiento manual con el proveedor. |
| Inventario | Historial formal de recepciones | Pendiente | Media | Compras F2 | La trazabilidad vive en movimientos, no en una bitacora documental propia de recepciones. | Revision historica menos directa. |
| Inventario | Cancelacion avanzada de OC | Pendiente | Media | Compras F2 | Solo existe cancelacion basica sin recepcion previa; no hay reversa de inventario para recepciones parciales. | Flujo de excepciones incompleto. |
| Inventario | Cuentas por pagar | Pendiente | Alta | Compras F3 | No implementado. | Seguimiento financiero fuera del sistema. |
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
| POS | Escaner en POS | Parcial | Media | POS F1 + UX | El catalogo POS ya busca por `codigo_barras`, soporta lector USB y camara para agregar cuando hay coincidencia unica. | Cobro mas lento si el escaner no resuelve el producto. |
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
| PM | PM Core proyectos | Implementado | Alta | PM F1 | CRUD base, dashboard, detalle de proyecto, miembros y desactivacion logica ya existen en `/pm`. | Sin gestion formal de ejecucion. |
| PM | PM tareas basicas | Implementado | Alta | PM F1 | Tareas, subtareas, checklist, comentarios y actualizacion de avance ya operan dentro del proyecto. | Seguimiento operativo incompleto. |
| PM | Project Workspace | Implementado | Alta | PM UX | El detalle de proyecto ya opera con vista general, plan de trabajo, selector de vistas y panel de detalle de tarea. | La ejecucion sigue mas fragmentada que una herramienta PM dedicada. |
| PM | Kanban simple | Parcial | Media | PM F1 | El detalle de proyecto ya muestra columnas simples por estatus, sin drag and drop ni reglas avanzadas. | Visualizacion operativa menos agil. |
| PM | Gantt simple visual | Parcial | Media | PM UX | Ya existe una linea de tiempo simple por tarea usando fechas de inicio y fin, con estado bloqueado y referencia textual de prerrequisitos. | Sin interaccion avanzada ni reprogramacion visual. |
| PM | Gantt con dependencias visuales | Parcial | Media | PM F4.5 | El Gantt simple ya marca tareas bloqueadas y muestra de que tarea dependen, sin flechas ni recalculo automatico. | La secuencia sigue siendo menos visible que en una herramienta PM avanzada. |
| PM | Gantt editable | Pendiente | Media | PM F4 | No existe edicion directa sobre barras ni ajustes de fechas desde la linea de tiempo. | Planeacion temporal aun manual. |
| PM | Dependencias | Implementado | Media | PM F4.5 | Ya existen dependencias `finish_to_start` entre tareas del mismo proyecto, con validacion backend y conteos en plan de trabajo. | Sin secuencia formal entre tareas. |
| PM | Prerrequisitos bloqueantes | Implementado | Media | PM F4.5 | Una tarea bloqueada no puede avanzar a `en_progreso`, `en_revision` o `completada` mientras su prerrequisito siga pendiente. | Ejecucion fuera de secuencia si la validacion falla. |
| PM | Dependencias avanzadas | Pendiente | Media | PM futura | No existen `start_to_start`, `finish_to_finish`, `start_to_finish` ni lag real sobre fechas. | Planeacion avanzada aun limitada. |
| PM | Ruta critica | Pendiente | Media | PM F4 | No implementado. | Priorizacion temporal limitada. |
| PM | Drag and drop | Pendiente | Media | PM F4 | No implementado en kanban ni Gantt. | Replaneacion visual menos agil. |
| PM | Materiales PM planeados | Implementado | Alta | PM F2 | Cada proyecto ya puede definir materiales planeados, cantidad, costo estimado y pendiente operativo. | Planeacion material fuera del proyecto. |
| PM | Consumo real desde inventario | Implementado | Alta | PM F2 | Los surtidos de requisicion y las salidas manuales de inventario con `proyecto_id` ya generan consumo formal PM y actualizan costo real. | Proyecto sin costo real de materiales. |
| PM | Costos de materiales | Implementado | Alta | PM F2 | Ya existe resumen por proyecto con estimado, real, variacion y dashboard agregado por costo de materiales. | Desviaciones de materiales sin visibilidad. |
| PM | Crear requisicion desde proyecto | Implementado | Alta | PM F2 | La tab de materiales ya puede crear requisiciones en borrador desde faltantes del proyecto con `es_proyecto=true`. | Solicitud de materiales fuera del flujo PM. |
| PM | Reservas de stock | Pendiente | Media | PM F3 | No existe reserva formal ni bloqueo preventivo de existencias para proyectos. | Sobreasignacion posible entre proyectos y operacion diaria. |
| PM | Compras directas desde PM | Pendiente | Media | PM F3 | PM todavia crea requisiciones; no lanza compras directas ni recepciones propias. | Flujo PM-Compras aun fragmentado. |
| PM | Registro de horas | Implementado | Alta | PM F3 | Ya existe captura de horas por proyecto y tarea, con desactivacion logica y snapshot del costo aplicado. | Costo laboral sin trazabilidad real. |
| PM | Tarifa por usuario | Implementado | Alta | PM F3 | Ya existe configuracion de tarifa horaria por usuario con vigencias y prioridad sobre rol. | Costeo real impreciso para personal clave. |
| PM | Tarifa por rol | Implementado | Alta | PM F3 | Ya existe tarifa fallback por rol de empresa o de proyecto cuando no hay tarifa individual. | Horas sin costo o con costo inconsistente. |
| PM | Snapshots de costo por hora | Implementado | Alta | PM F3 | Cada `pm_time_entry` guarda tarifa aplicada, costo total y fuente de tarifa sin recalculo retroactivo. | Historico de costos inestable. |
| PM | Costo laboral real | Implementado | Alta | PM F3 | `PMProyectoCostoResumen` ya acumula horas totales, horas sin tarifa y costo horas real por proyecto. | Proyectos sin visibilidad laboral real. |
| PM | Rentabilidad base | Parcial | Media | PM F3 | Ya existe costo total real y variacion contra presupuesto, pero aun no hay ingresos comerciales integrados ni margen real completo. | Rentabilidad parcial o estimada. |
| PM | Presupuesto detallado | Implementado | Alta | PM F4 | El proyecto ya soporta presupuesto activo, cabecera, totales y comparativo contra costo real dentro del workspace. | Ejecucion sin linea base economica detallada. |
| PM | Partidas / capitulos | Implementado | Alta | PM F4 | Ya existen capitulos y partidas para estructurar presupuesto detallado por proyecto. | Presupuesto plano y poco auditable. |
| PM | Presupuesto UX guiado | Implementado | Media | PM F4.5 | La vista de presupuesto ahora expone pasos, acciones visibles y lenguaje menos tecnico para crear capitulos, partidas, materiales, mano de obra e indirectos. | Presupuesto menos operable si la UX vuelve a ser demasiado tecnica. |
| PM | APU basico con lenguaje simplificado | Implementado | Alta | PM F4.5 | El detalle de partida ya se presenta como desglose de costo con materiales y mano de obra, manteniendo APU como concepto secundario. | Costeo estimado menos preciso o mas manual. |
| PM | APU basico | Parcial | Alta | PM F4 | Ya existe APU basico con materiales y mano de obra por partida, pero sin versiones avanzadas, plantillas ni formulas compuestas. | Costeo estimado menos preciso o mas manual. |
| PM | Indirectos | Parcial | Media | PM F4 | Ya existen indirectos por porcentaje o monto fijo, pero sin catalogo avanzado ni reglas contables. | Subestimacion de costo total presupuestado. |
| PM | Comparativo presupuesto vs real | Implementado | Alta | PM F4 | Ya compara presupuesto detallado contra costo real de materiales y horas en proyecto y dashboard. | Desviaciones economicas invisibles. |
| PM | Estados de pago / estimaciones formales | Pendiente | Media | PM F5 | No existen estimaciones, valuaciones ni estados de pago formales. | Seguimiento economico incompleto frente a obra real. |
| PM | Facturacion / cobranza | Pendiente | Alta | PM comercial futura | PM no conecta todavia con facturacion ni cobranza. | Rentabilidad sin cierre comercial completo. |
| PM | Aprobacion de horas | Pendiente | Media | PM F4 | No existe workflow formal de aprobacion o bloqueo previo al costeo. | Riesgo de capturas no validadas. |
| PM | Documentos | Pendiente | Media | PM F2 | Solo existe placeholder de UI; no hay almacenamiento ni flujos documentales. | Informacion dispersa. |
| PM | Portal externo | Pendiente | Baja | PM F3 | No implementado. | Experiencia limitada para clientes externos. |
| PM | Vinculos comerciales | Pendiente | Alta | PM F3 | No existe enlace operativo real con ventas, facturas o cobranza. | Flujo comercial-operativo desconectado. |
| PM | Automatizaciones / snapshots | Pendiente | Media | PM F3 | No implementado. | Se pierde contexto historico y trabajo repetitivo sigue manual. |
| PM | Feature flags PM | Implementado | Media | PM F1 | Existe `EmpresaPMConfig` por empresa y el modulo PM sigue gated por plan y `can_access_module`. | Empresas sin acceso correcto o con banderas inconsistentes. |
| PM | Mantenimiento | Excluido | Media | Fuera de alcance V2 actual | El roadmap actual de V2 no contempla mantenimiento preventivo/correctivo, garantias ni ordenes de trabajo de mantenimiento. | Riesgo de asumir alcance no planificado. |
| QA / Admin | Paginas QA | Pendiente | Media | Admin F2 | No implementado. | Validacion mas lenta. |
| QA / Admin | Diagnosticos | Parcial | Media | Admin F1 | Ya existen utilidades como `debug_db`, pero no portal formal. | Soporte tecnico mas manual. |
| QA / Admin | Logs | Parcial | Alta | Admin F1 | Hay audit logs y logs tecnicos, sin observabilidad integral todavia. | Investigacion lenta de incidentes. |
| QA / Admin | Health checks | Implementado | Alta | Core actual | `/health` ya existe. | Menor visibilidad de disponibilidad. |
| QA / Admin | Herramientas de superadmin | Implementado | Alta | Core actual | Empresas, usuarios, overview, cambios de acceso e impersonacion ya existen. | Operacion central limitada. |

## Regla de desarrollo futuro

Cada nuevo prompt de desarrollo debe respetar esta matriz. Si una funcionalidad ya existia en Base44, CapellaOpsV2 debe incluirla, reemplazarla por una alternativa superior o documentar explicitamente por que se omite.
