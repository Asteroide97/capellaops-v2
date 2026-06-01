import { CheckCheck, CircleOff, Eye, Link2, Lock, Pencil, Plus, RefreshCw } from "lucide-react";

import {
  ActionButton,
  DataCard,
  EmptyState,
  StatusBadge,
  formatDate,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";
import PMProjectGanttLite from "./PMProjectGanttLite";
import PMTaskDetailPanel from "./PMTaskDetailPanel";
import {
  formatPercent,
  getTaskStatusLabel,
  getTaskStatusTone,
  isTaskOverdue,
} from "./shared";


function diffInDays(startValue, endValue) {
  const start = new Date(startValue);
  const end = new Date(endValue);
  start.setHours(0, 0, 0, 0);
  end.setHours(0, 0, 0, 0);
  return Math.round((end - start) / (1000 * 60 * 60 * 24));
}


function getDurationLabel(task) {
  const startValue = task?.fecha_inicio || task?.fecha_vencimiento;
  const endValue = task?.fecha_vencimiento || task?.fecha_inicio;
  if (!startValue || !endValue) {
    return "Sin fechas";
  }
  const duration = Math.abs(diffInDays(startValue, endValue)) + 1;
  return `${formatNumber(duration)} d`;
}


function getDependencyLabel(task) {
  const blockers = task?.blockers ?? [];
  if (blockers.length > 0) {
    const firstTitle = safeDisplayText(blockers[0]?.titulo, "otra tarea");
    if (blockers.length === 1) {
      return `Depende de ${firstTitle}`;
    }
    return `Depende de ${firstTitle} y ${blockers.length - 1} más`;
  }

  if (task?.dependencies_count > 0) {
    return `${formatNumber(task.dependencies_count)} prerrequisitos`;
  }

  return "—";
}


function getFirstBlockerTitle(task) {
  const blockers = task?.blockers ?? [];
  return blockers.length > 0 ? safeDisplayText(blockers[0]?.titulo, "otra tarea") : "";
}


export default function PMProjectWorkPlanView({
  empresaId,
  materialConsumptions,
  materialPlans,
  onCreateTask,
  onDeactivateTask,
  onDependenciesChanged,
  onEditTask,
  onRefresh,
  onSelectTask,
  onSetTaskStatus,
  projectId,
  refreshing = false,
  selectedTaskId,
  tasks,
  timeEntries,
  token,
}) {
  const taskTimeMetrics = (timeEntries ?? []).reduce((accumulator, entry) => {
    if (!entry.tarea_id) {
      return accumulator;
    }
    const current = accumulator[entry.tarea_id] ?? { horas: 0, costo: 0 };
    current.horas += Number(entry.horas || 0);
    current.costo += Number(entry.costo_total_snapshot || 0);
    accumulator[entry.tarea_id] = current;
    return accumulator;
  }, {});

  const headerActions = (
    <>
      <ActionButton icon={<RefreshCw size={16} strokeWidth={1.9} />} onClick={onRefresh} type="button">
        {refreshing ? "Actualizando..." : "Actualizar"}
      </ActionButton>
      <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={onCreateTask} tone="primary" type="button">
        Nueva tarea
      </ActionButton>
    </>
  );

  if ((tasks ?? []).length === 0) {
    return (
      <section className="pm-workplan-stack">
        <div className="pm-workplan-toolbar">
          <div className="pm-workplan-toolbar-copy">
            <strong>Plan de trabajo</strong>
            <span>Tareas, fechas, responsables y prerrequisitos.</span>
          </div>
          <div className="inventory-actions inventory-actions-wrap">
            {headerActions}
          </div>
        </div>

        <DataCard subtitle="La tabla y la línea de tiempo se activan cuando existe plan de trabajo." title="Plan de trabajo">
          <EmptyState
            action={(
              <ActionButton onClick={onCreateTask} tone="primary" type="button">
                Crear primera tarea
              </ActionButton>
            )}
            note="Agrega tareas con fechas para visualizar el plan de trabajo y sus prerrequisitos."
            title="Sin tareas"
          />
        </DataCard>

        <ActionButton className="pm-workplan-fab" icon={<Plus size={18} strokeWidth={2} />} onClick={onCreateTask} tone="primary" type="button">
          + Tarea
        </ActionButton>
      </section>
    );
  }

  return (
    <section className="pm-workplan-stack">
      <div className="pm-workplan-toolbar">
        <div className="pm-workplan-toolbar-copy">
          <strong>Plan de trabajo</strong>
          <span>Tareas, fechas, responsables y prerrequisitos.</span>
        </div>
        <div className="inventory-actions inventory-actions-wrap">
          {headerActions}
        </div>
      </div>

      <div className="pm-workplan-layout">
        <DataCard
          className="pm-workplan-card"
          subtitle="Tabla operativa con tareas, fechas, responsables y bloqueo por prerrequisitos."
          title="Tabla de tareas"
        >
          <div className="pm-workplan-table">
            <div className="pm-workplan-row pm-workplan-row-head">
              <span>#</span>
              <span>Tarea</span>
              <span>Estatus</span>
              <span>Responsable</span>
              <span>Inicio</span>
              <span>Fin</span>
              <span>Duración</span>
              <span>Prerrequisitos</span>
              <span>Avance</span>
              <span>Acciones</span>
            </div>
            {tasks.map((task, index) => {
              const taskMetrics = taskTimeMetrics[task.id] ?? { horas: 0, costo: 0 };
              const selected = selectedTaskId === task.id;
              const blocked = Boolean(task.is_blocked);
              const blockerTitle = getFirstBlockerTitle(task);
              return (
                <div
                  className={`pm-workplan-row ${selected ? "is-selected" : ""} ${blocked ? "is-blocked" : ""}`}
                  key={task.id}
                  onClick={() => onSelectTask?.(task.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectTask?.(task.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <span>{task.orden > 0 ? task.orden : index + 1}</span>
                  <span>
                    <div className="inventory-cell-main">{safeDisplayText(task.titulo)}</div>
                    <div className="inventory-cell-sub">
                      {safeDisplayText(task.descripcion, "Sin descripción")} · {formatNumber(taskMetrics.horas)} h reales · {formatMoney(taskMetrics.costo)}
                    </div>
                  </span>
                  <span>
                    <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                  </span>
                  <span>{safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")}</span>
                  <span>{safeDisplayText(formatDate(task.fecha_inicio), "—")}</span>
                  <span>
                    <div>{safeDisplayText(formatDate(task.fecha_vencimiento), "—")}</div>
                    {isTaskOverdue(task) ? <div className="inventory-cell-sub">Vencida</div> : null}
                  </span>
                  <span>{getDurationLabel(task)}</span>
                  <span>
                    <div className="pm-workplan-dependency-stack">
                      <div className="pm-workplan-dependency-copy">
                        {task.dependencies_count > 0 ? <Link2 size={12} strokeWidth={1.9} /> : null}
                        <span>{getDependencyLabel(task)}</span>
                      </div>
                      {blocked ? (
                        <StatusBadge tone="warning">
                          <Lock size={12} strokeWidth={1.9} />
                          Bloqueada
                        </StatusBadge>
                      ) : null}
                    </div>
                  </span>
                  <span>{formatPercent(task.porcentaje_avance)}</span>
                  <span>
                    <div className="table-actions">
                      <ActionButton
                        icon={<Eye size={14} strokeWidth={1.9} />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelectTask?.(task.id);
                        }}
                        size="sm"
                        type="button"
                      >
                        Ver
                      </ActionButton>
                      <ActionButton
                        icon={<Pencil size={14} strokeWidth={1.9} />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onEditTask?.(task.id);
                        }}
                        size="sm"
                        type="button"
                      >
                        Editar
                      </ActionButton>
                      {task.estatus !== "completada" && task.estatus !== "cancelada" ? (
                        <ActionButton
                          disabled={blocked}
                          icon={<CheckCheck size={14} strokeWidth={1.9} />}
                          onClick={(event) => {
                            event.stopPropagation();
                            onSetTaskStatus?.(task, "completada");
                          }}
                          size="sm"
                          title={blocked && blockerTitle ? `Completa primero: ${blockerTitle}.` : undefined}
                          tone="primary"
                          type="button"
                        >
                          Completar
                        </ActionButton>
                      ) : null}
                      <ActionButton
                        icon={<CircleOff size={14} strokeWidth={1.9} />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeactivateTask?.(task);
                        }}
                        size="sm"
                        tone="danger"
                        type="button"
                      >
                        Desactivar
                      </ActionButton>
                    </div>
                  </span>
                </div>
              );
            })}
          </div>
        </DataCard>

        <PMProjectGanttLite onSelectTask={onSelectTask} selectedTaskId={selectedTaskId} tasks={tasks} />
      </div>

      <PMTaskDetailPanel
        empresaId={empresaId}
        materialConsumptions={materialConsumptions}
        materialPlans={materialPlans}
        onDependenciesChanged={onDependenciesChanged}
        onEditTask={onEditTask}
        onSelectTask={onSelectTask}
        projectId={projectId}
        taskId={selectedTaskId}
        tasks={tasks}
        timeEntries={timeEntries}
        token={token}
      />

      <ActionButton className="pm-workplan-fab" icon={<Plus size={18} strokeWidth={2} />} onClick={onCreateTask} tone="primary" type="button">
        + Tarea
      </ActionButton>
    </section>
  );
}
