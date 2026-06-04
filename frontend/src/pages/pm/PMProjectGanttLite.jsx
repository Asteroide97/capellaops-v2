import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CalendarRange,
  Link2,
  Lock,
  MoveHorizontal,
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

const DEFAULT_WORK_CALENDAR = {
  lunes: true,
  martes: true,
  miercoles: true,
  jueves: true,
  viernes: true,
  sabado: false,
  domingo: false,
};

function startOfDay(value) {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
}

function addCalendarDays(value, days) {
  const date = new Date(value);
  date.setDate(date.getDate() + days);
  return date;
}

function startOfWeek(value) {
  const date = startOfDay(value);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return addCalendarDays(date, diff);
}

function endOfWeek(value) {
  return addCalendarDays(startOfWeek(value), 6);
}

function diffInDays(start, end) {
  const millisecondsPerDay = 1000 * 60 * 60 * 24;
  return Math.round((startOfDay(end) - startOfDay(start)) / millisecondsPerDay);
}

function toIsoDate(value) {
  return startOfDay(value).toISOString().slice(0, 10);
}

function getWorkingDayKey(date) {
  const day = startOfDay(date).getDay();
  return ["domingo", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado"][day];
}

function isWorkingDay(date, workCalendar) {
  const calendar = workCalendar ?? DEFAULT_WORK_CALENDAR;
  const key = getWorkingDayKey(date);
  const value = calendar[key];
  return typeof value === "boolean" ? value : DEFAULT_WORK_CALENDAR[key];
}

function nextWorkingDay(date, workCalendar) {
  let cursor = startOfDay(date);
  for (let index = 0; index < 14; index += 1) {
    if (isWorkingDay(cursor, workCalendar)) {
      return cursor;
    }
    cursor = addCalendarDays(cursor, 1);
  }
  return startOfDay(date);
}

function countWorkingDays(start, end, workCalendar) {
  const normalizedStart = startOfDay(start);
  const normalizedEnd = startOfDay(end);
  const first = normalizedStart <= normalizedEnd ? normalizedStart : normalizedEnd;
  const last = normalizedStart <= normalizedEnd ? normalizedEnd : normalizedStart;
  let total = 0;
  let cursor = first;

  while (cursor <= last) {
    if (isWorkingDay(cursor, workCalendar)) {
      total += 1;
    }
    cursor = addCalendarDays(cursor, 1);
  }

  return Math.max(total, 1);
}

function addWorkingDays(start, days, workCalendar) {
  let cursor = nextWorkingDay(start, workCalendar);
  let remaining = Math.max(days, 0);

  while (remaining > 0) {
    cursor = addCalendarDays(cursor, 1);
    if (isWorkingDay(cursor, workCalendar)) {
      remaining -= 1;
    }
  }

  return cursor;
}

function getTaskDateRange(task, override = null) {
  const startValue =
    override?.start ||
    task?.fecha_inicio ||
    task?.schedule_suggestion?.fecha_inicio_sugerida ||
    task?.fecha_vencimiento;
  const endValue =
    override?.end ||
    task?.fecha_vencimiento ||
    task?.schedule_suggestion?.fecha_fin_sugerida ||
    task?.fecha_inicio;

  if (!startValue || !endValue) {
    return null;
  }

  const start = startOfDay(startValue);
  const end = startOfDay(endValue);
  return start <= end ? { start, end } : { start: end, end: start };
}

function buildTimeline(tasks) {
  const datedRanges = tasks.map((task) => getTaskDateRange(task)).filter(Boolean);
  if (datedRanges.length === 0) {
    return null;
  }

  const minDate = datedRanges.reduce(
    (current, range) => (range.start < current ? range.start : current),
    datedRanges[0].start,
  );
  const maxDate = datedRanges.reduce(
    (current, range) => (range.end > current ? range.end : current),
    datedRanges[0].end,
  );
  const totalDays = Math.max(1, diffInDays(minDate, maxDate) + 1);
  const scale = totalDays <= 42 ? "days" : "weeks";

  if (scale === "days") {
    const markers = Array.from({ length: totalDays }, (_, index) => {
      const currentDate = addCalendarDays(minDate, index);
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
    const start = addCalendarDays(weekStart, index * 7);
    const end = addCalendarDays(start, 6);
    return {
      key: `${start.toISOString()}-${end.toISOString()}`,
      label: `${new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short" }).format(start)} · ${new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short" }).format(end)}`,
    };
  });
  return { scale, markers, start: weekStart, end: weekEnd, totalDays: diffInDays(weekStart, weekEnd) + 1 };
}

function buildBarStyleFromRange(range, timeline) {
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

function buildBarStyle(task, timeline, override = null) {
  const range = getTaskDateRange(task, override);
  return buildBarStyleFromRange(range, timeline);
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

function hasMeaningfulMove(state) {
  if (!state?.previewStart || !state?.previewEnd || !state?.originalStart || !state?.originalEnd) {
    return false;
  }
  return (
    toIsoDate(state.previewStart) !== toIsoDate(state.originalStart) ||
    toIsoDate(state.previewEnd) !== toIsoDate(state.originalEnd)
  );
}

export default function PMProjectGanttLite({
  onApplySuggestedDates,
  onEditTaskDates,
  onGanttNotice,
  onPreviewReschedule,
  onSelectTask,
  selectedTaskId,
  taskActionLoading = {},
  tasks = [],
  workCalendar,
}) {
  const timeline = buildTimeline(tasks);
  const trackRefs = useRef({});
  const dragStateRef = useRef(null);
  const [dragState, setDragState] = useState(null);
  const supportsPointer = typeof window !== "undefined" && "PointerEvent" in window;

  function clearDragState() {
    dragStateRef.current = null;
    setDragState(null);
    if (typeof document !== "undefined") {
      document.body.classList.remove("pm-is-dragging");
    }
  }

  function setNextDragState(nextState) {
    dragStateRef.current = nextState;
    setDragState(nextState);
  }

  function computePreview(state, clientX) {
    if (!state) {
      return null;
    }

    const trackElement = trackRefs.current[state.taskId];
    if (!trackElement) {
      return state;
    }

    const trackWidth = trackElement.getBoundingClientRect().width || 1;
    const pixelsPerDay = trackWidth / Math.max(state.timeline.totalDays, 1);
    const rawDayDelta = Math.round((clientX - state.startX) / Math.max(pixelsPerDay, 1));
    const stepDays = state.timeline.scale === "weeks" ? 7 : 1;
    const snappedDayDelta = Math.round(rawDayDelta / stepDays) * stepDays;
    const movedEnough = Math.abs(clientX - state.startX) >= 4;

    let previewStart = state.originalStart;
    let previewEnd = state.originalEnd;

    if (state.kind === "move") {
      const shiftedStart = addCalendarDays(state.originalStart, snappedDayDelta);
      previewStart = nextWorkingDay(shiftedStart, state.workCalendar);
      previewEnd = addWorkingDays(previewStart, state.workingDuration - 1, state.workCalendar);
    } else {
      const shiftedEnd = addCalendarDays(state.originalEnd, snappedDayDelta);
      previewStart = state.originalStart;
      previewEnd = nextWorkingDay(shiftedEnd, state.workCalendar);
      if (previewEnd < previewStart) {
        previewEnd = previewStart;
      }
    }

    return {
      ...state,
      hasMoved: state.hasMoved || movedEnough,
      previewStart,
      previewEnd,
      barStyle: buildBarStyleFromRange({ start: previewStart, end: previewEnd }, state.timeline),
    };
  }

  function startInteraction(task, kind, event) {
    if (!supportsPointer || !timeline) {
      return;
    }

    const status = String(task?.estatus ?? "").toLowerCase();
    if (status === "completada") {
      onGanttNotice?.("No se puede mover una tarea completada.");
      return;
    }

    const range = getTaskDateRange(task);
    if (!range) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    onSelectTask?.(task.id);

    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // No-op si el navegador no soporta pointer capture en este target.
    }

    const nextState = {
      taskId: task.id,
      kind,
      pointerId: event.pointerId,
      startX: event.clientX,
      timeline,
      workCalendar,
      originalStart: range.start,
      originalEnd: range.end,
      workingDuration: countWorkingDays(range.start, range.end, workCalendar),
      previewStart: range.start,
      previewEnd: range.end,
      barStyle: buildBarStyleFromRange(range, timeline),
      hasMoved: false,
    };

    setNextDragState(nextState);
    if (typeof document !== "undefined") {
      document.body.classList.add("pm-is-dragging");
    }
  }

  function moveInteraction(event) {
    const currentState = dragStateRef.current;
    if (!currentState || currentState.pointerId !== event.pointerId) {
      return;
    }
    event.preventDefault();
    const nextState = computePreview(currentState, event.clientX);
    if (!nextState) {
      return;
    }
    setNextDragState(nextState);
  }

  function endInteraction(event) {
    const currentState = dragStateRef.current;
    if (!currentState || currentState.pointerId !== event.pointerId) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // No-op
    }

    const finalState = computePreview(currentState, event.clientX) ?? currentState;
    const shouldOpenImpact = finalState.hasMoved && hasMeaningfulMove(finalState);
    clearDragState();

    if (!shouldOpenImpact) {
      return;
    }

    onPreviewReschedule?.(finalState.taskId, {
      proposedStart: toIsoDate(finalState.previewStart),
      proposedEnd: toIsoDate(finalState.previewEnd),
      source: finalState.kind,
    });
  }

  function cancelInteraction(event) {
    const currentState = dragStateRef.current;
    if (!currentState || currentState.pointerId !== event.pointerId) {
      return;
    }
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // No-op
    }
    clearDragState();
  }

  const rows = useMemo(
    () =>
      tasks.map((task) => {
        const activeDrag = dragState?.taskId === task.id ? dragState : null;
        return {
          task,
          activeDrag,
          barStyle: activeDrag ? activeDrag.barStyle : buildBarStyle(task, timeline),
          previewCopy: activeDrag
            ? `Propuesto: ${safeDisplayText(formatDate(activeDrag.previewStart), "—")} → ${safeDisplayText(formatDate(activeDrag.previewEnd), "—")}`
            : "",
        };
      }),
    [dragState, tasks, timeline],
  );

  if (tasks.length === 0) {
    return (
      <DataCard className="pm-gantt-card" subtitle="Las barras aparecerán cuando existan tareas." title="Gantt / Línea de tiempo">
        <EmptyState compact note="Crea la primera tarea para ver la vista tipo Gantt." title="Sin tareas" />
      </DataCard>
    );
  }

  return (
    <DataCard
      className="pm-gantt-card"
      subtitle="Arrastra las barras para mover fechas. Usa el borde derecho para ajustar duración."
      title="Gantt / Línea de tiempo"
    >
      {!timeline ? (
        <EmptyState
          compact
          note="Las tareas sin fecha siguen apareciendo en la tabla, pero necesitan inicio o fin para dibujarse aquí."
          title="Sin fechas en tareas"
        />
      ) : (
        <div className="pm-gantt-shell">
          <div className="pm-gantt-help-copy">Tip: arrastra la barra, no la tarjeta completa.</div>

          <div
            className={`pm-gantt-header pm-gantt-header-${timeline.scale}`}
            style={{
              gridTemplateColumns: `repeat(${timeline.markers.length}, minmax(${timeline.scale === "days" ? "3.25rem" : "6rem"}, 1fr))`,
            }}
          >
            {timeline.markers.map((marker) => (
              <div className="pm-gantt-marker" key={marker.key}>
                <strong>{marker.label}</strong>
                {"meta" in marker ? <span>{marker.meta}</span> : null}
              </div>
            ))}
          </div>

          <div className="pm-gantt-body">
            {rows.map(({ task, activeDrag, barStyle, previewCopy }) => {
              const isSelected = selectedTaskId === task.id;
              const dependencyCopy = getDependencyCopy(task);
              const suggestedCopy = getSuggestedCopy(task);
              const blocked = Boolean(task?.dependency_state?.is_blocked);
              const outOfSequence = Boolean(task?.schedule_suggestion?.fuera_de_secuencia);
              const editingDates = isTaskActionPending(taskActionLoading, task.id, "dates");
              const applyingSuggestion = isTaskActionPending(taskActionLoading, task.id, "apply-suggestion");
              const isCompleted = String(task?.estatus ?? "").toLowerCase() === "completada";
              const canEditTask = supportsPointer && !isCompleted;

              return (
                <div
                  className={`pm-gantt-row ${isSelected ? "is-selected" : ""} ${blocked ? "is-blocked" : ""} ${task.es_critica ? "is-critical" : ""} ${outOfSequence ? "is-out-of-sequence" : ""} ${activeDrag ? "is-dragging" : ""}`}
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
                        {canEditTask ? <span className="table-note">Arrastra para mover</span> : null}
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

                    {dependencyCopy || suggestedCopy || previewCopy ? (
                      <div className="pm-gantt-dependency-stack">
                        {dependencyCopy ? (
                          <div className="pm-gantt-dependency-copy">
                            <Link2 size={12} strokeWidth={1.9} />
                            <span>{dependencyCopy}</span>
                          </div>
                        ) : null}
                        {suggestedCopy && !activeDrag ? (
                          <div className="pm-gantt-suggestion-copy">
                            <CalendarRange size={12} strokeWidth={1.9} />
                            <span>{suggestedCopy}</span>
                          </div>
                        ) : null}
                        {previewCopy ? (
                          <div className="pm-gantt-drag-copy">
                            <MoveHorizontal size={12} strokeWidth={1.9} />
                            <span>{previewCopy}</span>
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
                    className={`pm-gantt-track pm-gantt-track-${timeline.scale} ${activeDrag ? "is-dragging" : ""}`}
                    ref={(element) => {
                      trackRefs.current[task.id] = element;
                    }}
                    style={{
                      gridTemplateColumns: `repeat(${timeline.markers.length}, minmax(${timeline.scale === "days" ? "3.25rem" : "6rem"}, 1fr))`,
                    }}
                  >
                    {timeline.markers.map((marker) => (
                      <span className="pm-gantt-cell" key={`${task.id}-${marker.key}`} />
                    ))}
                    {barStyle ? (
                      <div
                        className={`pm-gantt-bar pm-gantt-task ${getGanttBarClass(task)} ${blocked ? "is-blocked" : ""} ${task.es_critica ? "is-critical" : ""} ${outOfSequence ? "is-out-of-sequence" : ""} ${canEditTask ? "" : "is-not-editable"} ${activeDrag ? "is-dragging" : ""}`}
                        style={barStyle}
                        title={isCompleted ? "No se puede mover una tarea completada." : "Arrastra para mover"}
                      >
                        <span className="pm-gantt-bar-progress" style={{ width: `${getProgressWidth(task)}%` }} />
                        <div
                          className={`pm-gantt-task-drag-surface ${canEditTask ? "" : "is-not-editable"}`}
                          onPointerCancel={cancelInteraction}
                          onPointerDown={(event) => startInteraction(task, "move", event)}
                          onPointerMove={moveInteraction}
                          onPointerUp={endInteraction}
                          role="presentation"
                        >
                          <span className="pm-gantt-bar-label">
                            <CalendarRange size={12} strokeWidth={1.9} />
                            {formatPercent(task.porcentaje_avance)}
                          </span>
                        </div>
                        {canEditTask ? (
                          <span
                            className="pm-gantt-resize-handle-right"
                            onPointerCancel={cancelInteraction}
                            onPointerDown={(event) => startInteraction(task, "resize-end", event)}
                            onPointerMove={moveInteraction}
                            onPointerUp={endInteraction}
                            role="presentation"
                            title="Arrastra para ajustar la duración"
                          />
                        ) : null}
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
