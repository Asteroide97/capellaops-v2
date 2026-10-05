"""Portable inspection; repair callers own a serializable transaction."""
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.models.pm import (
    PMPresupuesto, PMPresupuestoPartida, PMPresupuestoPartidaMaterial,
    PMPresupuestoPartidaManoObra, PMPresupuestoIndirecto, PMProyecto, PMProyectoCostoResumen,
    PMProyectoMaterialPlan, PMProyectoMaterialConsumo, PMTimeEntry,
)
from app.models.inventory import Almacen, MovimientoInventario
from app.services.pm import (
    calculate_budget_leaf_totals, calculate_budget_header_totals,
    decimal_or_zero, quantize_rate, quantize_money, get_current_project_budget_row,
    recalculate_project_cost_summary_totals,
)

SUMMARY_FIELDS = (
    "presupuesto_estimado", "presupuesto_detallado_costo", "presupuesto_detallado_venta",
    "margen_estimado", "variacion_presupuesto", "variacion_vs_presupuesto_detallado", "presupuesto_origen",
)


def _assert_clean(db: Session) -> None:
    if db.new or db.dirty or db.deleted:
        raise ValueError("El diagnostico requiere una sesion sin cambios pendientes.")


def project_summary_requirement_reasons(db: Session, project: PMProyecto) -> list[str]:
    """Persisted economic flows create a summary even when later deactivated."""
    reasons = []
    for model, reason in (
        (PMPresupuesto, "budget_history"),
        (PMProyectoMaterialPlan, "material_plans"),
        (PMProyectoMaterialConsumo, "material_consumptions"),
        (PMTimeEntry, "time_entries"),
    ):
        if db.scalar(select(model.id).where(
            model.empresa_id == project.empresa_id, model.proyecto_id == project.id,
        ).limit(1)) is not None:
            reasons.append(reason)
    if db.scalar(select(MovimientoInventario.id).where(
        MovimientoInventario.empresa_id == project.empresa_id,
        MovimientoInventario.proyecto_id == project.id,
        MovimientoInventario.es_proyecto == True,
        MovimientoInventario.estatus == "confirmado",
        or_(MovimientoInventario.tipo == "salida", and_(
            MovimientoInventario.tipo == "entrada",
            MovimientoInventario.referencia_tipo == "DEVOLUCION_PROYECTO",
        )),
    ).limit(1)) is not None:
        reasons.append("project_inventory_movements")
    return reasons


def calculate_expected_header(db: Session, budget: PMPresupuesto) -> dict:
    """Calculate from source values, never trust component/line subtotal caches."""
    items = db.scalars(select(PMPresupuestoPartida).where(
        PMPresupuestoPartida.empresa_id == budget.empresa_id,
        PMPresupuestoPartida.presupuesto_id == budget.id,
        PMPresupuestoPartida.proyecto_id == budget.proyecto_id,
        PMPresupuestoPartida.activo == True, PMPresupuestoPartida.tipo == "partida",
    )).all()
    costs = {item.id: Decimal("0") for item in items}
    for model, quantity_field in (
        (PMPresupuestoPartidaMaterial, "cantidad_por_unidad"),
        (PMPresupuestoPartidaManoObra, "horas_por_unidad"),
    ):
        rows = db.scalars(select(model).join(PMPresupuestoPartida, model.partida_id == PMPresupuestoPartida.id).where(
            model.empresa_id == budget.empresa_id, model.proyecto_id == budget.proyecto_id,
            model.activo == True, PMPresupuestoPartida.empresa_id == budget.empresa_id,
            PMPresupuestoPartida.proyecto_id == budget.proyecto_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.activo == True, PMPresupuestoPartida.tipo == "partida",
        )).all()
        for row in rows:
            rate = row.costo_unitario if model is PMPresupuestoPartidaMaterial else row.tarifa_hora
            costs[row.partida_id] += quantize_rate(decimal_or_zero(getattr(row, quantity_field)) * decimal_or_zero(rate))
    subtotal_cost = subtotal_sale = Decimal("0")
    for item in items:
        totals = calculate_budget_leaf_totals(item.cantidad, costs[item.id], item.margen_pct, item.precio_unitario_manual)
        subtotal_cost += totals["subtotal_costo"]
        subtotal_sale += totals["subtotal_venta"]
    indirects = db.scalars(select(PMPresupuestoIndirecto).where(
        PMPresupuestoIndirecto.empresa_id == budget.empresa_id,
        PMPresupuestoIndirecto.proyecto_id == budget.proyecto_id,
        PMPresupuestoIndirecto.presupuesto_id == budget.id, PMPresupuestoIndirecto.activo == True,
    )).all()
    amounts = [quantize_money(subtotal_cost * decimal_or_zero(row.porcentaje) / Decimal("100"))
               if row.tipo == "porcentaje" else quantize_money(row.monto) for row in indirects]
    return calculate_budget_header_totals(subtotal_cost, subtotal_sale, budget.indirectos_pct, amounts)


def diagnose_budget_headers(db: Session, *, empresa_id: str, budget_ids: set[str] | None = None) -> list[dict]:
    _assert_clean(db)
    if not empresa_id or not empresa_id.strip():
        raise ValueError("Selecciona una empresa.")
    discrepancies = []
    with db.no_autoflush:
        projects = db.scalars(select(PMProyecto.id).where(PMProyecto.empresa_id == empresa_id).order_by(PMProyecto.id)).all()
        for project_id in projects:
            budget = get_current_project_budget_row(db, empresa_id, project_id)
            if budget is None or (budget_ids is not None and budget.id not in budget_ids):
                continue
            expected = calculate_expected_header(db, budget)
            if (decimal_or_zero(budget.total_costo) == expected["total_costo"]
                    and decimal_or_zero(budget.total_venta) == expected["total_venta"]):
                continue
            discrepancies.append({
                "empresa_id": empresa_id, "proyecto_id": project_id, "presupuesto_id": budget.id,
                "version": budget.version, "estado": budget.estatus,
                "total_costo_guardado": decimal_or_zero(budget.total_costo),
                "total_costo_recalculado": expected["total_costo"],
                "diferencia_costo": expected["total_costo"] - decimal_or_zero(budget.total_costo),
                "total_venta_guardado": decimal_or_zero(budget.total_venta),
                "total_venta_recalculado": expected["total_venta"],
                "diferencia_venta": expected["total_venta"] - decimal_or_zero(budget.total_venta),
            })
    return discrepancies


def diagnose_project_economics(db: Session, *, empresa_id: str, budget_ids: set[str] | None = None) -> dict:
    """Inspect projections without ORM mutation or validation of actual cost sources."""
    headers = diagnose_budget_headers(db, empresa_id=empresa_id, budget_ids=budget_ids)
    summaries, states = [], []
    bad_headers = {row["presupuesto_id"] for row in headers}
    with db.no_autoflush:
        projects = db.scalars(select(PMProyecto).where(
            PMProyecto.empresa_id == empresa_id).order_by(PMProyecto.id)).all()
        for project in projects:
            budget = get_current_project_budget_row(db, empresa_id, project.id)
            if budget_ids is not None and (budget is None or budget.id not in budget_ids):
                continue
            summary = db.scalar(select(PMProyectoCostoResumen).where(
                PMProyectoCostoResumen.empresa_id == empresa_id,
                PMProyectoCostoResumen.proyecto_id == project.id,
            ))
            identity = {"empresa_id": empresa_id, "proyecto_id": project.id,
                        "presupuesto_id": budget.id if budget else None,
                        "resumen_id": summary.id if summary else None}
            if summary is None:
                reasons = project_summary_requirement_reasons(db, project)
                if not reasons:
                    states.append({**identity, "status": "summary_not_required",
                                   "requires_summary_repair": False, "summary_required": False,
                                   "summary_requirement_reasons": [], "summary_economics_checked": False})
                    continue
                summaries.append({**identity, "status": "missing_summary", "campo": None,
                                  "valor_guardado": None, "valor_recalculado": None, "diferencia": None})
                states.append({**identity, "status": "missing_summary", "requires_summary_repair": True,
                               "summary_required": True, "summary_requirement_reasons": reasons,
                               "header_inconsistent": budget.id in bad_headers if budget else False})
                continue
            if budget is None:
                states.append({**identity, "status": "no_current_detailed_budget",
                               "requires_summary_repair": False, "summary_economics_checked": False})
                continue
            totals = calculate_expected_header(db, budget)
            # The official projection function mutates only this detached namespace.
            # Actual components are read as-is; consumption/time sources are NOT validated.
            expected = SimpleNamespace(
                presupuesto_detallado_costo=totals["total_costo"],
                presupuesto_detallado_venta=totals["total_venta"],
                margen_estimado=totals["margen_estimado"],
                costo_materiales_real=summary.costo_materiales_real,
                costo_horas_real=summary.costo_horas_real,
            )
            recalculate_project_cost_summary_totals(project, expected)
            start = len(summaries)
            for field in SUMMARY_FIELDS:
                saved, calculated = getattr(summary, field), getattr(expected, field)
                if saved == calculated:
                    continue
                summaries.append({**identity, "status": "inconsistent", "campo": field,
                                  "valor_guardado": saved, "valor_recalculado": calculated,
                                  "diferencia": calculated - decimal_or_zero(saved)
                                  if field != "presupuesto_origen" and saved is not None else None})
            bad_summary = len(summaries) > start
            bad_header = budget.id in bad_headers
            states.append({**identity, "status": "both_inconsistent" if bad_header and bad_summary
                           else "header_inconsistent" if bad_header else "summary_inconsistent" if bad_summary
                           else "consistent", "requires_summary_repair": bad_summary})
    return {"budget_header_discrepancies": headers,
            "project_cost_summary_discrepancies": summaries, "project_states": states,
            "requires_summary_repair": bool(summaries),
            "checked_summary_fields": list(SUMMARY_FIELDS),
            "actual_costs_validation": "not_performed; variations use stored material/hour components"}


def repair_budget_headers(db: Session, *, empresa_id: str, budget_ids: set[str]) -> list[dict]:
    """No commit. Only header derived totals; no project summaries or source rows."""
    if not empresa_id or not empresa_id.strip() or not budget_ids or any(not value.strip() for value in budget_ids):
        raise ValueError("Selecciona presupuestos explicitamente para reparar.")
    if len(budget_ids) > 1000:
        raise ValueError("Selecciona como maximo 1000 IDs por transaccion.")
    _assert_clean(db)
    selected = db.scalars(select(PMPresupuesto).where(
        PMPresupuesto.empresa_id == empresa_id, PMPresupuesto.id.in_(budget_ids),
        PMPresupuesto.activo == True, PMPresupuesto.estatus.in_(["aprobado", "borrador"]),
    )).all()
    if {budget.id for budget in selected} != budget_ids or any(
        get_current_project_budget_row(db, empresa_id, budget.proyecto_id).id != budget.id for budget in selected
    ):
        raise ValueError("Los IDs deben pertenecer a presupuestos vigentes de la empresa seleccionada.")
    rows = diagnose_budget_headers(db, empresa_id=empresa_id, budget_ids=budget_ids)
    for row in rows:
        budget = get_current_project_budget_row(db, empresa_id, row["proyecto_id"])
        expected = calculate_expected_header(db, budget)
        result = db.execute(update(PMPresupuesto).where(
            PMPresupuesto.id == row["presupuesto_id"], PMPresupuesto.empresa_id == empresa_id,
            PMPresupuesto.activo == True, PMPresupuesto.estatus == row["estado"],
            PMPresupuesto.total_costo == row["total_costo_guardado"],
            PMPresupuesto.total_venta == row["total_venta_guardado"],
        ).values(**expected, updated_at=budget.updated_at).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise ValueError("El presupuesto cambio durante la revision; cancela y vuelve a diagnosticar.")
    db.flush()
    db.expire_all()
    return rows


def repair_missing_project_summaries(db: Session, *, empresa_id: str, project_ids: set[str]) -> list[dict]:
    """Opt-in creation only: existing summaries and economic sources stay untouched."""
    if not empresa_id or not empresa_id.strip() or not project_ids or any(not value.strip() for value in project_ids):
        raise ValueError("Selecciona empresa y proyectos explicitamente para reparar resumenes ausentes.")
    if len(project_ids) > 1000:
        raise ValueError("Selecciona como maximo 1000 IDs por transaccion.")
    _assert_clean(db)
    projects = db.scalars(select(PMProyecto).where(
        PMProyecto.empresa_id == empresa_id, PMProyecto.id.in_(project_ids),
    ).order_by(PMProyecto.id)).all()
    if {project.id for project in projects} != project_ids:
        raise ValueError("Todos los proyectos deben pertenecer a la empresa seleccionada.")
    created = []
    with db.no_autoflush:
        for project in projects:
            if db.scalar(select(PMProyectoCostoResumen.id).where(
                PMProyectoCostoResumen.empresa_id == empresa_id,
                PMProyectoCostoResumen.proyecto_id == project.id,
            )) is not None or not project_summary_requirement_reasons(db, project):
                continue
            summary = PMProyectoCostoResumen(empresa_id=empresa_id, proyecto_id=project.id)
            plans = db.scalars(select(PMProyectoMaterialPlan).where(
                PMProyectoMaterialPlan.empresa_id == empresa_id,
                PMProyectoMaterialPlan.proyecto_id == project.id, PMProyectoMaterialPlan.activo == True,
            )).all()
            consumptions = db.scalars(select(PMProyectoMaterialConsumo).where(
                PMProyectoMaterialConsumo.empresa_id == empresa_id,
                PMProyectoMaterialConsumo.proyecto_id == project.id,
                PMProyectoMaterialConsumo.activo == True, PMProyectoMaterialConsumo.movimiento_id.is_(None),
            )).all()
            movements = db.scalars(select(MovimientoInventario).join(
                Almacen, MovimientoInventario.almacen_id == Almacen.id,
            ).where(
                MovimientoInventario.empresa_id == empresa_id, MovimientoInventario.proyecto_id == project.id,
                MovimientoInventario.es_proyecto == True, MovimientoInventario.estatus == "confirmado",
                or_(MovimientoInventario.tipo == "salida", and_(
                    MovimientoInventario.tipo == "entrada",
                    MovimientoInventario.referencia_tipo == "DEVOLUCION_PROYECTO",
                )),
            )).all()
            # Same source snapshots as refresh_project_material_costs; no plan status writes.
            summary.costo_materiales_estimado = sum((decimal_or_zero(p.costo_total_estimado) for p in plans), Decimal("0"))
            summary.total_materiales_planeados = sum((decimal_or_zero(p.cantidad_planificada) for p in plans), Decimal("0"))
            summary.costo_materiales_real = sum((decimal_or_zero(c.costo_total_snapshot) for c in consumptions), Decimal("0"))
            summary.total_materiales_consumidos = sum((decimal_or_zero(c.cantidad_consumida) for c in consumptions), Decimal("0"))
            for movement in movements:
                sign = Decimal("1") if movement.tipo == "salida" else Decimal("-1")
                quantity = decimal_or_zero(movement.cantidad)
                summary.costo_materiales_real += sign * quantity * decimal_or_zero(
                    movement.costo_promedio_snapshot or movement.costo_unitario_snapshot)
                summary.total_materiales_consumidos += sign * quantity
            summary.variacion_materiales = summary.costo_materiales_real - summary.costo_materiales_estimado
            entries = db.scalars(select(PMTimeEntry).where(
                PMTimeEntry.empresa_id == empresa_id, PMTimeEntry.proyecto_id == project.id,
                PMTimeEntry.activo == True,
            )).all()
            summary.costo_horas_real = sum((decimal_or_zero(e.costo_total_snapshot) for e in entries), Decimal("0"))
            summary.horas_totales = sum((decimal_or_zero(e.horas) for e in entries), Decimal("0"))
            summary.horas_sin_tarifa = sum((decimal_or_zero(e.horas) for e in entries if e.fuente_tarifa == "sin_tarifa"), Decimal("0"))
            budget = get_current_project_budget_row(db, empresa_id, project.id)
            totals = calculate_expected_header(db, budget) if budget else None
            summary.presupuesto_detallado_costo = totals["total_costo"] if totals else Decimal("0")
            summary.presupuesto_detallado_venta = totals["total_venta"] if totals else Decimal("0")
            summary.margen_estimado = totals["margen_estimado"] if totals else None
            recalculate_project_cost_summary_totals(project, summary)
            db.add(summary)
            created.append({"empresa_id": empresa_id, "proyecto_id": project.id})
    db.flush()
    return created
