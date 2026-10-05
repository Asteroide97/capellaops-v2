# Diagnostico seguro de totales PM

El comando acepta DATABASE_URL suministrada explicitamente en el entorno,
usando Settings/SQLAlchemy normal de Capella. No acepta credenciales en argumentos,
no imprime URL ni parametros SQL y no toma la conexion implicitamente de `.env`.
Admite SQLite y SQL Server/Azure SQL. Exige siempre empresa_id no vacia.
No se ha conectado a Azure ni ejecutado sobre bases existentes o produccion.

## Politica

Se inspecciona el presupuesto detallado actual de cada proyecto del tenant,
mediante `get_current_project_budget_row`: activo, aprobado o borrador,
prioridad aprobado, version y timestamps descendentes, desempate por ID.
No se inspeccionan presupuestos cancelados, inactivos ni versiones no elegidas
como actuales. No se utiliza el presupuesto de referencia como fallback.

Se recalcula desde cantidades, precios y componentes activos, no desde sus
subtotales cacheados. Los capitulos no se suman como partidas. Se incluyen
indirectos fijos, porcentuales y porcentaje del encabezado, con la aritmetica
oficial compartida de PM y redondeo por partida. No se aplican tolerancias.
La diferencia reportada es recalculado menos guardado.

## Dry-run por defecto

Desde backend, con DATABASE_URL provisionada de forma segura en el entorno:

```powershell
python -m app.scripts.diagnose_pm_budget_totals --empresa-id EMPRESA_QA
```

Opcionalmente --sqlite-path permite una copia SQLite local existente; dry-run la
abre con mode=ro. La logica de negocio no usa PRAGMA, rowid, NULLS FIRST/LAST ni
bloqueos SQLite. El guard de SQLAlchemy solo permite SELECT compilados, impide
SQL textual, flush ORM, DML, DDL y commit. Siempre termina con rollback. La
inicializacion/descubrimiento del dialecto pertenece al driver y ocurre antes del
guard, sin consultas de negocio. Para una futura ejecucion real, usar ademas una
cuenta SQL con permisos exclusivamente SELECT; el guard no sustituye permisos DB.
El dry-run devuelve un objeto JSON con budget_header_discrepancies,
project_cost_summary_discrepancies, project_states y requires_summary_repair.
Listas de discrepancias vacias significan ninguna diferencia en los campos
verificados, no una validacion de todos los costos reales. No imprime nombres,
contactos, precios de partidas, credenciales ni URL de conexion.

## Apply preparado, no ejecutado sobre datos existentes

El flag `--apply` exige tambien uno o mas `--presupuesto-id` seleccionados
explicitamente tras revisar el diagnostico. Recalcula de nuevo bajo
una transaccion normal SQLAlchemy con aislamiento SERIALIZABLE y confirma
todos los cambios juntos. No hay BEGIN IMMEDIATE ni hacks por dialecto. Una
excepcion revierte la transaccion. La funcion de servicio no confirma: el caller
debe proporcionar commit/rollback y aislamiento SERIALIZABLE. Todo ID debe existir
y ser vigente en la empresa: si uno no cumple, aborta el lote antes de escribir.
Se permiten varios IDs solo cuando se enumeran explicitamente (maximo 1000).
El UPDATE vuelve a verificar tenant, estado y totales guardados. No se ha
ejecutado --apply; solo se prueban funciones de reparacion en fixtures temporales.

Solo actualiza en encabezados discrepantes: subtotal_costo, subtotal_venta,
indirectos_monto, total_costo, total_venta, utilidad_monto, utilidad_pct y
margen_estimado. Conserva updated_at para no cambiar la seleccion vigente.
No actualiza partidas, cantidades, precios, APU, indirectos fuente, proyectos,
resumenes de costo, tareas, planes, baselines, estimaciones ni auditoria.
Una segunda ejecucion sin cambios fuente produce cero cambios.

## Limites y operacion futura

- Hacer backup y revisar los IDs antes de autorizar apply.
- Este alcance detecta desajuste en total_costo/total_venta; otros derivados
  aislados incorrectos no disparan reparacion si ambos totales coinciden.
- Los resumenes pueden seguir desactualizados: dry-run ahora los diagnostica,
  pero apply sigue limitado a encabezados. Ver alcance siguiente.
- Una baseline historica permanece intacta, aunque sus montos sean antiguos.
- Dry-run durante ediciones concurrentes puede requerir repeticion sobre una
  copia consistente; no confundir el diagnostico con autorizacion de apply.
- SQL Server se valida por compilacion de las consultas reales, no por conexion.
  Driver ODBC, credenciales, permisos, deadlocks/aislamiento y operacion real Azure
  requieren validacion futura autorizada. SERIALIZABLE puede producir contencion;
  un fallo aborta la transaccion, no se reintenta ni se repara parcialmente.
- Un error inesperado muestra mensaje neutral y codigo de salida 1; no imprime
  SQL ni secretos. En dry-run IDs no actuales/de otro tenant no aparecen; en
  apply invalidan el lote completo.

Tests usan SQLite temporal generado por fixtures y se eliminan al terminar.
Se comprueba igualdad de tablas antes/despues, timestamps y metadatos del
encabezado, ausencia de DML en dry-run y hash identico del archivo tras CLI.
Apply solo se invoca como funcion en esos fixtures, no como reparacion real.

## Resumenes economicos: analisis sin reparacion

Modelo PMProyectoCostoResumen, tabla pm_proyecto_costo_resumen, un registro por
proyecto. Presupuesto_detallado_costo, presupuesto_detallado_venta, margen_estimado,
presupuesto_estimado, presupuesto_origen y variaciones son derivados; no son otra
fuente de verdad. Tambien guarda derivados reales de materiales/horas, cantidades
y costo_total_real, calculados a partir de consumos y registros de tiempo.

Responsables:
- refresh_project_budget_totals calcula encabezado desde partidas/indirectos y
  copia economia detallada al resumen. Se invoca al editar presupuesto, partidas,
  APU e indirectos, y en consultas de presupuesto/costos/comparativo/estimaciones.
- recalculate_project_cost_summary_totals calcula origen, presupuesto efectivo,
  costo_total_real y variaciones. Por si sola no relee el presupuesto detallado.
- refresh_project_material_costs y refresh_project_labor_costs actualizan los
  costos reales/planeados; refresh_project_total_costs integra todo.
- Las rutas de escritura run_pm_write confirman cambios; get_db solo cierra la
  sesion. Un GET que hace flush puede devolver cifras recalculadas, pero sin commit
  no las repara persistentemente. El dashboard agrega directamente resumenes,
  por lo que no existe garantia de autocorreccion persistente por navegar.

Consumidores de plan/control:
- plan-preview y plan-apply usan el presupuesto solicitado y sus partidas/linaje;
  no toman presupuesto_detallado_costo/venta del resumen.
- baseline-readiness usa get_current_project_budget_row y los totales del encabezado.
- Creacion de baseline toma costo/venta planificados del encabezado, pero puede
  leer costo_total_real del resumen para el snapshot real. Reparar encabezado no
  garantiza corregir este costo real ni modifica baselines historicas.
- La planeacion general usa el resumen para algunas alertas de costo; comparacion
  baseline/actual llama refresh_project_total_costs. Eso no implica persistencia
  automatica de todas las lecturas ni cambia la fuente de verdad del plan.

La prueba de resumen crea encabezado y resumen antiguos, repara solo encabezado,
confirma, y demuestra: readiness obtiene 170/376.65 mientras resumen sigue en
120/251.10. Un GET de presupuesto recalcula el resumen en su transaccion; al hacer
rollback los valores persistidos vuelven a 120/251.10. Por tanto, si existen
resumenes desactualizados necesitan una fase separada y autorizada de reparacion
de derivados. Su diagnostico de lectura se incluye ahora, sin reparacion.

## Refactor limitado de pm.py

Dos helpers puros (partida y encabezado) reutilizan la aritmetica oficial y son
invocados tanto por PM normal como por el diagnostico. Se conserva la misma
precision, orden de redondeo, comportamiento publico y flush del hotfix. No se
cambian endpoints, reglas de seleccion, tareas, baseline o calculo de estimaciones.

## Extension dry-run de PMProyectoCostoResumen

Campos comparados, usando calculate_expected_header y la funcion oficial
recalculate_project_cost_summary_totals sobre SimpleNamespace, nunca sobre ORM:

| Campo | Base de calculo |
| --- | --- |
| presupuesto_detallado_costo | Costo oficial de partidas activas + indirectos |
| presupuesto_detallado_venta | Venta oficial por partida redondeada |
| margen_estimado | Venta detallada menos costo detallado |
| presupuesto_estimado | Costo detallado si > 0; si no, referencia del proyecto, conforme a la regla existente |
| presupuesto_origen | detallado si costo detallado > 0; si no, simple |
| variacion_presupuesto | Presupuesto efectivo menos suma de componentes reales persistidos |
| variacion_vs_presupuesto_detallado | Costo detallado menos suma de componentes reales persistidos |

Los componentes reales utilizados son costo_materiales_real y costo_horas_real
del resumen: se leen tal cual. No se valida su exactitud ni se consultan consumos,
registros de horas o tarifas. La regla oficial suma esos componentes para las
variaciones; no se confunde costo_total_real cacheado con la fuente presupuestaria.
Una diferencia en variacion es una inconsistencia aritmetica/proyectada bajo esta
base, no una certificacion del costo real. actual_costs_validation lo advierte.

No se comparan ni reparan costo_materiales_real, costo_horas_real, costo_total_real,
costo_materiales_estimado, variacion_materiales, cantidades planeadas/consumidas,
horas_totales ni horas_sin_tarifa: necesitan fuentes operativas adicionales.
La comprobacion de origen es textual y su diferencia numerica es null. Valores
guardados null conservan null: no se inventa una diferencia numerica.

Estados por proyecto: consistent, header_inconsistent, summary_inconsistent,
both_inconsistent, missing_summary, summary_not_required. Consistent se limita a los campos enumerados
en checked_summary_fields y los dos totales de encabezado. Un resumen ausente
reporta IDs y valores null solo si existe evidencia de un flujo economico que exige resumen.
El dry-run nunca lo inserta. summary_not_required se incluye solo en project_states,
con requires_summary_repair=false; no se incluye como discrepancia.
Sin presupuesto detallado vigente, summary_economics_checked=false y estado
no_current_detailed_budget: no se compara contra un presupuesto viejo.

requires_summary_repair=true si hay discrepancia de resumen existente o ausencia requerida;
no se activa por un proyecto vacio ni por su importe simple de referencia. Apply
mantiene su respuesta anterior (lista de encabezados reparados). Su segunda
ejecucion puede dar cero cambios aunque el resumen siga desactualizado.

### Resumen requerido y reparacion opt-in de ausencias

La evidencia se limita al tenant: cualquier presupuesto historico (tambien
cancelado/inactivo), plan de materiales, consumo PM o registro de horas;
ademas, movimientos confirmados del proyecto de salida o devolucion.
Sus flujos crean el resumen; desactivar o cancelar no lo elimina.
Partidas, APU e indirectos estan cubiertos por su presupuesto padre.
Un importe simple, tareas, tarifas sin horas o staging de importacion no prueban
que el resumen deba existir. Consultas GET pueden crearlo bajo demanda, pero
sin evidencia persistida no se infiere una corrupcion por una visita anterior.

La ampliacion autorizada agrega --repair-missing-summaries como opt-in adicional
de --apply, exclusivamente con --empresa-id y uno o mas --proyecto-id explicitos
(maximo 1000). No admite --presupuesto-id en esa misma ejecucion. Sin el opt-in,
apply sigue limitado a encabezados. No se admite reparacion global.

Solo crea resumenes realmente ausentes que lo requieren, desde snapshots
operativos activos y el presupuesto vigente recalculado con helpers oficiales.
Sin presupuesto vigente usa la referencia simple, no el presupuesto cancelado.
No toca resumenes existentes (aunque esten inconsistentes), encabezados,
partidas, planes, movimientos, horas, baseline ni estimaciones.
La transaccion SERIALIZABLE pertenece al comando; el servicio no hace commit.
Un ID inexistente o de otro tenant aborta el lote antes de escribir.
Una segunda ejecucion no crea filas adicionales. No ejecutar reparacion sin
revision y autorizacion separadas; este gate solo valida localmente.

Ejemplo ficticio (abreviado):

```json
{
  "budget_header_discrepancies": [],
  "project_cost_summary_discrepancies": [{
    "empresa_id": "QA", "proyecto_id": "TRABAJO_QA",
    "presupuesto_id": "PRESUPUESTO_QA", "resumen_id": "RESUMEN_QA",
    "status": "inconsistent", "campo": "presupuesto_detallado_costo",
    "valor_guardado": "120.00", "valor_recalculado": "170.00", "diferencia": "50.00"
  }],
  "requires_summary_repair": true
}
```

Pruebas nuevas cubren las cuatro combinaciones de encabezado/resumen, ausencia,
aislamiento tenant, no creacion en lectura, conservacion de costos reales y
reparacion exclusiva de encabezado con resumen pendiente e idempotencia.
