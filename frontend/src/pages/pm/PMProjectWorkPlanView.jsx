import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CalendarRange,
  CheckCheck,
  ChevronDown,
  ChevronUp,
  Eye,
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
  formatWorkCalendarSummary,
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
  return `${formatNumber(Math.abs(diffInDays(startValue, endValue)) + 1)} d`;
}

function getPlanningDetail(task) {
  const dependencyState = task?.dependency_state ?? null;
  const scheduleSuggestion = task?.schedule_suggestion ?? null;
  const badges = [];

  if (task?.es_critica) {
    badges.push(
      <StatusBadge key="critical" tone="danger">
        En ruta crítica
      </StatusBadge>,
    );
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
    badges.push(
      <StatusBadge key="overdue" tone="danger">
        Vencida
      </StatusBadge>,
    );
  }

  let note = "Sin riesgos inmediatos.";
  if (dependencyState?.is_blocked && dependencyState?.detail) {
    note = dependencyState.detail;
  } else if (scheduleSuggestion?.fuera_de_secuencia && scheduleSuggestion?.razon) {
    note = scheduleSuggestion.razon;
  } else if (dependencyState?.title === "Prerrequisitos completados" && dependencyState?.detail) {
    note = `Prerrequisitos completados: ${dependencyState.detail}`;
  }

  return { badges, note };
}

function isTaskActionPending(taskActionLoading, taskId, action) {
  return Boolean(taskActionLoading?.[`${taskId}:${action}`]);
}

function readStoredExpandedState(storageKey, fallback) {
  if (typeof window === "undefined" || !storageKey) {
    return fallback;
  }
  const stored = window.localStorage.getItem(storageKey);
  if (stored === null) {
    return fallback;
  }
  return stored === "1";
}

function useStoredExpandedState(storageKey, fallback) {
  const [isOpen, setIsOpen] = useState(() => readStoredExpandedState(storageKey, fallback));

  useEffect(() => {
    if (typeof window === "undefined" || !storageKey) {
      return;
    }
    window.localStorage.setItem(storageKey, isOpen ? "1" : "0");
  }, [isOpen, storageKey]);

  return [isOpen, setIsOpen];
}

function formatCountLabel(count, singular, plural, emptyLabel) {
  if (!count) {
    return emptyLabel;
  }
  return `${formatNumber(count)} ${count === 1 ? singular : plural}`;
}

function CollapsibleSection({
  children,
  className = "",
  collapsedContent = null,
  countLabel = "",
  defaultOpen = true,
  isOpen: controlledOpen,
  onToggle,
  rightActions = null,
  storageKey,
  subtitle,
  title,
}) {
  const [storedOpen, setStoredOpen] = useStoredExpandedState(storageKey, defaultOpen);
  const isControlled = typeof controlledOpen === "boolean";
  const isOpen = isControlled ? controlledOpen : storedOpen;

  function handleToggle() {
    if (isControlled) {
      onToggle?.(!isOpen);
      return;
    }
    setStoredOpen((current) => !current);
  }

  return (
    <DataCard
      className={`pm-collapsible-section ${isOpen ? "" : "pm-collapsible-collapsed"} ${className}`.trim()}
      subtitle={subtitle}
      title={title}
      actions={(
        <div className="pm-collapsible-actions">
          {countLabel ? <span className="pm-section-count-badge">{countLabel}</span> : null}
          {rightActions}
          <ActionButton
            className="pm-collapsible-toggle"
            icon={isOpen ? <ChevronUp size={16} strokeWidth={1.9} /> : <ChevronDown size={16} strokeWidth={1.9} />}
            onClick={handleToggle}
            type="button"
          >
            {isOpen ? "Minimizar" : "Expandir"}
          </ActionButton>
        </div>
      )}
    >
      {isOpen ? (
        <div className="pm-collapsible-body">{children}</div>
      ) : collapsedContent ? (
        <div className="pm-collapsible-body">{collapsedContent}</div>
      ) : null}
    </DataCard>
  );
}

export default function PMProjectWorkPlanView({
  alerts = [],
  alertActionLoading = {},
  baselineComparison = null,
  empresaId,
  materialConsumptions,
  materialPlans,
  onApplyAllSuggestions,
  onApplySuggestedDates,
  onConfigureCalendar,
  onCreateTask,
  onDependenciesChanged,
  onDismissAlert,
  onEditTask,
  onEditTaskDates,
  onRefresh,
  onRecalculatePlanning,
  onResolveAlert,
  onSelectTask,
  planningCriticalPath,
  planningSummary,
  projectId,
  refreshing = false,
  planningRefreshing = false,
  selectedTaskId,
  taskActionLoading,
  taskDependencyContextMap,
  tasks = [],
  timeEntries,
  token,
  workCalendar,
}) {
  const detailSectionRef = useRef(null);
  const [isDetailExpanded, setIsDetailExpanded] = useStoredExpandedState(`pm.workplan.detail.expanded.${projectId}`, false);

  const taskTimeMetrics = useMemo(
    () =>
      (timeEntries ?? []).reduce((accumulator, entry) => {
        if (!entry.tarea_id) {
          return accumulator;
        }
        const current = accumulator[entry.tarea_id] ?? { horas: 0, costo: 0 };
        current.horas += Number(entry.horas || 0);
        current.costo += Number(entry.costo_total_snapshot || 0);
        accumulator[entry.tarea_id] = current;
        return accumulator;
      }, {}),
    [timeEntries],
  );

  const outOfSequenceTasks = useMemo(
    () => tasks.filter((task) => task?.schedule_suggestion?.fuera_de_secuencia),
    [tasks],
  );

  const baselineTaskComparisonMap = useMemo(
    () =>
      (baselineComparison?.task_changes ?? []).reduce((accumulator, item) => {
        if (item?.task_id) {
          accumulator[item.task_id] = item;
        }
        return accumulator;
      }, {}),
    [baselineComparison],
  );

  const hasBaselineComparison = Boolean(baselineComparison?.baseline?.id);
  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [tasks, selectedTaskId],
  );

  function openTaskDetail(taskId) {
    onSelectTask?.(taskId);
    setIsDetailExpanded(true);
    if (typeof window !== "undefined") {
      window.setTimeout(() => {
        detailSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 80);
    }
  }

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

  if (tasks.length === 0) {
    return (
      <section className="pm-workplan-stack">
        <div className="pm-workplan-toolbar">
          <div className="pm-workplan-toolbar-copy">
            <strong>Plan de trabajo</strong>
            <span>Tareas, fechas, responsables y prerrequisitos.</span>
          </div>
          <div className="inventory-actions inventory-actions-wrap">{headerActions}</div>
        </div>

        <DataCard subtitle="La tabla y el cronograma se activan cuando existe plan de trabajo." title="Plan de trabajo">
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

  const alertsCountLabel = alerts.length > 0 ? formatCountLabel(alerts.length, "alerta", "alertas", "Sin alertas") : "Sin alertas";
  const tasksCountLabel = formatCountLabel(tasks.length, "tarea", "tareas", "Sin tareas");

  const detailCollapsedContent = !selectedTask ? (
    <EmptyState compact note="Selecciona una tarea para ver su detalle." title="Sin tarea seleccionada" />
  ) : (
    <div className="pm-task-detail-collapsed">
      <div className="pm-task-detail-collapsed-head">
        <strong>{normalizePmCopy(safeDisplayText(selectedTask.titulo, "Tarea seleccionada"))}</strong>
        <StatusBadge tone={getTaskStatusTone(selectedTask.estatus)}>{getTaskStatusLabel(selectedTask.estatus)}</StatusBadge>
      </div>
      <div className="pm-task-detail-collapsed-summary">
        <div>
          <span>Tarea seleccionada</span>
          <strong>{normalizePmCopy(safeDisplayText(selectedTask.titulo))}</strong>
        </div>
        <div>
          <span>Inicio</span>
          <strong>{safeDisplayText(formatDate(selectedTask.fecha_inicio), "—")}</strong>
        </div>
        <div>
          <span>Fin</span>
          <strong>{safeDisplayText(formatDate(selectedTask.fecha_vencimiento), "—")}</strong>
        </div>
        <div>
          <span>Avance</span>
          <strong>{formatPercent(selectedTask.porcentaje_avance)}</strong>
        </div>
      </div>
    </div>
  );

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
          label="En ruta crítica"
          meta="Afectan la fecha final"
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

      {hasBaselineComparison ? (
        <div className="inventory-form-note">
          <strong>Comparado con línea base</strong>
          <p className="table-note">
            El plan actual se compara contra {safeDisplayText(baselineComparison?.baseline?.nombre, "la línea base principal")} para detectar desviaciones.
          </p>
        </div>
      ) : null}

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard
          actions={(
            <ActionButton icon={<CalendarRange size={16} strokeWidth={1.9} />} onClick={onConfigureCalendar} type="button">
              Configurar calendario
            </ActionButton>
          )}
          subtitle="Días laborales que usa la planeación para sugerir fechas."
          title="Calendario laboral"
        >
          <div className="inventory-form-note">
            <strong>{safeDisplayText(workCalendar?.nombre, "Calendario estándar")}</strong>
            <p className="table-note">{formatWorkCalendarSummary(workCalendar)}</p>
            <p className="table-note">Usa Editar fechas o Aplicar sugerencia para reprogramar tareas con confirmación guiada.</p>
          </div>
        </DataCard>

        <DataCard
          actions={outOfSequenceTasks.length > 0 ? (
            <ActionButton onClick={onApplyAllSuggestions} tone="primary" type="button">
              Aplicar sugerencias
            </ActionButton>
          ) : null}
          subtitle="Tareas que inician antes de completar sus prerrequisitos."
          title="Ajustes sugeridos"
        >
          {outOfSequenceTasks.length > 0 ? (
            <div className="inventory-form-note inventory-form-note-warning">
              <strong>Hay {outOfSequenceTasks.length} tareas con fechas fuera de secuencia.</strong>
              <p className="table-note">Aplica las fechas sugeridas o edita manualmente las tareas afectadas.</p>
            </div>
          ) : (
            <EmptyState compact note="La secuencia del proyecto está alineada con sus prerrequisitos." title="Sin conflictos" />
          )}
        </DataCard>
      </div>

      {planningCriticalPath?.critical_path?.length ? (
        <DataCard subtitle="Cadena principal que afecta la fecha final del proyecto." title="Ruta crítica">
          <div className="pm-critical-path-strip">
            {planningCriticalPath.critical_path.map((item) => (
              <div className="pm-critical-path-step" key={item.task_id}>
                <strong>{normalizePmCopy(safeDisplayText(item.titulo))}</strong>
                <span>{item.duracion_dias} d · Holgura {item.holgura_dias ?? 0} d</span>
              </div>
            ))}
          </div>
        </DataCard>
      ) : null}

      <div className="pm-workplan-layout-vertical">
        <CollapsibleSection
          countLabel={alertsCountLabel}
          defaultOpen={alerts.length > 0}
          storageKey={`pm.workplan.alerts.expanded.${projectId}`}
          subtitle="Señales operativas del proyecto deduplicadas por tipo y tarea."
          title="Alertas activas"
        >
          <PMProjectAlertsPanel
            actionLoading={alertActionLoading}
            alerts={alerts}
            compact
            embedded
            onDismiss={onDismissAlert}
            onResolve={onResolveAlert}
          />
        </CollapsibleSection>

        <CollapsibleSection
          countLabel={tasksCountLabel}
          defaultOpen
          storageKey={`pm.workplan.timeline.expanded.${projectId}`}
          subtitle="Consulta fechas, dependencias, ruta crítica y sugerencias de reprogramación."
          title="Cronograma del proyecto"
        >
          <PMProjectGanttLite
            embedded
            onApplySuggestedDates={onApplySuggestedDates}
            onEditTaskDates={onEditTaskDates}
            onSelectTask={onSelectTask}
            onViewTaskDetail={openTaskDetail}
            selectedTaskId={selectedTaskId}
            taskActionLoading={taskActionLoading}
            tasks={tasks}
          />
        </CollapsibleSection>

        <CollapsibleSection
          className="pm-task-table-compact"
          countLabel={tasksCountLabel}
          defaultOpen
          storageKey={`pm.workplan.table.expanded.${projectId}`}
          subtitle="Resumen operativo del plan. Abre una tarea para ver su detalle."
          title="Tabla de tareas"
        >
          <div className="pm-workplan-table">
            <div className="pm-workplan-row pm-workplan-row-head pm-workplan-row-compact-head">
              <span>Tarea</span>
              <span>Estado</span>
              <span>Inicio</span>
              <span>Fin</span>
              <span>Sugerido / alerta</span>
              <span>Acciones</span>
            </div>

            {tasks.map((task) => {
              const taskMetrics = taskTimeMetrics[task.id] ?? { horas: 0, costo: 0 };
              const baselineTaskComparison = baselineTaskComparisonMap[task.id] ?? null;
              const selected = selectedTaskId === task.id;
              const dependencyState = taskDependencyContextMap?.[task.id] ?? task.dependency_state ?? null;
              const blocked = Boolean(dependencyState?.is_blocked ?? dependencyState?.blocked ?? task.is_blocked);
              const planningDetail = getPlanningDetail({ ...task, dependency_state: dependencyState });
              const editingDates = isTaskActionPending(taskActionLoading, task.id, "dates");
              const suggestionCopy = task?.schedule_suggestion?.fecha_inicio_sugerida
                ? `${safeDisplayText(formatDate(task.schedule_suggestion.fecha_inicio_sugerida), "—")} → ${safeDisplayText(formatDate(task.schedule_suggestion.fecha_fin_sugerida), "—")}`
                : "—";
              const deviationCopy =
                baselineTaskComparison?.has_change && Number(baselineTaskComparison?.desviacion_dias_fin ?? 0) !== 0
                  ? `Fin actual ${baselineTaskComparison.desviacion_dias_fin > 0 ? "+" : ""}${formatNumber(baselineTaskComparison.desviacion_dias_fin)} días vs línea base`
                  : "";

              return (
                <div
                  className={`pm-workplan-row pm-workplan-row-compact ${selected ? "is-selected" : ""} ${blocked ? "is-blocked" : ""} ${task.es_critica ? "is-critical" : ""}`}
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
                  <div className="pm-task-table-cell is-primary" data-label="Tarea">
                    <div className="inventory-cell-main">{normalizePmCopy(safeDisplayText(task.titulo))}</div>
                    <div className="pm-task-row-secondary">
                      {safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")} · {getDurationLabel(task)} · {formatNumber(taskMetrics.horas)} h reales · {formatMoney(taskMetrics.costo)}
                    </div>
                  </div>

                  <div className="pm-task-table-cell" data-label="Estado">
                    <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                  </div>

                  <div className="pm-task-table-cell" data-label="Inicio">
                    {safeDisplayText(formatDate(task.fecha_inicio), "—")}
                  </div>

                  <div className="pm-task-table-cell" data-label="Fin">
                    {safeDisplayText(formatDate(task.fecha_vencimiento), "—")}
                  </div>

                  <div className="pm-task-table-cell" data-label="Sugerido / alerta">
                    <div className="pm-workplan-planning-stack">
                      <div className="pm-workplan-planning-badges">
                        {planningDetail.badges}
                        {baselineTaskComparison?.has_change ? <StatusBadge tone="warning">Desviada</StatusBadge> : null}
                      </div>
                      <div className="pm-workplan-planning-copy">
                        {task?.schedule_suggestion?.fuera_de_secuencia ? suggestionCopy : planningDetail.note}
                      </div>
                      {task?.schedule_suggestion?.fuera_de_secuencia && task.schedule_suggestion?.razon ? (
                        <div className="pm-workplan-planning-copy">{safeDisplayText(task.schedule_suggestion.razon)}</div>
                      ) : null}
                      {deviationCopy ? <div className="pm-workplan-planning-copy">{deviationCopy}</div> : null}
                    </div>
                  </div>

                  <div className="pm-task-table-cell" data-label="Acciones">
                    <div className="pm-task-table-actions">
                      <ActionButton
                        icon={<Eye size={14} strokeWidth={1.9} />}
                        onClick={(event) => {
                          event.stopPropagation();
                          openTaskDetail(task.id);
                        }}
                        size="sm"
                        type="button"
                      >
                        Ver detalle
                      </ActionButton>
                      <ActionButton
                        className={editingDates ? "pm-button-loading" : ""}
                        disabled={editingDates}
                        icon={<Pencil size={14} strokeWidth={1.9} />}
                        onClick={(event) => {
                          event.stopPropagation();
                          onEditTaskDates?.(task.id);
                        }}
                        size="sm"
                        type="button"
                      >
                        {editingDates ? "Guardando..." : "Editar fechas"}
                      </ActionButton>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CollapsibleSection>

        <div className="pm-task-detail-shell" ref={detailSectionRef}>
          <CollapsibleSection
            collapsedContent={detailCollapsedContent}
            countLabel={selectedTask ? normalizePmCopy(safeDisplayText(selectedTask.titulo)) : "Sin tarea"}
            defaultOpen={false}
            isOpen={isDetailExpanded}
            onToggle={setIsDetailExpanded}
            rightActions={selectedTask ? (
              <>
                <ActionButton onClick={() => onEditTask?.(selectedTask.id)} size="sm" type="button">
                  Editar tarea
                </ActionButton>
                <ActionButton onClick={() => onEditTaskDates?.(selectedTask.id)} size="sm" type="button">
                  Editar fechas
                </ActionButton>
              </>
            ) : null}
            storageKey={`pm.workplan.detail.expanded.${projectId}`}
            subtitle="Información completa de la tarea seleccionada."
            title="Detalle de tarea"
          >
            {!selectedTask ? (
              <EmptyState compact note="Selecciona una tarea para ver su detalle." title="Sin tarea seleccionada" />
            ) : (
              <PMTaskDetailPanel
                baselineTaskComparison={selectedTaskId ? baselineTaskComparisonMap?.[selectedTaskId] ?? null : null}
                embedded
                empresaId={empresaId}
                isExpanded={isDetailExpanded}
                materialConsumptions={materialConsumptions}
                materialPlans={materialPlans}
                onApplySuggestedDates={onApplySuggestedDates}
                onDependenciesChanged={onDependenciesChanged}
                onEditTask={onEditTask}
                onEditTaskDates={onEditTaskDates}
                onSelectTask={onSelectTask}
                onToggleExpanded={() => setIsDetailExpanded(false)}
                projectId={projectId}
                taskActionLoading={taskActionLoading}
                taskDependencyContext={selectedTaskId ? taskDependencyContextMap?.[selectedTaskId] ?? null : null}
                taskId={selectedTaskId}
                taskSummary={selectedTask}
                tasks={tasks}
                timeEntries={timeEntries}
                token={token}
              />
            )}
          </CollapsibleSection>
        </div>
      </div>

      <ActionButton className="pm-workplan-fab" icon={<Plus size={18} strokeWidth={2} />} onClick={onCreateTask} tone="primary" type="button">
        + Tarea
      </ActionButton>
    </section>
  );
}
