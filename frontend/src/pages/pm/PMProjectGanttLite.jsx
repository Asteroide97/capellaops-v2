import {
  AlertTriangle,
  CalendarRange,
  Link2,
  Lock,
  Pencil,
  Route,
  Sparkles,
} from "lucide-react";

import {
  ActionButton,
  DataCard,
  EmptyState,
  StatusBadge,
  formatDate,
  safeDisplayText,
} from "../inventory/shared";
import {
  formatPercent,
  getTaskStatusLabel,
  getTaskStatusTone,
  normalizePmCopy,
} from "./shared";

function startOfDay(value) {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
}

function addDays(value, days) {
  const date = new Date(value);
  date.setDate(date.getDate() + days);
  return date;
}

function startOfWeek(value) {
  const date = startOfDay(value);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return addDays(date, diff);
}

function endOfWeek(value) {
  return addDays(startOfWeek(value), 6);
}

function diffInDays(start, end) {
  const millisecondsPerDay = 1000 * 60 * 60 * 24;
  return Math.round((startOfDay(end) - startOfDay(start)) / millisecondsPerDay);
}

function getTaskDateRange(task) {
  const startValue = task?.fecha_inicio || task?.schedule_suggestion?.fecha_inicio_sugerida || task?.fecha_vencimiento;
  const endValue = task?.fecha_vencimiento || task?.schedule_suggestion?.fecha_fin_sugerida || task?.fecha_inicio;
  if (!startValue || !endValue) {
    return null;
  }
  const start = startOfDay(startValue);
  const end = startOfDay(endValue);
  return start <= end ? { start, end } : { start: end, end: start };
}

function buildTimeline(tasks) {
  const datedRanges = tasks.map(getTaskDateRange).filter(Boolean);
  if (datedRanges.length === 0) {
    return null;
  }

  const minDate = datedRanges.reduce((current, range) => (range.start < current ? range.start : current), datedRanges[0].start);
  const maxDate = datedRanges.reduce((current, range) => (range.end > current ? range.end : current), datedRanges[0].end);
  const totalDays = Math.max(1, diffInDays(minDate, maxDate) + 1);
  const scale = totalDays <= 42 ? "days" : "weeks";

  if (scale === "days") {
    const markers = Array.from({ length: totalDays }, (_, index) => {
      const currentDate = addDays(minDate, index);
      return {
        key: currentDate.toISOString(),
        label: new Intl.DateTimeFormat("es-MX", { day: "2-digit" }).format(currentDate),
        meta: new Intl.DateTimeFormat("es-MX", { month: "short" }).format(currentDate),
      };
    });
    return { scale, markers, start: minDate, end: maxDate, totalDays };
  }

  const weekStart = startOfWeek(minDate);
  const weekEnd = endOfWeek(maxDate);
  const weekCount = Math.max(1, Math.ceil((diffInDays(weekStart, weekEnd) + 1) / 7));
  const markers = Array.from({ length: weekCount }, (_, index) => {
    const start = addDays(weekStart, index * 7);
    const end = addDays(start, 6);
    return {
      key: `${start.toISOString()}-${end.toISOString()}`,
      label: `${new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short" }).format(start)} · ${new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short" }).format(end)}`,
    };
  });
  return { scale, markers, start: weekStart, end: weekEnd, totalDays: diffInDays(weekStart, weekEnd) + 1 };
}

function buildBarStyle(task, timeline) {
  const range = getTaskDateRange(task);
  if (!range || !timeline) {
    return null;
  }
  const leftDays = diffInDays(timeline.start, range.start);
  const widthDays = diffInDays(range.start, range.end) + 1;
  return {
    left: `${(leftDays / timeline.totalDays) * 100}%`,
    width: `${Math.max((widthDays / timeline.totalDays) * 100, 2)}%`,
  };
}

function getProgressWidth(task) {
  const rawValue = Number(task?.porcentaje_avance ?? 0);
  if (Number.isNaN(rawValue)) {
    return 0;
  }
  return Math.min(100, Math.max(0, rawValue));
}

function getDependencyCopy(task) {
  const dependencyState = task?.dependency_state;
  if (dependencyState?.is_blocked && dependencyState?.detail) {
    return dependencyState.detail;
  }
  if (dependencyState?.title === "Prerrequisitos completados" && dependencyState?.detail) {
    return `Prerrequisitos completados: ${dependencyState.detail}`;
  }
  return "";
}

function getSuggestedCopy(task) {
  if (!task?.schedule_suggestion?.fuera_de_secuencia) {
    return "";
  }
  const suggestedStart = task.schedule_suggestion.fecha_inicio_sugerida;
  const suggestedEnd = task.schedule_suggestion.fecha_fin_sugerida;
  if (!suggestedStart && !suggestedEnd) {
    return "Sugerencia pendiente";
  }
  return `Sugerido: ${safeDisplayText(formatDate(suggestedStart), "—")} → ${safeDisplayText(formatDate(suggestedEnd), "—")}`;
}

function getTaskDateCopy(task) {
  const startLabel = formatDate(task?.fecha_inicio);
  const endLabel = formatDate(task?.fecha_vencimiento);
  if (startLabel && endLabel) {
    return `${startLabel} → ${endLabel}`;
  }
  return startLabel || endLabel || "Sin fechas";
}

function getGanttBarClass(task) {
  if (task?.schedule_suggestion?.fuera_de_secuencia) {
    return "danger";
  }
  if (task?.dependency_state?.is_blocked) {
    return "warning";
  }
  if (task?.estatus === "completada") {
    return "success";
  }
  return getTaskStatusTone(task?.estatus);
}

function isTaskActionPending(taskActionLoading, taskId, action) {
  return Boolean(taskActionLoading?.[`${taskId}:${action}`]);
}

export default function PMProjectGanttLite({
  tasks = [],
  selectedTaskId,
  onSelectTask,
  onEditTaskDates,
  onApplySuggestedDates,
  taskActionLoading = {},
}) {
  const timeline = buildTimeline(tasks);

  if (tasks.length === 0) {
    return (
      <DataCard className="pm-gantt-card" subtitle="Las barras aparecerán cuando existan tareas." title="Línea de tiempo">
        <EmptyState compact note="Crea la primera tarea para ver la vista tipo Gantt." title="Sin tareas" />
      </DataCard>
    );
  }

  return (
    <DataCard
      className="pm-gantt-card"
      subtitle={timeline ? `Escala ${timeline.scale === "days" ? "diaria" : "semanal"} para el plan vigente.` : "Agrega fechas a las tareas para visualizar la línea de tiempo."}
      title="Línea de tiempo"
    >
      {!timeline ? (
        <EmptyState
          compact
          note="Las tareas sin fecha siguen apareciendo en la tabla, pero necesitan inicio o fin para dibujarse aquí."
          title="Sin fechas en tareas"
        />
      ) : (
        <div className="pm-gantt-shell">
          <div
            className={`pm-gantt-header pm-gantt-header-${timeline.scale}`}
            style={{ gridTemplateColumns: `repeat(${timeline.markers.length}, minmax(${timeline.scale === "days" ? "3.25rem" : "6rem"}, 1fr))` }}
          >
            {timeline.markers.map((marker) => (
              <div className="pm-gantt-marker" key={marker.key}>
                <strong>{marker.label}</strong>
                {"meta" in marker ? <span>{marker.meta}</span> : null}
              </div>
            ))}
          </div>

          <div className="pm-gantt-body">
            {tasks.map((task) => {
              const barStyle = buildBarStyle(task, timeline);
              const isSelected = selectedTaskId === task.id;
              const dependencyCopy = getDependencyCopy(task);
              const suggestedCopy = getSuggestedCopy(task);
              const blocked = Boolean(task?.dependency_state?.is_blocked);
              const outOfSequence = Boolean(task?.schedule_suggestion?.fuera_de_secuencia);
              const editingDates = isTaskActionPending(taskActionLoading, task.id, "dates");
              const applyingSuggestion = isTaskActionPending(taskActionLoading, task.id, "apply-suggestion");

              return (
                <div
                  className={`pm-gantt-row ${isSelected ? "is-selected" : ""} ${blocked ? "is-blocked" : ""} ${task.es_critica ? "is-critical" : ""} ${outOfSequence ? "is-out-of-sequence" : ""}`}
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
                  <div className="pm-gantt-row-head">
                    <div className="pm-gantt-row-title">
                      <strong>{normalizePmCopy(safeDisplayText(task.titulo))}</strong>
                      <div className="pm-inline-metadata">
                        <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                        <span className="table-note">{getTaskDateCopy(task)}</span>
                        <span className="table-note">{formatPercent(task.porcentaje_avance)} avance</span>
                        {task.es_critica ? (
                          <StatusBadge tone="danger">
                            <Route size={12} strokeWidth={1.9} />
                            Ruta crítica
                          </StatusBadge>
                        ) : null}
                        {blocked ? (
                          <StatusBadge tone="warning">
                            <Lock size={12} strokeWidth={1.9} />
                            Bloqueada
                          </StatusBadge>
                        ) : null}
                        {outOfSequence ? (
                          <StatusBadge tone="warning">
                            <AlertTriangle size={12} strokeWidth={1.9} />
                            Fuera de secuencia
                          </StatusBadge>
                        ) : null}
                      </div>
                    </div>

                    {dependencyCopy || suggestedCopy ? (
                      <div className="pm-gantt-dependency-stack">
                        {dependencyCopy ? (
                          <div className="pm-gantt-dependency-copy">
                            <Link2 size={12} strokeWidth={1.9} />
                            <span>{dependencyCopy}</span>
                          </div>
                        ) : null}
                        {suggestedCopy ? (
                          <div className="pm-gantt-suggestion-copy">
                            <CalendarRange size={12} strokeWidth={1.9} />
                            <span>{suggestedCopy}</span>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="pm-gantt-row-actions">
                      <ActionButton
                        className={editingDates ? "pm-button-loading" : ""}
                        disabled={editingDates || applyingSuggestion}
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
                      {outOfSequence ? (
                        <ActionButton
                          className={applyingSuggestion ? "pm-button-loading" : ""}
                          disabled={editingDates || applyingSuggestion}
                          icon={<Sparkles size={14} strokeWidth={1.9} />}
                          onClick={(event) => {
                            event.stopPropagation();
                            onApplySuggestedDates?.(task.id);
                          }}
                          size="sm"
                          tone="primary"
                          type="button"
                        >
                          {applyingSuggestion ? "Aplicando..." : "Aplicar sugerencia"}
                        </ActionButton>
                      ) : null}
                    </div>
                  </div>

                  <div
                    className={`pm-gantt-track pm-gantt-track-${timeline.scale}`}
                    style={{ gridTemplateColumns: `repeat(${timeline.markers.length}, minmax(${timeline.scale === "days" ? "3.25rem" : "6rem"}, 1fr))` }}
                  >
                    {timeline.markers.map((marker) => (
                      <span className="pm-gantt-cell" key={`${task.id}-${marker.key}`} />
                    ))}
                    {barStyle ? (
                      <div className={`pm-gantt-bar ${getGanttBarClass(task)} ${blocked ? "is-blocked" : ""} ${task.es_critica ? "is-critical" : ""} ${outOfSequence ? "is-out-of-sequence" : ""}`} style={barStyle}>
                        <span className="pm-gantt-bar-progress" style={{ width: `${getProgressWidth(task)}%` }} />
                        <span className="pm-gantt-bar-label">
                          <CalendarRange size={12} strokeWidth={1.9} />
                          {formatPercent(task.porcentaje_avance)}
                        </span>
                      </div>
                    ) : (
                      <span className="pm-gantt-no-dates">Sin fechas</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </DataCard>
  );
}
