import logging
from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_tenant_context
from app.db.session import get_db
from app.schemas.pm import (
    PMChecklistItemCreate,
    PMChecklistItemOut,
    PMChecklistItemUpdate,
    PMCommentOut,
    PMComentarioCreate,
    PMConfigOut,
    PMDashboardOut,
    PMProjectMembersListResponse,
    PMProjectCostsOut,
    PMCreateProjectRequisitionRequest,
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
    PMSubtareaCreate,
    PMSubtareaOut,
    PMSubtareaUpdate,
    PMTareaCreate,
    PMTareaListResponse,
    PMTareaOut,
    PMTareaUpdate,
)
from app.services.pm import (
    PMContext,
    add_project_member,
    add_project_material_plan,
    create_project_material_requisition,
    create_checklist_item,
    create_project,
    create_project_comment,
    create_subtask,
    create_task,
    create_task_comment,
    deactivate_project,
    deactivate_project_material_plan,
    deactivate_project_member,
    deactivate_task,
    get_pm_context,
    get_pm_dashboard,
    get_project,
    get_project_costs,
    get_task,
    list_project_material_plan,
    list_project_members,
    list_projects,
    list_tasks,
    serialize_pm_config,
    update_checklist_item,
    update_project,
    update_project_material_plan,
    update_subtask,
    update_task,
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


@router.get("/projects/{project_id}/costs", response_model=PMProjectCostsOut)
def get_project_costs_endpoint(
    project_id: str,
    pm_context: PMContext = Depends(get_pm_route_context),
    db: Session = Depends(get_db),
) -> PMProjectCostsOut:
    return get_project_costs(db, pm_context, project_id)


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
