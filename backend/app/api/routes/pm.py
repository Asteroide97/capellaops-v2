import logging
from datetime import date
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.pm import (
    PMApplyScheduleOut,
    PMAlertOut,
    PMAlertResolveRequest,
    PMAprobacionCreate,
    PMAprobacionOut,
    PMAprobacionResolve,
    PMBaselineVsActualOut,
    PMBudgetVsActualOut,
    PMCambioProyectoApplyRequest,
    PMCambioProyectoCreate,
    PMCambioProyectoOut,
    PMCambioProyectoSubmitRequest,
    PMCambioProyectoUpdate,
    PMChecklistItemCreate,
    PMChecklistItemOut,
    PMChecklistItemUpdate,
    PMCommentOut,
    PMComentarioCreate,
    PMConfigOut,
    PMDashboardOut,
    PMDocumentoOut,
    PMDocumentoUpdate,
    PMExecutiveReportOut,
    PMEstimationCandidateOut,
    PMEstimacionCobroRequest,
    PMEstimacionCreate,
    PMEstimacionDetailOut,
    PMEstimacionDetalleCreate,
    PMEstimacionDetalleUpdate,
    PMEstimacionOut,
    PMEstimacionResolveRequest,
    PMEstimacionSubmitRequest,
    PMEstimacionUpdate,
    PMInvitadoExternoCreate,
    PMInvitadoExternoCreatedOut,
    PMInvitadoExternoOut,
    PMLineaBaseCreate,
    PMLineaBaseDetailOut,
    PMLineaBaseOut,
    PMPortalAccessLogOut,
    PMPortalCommentCreate,
    PMPortalCommentOut,
    PMPortalProjectOut,
    PMCriticalPathOut,
    PMProjectMembersListResponse,
    PMProjectPlanningOut,
    PMRescheduleImpactOut,
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
    PMProjectMaterialConsumeRequest,
    PMProjectMaterialReturnRequest,
    PMProyectoMaterialPlanOut,
    PMProyectoMaterialPlanUpdate,
    PMProyectoMaterialesOut,
    PMProyectoCreate,
    PMProyectoListResponse,
    PMProyectoMiembroCreate,
    PMProyectoMiembroOut,
    PMProyectoEstimacionesResumenOut,
    PMProyectoOut,
    PMProjectCrmLinkRequest,
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
    PMTaskDateUpdateRequest,
    PMTareaListResponse,
    PMTareaOut,
    PMTareaUpdate,
    PMScheduleApplySuggestionRequest,
    PMWorkCalendarOut,
    PMWorkCalendarUpdate,
)
from app.services.pm import (
    PMContext,
    add_budget_indirect,
    add_budget_item_labor,
    add_budget_item_material,
    add_estimation_detail,
    add_project_member,
    add_project_material_plan,
    apply_project_change,
    approve_project_budget,
    approve_project_change,
    approve_estimation,
    cancel_project_budget,
    cancel_project_change,
    cancel_project_approval,
    cancel_project_estimation,
    create_task_dependency,
    create_external_invite,
    create_project_baseline,
    create_budget_item,
    create_project_estimation,
    create_project_change,
    create_portal_comment,
    create_project_budget,
    create_project_approval,
    consume_project_material_from_inventory,
    create_project_material_requisition,
    create_checklist_item,
    create_project,
    create_project_comment,
    upload_project_document,
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
    deactivate_project_document,
    deactivate_budget_indirect,
    deactivate_budget_item,
    deactivate_budget_item_labor,
    deactivate_budget_item_material,
    deactivate_estimation_detail,
    dismiss_pm_alert,
    get_pm_context,
    get_pm_dashboard,
    get_pm_executive_report,
    get_portal_project,
    get_project_baseline,
    get_project_baseline_vs_actual,
    get_project_critical_path,
    get_project_planning,
    get_project_budget,
    get_project_budget_vs_actual,
    get_project_change,
    get_project_estimation,
    get_project_estimations_summary,
    get_project_for_company,
    get_project_requisition,
    get_project,
    get_project_costs,
    get_task,
    get_task_dependencies,
    list_project_approvals,
    list_project_alerts,
    list_project_baselines,
    list_project_changes,
    list_project_estimation_candidates,
    list_project_estimations,
    list_project_documents,
    list_project_external_invites,
    list_project_portal_access_logs,
    list_project_requisitions,
    list_project_time_entries,
    list_project_material_plan,
    list_project_members,
    list_task_dependencies,
    list_projects,
    link_project_to_crm,
    list_role_hourly_rates,
    list_tasks,
    list_user_hourly_rates,
    regenerate_external_invite,
    refresh_project_planning,
    refresh_project_total_costs,
    reject_project_change,
    reject_estimation,
    cancel_project_requisition,
    return_project_material_to_inventory,
    return_estimation_to_draft,
    resolve_pm_alert,
    serialize_pm_config,
    approve_project_approval,
    apply_task_suggested_dates,
    reject_project_approval,
    revoke_external_invite,
    calculate_reschedule_impact,
    get_project_work_calendar,
    update_project_document,
    update_budget_indirect,
    update_budget_item,
    update_budget_item_labor,
    update_budget_item_material,
    update_estimation_detail,
    update_project_budget,
    update_project_estimation,
    update_project_change,
    update_project_time_entry,
    update_checklist_item,
    update_project,
    update_project_material_plan,
    update_role_hourly_rate,
    update_subtask,
    update_task_dates_with_impact,
    update_task,
    update_project_work_calendar,
    update_user_hourly_rate,
    set_project_baseline_as_main,
    archive_project_baseline,
    mark_estimation_collected,
    mark_estimation_sent,
    submit_project_requisition,
    submit_project_change,
    submit_estimation,
    unlink_project_from_crm,
)
from app.services.documents_pdf import build_pm_estimation_pdf
from app.schemas.procurement import RequisitionListResponse, RequisitionResponse
from app.services.storage import StorageConfigurationError


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


def build_portal_url(request: Request, token: str) -> str:
    settings = get_settings()
    frontend_origin = settings.public_frontend_origin or str(request.headers.get("origin") or "").strip().rstrip("/")
    if not frontend_origin:
        frontend_origin = str(request.base_url).strip().rstrip("/")
    return f"{frontend_origin}/portal/pm/{token}"


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


@router.get("/reports/executive", response_model=PMExecutiveReportOut)
def pm_executive_report(
    estatus: str | None = None,
    prioridad: str | None = None,
    responsable_id: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    salud: str | None = None,
    con_alertas: bool | None = None,
    con_pendiente_cobro: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMExecutiveReportOut:
    return get_pm_executive_report(
        db,
        pm_context,
        estatus=estatus,
        prioridad=prioridad,
        responsable_id=responsable_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        salud=salud,
        con_alertas=con_alertas,
        con_pendiente_cobro=con_pendiente_cobro,
        limit=limit,
        offset=offset,
    )


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


@router.put("/projects/{project_id}/crm-link", response_model=PMProyectoOut)
def link_project_to_crm_endpoint(
    project_id: str,
    payload: PMProjectCrmLinkRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoOut:
    return run_pm_write(
        db,
        "link_project_to_crm",
        lambda: link_project_to_crm(
            db,
            pm_context,
            project_id=project_id,
            cliente_id=payload.cliente_id,
            contacto_id=payload.contacto_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.delete("/projects/{project_id}/crm-link", response_model=PMProyectoOut)
def unlink_project_from_crm_endpoint(
    project_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoOut:
    return run_pm_write(
        db,
        "unlink_project_from_crm",
        lambda: unlink_project_from_crm(
            db,
            pm_context,
            project_id=project_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


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


@router.get("/projects/{project_id}/requisitions", response_model=RequisitionListResponse)
def list_project_requisitions_endpoint(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> RequisitionListResponse:
    total, items = list_project_requisitions(
        db,
        pm_context,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    return RequisitionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/projects/{project_id}/requisitions", response_model=RequisitionResponse, status_code=status.HTTP_201_CREATED)
def create_project_requisition_endpoint(
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
            tarea_id=payload.tarea_id,
            partida_id=payload.partida_id,
            prioridad=payload.prioridad,
            items=[
                {
                    "plan_id": item.plan_id,
                    "cantidad_solicitada": item.cantidad_solicitada,
                    "notas": item.notas,
                }
                for item in payload.items
            ],
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/requisitions/{requisition_id}", response_model=RequisitionResponse)
def get_project_requisition_endpoint(
    requisition_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return get_project_requisition(db, pm_context, requisition_id=requisition_id)


@router.post("/requisitions/{requisition_id}/submit", response_model=RequisitionResponse)
def submit_project_requisition_endpoint(
    requisition_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_pm_write(
        db,
        "submit_project_requisition",
        lambda: submit_project_requisition(
            db,
            pm_context,
            requisition_id=requisition_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/requisitions/{requisition_id}/cancel", response_model=RequisitionResponse)
def cancel_project_requisition_endpoint(
    requisition_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> RequisitionResponse:
    return run_pm_write(
        db,
        "cancel_project_requisition",
        lambda: cancel_project_requisition(
            db,
            pm_context,
            requisition_id=requisition_id,
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
            tarea_id=payload.tarea_id,
            partida_id=payload.partida_id,
            prioridad=payload.prioridad,
            items=[
                {
                    "plan_id": item.plan_id,
                    "cantidad_solicitada": item.cantidad_solicitada,
                    "notas": item.notas,
                }
                for item in payload.items
            ],
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/materials/consume", response_model=PMProyectoMaterialesOut)
def consume_project_material_endpoint(
    project_id: str,
    payload: PMProjectMaterialConsumeRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMaterialesOut:
    return run_pm_write(
        db,
        "consume_project_material",
        lambda: consume_project_material_from_inventory(
            db,
            pm_context,
            project_id=project_id,
            material_id=payload.material_id,
            almacen_id=payload.almacen_id,
            cantidad=payload.cantidad,
            tarea_id=payload.tarea_id,
            partida_id=payload.partida_id,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/materials/return", response_model=PMProyectoMaterialesOut)
def return_project_material_endpoint(
    project_id: str,
    payload: PMProjectMaterialReturnRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoMaterialesOut:
    return run_pm_write(
        db,
        "return_project_material",
        lambda: return_project_material_to_inventory(
            db,
            pm_context,
            project_id=project_id,
            material_id=payload.material_id,
            almacen_id=payload.almacen_id,
            cantidad=payload.cantidad,
            tarea_id=payload.tarea_id,
            partida_id=payload.partida_id,
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


@router.get("/projects/{project_id}/estimations", response_model=list[PMEstimacionOut])
def list_project_estimations_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMEstimacionOut]:
    return list_project_estimations(db, pm_context, project_id=project_id)


@router.post("/projects/{project_id}/estimations", response_model=PMEstimacionOut, status_code=status.HTTP_201_CREATED)
def create_project_estimation_endpoint(
    project_id: str,
    payload: PMEstimacionCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "create_project_estimation",
        lambda: create_project_estimation(
            db,
            pm_context,
            project_id=project_id,
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            periodo_inicio=payload.periodo_inicio,
            periodo_fin=payload.periodo_fin,
            retencion_pct=payload.retencion_pct,
            anticipo_aplicado=payload.anticipo_aplicado,
            requiere_aprobacion=payload.requiere_aprobacion,
            moneda=payload.moneda,
            linea_base_id=payload.linea_base_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/estimations/{estimation_id}", response_model=PMEstimacionDetailOut)
def get_project_estimation_endpoint(
    estimation_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionDetailOut:
    return get_project_estimation(db, pm_context, estimation_id=estimation_id)


@router.get("/estimations/{estimation_id}/pdf")
def export_project_estimation_pdf_endpoint(
    estimation_id: str,
    context: TenantContext = Depends(get_tenant_context),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> Response:
    estimation = get_project_estimation(db, pm_context, estimation_id=estimation_id)
    project = get_project_for_company(db, pm_context.empresa_id, estimation.proyecto_id)
    pdf_bytes, filename = build_pm_estimation_pdf(context.empresa, project, estimation)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/estimations/{estimation_id}", response_model=PMEstimacionOut)
def update_project_estimation_endpoint(
    estimation_id: str,
    payload: PMEstimacionUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "update_project_estimation",
        lambda: update_project_estimation(
            db,
            pm_context,
            estimation_id=estimation_id,
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            periodo_inicio=payload.periodo_inicio,
            periodo_fin=payload.periodo_fin,
            retencion_pct=payload.retencion_pct,
            anticipo_aplicado=payload.anticipo_aplicado,
            requiere_aprobacion=payload.requiere_aprobacion,
            moneda=payload.moneda,
            linea_base_id=payload.linea_base_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/cancel", response_model=PMEstimacionOut)
def cancel_project_estimation_endpoint(
    estimation_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "cancel_project_estimation",
        lambda: cancel_project_estimation(
            db,
            pm_context,
            estimation_id=estimation_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/details", response_model=PMEstimacionDetailOut, status_code=status.HTTP_201_CREATED)
def add_estimation_detail_endpoint(
    estimation_id: str,
    payload: PMEstimacionDetalleCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionDetailOut:
    return run_pm_write(
        db,
        "add_estimation_detail",
        lambda: add_estimation_detail(
            db,
            pm_context,
            estimation_id=estimation_id,
            presupuesto_partida_id=payload.presupuesto_partida_id,
            tarea_id=payload.tarea_id,
            avance_actual_pct=payload.avance_actual_pct,
            notas=payload.notas,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.put("/estimation-details/{detail_id}", response_model=PMEstimacionDetailOut)
def update_estimation_detail_endpoint(
    detail_id: str,
    payload: PMEstimacionDetalleUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionDetailOut:
    return run_pm_write(
        db,
        "update_estimation_detail",
        lambda: update_estimation_detail(
            db,
            pm_context,
            detail_id=detail_id,
            tarea_id=payload.tarea_id,
            avance_actual_pct=payload.avance_actual_pct,
            notas=payload.notas,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimation-details/{detail_id}/deactivate", response_model=PMEstimacionDetailOut)
def deactivate_estimation_detail_endpoint(
    detail_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionDetailOut:
    return run_pm_write(
        db,
        "deactivate_estimation_detail",
        lambda: deactivate_estimation_detail(
            db,
            pm_context,
            detail_id=detail_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/submit", response_model=PMEstimacionOut)
def submit_estimation_endpoint(
    estimation_id: str,
    payload: PMEstimacionSubmitRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "submit_estimation",
        lambda: submit_estimation(
            db,
            pm_context,
            estimation_id=estimation_id,
            comment=payload.comentario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/approve", response_model=PMEstimacionOut)
def approve_estimation_endpoint(
    estimation_id: str,
    payload: PMEstimacionResolveRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "approve_estimation",
        lambda: approve_estimation(
            db,
            pm_context,
            estimation_id=estimation_id,
            comment=payload.comentario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/reject", response_model=PMEstimacionOut)
def reject_estimation_endpoint(
    estimation_id: str,
    payload: PMEstimacionResolveRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "reject_estimation",
        lambda: reject_estimation(
            db,
            pm_context,
            estimation_id=estimation_id,
            comment=payload.comentario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/return-to-draft", response_model=PMEstimacionOut)
def return_estimation_to_draft_endpoint(
    estimation_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "return_estimation_to_draft",
        lambda: return_estimation_to_draft(
            db,
            pm_context,
            estimation_id=estimation_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/mark-sent", response_model=PMEstimacionOut)
def mark_estimation_sent_endpoint(
    estimation_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "mark_estimation_sent",
        lambda: mark_estimation_sent(
            db,
            pm_context,
            estimation_id=estimation_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/estimations/{estimation_id}/mark-collected", response_model=PMEstimacionOut)
def mark_estimation_collected_endpoint(
    estimation_id: str,
    payload: PMEstimacionCobroRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMEstimacionOut:
    return run_pm_write(
        db,
        "mark_estimation_collected",
        lambda: mark_estimation_collected(
            db,
            pm_context,
            estimation_id=estimation_id,
            amount=payload.monto_cobrado,
            comment=payload.comentario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/estimations-summary", response_model=PMProyectoEstimacionesResumenOut)
def get_project_estimations_summary_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProyectoEstimacionesResumenOut:
    return get_project_estimations_summary(db, pm_context, project_id=project_id)


@router.get("/projects/{project_id}/estimation-candidates", response_model=list[PMEstimationCandidateOut])
def list_project_estimation_candidates_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMEstimationCandidateOut]:
    return list_project_estimation_candidates(db, pm_context, project_id=project_id)


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


@router.get("/projects/{project_id}/planning", response_model=PMProjectPlanningOut)
def get_project_planning_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectPlanningOut:
    return get_project_planning(db, pm_context, project_id)


@router.get("/projects/{project_id}/critical-path", response_model=PMCriticalPathOut)
def get_project_critical_path_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCriticalPathOut:
    return get_project_critical_path(db, pm_context, project_id=project_id)


@router.get("/projects/{project_id}/work-calendar", response_model=PMWorkCalendarOut)
def get_project_work_calendar_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMWorkCalendarOut:
    return get_project_work_calendar(db, pm_context, project_id=project_id)


@router.put("/projects/{project_id}/work-calendar", response_model=PMWorkCalendarOut)
def update_project_work_calendar_endpoint(
    project_id: str,
    payload: PMWorkCalendarUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMWorkCalendarOut:
    return run_pm_write(
        db,
        "update_project_work_calendar",
        lambda: update_project_work_calendar(
            db,
            pm_context,
            project_id=project_id,
            nombre=payload.nombre,
            lunes=payload.lunes,
            martes=payload.martes,
            miercoles=payload.miercoles,
            jueves=payload.jueves,
            viernes=payload.viernes,
            sabado=payload.sabado,
            domingo=payload.domingo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/refresh-planning", response_model=PMProjectPlanningOut)
def refresh_project_planning_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectPlanningOut:
    return run_pm_write(
        db,
        "refresh_project_planning",
        lambda: refresh_project_planning(db, pm_context, project_id=project_id),
    )


@router.get("/projects/{project_id}/baselines", response_model=list[PMLineaBaseOut])
def list_project_baselines_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMLineaBaseOut]:
    return list_project_baselines(db, pm_context, project_id=project_id)


@router.post("/projects/{project_id}/baselines", response_model=PMLineaBaseDetailOut, status_code=status.HTTP_201_CREATED)
def create_project_baseline_endpoint(
    project_id: str,
    payload: PMLineaBaseCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMLineaBaseDetailOut:
    return run_pm_write(
        db,
        "create_project_baseline",
        lambda: create_project_baseline(
            db,
            pm_context,
            project_id=project_id,
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            es_principal=payload.es_principal,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/baselines/{baseline_id}", response_model=PMLineaBaseDetailOut)
def get_project_baseline_endpoint(
    baseline_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMLineaBaseDetailOut:
    return get_project_baseline(db, pm_context, baseline_id=baseline_id)


@router.post("/baselines/{baseline_id}/set-main", response_model=PMLineaBaseOut)
def set_project_baseline_as_main_endpoint(
    baseline_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMLineaBaseOut:
    return run_pm_write(
        db,
        "set_project_baseline_as_main",
        lambda: set_project_baseline_as_main(
            db,
            pm_context,
            baseline_id=baseline_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/baselines/{baseline_id}/archive", response_model=PMLineaBaseOut)
def archive_project_baseline_endpoint(
    baseline_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMLineaBaseOut:
    return run_pm_write(
        db,
        "archive_project_baseline",
        lambda: archive_project_baseline(
            db,
            pm_context,
            baseline_id=baseline_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/baseline-vs-actual", response_model=PMBaselineVsActualOut)
def get_project_baseline_vs_actual_endpoint(
    project_id: str,
    baseline_id: str | None = None,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMBaselineVsActualOut:
    return get_project_baseline_vs_actual(
        db,
        pm_context,
        project_id=project_id,
        baseline_id=baseline_id,
    )


@router.get("/projects/{project_id}/tasks/{task_id}/reschedule-impact", response_model=PMRescheduleImpactOut)
def get_task_reschedule_impact_endpoint(
    project_id: str,
    task_id: str,
    fecha_inicio: str,
    fecha_fin: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMRescheduleImpactOut:
    return calculate_reschedule_impact(
        db,
        pm_context,
        project_id=project_id,
        task_id=task_id,
        fecha_inicio=date.fromisoformat(fecha_inicio),
        fecha_fin=date.fromisoformat(fecha_fin),
    )


@router.get("/projects/{project_id}/alerts", response_model=list[PMAlertOut])
def list_project_alerts_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMAlertOut]:
    return list_project_alerts(db, pm_context, project_id=project_id)


@router.post("/alerts/{alert_id}/resolve", response_model=PMAlertOut)
def resolve_pm_alert_endpoint(
    alert_id: str,
    payload: PMAlertResolveRequest,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMAlertOut:
    return run_pm_write(
        db,
        "resolve_pm_alert",
        lambda: resolve_pm_alert(
            db,
            pm_context,
            alert_id=alert_id,
            comentario=payload.comentario,
        ),
    )


@router.post("/alerts/{alert_id}/dismiss", response_model=PMAlertOut)
def dismiss_pm_alert_endpoint(
    alert_id: str,
    payload: PMAlertResolveRequest,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMAlertOut:
    return run_pm_write(
        db,
        "dismiss_pm_alert",
        lambda: dismiss_pm_alert(
            db,
            pm_context,
            alert_id=alert_id,
            comentario=payload.comentario,
        ),
    )


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


@router.post("/projects/{project_id}/tasks/{task_id}/apply-suggested-dates", response_model=PMApplyScheduleOut)
def apply_task_suggested_dates_endpoint(
    project_id: str,
    task_id: str,
    payload: PMScheduleApplySuggestionRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMApplyScheduleOut:
    return run_pm_write(
        db,
        "apply_task_suggested_dates",
        lambda: apply_task_suggested_dates(
            db,
            pm_context,
            project_id=project_id,
            task_id=task_id,
            apply_dependents=payload.apply_dependents,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/projects/{project_id}/tasks/{task_id}/update-dates", response_model=PMApplyScheduleOut)
def update_task_dates_endpoint(
    project_id: str,
    task_id: str,
    payload: PMTaskDateUpdateRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMApplyScheduleOut:
    return run_pm_write(
        db,
        "update_task_dates",
        lambda: update_task_dates_with_impact(
            db,
            pm_context,
            project_id=project_id,
            task_id=task_id,
            fecha_inicio=payload.fecha_inicio,
            fecha_fin=payload.fecha_fin,
            apply_dependents=payload.apply_dependents,
            ip_address=request.client.host if request.client else None,
        ),
    )


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


@router.get("/projects/{project_id}/documents", response_model=list[PMDocumentoOut])
def list_project_documents_endpoint(
    project_id: str,
    include_inactive: bool = False,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMDocumentoOut]:
    return list_project_documents(db, pm_context, project_id, include_inactive=include_inactive)


@router.post("/projects/{project_id}/documents", response_model=PMDocumentoOut, status_code=status.HTTP_201_CREATED)
async def upload_project_document_endpoint(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    tipo_documento: str = Form("otro"),
    nombre: str = Form(...),
    descripcion: str | None = Form(None),
    visible_externo: bool = Form(False),
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMDocumentoOut:
    try:
        document = await upload_project_document(
            db,
            pm_context,
            project_id=project_id,
            file=file,
            tipo_documento=tipo_documento,
            nombre=nombre,
            descripcion=descripcion,
            visible_externo=visible_externo,
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        return document
    except HTTPException:
        db.rollback()
        raise
    except StorageConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Conflicto de integridad en PM durante upload_project_document.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pudo completar la operacion de PM.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Error de base de datos en PM durante upload_project_document.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo completar la operacion de PM.") from exc
    finally:
        await file.close()


@router.put("/documents/{document_id}", response_model=PMDocumentoOut)
def update_project_document_endpoint(
    document_id: str,
    payload: PMDocumentoUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMDocumentoOut:
    return run_pm_write(
        db,
        "update_project_document",
        lambda: update_project_document(
            db,
            pm_context,
            document_id=document_id,
            tipo_documento=payload.tipo_documento,
            nombre=payload.nombre,
            descripcion=payload.descripcion,
            visible_externo=payload.visible_externo,
            activo=payload.activo,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/documents/{document_id}/deactivate", response_model=PMDocumentoOut)
def deactivate_project_document_endpoint(
    document_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMDocumentoOut:
    return run_pm_write(
        db,
        "deactivate_project_document",
        lambda: deactivate_project_document(
            db,
            pm_context,
            document_id=document_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/changes", response_model=list[PMCambioProyectoOut])
def list_project_changes_endpoint(
    project_id: str,
    estatus: str | None = None,
    tipo_cambio: str | None = None,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMCambioProyectoOut]:
    return list_project_changes(
        db,
        pm_context,
        project_id=project_id,
        estatus=estatus,
        tipo_cambio=tipo_cambio,
    )


@router.post("/projects/{project_id}/changes", response_model=PMCambioProyectoOut, status_code=status.HTTP_201_CREATED)
def create_project_change_endpoint(
    project_id: str,
    payload: PMCambioProyectoCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return run_pm_write(
        db,
        "create_project_change",
        lambda: create_project_change(
            db,
            pm_context,
            project_id=project_id,
            linea_base_id=payload.linea_base_id,
            tipo_cambio=payload.tipo_cambio,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            motivo=payload.motivo,
            requiere_aprobacion=payload.requiere_aprobacion,
            entidad_tipo=payload.entidad_tipo,
            entidad_id=payload.entidad_id,
            antes_json=payload.antes_json,
            despues_json=payload.despues_json,
            impacto_dias=payload.impacto_dias,
            impacto_costo=payload.impacto_costo,
            impacto_venta=payload.impacto_venta,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/changes/{change_id}", response_model=PMCambioProyectoOut)
def get_project_change_endpoint(
    change_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return get_project_change(db, pm_context, change_id=change_id)


@router.put("/changes/{change_id}", response_model=PMCambioProyectoOut)
def update_project_change_endpoint(
    change_id: str,
    payload: PMCambioProyectoUpdate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return run_pm_write(
        db,
        "update_project_change",
        lambda: update_project_change(
            db,
            pm_context,
            change_id=change_id,
            linea_base_id=payload.linea_base_id,
            tipo_cambio=payload.tipo_cambio,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            motivo=payload.motivo,
            requiere_aprobacion=payload.requiere_aprobacion,
            entidad_tipo=payload.entidad_tipo,
            entidad_id=payload.entidad_id,
            antes_json=payload.antes_json,
            despues_json=payload.despues_json,
            impacto_dias=payload.impacto_dias,
            impacto_costo=payload.impacto_costo,
            impacto_venta=payload.impacto_venta,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/changes/{change_id}/submit", response_model=PMCambioProyectoOut)
def submit_project_change_endpoint(
    change_id: str,
    payload: PMCambioProyectoSubmitRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return run_pm_write(
        db,
        "submit_project_change",
        lambda: submit_project_change(
            db,
            pm_context,
            change_id=change_id,
            comment=payload.comentario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/changes/{change_id}/approve", response_model=PMCambioProyectoOut)
def approve_project_change_endpoint(
    change_id: str,
    payload: PMAprobacionResolve,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return run_pm_write(
        db,
        "approve_project_change",
        lambda: approve_project_change(
            db,
            pm_context,
            change_id=change_id,
            comment=payload.comentario_resolucion,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/changes/{change_id}/reject", response_model=PMCambioProyectoOut)
def reject_project_change_endpoint(
    change_id: str,
    payload: PMAprobacionResolve,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return run_pm_write(
        db,
        "reject_project_change",
        lambda: reject_project_change(
            db,
            pm_context,
            change_id=change_id,
            comment=payload.comentario_resolucion,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/changes/{change_id}/cancel", response_model=PMCambioProyectoOut)
def cancel_project_change_endpoint(
    change_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return run_pm_write(
        db,
        "cancel_project_change",
        lambda: cancel_project_change(
            db,
            pm_context,
            change_id=change_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/changes/{change_id}/apply", response_model=PMCambioProyectoOut)
def apply_project_change_endpoint(
    change_id: str,
    payload: PMCambioProyectoApplyRequest,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMCambioProyectoOut:
    return run_pm_write(
        db,
        "apply_project_change",
        lambda: apply_project_change(
            db,
            pm_context,
            change_id=change_id,
            apply_dependents=payload.apply_dependents,
            comment=payload.comentario,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/approvals", response_model=list[PMAprobacionOut])
def list_project_approvals_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMAprobacionOut]:
    return list_project_approvals(db, pm_context, project_id)


@router.post("/projects/{project_id}/approvals", response_model=PMAprobacionOut, status_code=status.HTTP_201_CREATED)
def create_project_approval_endpoint(
    project_id: str,
    payload: PMAprobacionCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMAprobacionOut:
    return run_pm_write(
        db,
        "create_project_approval",
        lambda: create_project_approval(
            db,
            pm_context,
            project_id=project_id,
            tipo_aprobacion=payload.tipo_aprobacion,
            titulo=payload.titulo,
            descripcion=payload.descripcion,
            entidad_tipo=payload.entidad_tipo,
            entidad_id=payload.entidad_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/approvals/{approval_id}/approve", response_model=PMAprobacionOut)
def approve_project_approval_endpoint(
    approval_id: str,
    payload: PMAprobacionResolve,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMAprobacionOut:
    return run_pm_write(
        db,
        "approve_project_approval",
        lambda: approve_project_approval(
            db,
            pm_context,
            approval_id=approval_id,
            comment=payload.comentario_resolucion,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/approvals/{approval_id}/reject", response_model=PMAprobacionOut)
def reject_project_approval_endpoint(
    approval_id: str,
    payload: PMAprobacionResolve,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMAprobacionOut:
    return run_pm_write(
        db,
        "reject_project_approval",
        lambda: reject_project_approval(
            db,
            pm_context,
            approval_id=approval_id,
            comment=payload.comentario_resolucion,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/approvals/{approval_id}/cancel", response_model=PMAprobacionOut)
def cancel_project_approval_endpoint(
    approval_id: str,
    payload: PMAprobacionResolve,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMAprobacionOut:
    return run_pm_write(
        db,
        "cancel_project_approval",
        lambda: cancel_project_approval(
            db,
            pm_context,
            approval_id=approval_id,
            comment=payload.comentario_resolucion,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.get("/projects/{project_id}/external-invites", response_model=list[PMInvitadoExternoOut])
def list_project_external_invites_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMInvitadoExternoOut]:
    return list_project_external_invites(db, pm_context, project_id)


@router.get("/projects/{project_id}/portal-access-logs", response_model=list[PMPortalAccessLogOut])
def list_project_portal_access_logs_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> list[PMPortalAccessLogOut]:
    return list_project_portal_access_logs(db, pm_context, project_id)


@router.post("/projects/{project_id}/external-invites", response_model=PMInvitadoExternoCreatedOut, status_code=status.HTTP_201_CREATED)
def create_project_external_invite_endpoint(
    project_id: str,
    payload: PMInvitadoExternoCreate,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMInvitadoExternoCreatedOut:
    invite = run_pm_write(
        db,
        "create_project_external_invite",
        lambda: create_external_invite(
            db,
            pm_context,
            project_id=project_id,
            nombre=payload.nombre,
            email=payload.email,
            modo_acceso=payload.modo_acceso,
            expira_at=payload.expira_at,
            ip_address=request.client.host if request.client else None,
        ),
    )
    return invite.model_copy(update={"portal_url": build_portal_url(request, invite.token)})


@router.post("/external-invites/{invite_id}/revoke", response_model=PMInvitadoExternoOut)
def revoke_project_external_invite_endpoint(
    invite_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMInvitadoExternoOut:
    return run_pm_write(
        db,
        "revoke_project_external_invite",
        lambda: revoke_external_invite(
            db,
            pm_context,
            invite_id=invite_id,
            ip_address=request.client.host if request.client else None,
        ),
    )


@router.post("/external-invites/{invite_id}/regenerate", response_model=PMInvitadoExternoCreatedOut)
def regenerate_project_external_invite_endpoint(
    invite_id: str,
    request: Request,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMInvitadoExternoCreatedOut:
    invite = run_pm_write(
        db,
        "regenerate_project_external_invite",
        lambda: regenerate_external_invite(
            db,
            pm_context,
            invite_id=invite_id,
            ip_address=request.client.host if request.client else None,
        ),
    )
    return invite.model_copy(update={"portal_url": build_portal_url(request, invite.token)})


@router.get("/portal/{token}", response_model=PMPortalProjectOut)
def get_pm_portal_project_endpoint(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> PMPortalProjectOut:
    return run_pm_write(
        db,
        "pm_portal_project_access",
        lambda: get_portal_project(
            db,
            token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        ),
    )


@router.post("/portal/{token}/comments", response_model=PMPortalCommentOut, status_code=status.HTTP_201_CREATED)
def create_pm_portal_comment_endpoint(
    token: str,
    payload: PMPortalCommentCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> PMPortalCommentOut:
    return run_pm_write(
        db,
        "pm_portal_comment_create",
        lambda: create_portal_comment(
            db,
            token,
            author_name=payload.autor_nombre,
            body=payload.body,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        ),
    )
