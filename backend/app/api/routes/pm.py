import logging
from datetime import date
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.pm import (
    PMBudgetVsActualOut,
    PMChecklistItemCreate,
    PMChecklistItemOut,
    PMChecklistItemUpdate,
    PMCommentOut,
    PMComentarioCreate,
    PMConfigOut,
    PMDashboardOut,
    PMProjectMembersListResponse,
    PMProjectBudgetBundleOut,
    PMProjectCostsOut,
    PMCreateProjectRequisitionRequest,
    PMPresupuestoCreate,
    PMPresupuestoIndirectoCreate,
    PMPresupuestoIndirectoOut,
    PMPresupuestoIndirectoUpdate,
    PMPresupuestoOut,
    PMPresupuestoPartidaCreate,
    PMPresupuestoPartidaManoObraCreate,
    PMPresupuestoPartidaManoObraOut,
    PMPresupuestoPartidaManoObraUpdate,
    PMPresupuestoPartidaMaterialCreate,
    PMPresupuestoPartidaMaterialOut,
    PMPresupuestoPartidaMaterialUpdate,
    PMPresupuestoPartidaOut,
    PMPresupuestoPartidaUpdate,
    PMPresupuestoUpdate,
    PMProyectoMaterialPlanCreate,
    PMProyectoMaterialPlanOut,
    PMProyectoMaterialPlanUpdate,
    PMProyectoMaterialesOut,
    PMProyectoCreate,
    PMProyectoListResponse,
    PMProyectoMiembroCreate,
    PMProyectoMiembroOut,
    PMProyectoOut,
    PMProyectoUpdate,
    PMTarifaHoraRolCreate,
    PMTarifaHoraRolListResponse,
    PMTarifaHoraRolOut,
    PMTarifaHoraRolUpdate,
    PMTarifaHoraUsuarioCreate,
    PMTarifaHoraUsuarioListResponse,
    PMTarifaHoraUsuarioOut,
    PMTarifaHoraUsuarioUpdate,
    PMTimeEntryCreate,
    PMTimeEntryListResponse,
    PMTimeEntryOut,
    PMTimeEntryUpdate,
    PMSubtareaCreate,
    PMSubtareaOut,
    PMSubtareaUpdate,
    PMTareaDependenciaCreate,
    PMTareaDependenciaOut,
    PMTareaCreate,
    PMTaskDependenciesOut,
    PMTareaListResponse,
    PMTareaOut,
    PMTareaUpdate,
)
from app.services.pm import (
    PMContext,
    add_budget_indirect,
    add_budget_item_labor,
    add_budget_item_material,
    add_project_member,
    add_project_material_plan,
    approve_project_budget,
    cancel_project_budget,
    create_task_dependency,
    create_budget_item,
    create_project_budget,
    create_project_material_requisition,
    create_checklist_item,
    create_project,
    create_project_comment,
    create_project_time_entry,
    create_role_hourly_rate,
    create_subtask,
    create_task,
    create_task_comment,
    create_user_hourly_rate,
    deactivate_project_time_entry,
    deactivate_project,
    deactivate_project_material_plan,
    deactivate_project_member,
    deactivate_role_hourly_rate,
    deactivate_task,
    deactivate_task_dependency,
    deactivate_user_hourly_rate,
    deactivate_budget_indirect,
    deactivate_budget_item,
    deactivate_budget_item_labor,
    deactivate_budget_item_material,
    get_pm_context,
    get_pm_dashboard,
    get_project_budget,
    get_project_budget_vs_actual,
    get_project,
    get_project_costs,
    get_task,
    get_task_dependencies,
    list_project_time_entries,
    list_project_material_plan,
    list_project_members,
    list_task_dependencies,
    list_projects,
    list_role_hourly_rates,
    list_tasks,
    list_user_hourly_rates,
    refresh_project_total_costs,
    serialize_pm_config,
    update_budget_indirect,
    update_budget_item,
    update_budget_item_labor,
    update_budget_item_material,
    update_project_budget,
    update_project_time_entry,
    update_checklist_item,
    update_project,
    update_project_material_plan,
    update_role_hourly_rate,
    update_subtask,
    update_task,
    update_user_hourly_rate,
)
from app.schemas.procurement import RequisitionResponse


router = APIRouter(prefix="/pm", tags=["pm"])
logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_pm_route_context(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> PMContext:
    return get_pm_context(db, context)


def run_pm_write(db: Session, action: str, operation: Callable[[], T]) -> T:
    try:
        result = operation()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Conflicto de integridad en PM durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo completar la operacion de PM.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error de base de datos en PM durante %s.", action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la operacion de PM.",
        ) from exc


@router.get("/config", response_model=PMConfigOut)
def pm_config(
    pm_context: PMContext = Depends(get_pm_route_context),
) -> PMConfigOut:
    return serialize_pm_config(pm_context.config)


@router.get("/dashboard", response_model=PMDashboardOut)
def pm_dashboard(
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMDashboardOut:
    return get_pm_dashboard(db, pm_context)


@router.get("/projects", response_model=PMProyectoListResponse)
def get_projects(
    q: str | None = None,
    estatus: str | None = None,
    prioridad: str | None = None,
    activo: bool | None = True,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoListResponse:
    return list_projects(
        db,
        pm_context,
        q=q,
        estatus=estatus,
        prioridad=prioridad,
        activo=activo,
        limit=limit,
        offset=offset,
    )


@router.post("/projects", response_model=PMProyectoOut, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    payload: PMProyectoCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoOut:
    return run_pm_write(
        db,
        "create_project",
        lambda: create_project(
            db,
            pm_context,
            nombre=payload.nombre,
            codigo=payload.codigo,
            descripcion=payload.descripcion,
            tipo_proyecto=payload.tipo_proyecto,
            estatus=payload.estatus,
            prioridad=payload.prioridad,
            fecha_inicio=payload.fecha_inicio,
            fecha_fin_planificada=payload.fecha_fin_planificada,
            fecha_fin_real=payload.fecha_fin_real,
            porcentaje_avance=payload.porcentaje_avance,
            responsable_user_id=payload.responsable_user_id,
            responsable_nombre_snapshot=payload.responsable_nombre_snapshot,
            cliente_nombre_snapshot=payload.cliente_nombre_snapshot,
            presupuesto_estimado=payload.presupuesto_estimado,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}", response_model=PMProyectoOut)
def get_project_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoOut:
    return get_project(db, pm_context, project_id)


@router.get("/projects/{project_id}/materials", response_model=PMProyectoMaterialesOut)
def get_project_materials_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMaterialesOut:
    return list_project_material_plan(db, pm_context, project_id)


@router.post("/projects/{project_id}/materials/plan", response_model=PMProyectoMaterialPlanOut, status_code=status.HTTP_201_CREATED)
def create_project_material_plan_endpoint(
    project_id: str,
    payload: PMProyectoMaterialPlanCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMaterialPlanOut:
    return run_pm_write(
        db,
        "create_project_material_plan",
        lambda: add_project_material_plan(
            db,
            pm_context,
            project_id=project_id,
            task_id=payload.tarea_id,
            material_id=payload.material_id,
            cantidad_planificada=payload.cantidad_planificada,
            costo_unitario_estimado=payload.costo_unitario_estimado,
            observaciones=payload.observaciones,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/projects/{project_id}/materials/plan/{plan_id}", response_model=PMProyectoMaterialPlanOut)
def update_project_material_plan_endpoint(
    project_id: str,
    plan_id: str,
    payload: PMProyectoMaterialPlanUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMaterialPlanOut:
    return run_pm_write(
        db,
        "update_project_material_plan",
        lambda: update_project_material_plan(
            db,
            pm_context,
            project_id=project_id,
            plan_id=plan_id,
            task_id=payload.tarea_id,
            material_id=payload.material_id,
            cantidad_planificada=payload.cantidad_planificada,
            costo_unitario_estimado=payload.costo_unitario_estimado,
            observaciones=payload.observaciones,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/materials/plan/{plan_id}/deactivate", response_model=PMProyectoMaterialPlanOut)
def deactivate_project_material_plan_endpoint(
    project_id: str,
    plan_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMaterialPlanOut:
    return run_pm_write(
        db,
        "deactivate_project_material_plan",
        lambda: deactivate_project_material_plan(
            db,
            pm_context,
            project_id=project_id,
            plan_id=plan_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/materials/create-requisition", response_model=RequisitionResponse, status_code=status.HTTP_201_CREATED)
def create_project_material_requisition_endpoint(
    project_id: str,
    payload: PMCreateProjectRequisitionRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_pm_write(
        db,
        "create_project_material_requisition",
        lambda: create_project_material_requisition(
            db,
            pm_context,
            project_id=project_id,
            almacen_destino_id=payload.almacen_destino_id,
            items=[{"plan_id": item.plan_id, "cantidad_solicitada": item.cantidad_solicitada} for item in payload.items],
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/budget", response_model=PMProjectBudgetBundleOut)
def get_project_budget_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectBudgetBundleOut:
    return get_project_budget(db, pm_context, project_id)


@router.post("/projects/{project_id}/budget", response_model=PMPresupuestoOut, status_code=status.HTTP_201_CREATED)
def create_project_budget_endpoint(
    project_id: str,
    payload: PMPresupuestoCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoOut:
    return run_pm_write(
        db,
        "create_project_budget",
        lambda: create_project_budget(
            db,
            pm_context,
            project_id=project_id,
            nombre=payload.nombre,
            moneda=payload.moneda,
            indirectos_pct=payload.indirectos_pct,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/budgets/{budget_id}", response_model=PMPresupuestoOut)
def update_project_budget_endpoint(
    budget_id: str,
    payload: PMPresupuestoUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoOut:
    return run_pm_write(
        db,
        "update_project_budget",
        lambda: update_project_budget(
            db,
            pm_context,
            budget_id=budget_id,
            nombre=payload.nombre,
            moneda=payload.moneda,
            indirectos_pct=payload.indirectos_pct,
            notas=payload.notas,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budgets/{budget_id}/approve", response_model=PMPresupuestoOut)
def approve_project_budget_endpoint(
    budget_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoOut:
    return run_pm_write(
        db,
        "approve_project_budget",
        lambda: approve_project_budget(
            db,
            pm_context,
            budget_id=budget_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budgets/{budget_id}/cancel", response_model=PMPresupuestoOut)
def cancel_project_budget_endpoint(
    budget_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoOut:
    return run_pm_write(
        db,
        "cancel_project_budget",
        lambda: cancel_project_budget(
            db,
            pm_context,
            budget_id=budget_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/budget/refresh", response_model=PMProjectCostsOut)
def refresh_project_budget_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectCostsOut:
    return run_pm_write(
        db,
        "refresh_project_budget",
        lambda: refresh_project_total_costs(
            db,
            empresa_id=pm_context.empresa_id,
            project_id=project_id,
        ),
    )


@router.get("/projects/{project_id}/budget-vs-actual", response_model=PMBudgetVsActualOut)
def get_project_budget_vs_actual_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMBudgetVsActualOut:
    return get_project_budget_vs_actual(db, pm_context, project_id)


@router.post("/budgets/{budget_id}/items", response_model=PMPresupuestoPartidaOut, status_code=status.HTTP_201_CREATED)
def create_budget_item_endpoint(
    budget_id: str,
    payload: PMPresupuestoPartidaCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaOut:
    return run_pm_write(
        db,
        "create_budget_item",
        lambda: create_budget_item(
            db,
            pm_context,
            budget_id=budget_id,
            parent_id=payload.parent_id,
            codigo=payload.codigo,
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            tipo=payload.tipo,
            unidad=payload.unidad,
            cantidad=payload.cantidad,
            margen_pct=payload.margen_pct,
            precio_unitario_manual=payload.precio_unitario_manual,
            orden=payload.orden,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/budget-items/{item_id}", response_model=PMPresupuestoPartidaOut)
def update_budget_item_endpoint(
    item_id: str,
    payload: PMPresupuestoPartidaUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaOut:
    return run_pm_write(
        db,
        "update_budget_item",
        lambda: update_budget_item(
            db,
            pm_context,
            item_id=item_id,
            parent_id=payload.parent_id,
            codigo=payload.codigo,
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            tipo=payload.tipo,
            unidad=payload.unidad,
            cantidad=payload.cantidad,
            margen_pct=payload.margen_pct,
            precio_unitario_manual=payload.precio_unitario_manual,
            orden=payload.orden,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budget-items/{item_id}/deactivate", response_model=PMPresupuestoPartidaOut)
def deactivate_budget_item_endpoint(
    item_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaOut:
    return run_pm_write(
        db,
        "deactivate_budget_item",
        lambda: deactivate_budget_item(
            db,
            pm_context,
            item_id=item_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budget-items/{item_id}/materials", response_model=PMPresupuestoPartidaMaterialOut, status_code=status.HTTP_201_CREATED)
def create_budget_item_material_endpoint(
    item_id: str,
    payload: PMPresupuestoPartidaMaterialCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaMaterialOut:
    return run_pm_write(
        db,
        "create_budget_item_material",
        lambda: add_budget_item_material(
            db,
            pm_context,
            item_id=item_id,
            material_id=payload.material_id,
            material_nombre_snapshot=payload.material_nombre_snapshot,
            material_sku_snapshot=payload.material_sku_snapshot,
            unidad=payload.unidad,
            cantidad_por_unidad=payload.cantidad_por_unidad,
            costo_unitario=payload.costo_unitario,
            proveedor_nombre_snapshot=payload.proveedor_nombre_snapshot,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/budget-item-materials/{component_id}", response_model=PMPresupuestoPartidaMaterialOut)
def update_budget_item_material_endpoint(
    component_id: str,
    payload: PMPresupuestoPartidaMaterialUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaMaterialOut:
    return run_pm_write(
        db,
        "update_budget_item_material",
        lambda: update_budget_item_material(
            db,
            pm_context,
            component_id=component_id,
            material_id=payload.material_id,
            material_nombre_snapshot=payload.material_nombre_snapshot,
            material_sku_snapshot=payload.material_sku_snapshot,
            unidad=payload.unidad,
            cantidad_por_unidad=payload.cantidad_por_unidad,
            costo_unitario=payload.costo_unitario,
            proveedor_nombre_snapshot=payload.proveedor_nombre_snapshot,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budget-item-materials/{component_id}/deactivate", response_model=PMPresupuestoPartidaMaterialOut)
def deactivate_budget_item_material_endpoint(
    component_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaMaterialOut:
    return run_pm_write(
        db,
        "deactivate_budget_item_material",
        lambda: deactivate_budget_item_material(
            db,
            pm_context,
            component_id=component_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budget-items/{item_id}/labor", response_model=PMPresupuestoPartidaManoObraOut, status_code=status.HTTP_201_CREATED)
def create_budget_item_labor_endpoint(
    item_id: str,
    payload: PMPresupuestoPartidaManoObraCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaManoObraOut:
    return run_pm_write(
        db,
        "create_budget_item_labor",
        lambda: add_budget_item_labor(
            db,
            pm_context,
            item_id=item_id,
            rol=payload.rol,
            descripcion=payload.descripcion,
            horas_por_unidad=payload.horas_por_unidad,
            tarifa_hora=payload.tarifa_hora,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/budget-item-labor/{component_id}", response_model=PMPresupuestoPartidaManoObraOut)
def update_budget_item_labor_endpoint(
    component_id: str,
    payload: PMPresupuestoPartidaManoObraUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaManoObraOut:
    return run_pm_write(
        db,
        "update_budget_item_labor",
        lambda: update_budget_item_labor(
            db,
            pm_context,
            component_id=component_id,
            rol=payload.rol,
            descripcion=payload.descripcion,
            horas_por_unidad=payload.horas_por_unidad,
            tarifa_hora=payload.tarifa_hora,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budget-item-labor/{component_id}/deactivate", response_model=PMPresupuestoPartidaManoObraOut)
def deactivate_budget_item_labor_endpoint(
    component_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoPartidaManoObraOut:
    return run_pm_write(
        db,
        "deactivate_budget_item_labor",
        lambda: deactivate_budget_item_labor(
            db,
            pm_context,
            component_id=component_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budgets/{budget_id}/indirects", response_model=PMPresupuestoIndirectoOut, status_code=status.HTTP_201_CREATED)
def create_budget_indirect_endpoint(
    budget_id: str,
    payload: PMPresupuestoIndirectoCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoIndirectoOut:
    return run_pm_write(
        db,
        "create_budget_indirect",
        lambda: add_budget_indirect(
            db,
            pm_context,
            budget_id=budget_id,
            nombre=payload.nombre,
            tipo=payload.tipo,
            porcentaje=payload.porcentaje,
            monto=payload.monto,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/budget-indirects/{indirect_id}", response_model=PMPresupuestoIndirectoOut)
def update_budget_indirect_endpoint(
    indirect_id: str,
    payload: PMPresupuestoIndirectoUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoIndirectoOut:
    return run_pm_write(
        db,
        "update_budget_indirect",
        lambda: update_budget_indirect(
            db,
            pm_context,
            indirect_id=indirect_id,
            nombre=payload.nombre,
            tipo=payload.tipo,
            porcentaje=payload.porcentaje,
            monto=payload.monto,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/budget-indirects/{indirect_id}/deactivate", response_model=PMPresupuestoIndirectoOut)
def deactivate_budget_indirect_endpoint(
    indirect_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMPresupuestoIndirectoOut:
    return run_pm_write(
        db,
        "deactivate_budget_indirect",
        lambda: deactivate_budget_indirect(
            db,
            pm_context,
            indirect_id=indirect_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/costs", response_model=PMProjectCostsOut)
def get_project_costs_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectCostsOut:
    return get_project_costs(db, pm_context, project_id)


@router.post("/projects/{project_id}/costs/refresh", response_model=PMProjectCostsOut)
def refresh_project_costs_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectCostsOut:
    return run_pm_write(
        db,
        "refresh_project_costs",
        lambda: refresh_project_total_costs(
            db,
            empresa_id=pm_context.empresa_id,
            project_id=project_id,
        ),
    )


@router.get("/projects/{project_id}/time-entries", response_model=PMTimeEntryListResponse)
def list_project_time_entries_endpoint(
    project_id: str,
    user_id: str | None = None,
    task_id: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    activo: bool | None = True,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTimeEntryListResponse:
    parsed_fecha_desde = date.fromisoformat(fecha_desde) if fecha_desde else None
    parsed_fecha_hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else None
    return list_project_time_entries(
        db,
        pm_context,
        project_id=project_id,
        user_id=user_id,
        task_id=task_id,
        fecha_desde=parsed_fecha_desde,
        fecha_hasta=parsed_fecha_hasta,
        activo=activo,
        limit=limit,
        offset=offset,
    )


@router.post("/projects/{project_id}/time-entries", response_model=PMTimeEntryOut, status_code=status.HTTP_201_CREATED)
def create_project_time_entry_endpoint(
    project_id: str,
    payload: PMTimeEntryCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTimeEntryOut:
    return run_pm_write(
        db,
        "create_project_time_entry",
        lambda: create_project_time_entry(
            db,
            pm_context,
            project_id=project_id,
            tarea_id=payload.tarea_id,
            usuario_id=payload.usuario_id,
            usuario_email_snapshot=payload.usuario_email_snapshot,
            usuario_nombre_snapshot=payload.usuario_nombre_snapshot,
            fecha=payload.fecha,
            horas=payload.horas,
            descripcion=payload.descripcion,
            moneda=payload.moneda,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/time-entries/{time_entry_id}", response_model=PMTimeEntryOut)
def update_project_time_entry_endpoint(
    time_entry_id: str,
    payload: PMTimeEntryUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTimeEntryOut:
    return run_pm_write(
        db,
        "update_project_time_entry",
        lambda: update_project_time_entry(
            db,
            pm_context,
            time_entry_id=time_entry_id,
            tarea_id=payload.tarea_id,
            usuario_id=payload.usuario_id,
            usuario_email_snapshot=payload.usuario_email_snapshot,
            usuario_nombre_snapshot=payload.usuario_nombre_snapshot,
            fecha=payload.fecha,
            horas=payload.horas,
            descripcion=payload.descripcion,
            moneda=payload.moneda,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/time-entries/{time_entry_id}/deactivate", response_model=PMTimeEntryOut)
def deactivate_project_time_entry_endpoint(
    time_entry_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTimeEntryOut:
    return run_pm_write(
        db,
        "deactivate_project_time_entry",
        lambda: deactivate_project_time_entry(
            db,
            pm_context,
            time_entry_id=time_entry_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/rates/users", response_model=PMTarifaHoraUsuarioListResponse)
def list_user_hourly_rates_endpoint(
    q: str | None = None,
    activa: bool | None = True,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraUsuarioListResponse:
    return list_user_hourly_rates(
        db,
        pm_context,
        q=q,
        activa=activa,
        limit=limit,
        offset=offset,
    )


@router.post("/rates/users", response_model=PMTarifaHoraUsuarioOut, status_code=status.HTTP_201_CREATED)
def create_user_hourly_rate_endpoint(
    payload: PMTarifaHoraUsuarioCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraUsuarioOut:
    return run_pm_write(
        db,
        "create_user_hourly_rate",
        lambda: create_user_hourly_rate(
            db,
            pm_context,
            usuario_id=payload.usuario_id,
            usuario_email=payload.usuario_email,
            usuario_nombre_snapshot=payload.usuario_nombre_snapshot,
            tarifa_hora=payload.tarifa_hora,
            moneda=payload.moneda,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/rates/users/{rate_id}", response_model=PMTarifaHoraUsuarioOut)
def update_user_hourly_rate_endpoint(
    rate_id: str,
    payload: PMTarifaHoraUsuarioUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraUsuarioOut:
    return run_pm_write(
        db,
        "update_user_hourly_rate",
        lambda: update_user_hourly_rate(
            db,
            pm_context,
            rate_id=rate_id,
            usuario_id=payload.usuario_id,
            usuario_email=payload.usuario_email,
            usuario_nombre_snapshot=payload.usuario_nombre_snapshot,
            tarifa_hora=payload.tarifa_hora,
            moneda=payload.moneda,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            activa=payload.activa,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/rates/users/{rate_id}/deactivate", response_model=PMTarifaHoraUsuarioOut)
def deactivate_user_hourly_rate_endpoint(
    rate_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraUsuarioOut:
    return run_pm_write(
        db,
        "deactivate_user_hourly_rate",
        lambda: deactivate_user_hourly_rate(
            db,
            pm_context,
            rate_id=rate_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/rates/roles", response_model=PMTarifaHoraRolListResponse)
def list_role_hourly_rates_endpoint(
    q: str | None = None,
    activa: bool | None = True,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraRolListResponse:
    return list_role_hourly_rates(
        db,
        pm_context,
        q=q,
        activa=activa,
        limit=limit,
        offset=offset,
    )


@router.post("/rates/roles", response_model=PMTarifaHoraRolOut, status_code=status.HTTP_201_CREATED)
def create_role_hourly_rate_endpoint(
    payload: PMTarifaHoraRolCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraRolOut:
    return run_pm_write(
        db,
        "create_role_hourly_rate",
        lambda: create_role_hourly_rate(
            db,
            pm_context,
            rol=payload.rol,
            tarifa_hora=payload.tarifa_hora,
            moneda=payload.moneda,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/rates/roles/{rate_id}", response_model=PMTarifaHoraRolOut)
def update_role_hourly_rate_endpoint(
    rate_id: str,
    payload: PMTarifaHoraRolUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraRolOut:
    return run_pm_write(
        db,
        "update_role_hourly_rate",
        lambda: update_role_hourly_rate(
            db,
            pm_context,
            rate_id=rate_id,
            rol=payload.rol,
            tarifa_hora=payload.tarifa_hora,
            moneda=payload.moneda,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            activa=payload.activa,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/rates/roles/{rate_id}/deactivate", response_model=PMTarifaHoraRolOut)
def deactivate_role_hourly_rate_endpoint(
    rate_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTarifaHoraRolOut:
    return run_pm_write(
        db,
        "deactivate_role_hourly_rate",
        lambda: deactivate_role_hourly_rate(
            db,
            pm_context,
            rate_id=rate_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/projects/{project_id}", response_model=PMProyectoOut)
def update_project_endpoint(
    project_id: str,
    payload: PMProyectoUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoOut:
    return run_pm_write(
        db,
        "update_project",
        lambda: update_project(
            db,
            pm_context,
            project_id=project_id,
            nombre=payload.nombre,
            codigo=payload.codigo,
            descripcion=payload.descripcion,
            tipo_proyecto=payload.tipo_proyecto,
            estatus=payload.estatus,
            prioridad=payload.prioridad,
            fecha_inicio=payload.fecha_inicio,
            fecha_fin_planificada=payload.fecha_fin_planificada,
            fecha_fin_real=payload.fecha_fin_real,
            porcentaje_avance=payload.porcentaje_avance,
            responsable_user_id=payload.responsable_user_id,
            responsable_nombre_snapshot=payload.responsable_nombre_snapshot,
            cliente_nombre_snapshot=payload.cliente_nombre_snapshot,
            presupuesto_estimado=payload.presupuesto_estimado,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/deactivate", response_model=PMProyectoOut)
def deactivate_project_endpoint(
    project_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoOut:
    return run_pm_write(
        db,
        "deactivate_project",
        lambda: deactivate_project(
            db,
            pm_context,
            project_id=project_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/members", response_model=PMProjectMembersListResponse)
def get_project_members(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectMembersListResponse:
    return list_project_members(db, pm_context, project_id)


@router.post("/projects/{project_id}/members", response_model=PMProyectoMiembroOut, status_code=status.HTTP_201_CREATED)
def add_project_member_endpoint(
    project_id: str,
    payload: PMProyectoMiembroCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMiembroOut:
    return run_pm_write(
        db,
        "add_project_member",
        lambda: add_project_member(
            db,
            pm_context,
            project_id=project_id,
            usuario_id=payload.usuario_id,
            email=payload.email,
            nombre_snapshot=payload.nombre_snapshot,
            rol_en_proyecto=payload.rol_en_proyecto,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/members/{member_id}/deactivate", response_model=PMProyectoMiembroOut)
def deactivate_project_member_endpoint(
    project_id: str,
    member_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMiembroOut:
    return run_pm_write(
        db,
        "deactivate_project_member",
        lambda: deactivate_project_member(
            db,
            pm_context,
            project_id=project_id,
            member_id=member_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/dependencies", response_model=list[PMTareaDependenciaOut])
def list_project_dependencies_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMTareaDependenciaOut]:
    return list_task_dependencies(db, pm_context, project_id=project_id)


@router.get("/projects/{project_id}/tasks", response_model=PMTareaListResponse)
def get_project_tasks(
    project_id: str,
    q: str | None = None,
    estatus: str | None = None,
    prioridad: str | None = None,
    activo: bool | None = True,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTareaListResponse:
    return list_tasks(
        db,
        pm_context,
        project_id=project_id,
        q=q,
        estatus=estatus,
        prioridad=prioridad,
        activo=activo,
        limit=limit,
        offset=offset,
    )


@router.post("/projects/{project_id}/tasks", response_model=PMTareaOut, status_code=status.HTTP_201_CREATED)
def create_task_endpoint(
    project_id: str,
    payload: PMTareaCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTareaOut:
    return run_pm_write(
        db,
        "create_task",
        lambda: create_task(
            db,
            pm_context,
            project_id=project_id,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            estatus=payload.estatus,
            prioridad=payload.prioridad,
            asignado_user_id=payload.asignado_user_id,
            asignado_nombre_snapshot=payload.asignado_nombre_snapshot,
            fecha_inicio=payload.fecha_inicio,
            fecha_vencimiento=payload.fecha_vencimiento,
            fecha_completada=payload.fecha_completada,
            estimacion_horas=payload.estimacion_horas,
            porcentaje_avance=payload.porcentaje_avance,
            orden=payload.orden,
            bloqueada=payload.bloqueada,
            requiere_materiales=payload.requiere_materiales,
            requiere_compra=payload.requiere_compra,
            requiere_venta_pos=payload.requiere_venta_pos,
            requiere_factura=payload.requiere_factura,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/tasks/{task_id}", response_model=PMTareaOut)
def get_task_endpoint(
    task_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTareaOut:
    return get_task(db, pm_context, task_id)


@router.get("/tasks/{task_id}/dependencies", response_model=PMTaskDependenciesOut)
def get_task_dependencies_endpoint(
    task_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTaskDependenciesOut:
    return get_task_dependencies(db, pm_context, task_id=task_id)


@router.post("/tasks/{task_id}/dependencies", response_model=PMTaskDependenciesOut, status_code=status.HTTP_201_CREATED)
def create_task_dependency_endpoint(
    task_id: str,
    payload: PMTareaDependenciaCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTaskDependenciesOut:
    return run_pm_write(
        db,
        "create_task_dependency",
        lambda: create_task_dependency(
            db,
            pm_context,
            task_id=task_id,
            depende_de_tarea_id=payload.depende_de_tarea_id,
            tipo_dependencia=payload.tipo_dependencia,
            lag_dias=payload.lag_dias,
            bloqueante=payload.bloqueante,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/task-dependencies/{dependency_id}/deactivate", response_model=PMTaskDependenciesOut)
def deactivate_task_dependency_endpoint(
    dependency_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTaskDependenciesOut:
    return run_pm_write(
        db,
        "deactivate_task_dependency",
        lambda: deactivate_task_dependency(
            db,
            pm_context,
            dependency_id=dependency_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/tasks/{task_id}", response_model=PMTareaOut)
def update_task_endpoint(
    task_id: str,
    payload: PMTareaUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTareaOut:
    return run_pm_write(
        db,
        "update_task",
        lambda: update_task(
            db,
            pm_context,
            task_id=task_id,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            estatus=payload.estatus,
            prioridad=payload.prioridad,
            asignado_user_id=payload.asignado_user_id,
            asignado_nombre_snapshot=payload.asignado_nombre_snapshot,
            fecha_inicio=payload.fecha_inicio,
            fecha_vencimiento=payload.fecha_vencimiento,
            fecha_completada=payload.fecha_completada,
            estimacion_horas=payload.estimacion_horas,
            porcentaje_avance=payload.porcentaje_avance,
            orden=payload.orden,
            bloqueada=payload.bloqueada,
            requiere_materiales=payload.requiere_materiales,
            requiere_compra=payload.requiere_compra,
            requiere_venta_pos=payload.requiere_venta_pos,
            requiere_factura=payload.requiere_factura,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/tasks/{task_id}/deactivate", response_model=PMTareaOut)
def deactivate_task_endpoint(
    task_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMTareaOut:
    return run_pm_write(
        db,
        "deactivate_task",
        lambda: deactivate_task(
            db,
            pm_context,
            task_id=task_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/tasks/{task_id}/subtasks", response_model=PMSubtareaOut, status_code=status.HTTP_201_CREATED)
def create_subtask_endpoint(
    task_id: str,
    payload: PMSubtareaCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMSubtareaOut:
    return run_pm_write(
        db,
        "create_subtask",
        lambda: create_subtask(
            db,
            pm_context,
            task_id=task_id,
            titulo=payload.titulo,
            estatus=payload.estatus,
            orden=payload.orden,
            asignado_user_id=payload.asignado_user_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/subtasks/{subtask_id}", response_model=PMSubtareaOut)
def update_subtask_endpoint(
    subtask_id: str,
    payload: PMSubtareaUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMSubtareaOut:
    return run_pm_write(
        db,
        "update_subtask",
        lambda: update_subtask(
            db,
            pm_context,
            subtask_id=subtask_id,
            titulo=payload.titulo,
            estatus=payload.estatus,
            orden=payload.orden,
            asignado_user_id=payload.asignado_user_id,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/tasks/{task_id}/checklist", response_model=PMChecklistItemOut, status_code=status.HTTP_201_CREATED)
def create_checklist_item_endpoint(
    task_id: str,
    payload: PMChecklistItemCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMChecklistItemOut:
    return run_pm_write(
        db,
        "create_checklist_item",
        lambda: create_checklist_item(
            db,
            pm_context,
            task_id=task_id,
            titulo=payload.titulo,
            completado=payload.completado,
            orden=payload.orden,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/checklist/{item_id}", response_model=PMChecklistItemOut)
def update_checklist_item_endpoint(
    item_id: str,
    payload: PMChecklistItemUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMChecklistItemOut:
    return run_pm_write(
        db,
        "update_checklist_item",
        lambda: update_checklist_item(
            db,
            pm_context,
            item_id=item_id,
            titulo=payload.titulo,
            completado=payload.completado,
            orden=payload.orden,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/comments", response_model=PMCommentOut, status_code=status.HTTP_201_CREATED)
def create_project_comment_endpoint(
    project_id: str,
    payload: PMComentarioCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCommentOut:
    return run_pm_write(
        db,
        "create_project_comment",
        lambda: create_project_comment(
            db,
            pm_context,
            project_id=project_id,
            body=payload.body,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/tasks/{task_id}/comments", response_model=PMCommentOut, status_code=status.HTTP_201_CREATED)
def create_task_comment_endpoint(
    task_id: str,
    payload: PMComentarioCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCommentOut:
    return run_pm_write(
        db,
        "create_task_comment",
        lambda: create_task_comment(
            db,
            pm_context,
            task_id=task_id,
            body=payload.body,
            ip_address=request.client.host if request.client else None,
        ),
    )
