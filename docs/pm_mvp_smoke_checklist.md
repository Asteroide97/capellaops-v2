# PM MVP - Smoke Checklist

Checklist manual mínimo para validar el módulo PM antes de demo o venta.

## A. PM Dashboard

- Acción principal: abrir `Gestión de Proyectos` y revisar KPIs, proyectos recientes y accesos a `Reporte ejecutivo`.
- Resultado esperado: cards cargan sin errores, los importes no se cortan y los accesos navegan correctamente.
- Validaciones de error: no aparece `[object Object]`, no hay mojibake y no se rompen filtros rápidos.
- Permisos básicos: `owner/admin` ven acciones de configuración y nuevo proyecto; `user` solo consulta.

## B. Reporte ejecutivo

- Acción principal: abrir `/pm/reports/executive`, revisar KPIs, tabla, riesgos y filtros.
- Resultado esperado: salud verde/amarillo/rojo coherente, filtros de alertas y pendiente por cobrar sí afectan KPIs, tabla y riesgos.
- Validaciones de error: proyectos con `pendiente_cobrar = 0` no aparecen cuando el filtro está activo.
- Permisos básicos: vista disponible para usuarios con acceso a PM; acciones de navegación abren proyecto, línea base o estimaciones.

## C. Proyecto

- Acción principal: abrir un proyecto desde listado y revisar tabs, encabezado y botones de retorno.
- Resultado esperado: `?pmView=` conserva la tab solicitada, `Volver a proyectos` regresa al listado y no hay tabs rotas.
- Validaciones de error: proyecto inactivo o cancelado no debe mostrar acciones operativas inválidas.
- Permisos básicos: `owner/admin` pueden gestionar proyecto; `user` consulta y opera solo lo permitido.

## D. Plan de trabajo

- Acción principal: crear tarea, editar fechas, revisar dependencias, alertas y cronograma.
- Resultado esperado: detalle colapsable, secciones minimizables, cronograma sin barras Gantt y tabla compacta sin scroll horizontal innecesario.
- Validaciones de error: una tarea bloqueada no debe completarse; si hay error al guardar, el modal no se cierra.
- Permisos básicos: `user` puede editar tareas si PM lo permite; `owner/admin` configuran calendario y reprogramación.

## E. Kanban

- Acción principal: mover foco entre columnas, abrir tarea, editarla y cambiar avance.
- Resultado esperado: tarjetas muestran estado correcto y acciones válidas por estatus.
- Validaciones de error: tareas completadas no muestran acciones de avance inválidas.
- Permisos básicos: edición visible solo si el rol puede operar tareas.

## F. Presupuesto

- Acción principal: crear presupuesto, agregar capítulo, partida, materiales, mano de obra e indirectos; aprobar presupuesto.
- Resultado esperado: el comparativo contra costo real carga y los totales se actualizan sin cerrar de forma incorrecta los modales.
- Validaciones de error: no se aprueba presupuesto vacío; montos negativos deben bloquearse con mensaje claro.
- Permisos básicos: `owner/admin` gestionan presupuesto; `user` solo consulta.

## G. Estimaciones

- Acción principal: crear borrador, agregar partida, capturar avance, enviar a aprobación, aprobar, marcar enviada y cobrar o cerrar sin saldo.
- Resultado esperado: el detalle se mantiene abierto durante el flujo y guía el siguiente paso.
- Validaciones de error: no se envía sin partidas ni con `monto_bruto <= 0`; si no hay saldo, aparece `Cerrar sin saldo`.
- Permisos básicos: `user` puede crear borrador si PM lo permite; `owner/admin` aprueban, marcan enviada y cierran cobro.

## H. Línea base

- Acción principal: crear línea base, revisar comparativo, detectar desviación, registrar cambio y aplicarlo.
- Resultado esperado: solo una línea base principal activa; el comparativo muestra desviaciones y el control de cambios refleja el flujo completo.
- Validaciones de error: no se aplica un cambio rechazado o pendiente de aprobación; si falla, el modal queda abierto con error legible.
- Permisos básicos: `owner/admin` crean y archivan línea base, aprueban y aplican cambios; `user` puede registrar borradores si está permitido.

## I. Materiales

- Acción principal: planear material por proyecto, actualizar cantidades y revisar consumo ligado a PM.
- Resultado esperado: el proyecto refleja materiales planeados sin romper inventario base.
- Validaciones de error: no debe exponer errores técnicos ni perder contexto al volver al proyecto.
- Permisos básicos: edición solo para roles habilitados por PM.

## J. Tiempo y costos

- Acción principal: registrar horas, revisar costos laborales y resumen del proyecto.
- Resultado esperado: horas y costo aplicado se reflejan en el resumen sin recargar tabs ajenas.
- Validaciones de error: tarifas faltantes o capturas inválidas muestran mensaje claro.
- Permisos básicos: `user` registra horas; configuración de tarifas queda para `owner/admin`.

## K. Aprobaciones

- Acción principal: revisar aprobaciones pendientes de presupuesto, cambio y estimación; aprobar, rechazar o cancelar.
- Resultado esperado: el tipo visible es claro y las entidades relacionadas sincronizan su estatus.
- Validaciones de error: aprobaciones canceladas ya no deben aparecer como pendientes.
- Permisos básicos: `owner/admin` resuelven aprobaciones; `user` solo consulta.

## L. Documentos

- Acción principal: subir documento, editar metadatos y revisar visibilidad externa.
- Resultado esperado: el documento queda ligado al proyecto y el modal cierra al guardar correctamente.
- Validaciones de error: no mostrar URLs rotas, `[object Object]` ni documentos internos en accesos externos.
- Permisos básicos: carga/edición según rol PM permitido.

## M. Portal externo

- Acción principal: crear acceso, abrir portal público, revisar proyecto y revocar acceso.
- Resultado esperado: el portal no expone costos, estimaciones internas ni documentos internos.
- Validaciones de error: tokens revocados o expirados muestran mensaje claro y no abren contenido.
- Permisos básicos: solo `owner/admin` crean, regeneran o revocan accesos externos.

## Validación transversal

- No debe aparecer `[object Object]`.
- No debe haber caracteres rotos por codificación.
- Los modales de formulario deben cerrar solo en éxito.
- Los modales de lectura deben mostrar un solo cierre visible.
- Acciones inválidas no deben mostrarse para el rol o estado actual.
