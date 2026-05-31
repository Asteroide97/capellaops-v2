import { CheckCheck, CircleOff, Pencil, Play } from "lucide-react";

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
  getPriorityLabel,
  getPriorityTone,
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


export default function PMProjectWorkPlanView({
  empresaId,
  materialConsumptions,
  materialPlans,
  onCreateTask,
  onDeactivateTask,
  onEditTask,
  onSelectTask,
  onSetTaskStatus,
  projectId,
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

  if ((tasks ?? []).length === 0) {
    return (
      <DataCard
        actions={
          <ActionButton onClick={onCreateTask} tone="primary" type="button">
            Nueva tarea
          </ActionButton>
        }
        subtitle="La tabla y la línea de tiempo se activan cuando existe plan de trabajo."
        title="Plan de trabajo"
      >
        <EmptyState
          action={
            <ActionButton onClick={onCreateTask} tone="primary" type="button">
              Crear primera tarea
            </ActionButton>
          }
          note="Agrega tareas con fechas para visualizar el plan tipo workspace."
          title="Sin tareas"
        />
      </DataCard>
    );
  }

  return (
    <div className="inventory-content-grid">
      <div className="pm-workspace-grid">
        <DataCard
          actions={
            <ActionButton onClick={onCreateTask} tone="primary" type="button">
              Nueva tarea
            </ActionButton>
          }
          className="pm-workplan-card"
          subtitle="Tabla operativa con responsables, fechas, horas y costo real por tarea."
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
              <span>Avance</span>
              <span>Horas estimadas</span>
              <span>Horas reales</span>
              <span>Costo real</span>
              <span>Acciones</span>
            </div>
            {tasks.map((task, index) => {
              const taskMetrics = taskTimeMetrics[task.id] ?? { horas: 0, costo: 0 };
              const selected = selectedTaskId === task.id;
              return (
                <div
                  className={`pm-workplan-row ${selected ? "is-selected" : ""}`}
                  key={task.id}
                  onClick={() => onSelectTask?.(task.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectTask?.(task.id);
                    }
                  }}
                >
                  <span>{task.orden > 0 ? task.orden : index + 1}</span>
                  <span>
                    <div className="inventory-cell-main">{safeDisplayText(task.titulo)}</div>
                    <div className="inventory-cell-sub">
                      {safeDisplayText(task.descripcion, "Sin descripción")}
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
                  <span>{formatPercent(task.porcentaje_avance)}</span>
                  <span>{formatNumber(task.estimacion_horas ?? 0)}</span>
                  <span>{formatNumber(taskMetrics.horas)}</span>
                  <span>{formatMoney(taskMetrics.costo)}</span>
                  <span>
                    <div className="table-actions">
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
                      {task.estatus !== "en_progreso" && task.estatus !== "completada" && task.estatus !== "cancelada" ? (
                        <ActionButton
                          icon={<Play size={14} strokeWidth={1.9} />}
                          onClick={(event) => {
                            event.stopPropagation();
                            onSetTaskStatus?.(task, "en_progreso");
                          }}
                          size="sm"
                          type="button"
                        >
                          En progreso
                        </ActionButton>
                      ) : null}
                      {task.estatus !== "completada" && task.estatus !== "cancelada" ? (
                        <ActionButton
                          icon={<CheckCheck size={14} strokeWidth={1.9} />}
                          onClick={(event) => {
                            event.stopPropagation();
                            onSetTaskStatus?.(task, "completada");
                          }}
                          size="sm"
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
        onEditTask={onEditTask}
        projectId={projectId}
        taskId={selectedTaskId}
        timeEntries={timeEntries}
        token={token}
      />
    </div>
  );
}
