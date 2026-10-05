"""Portable inspection; repair callers own a serializable transaction."""
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.pm import (
    PMPresupuesto, PMPresupuestoPartida, PMPresupuestoPartidaMaterial,
    PMPresupuestoPartidaManoObra, PMPresupuestoIndirecto, PMProyecto, PMProyectoCostoResumen,
)
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
                summaries.append({**identity, "status": "missing_summary", "campo": None,
                                  "valor_guardado": None, "valor_recalculado": None, "diferencia": None})
                states.append({**identity, "status": "missing_summary", "requires_summary_repair": True,
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
