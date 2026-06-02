import {
  AlertTriangle,
  CheckCheck,
  CircleOff,
  Eye,
  Link2,
  Lock,
  Pencil,
  Plus,
  RefreshCw,
  Route,
  Sparkles,
} from "lucide-react";

import {
  ActionButton,
  DataCard,
  EmptyState,
  MetricCard,
  StatusBadge,
  formatDate,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";
import PMProjectAlertsPanel from "./PMProjectAlertsPanel";
import PMProjectGanttLite from "./PMProjectGanttLite";
import PMTaskDetailPanel from "./PMTaskDetailPanel";
import {
  formatPercent,
  getTaskStatusLabel,
  getTaskStatusTone,
  isTaskOverdue,
  normalizePmCopy,
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

function getPlanningDetail(task) {
  const dependencyState = task?.dependency_state ?? null;
  const scheduleSuggestion = task?.schedule_suggestion ?? null;
  const badges = [];

  if (task?.es_critica) {
    badges.push(<StatusBadge key="critical" tone="danger">Crítica</StatusBadge>);
  }
  if (dependencyState?.is_blocked) {
    badges.push(
      <StatusBadge key="blocked" tone="warning">
        <Lock size={12} strokeWidth={1.9} />
        Bloqueada
      </StatusBadge>,
    );
  }
  if (scheduleSuggestion?.fuera_de_secuencia) {
    badges.push(
      <StatusBadge key="sequence" tone="warning">
        <AlertTriangle size={12} strokeWidth={1.9} />
        Fuera de secuencia
      </StatusBadge>,
    );
  }
  if (isTaskOverdue(task)) {
    badges.push(<StatusBadge key="overdue" tone="danger">Vencida</StatusBadge>);
  }

  let note = "Sin riesgos inmediatos.";
  if (dependencyState?.is_blocked && dependencyState?.detail) {
    note = dependencyState.detail;
  } else if (scheduleSuggestion?.fuera_de_secuencia && scheduleSuggestion?.razon) {
    note = scheduleSuggestion.razon;
  } else if (dependencyState?.title === "Prerrequisitos completados" && dependencyState?.detail) {
    note = `Prerrequisitos completados: ${dependencyState.detail}`;
  }

  const suggestion = scheduleSuggestion?.fecha_inicio_sugerida
    ? `Mover inicio a ${safeDisplayText(formatDate(scheduleSuggestion.fecha_inicio_sugerida), "—")}`
    : "";

  return { badges, note, suggestion };
}

function getFirstBlockerTitle(task) {
  const blockers = task?.dependency_state?.blockers ?? task?.blockers ?? [];
  return blockers.length > 0 ? safeDisplayText(blockers[0]?.titulo, "otra tarea") : "";
}

export default function PMProjectWorkPlanView({
  alerts = [],
  alertActionLoading = {},
  empresaId,
  materialConsumptions,
  materialPlans,
  onCreateTask,
  onDeactivateTask,
  onDependenciesChanged,
  onDismissAlert,
  onEditTask,
  onRefresh,
  onRecalculatePlanning,
  onResolveAlert,
  onSelectTask,
  onSetTaskStatus,
  planningCriticalPath,
  planningSummary,
  projectId,
  refreshing = false,
  planningRefreshing = false,
  selectedTaskId,
  taskActionLoading,
  taskDependencyContextMap,
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
      <ActionButton
        className={refreshing ? "pm-button-loading" : ""}
        disabled={refreshing || planningRefreshing}
        icon={<RefreshCw size={16} strokeWidth={1.9} />}
        onClick={onRefresh}
        type="button"
      >
        {refreshing ? "Actualizando..." : "Actualizar"}
      </ActionButton>
      <ActionButton
        className={planningRefreshing ? "pm-button-loading" : ""}
        disabled={refreshing || planningRefreshing}
        icon={<Sparkles size={16} strokeWidth={1.9} />}
        onClick={onRecalculatePlanning}
        type="button"
      >
        {planningRefreshing ? "Recalculando..." : "Recalcular planeación"}
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
          <div className="inventory-actions inventory-actions-wrap">{headerActions}</div>
        </div>

        <DataCard subtitle="La tabla y la línea de tiempo se activan cuando existe plan de trabajo." title="Plan de trabajo">
          <EmptyState
            action={(
              <ActionButton onClick={onCreateTask} tone="primary" type="button">
                Crear primera tarea
              </ActionButton>
            )}
            note="Agrega tareas con fechas para visualizar el plan, las dependencias y la ruta crítica."
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
        <div className="inventory-actions inventory-actions-wrap">{headerActions}</div>
      </div>

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard
          icon={<Route size={18} strokeWidth={1.9} />}
          label="Tareas críticas"
          meta="Impactan la fecha final"
          tone="danger"
          value={planningSummary?.tareas_criticas ?? 0}
        />
        <MetricCard
          icon={<Lock size={18} strokeWidth={1.9} />}
          label="Tareas bloqueadas"
          meta="Prerrequisitos pendientes"
          tone="warning"
          value={planningSummary?.tareas_bloqueadas ?? 0}
        />
        <MetricCard
          icon={<AlertTriangle size={18} strokeWidth={1.9} />}
          label="Fuera de secuencia"
          meta="Requieren ajuste de fechas"
          tone="warning"
          value={planningSummary?.tareas_fuera_de_secuencia ?? 0}
        />
        <MetricCard
          icon={<CheckCheck size={18} strokeWidth={1.9} />}
          label="Alertas activas"
          meta="Incidencias abiertas"
          tone={(planningSummary?.alertas_abiertas ?? 0) > 0 ? "danger" : "success"}
          value={planningSummary?.alertas_abiertas ?? 0}
        />
      </section>

      {planningCriticalPath?.critical_path?.length ? (
        <DataCard subtitle="Cadena principal que afecta la fecha final del proyecto." title="Ruta crítica">
          <div className="pm-critical-path-strip">
            {planningCriticalPath.critical_path.map((item) => (
              <div className="pm-critical-path-step" key={item.task_id}>
                <strong>{normalizePmCopy(safeDisplayText(item.titulo))}</strong>
                <span>
                  {item.duracion_dias} d · Holgura {item.holgura_dias ?? 0} d
                </span>
              </div>
            ))}
          </div>
        </DataCard>
      ) : null}

      <PMProjectAlertsPanel
        actionLoading={alertActionLoading}
        alerts={alerts}
        compact
        onDismiss={onDismissAlert}
        onResolve={onResolveAlert}
      />

      <div className="pm-workplan-layout">
        <DataCard
          className="pm-workplan-card"
          subtitle="Tabla operativa con planeación, bloqueo y sugerencias de fechas."
          title="Tabla de tareas"
        >
          <div className="pm-workplan-table">
            <div className="pm-workplan-row pm-workplan-row-head pm-workplan-row-phase6-head">
              <span>#</span>
              <span>Tarea</span>
              <span>Estatus</span>
              <span>Responsable</span>
              <span>Inicio</span>
              <span>Fin</span>
              <span>Duración</span>
              <span>Planeación</span>
              <span>Avance</span>
              <span>Acciones</span>
            </div>
            {tasks.map((task, index) => {
              const taskMetrics = taskTimeMetrics[task.id] ?? { horas: 0, costo: 0 };
              const selected = selectedTaskId === task.id;
              const dependencyState = taskDependencyContextMap?.[task.id] ?? task.dependency_state ?? null;
              const blocked = Boolean(dependencyState?.is_blocked ?? dependencyState?.blocked ?? task.is_blocked);
              const blockerTitle = getFirstBlockerTitle(task);
              const completing = Boolean(taskActionLoading?.[`${task.id}:complete`]);
              const starting = Boolean(taskActionLoading?.[`${task.id}:start`]);
              const deactivating = Boolean(taskActionLoading?.[`${task.id}:deactivate`]);
              const planningDetail = getPlanningDetail({ ...task, dependency_state: dependencyState });

              return (
                <div
                  className={`pm-workplan-row pm-workplan-row-phase6 ${selected ? "is-selected" : ""} ${blocked ? "is-blocked" : ""} ${task.es_critica ? "is-critical" : ""} ${completing || starting || deactivating ? "pm-card-updating" : ""}`}
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
                    <div className="inventory-cell-main">{normalizePmCopy(safeDisplayText(task.titulo))}</div>
                    <div className="inventory-cell-sub">
                      {safeDisplayText(task.descripcion, "Sin descripción")} · {formatNumber(taskMetrics.horas)} h reales · {formatMoney(taskMetrics.costo)}
                    </div>
                  </span>
                  <span>
                    <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                  </span>
                  <span>{safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")}</span>
                  <span>{safeDisplayText(formatDate(task.fecha_inicio), "—")}</span>
                  <span>{safeDisplayText(formatDate(task.fecha_vencimiento), "—")}</span>
                  <span>{getDurationLabel(task)}</span>
                  <span>
                    <div className="pm-workplan-planning-stack">
                      <div className="pm-workplan-planning-badges">{planningDetail.badges}</div>
                      <div className="pm-workplan-planning-copy">{planningDetail.note}</div>
                      {planningDetail.suggestion ? (
                        <div className="pm-workplan-suggestion-copy">Fecha sugerida: {planningDetail.suggestion.replace("Mover inicio a ", "")}</div>
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
                      {task.estatus === "pendiente" ? (
                        <ActionButton
                          className={`${blocked ? "is-soft-disabled" : ""} ${starting ? "pm-button-loading" : ""}`.trim()}
                          disabled={starting || completing || deactivating}
                          icon={<Link2 size={14} strokeWidth={1.9} />}
                          onClick={(event) => {
                            event.stopPropagation();
                            onSetTaskStatus?.(task, "en_progreso");
                          }}
                          size="sm"
                          title={blocked && blockerTitle ? `Completa primero: ${blockerTitle}.` : undefined}
                          type="button"
                        >
                          {starting ? "Actualizando..." : "Marcar en progreso"}
                        </ActionButton>
                      ) : null}
                      {task.estatus !== "completada" && task.estatus !== "cancelada" ? (
                        <ActionButton
                          className={`${blocked ? "is-soft-disabled" : ""} ${completing ? "pm-button-loading" : ""}`.trim()}
                          disabled={starting || completing || deactivating}
                          icon={<CheckCheck size={14} strokeWidth={1.9} />}
                          onClick={(event) => {
                            event.stopPropagation();
                            onSetTaskStatus?.(task, "completada");
                          }}
                          size="sm"
                          title={blocked && blockerTitle ? `Completa primero: ${blockerTitle}.` : undefined}
                          tone={blocked ? "warning" : "primary"}
                          type="button"
                        >
                          {completing ? "Completando..." : "Completar"}
                        </ActionButton>
                      ) : null}
                      <ActionButton
                        className={deactivating ? "pm-button-loading" : ""}
                        disabled={completing || starting || deactivating}
                        icon={<CircleOff size={14} strokeWidth={1.9} />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeactivateTask?.(task);
                        }}
                        size="sm"
                        tone="danger"
                        type="button"
                      >
                        {deactivating ? "Desactivando..." : "Desactivar"}
                      </ActionButton>
                    </div>
                  </span>
                </div>
              );
            })}
          </div>
        </DataCard>

        <PMProjectGanttLite criticalPath={planningCriticalPath} onSelectTask={onSelectTask} selectedTaskId={selectedTaskId} tasks={tasks} />
      </div>

      <PMTaskDetailPanel
        empresaId={empresaId}
        materialConsumptions={materialConsumptions}
        materialPlans={materialPlans}
        onDependenciesChanged={onDependenciesChanged}
        onEditTask={onEditTask}
        onSelectTask={onSelectTask}
        projectId={projectId}
        taskDependencyContext={selectedTaskId ? taskDependencyContextMap?.[selectedTaskId] ?? null : null}
        taskId={selectedTaskId}
        taskSummary={tasks.find((task) => task.id === selectedTaskId) ?? null}
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
