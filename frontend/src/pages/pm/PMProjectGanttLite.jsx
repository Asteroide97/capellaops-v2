import { useEffect, useMemo, useState } from "react";
import {
  CalendarRange,
  Eye,
  Gauge,
  Pencil,
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
  isTaskOverdue,
  normalizePmCopy,
} from "./shared";

const projectGanttColumns = "2.55fr 1fr 0.85fr 0.7fr 0.75fr 0.75fr";

function parseDateValue(value) {
  if (!value) {
    return null;
  }

  const rawValue = String(value).slice(0, 10);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(rawValue);
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }

  const parsed = new Date(String(value));
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

function addDays(date, days) {
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + days);
  return nextDate;
}

function toIsoDate(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function startOfWeek(date) {
  const nextDate = new Date(date);
  const day = nextDate.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return addDays(nextDate, diff);
}

function endOfWeek(date) {
  return addDays(startOfWeek(date), 6);
}

function diffDays(start, end) {
  const millisecondsPerDay = 1000 * 60 * 60 * 24;
  const startUtc = Date.UTC(start.getFullYear(), start.getMonth(), start.getDate());
  const endUtc = Date.UTC(end.getFullYear(), end.getMonth(), end.getDate());
  return Math.round((endUtc - startUtc) / millisecondsPerDay);
}

function formatMarkerLabel(date, options) {
  return new Intl.DateTimeFormat("es-MX", options).format(date);
}

function stopEvent(event, callback) {
  event.stopPropagation();
  callback();
}

function getTaskVisualDates(task) {
  const startDate = parseDateValue(task?.fecha_inicio);
  const endDate = parseDateValue(task?.fecha_vencimiento);

  if (!startDate && !endDate) {
    return {
      hasDates: false,
      startDate: null,
      endDate: null,
    };
  }

  return {
    hasDates: true,
    startDate: startDate ?? endDate,
    endDate: endDate ?? startDate,
  };
}

function getTaskDependencySummary(task) {
  const dependencyState = task?.dependency_state ?? {};
  const blockerTitles =
    dependencyState?.blockers?.map((item) => normalizePmCopy(safeDisplayText(item?.titulo))).filter(Boolean) ?? [];
  const dependencyTitles =
    dependencyState?.dependencies
      ?.map((item) => normalizePmCopy(safeDisplayText(item?.resolved_title ?? item?.depende_de_tarea_titulo)))
      .filter(Boolean) ?? [];

  if (blockerTitles.length > 0) {
    return `Depende de ${blockerTitles.join(", ")}`;
  }

  if (dependencyTitles.length > 0) {
    return `Depende de ${dependencyTitles.join(", ")}`;
  }

  return "Sin dependencias registradas";
}

function getTaskVisualMeta(task) {
  const dependencyState = task?.dependency_state ?? {};
  const outOfSequence = Boolean(task?.schedule_suggestion?.fuera_de_secuencia);
  const blocked = Boolean(dependencyState?.is_blocked ?? dependencyState?.blocked ?? task?.is_blocked);
  const completed = String(task?.estatus ?? "").toLowerCase() === "completada";
  const inProgress = ["en_progreso", "en_revision"].includes(String(task?.estatus ?? "").toLowerCase());
  const overdue = isTaskOverdue(task);

  let tone = "neutral";
  if (completed) {
    tone = "success";
  } else if (blocked || overdue) {
    tone = "danger";
  } else if (outOfSequence || task?.es_critica) {
    tone = "warning";
  } else if (inProgress) {
    tone = "info";
  }

  return {
    blocked,
    completed,
    inProgress,
    outOfSequence,
    overdue,
    tone,
  };
}

function getTaskCompactAlert(task, visualMeta) {
  const dependencySummary = getTaskDependencySummary(task);
  const dependencyDetail = normalizePmCopy(safeDisplayText(task?.dependency_state?.detail));
  const sequenceReason = normalizePmCopy(safeDisplayText(task?.schedule_suggestion?.razon));

  if (visualMeta.blocked) {
    return dependencyDetail ? `Bloqueada - ${dependencyDetail}` : `Bloqueada - ${dependencySummary}`;
  }
  if (visualMeta.outOfSequence) {
    return sequenceReason ? `Fuera de secuencia - ${sequenceReason}` : "Fuera de secuencia";
  }
  if (task?.es_critica) {
    return dependencySummary !== "Sin dependencias registradas"
      ? `En ruta critica - ${dependencySummary}`
      : "En ruta critica";
  }
  if (visualMeta.overdue) {
    return "Atrasada - Revisar fecha compromiso";
  }
  return dependencySummary !== "Sin dependencias registradas" ? dependencySummary : "Sin alertas";
}

function getTaskSortValue(task) {
  const { startDate, endDate } = getTaskVisualDates(task);
  const selectedDate = startDate ?? endDate;
  if (!selectedDate) {
    return Number.MAX_SAFE_INTEGER;
  }
  return selectedDate.getTime();
}

function buildTimelineRange(tasks) {
  const datedTasks = tasks.filter((task) => getTaskVisualDates(task).hasDates);
  if (datedTasks.length === 0) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const rangeStart = startOfWeek(today);
    const rangeEnd = addDays(rangeStart, 20);
    const totalDays = diffDays(rangeStart, rangeEnd) + 1;
    return {
      rangeStart,
      rangeEnd,
      totalDays,
      pxPerDay: 28,
    };
  }

  const minDate = new Date(
    Math.min(
      ...datedTasks.map((task) => {
        const { startDate, endDate } = getTaskVisualDates(task);
        return (startDate ?? endDate).getTime();
      }),
    ),
  );
  const maxDate = new Date(
    Math.max(
      ...datedTasks.map((task) => {
        const { startDate, endDate } = getTaskVisualDates(task);
        return (endDate ?? startDate).getTime();
      }),
    ),
  );

  const rangeStart = startOfWeek(minDate);
  const rangeEnd = endOfWeek(maxDate);
  const totalDays = diffDays(rangeStart, rangeEnd) + 1;
  const pxPerDay = totalDays <= 21 ? 30 : totalDays <= 49 ? 18 : 12;

  return {
    rangeStart,
    rangeEnd,
    totalDays,
    pxPerDay,
  };
}

function buildTimelineMarkers({ rangeStart, rangeEnd, pxPerDay, totalDays }) {
  const markers = [];

  if (totalDays <= 21) {
    let cursor = new Date(rangeStart);
    while (cursor <= rangeEnd) {
      markers.push({
        key: cursor.toISOString(),
        label: formatMarkerLabel(cursor, { day: "2-digit" }),
        caption: formatMarkerLabel(cursor, { month: "short" }),
        width: pxPerDay,
      });
      cursor = addDays(cursor, 1);
    }
    return markers;
  }

  let cursor = new Date(rangeStart);
  while (cursor <= rangeEnd) {
    const markerEnd = endOfWeek(cursor) < rangeEnd ? endOfWeek(cursor) : new Date(rangeEnd);
    const days = diffDays(cursor, markerEnd) + 1;
    markers.push({
      key: cursor.toISOString(),
      label: `${formatMarkerLabel(cursor, { day: "2-digit" })}-${formatMarkerLabel(markerEnd, { day: "2-digit" })}`,
      caption: formatMarkerLabel(cursor, { month: "short" }),
      width: days * pxPerDay,
    });
    cursor = addDays(markerEnd, 1);
  }

  return markers;
}

function buildBarLayout(task, timelineRange) {
  const { hasDates, startDate, endDate } = getTaskVisualDates(task);
  if (!hasDates || !startDate || !endDate) {
    return {
      hasDates: false,
      left: 0,
      width: timelineRange.pxPerDay,
    };
  }

  const visualStart = startDate < endDate ? startDate : endDate;
  const visualEnd = startDate < endDate ? endDate : startDate;
  const left = Math.max(0, diffDays(timelineRange.rangeStart, visualStart)) * timelineRange.pxPerDay;
  const width = Math.max(
    timelineRange.pxPerDay,
    (diffDays(visualStart, visualEnd) + 1) * timelineRange.pxPerDay,
  );

  return {
    hasDates: true,
    left,
    width,
  };
}

function buildBarLayoutFromDates(startDate, endDate, timelineRange) {
  if (!startDate || !endDate) {
    return {
      hasDates: false,
      left: 0,
      width: timelineRange.pxPerDay,
    };
  }

  const visualStart = startDate < endDate ? startDate : endDate;
  const visualEnd = startDate < endDate ? endDate : startDate;
  const left = Math.max(0, diffDays(timelineRange.rangeStart, visualStart)) * timelineRange.pxPerDay;
  const width = Math.max(
    timelineRange.pxPerDay,
    (diffDays(visualStart, visualEnd) + 1) * timelineRange.pxPerDay,
  );

  return {
    hasDates: true,
    left,
    width,
  };
}

function GanttBody({
  canEditTask = true,
  onApplySuggestedDates,
  onGanttNotice,
  onEditTask,
  onEditTaskDates,
  onPreviewReschedule,
  onSelectTask,
  onViewTaskDetail,
  selectedTaskId,
  taskActionLoading = {},
  tasks = [],
}) {
  const [interaction, setInteraction] = useState(null);
  const sortedTasks = useMemo(
    () =>
      [...tasks].sort((left, right) => {
        const startDiff = getTaskSortValue(left) - getTaskSortValue(right);
        if (startDiff !== 0) {
          return startDiff;
        }
        return String(left?.titulo ?? "").localeCompare(String(right?.titulo ?? ""), "es-MX");
      }),
    [tasks],
  );

  const tasksWithDates = useMemo(
    () => sortedTasks.filter((task) => getTaskVisualDates(task).hasDates),
    [sortedTasks],
  );
  const tasksWithoutDates = useMemo(
    () => sortedTasks.filter((task) => !getTaskVisualDates(task).hasDates),
    [sortedTasks],
  );
  const timelineRange = useMemo(() => buildTimelineRange(tasksWithDates), [tasksWithDates]);
  const markers = useMemo(
    () => buildTimelineMarkers(timelineRange),
    [timelineRange],
  );
  const selectedTask = useMemo(
    () => sortedTasks.find((task) => task.id === selectedTaskId) ?? null,
    [selectedTaskId, sortedTasks],
  );

  useEffect(() => {
    if (!interaction) {
      return undefined;
    }

    function handleMouseMove(event) {
      setInteraction((current) => {
        if (!current) {
          return current;
        }

        const deltaPx = event.clientX - current.startClientX;
        const deltaDays = Math.round(deltaPx / current.pxPerDay);
        if (deltaDays === current.deltaDays) {
          return current;
        }

        if (current.kind === "move") {
          return {
            ...current,
            deltaDays,
            nextStart: addDays(current.originalStart, deltaDays),
            nextEnd: addDays(current.originalEnd, deltaDays),
          };
        }

        if (current.kind === "resize-start") {
          const candidateStart = addDays(current.originalStart, deltaDays);
          const clampedStart = candidateStart > current.originalEnd ? current.originalEnd : candidateStart;
          return {
            ...current,
            deltaDays,
            nextStart: clampedStart,
            nextEnd: current.originalEnd,
          };
        }

        const candidateEnd = addDays(current.originalEnd, deltaDays);
        const clampedEnd = candidateEnd < current.originalStart ? current.originalStart : candidateEnd;
        return {
          ...current,
          deltaDays,
          nextStart: current.originalStart,
          nextEnd: clampedEnd,
        };
      });
    }

    function handleMouseUp() {
      setInteraction((current) => {
        if (!current) {
          return null;
        }

        const startChanged = toIsoDate(current.nextStart) !== toIsoDate(current.originalStart);
        const endChanged = toIsoDate(current.nextEnd) !== toIsoDate(current.originalEnd);

        if ((startChanged || endChanged) && onPreviewReschedule) {
          onPreviewReschedule(current.taskId, {
            proposedStart: toIsoDate(current.nextStart),
            proposedEnd: toIsoDate(current.nextEnd),
            source: current.kind,
          });
        }

        return null;
      });
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [interaction, onPreviewReschedule]);

  function handleTaskSelect(taskId) {
    onSelectTask?.(taskId);
  }

  function startInteraction(event, task, kind) {
    event.preventDefault();
    event.stopPropagation();

    if (!canEditTask) {
      onGanttNotice?.("No tienes permiso para editar fechas en este trabajo.");
      return;
    }

    const { startDate, endDate, hasDates } = getTaskVisualDates(task);
    if (!hasDates || !startDate || !endDate) {
      onGanttNotice?.("Agrega inicio y fecha compromiso antes de mover esta tarea.");
      return;
    }

    onSelectTask?.(task.id);
    setInteraction({
      taskId: task.id,
      kind,
      startClientX: event.clientX,
      deltaDays: 0,
      originalStart: startDate,
      originalEnd: endDate,
      nextStart: startDate,
      nextEnd: endDate,
      pxPerDay: timelineRange.pxPerDay,
    });
  }

  if (tasks.length === 0) {
    return <EmptyState compact note="Crea la primera etapa o tarea para ver el cronograma del trabajo." title="Sin tareas" />;
  }

  return (
    <div className="pm-project-gantt-shell" style={{ "--pm-project-gantt-columns": projectGanttColumns }}>
      {selectedTask ? (
        <div className="pm-project-gantt-summary">
          <div className="pm-project-gantt-summary-main">
            <div className="pm-project-gantt-summary-copy">
              <span className="pm-project-gantt-summary-eyebrow">Tarea seleccionada</span>
              <strong>{normalizePmCopy(safeDisplayText(selectedTask.titulo, "Tarea sin nombre"))}</strong>
            </div>
            <div className="pm-project-gantt-summary-meta">
              <span>Responsable: {safeDisplayText(selectedTask.asignado_nombre_snapshot, "Sin responsable")}</span>
              <span>Inicio: {safeDisplayText(formatDate(selectedTask.fecha_inicio), "Sin fecha")}</span>
              <span>Fin: {safeDisplayText(formatDate(selectedTask.fecha_vencimiento), "Sin fecha")}</span>
              <span>{getTaskCompactAlert(selectedTask, getTaskVisualMeta(selectedTask))}</span>
            </div>
            <div className="pm-project-gantt-summary-badges">
              <StatusBadge tone={getTaskStatusTone(selectedTask.estatus)}>{getTaskStatusLabel(selectedTask.estatus)}</StatusBadge>
              <StatusBadge tone="info">{formatPercent(selectedTask.porcentaje_avance)}</StatusBadge>
              {selectedTask?.es_critica ? <StatusBadge tone="danger">Ruta critica</StatusBadge> : null}
              {selectedTask?.dependency_state?.is_blocked ? <StatusBadge tone="warning">Bloqueada</StatusBadge> : null}
              {selectedTask?.schedule_suggestion?.fuera_de_secuencia ? <StatusBadge tone="warning">Fuera de secuencia</StatusBadge> : null}
            </div>
            <div className="pm-project-gantt-summary-actions">
              <ActionButton
                icon={<Eye size={14} strokeWidth={1.9} />}
                onClick={() => onViewTaskDetail?.(selectedTask.id)}
                size="sm"
                type="button"
              >
                Ver
              </ActionButton>
              <ActionButton
                icon={<Gauge size={14} strokeWidth={1.9} />}
                disabled={!canEditTask}
                onClick={() => onEditTask?.(selectedTask.id)}
                size="sm"
                type="button"
              >
                Avance
              </ActionButton>
              <ActionButton
                icon={<Pencil size={14} strokeWidth={1.9} />}
                disabled={!canEditTask}
                onClick={() => onEditTaskDates?.(selectedTask.id)}
                size="sm"
                type="button"
              >
                Fechas
              </ActionButton>
              {selectedTask?.schedule_suggestion?.fuera_de_secuencia && canEditTask ? (
                <ActionButton
                  icon={<Sparkles size={14} strokeWidth={1.9} />}
                  onClick={() => onApplySuggestedDates?.(selectedTask.id)}
                  size="sm"
                  tone="primary"
                  type="button"
                >
                  Sugerida
                </ActionButton>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <div className="pm-project-gantt-board">
        <div className="pm-project-gantt-head">
          <div className="pm-project-gantt-left-head">
            <span>Tarea / etapa</span>
            <span>Responsable</span>
            <span>Estado</span>
            <span>Avance</span>
            <span>Inicio</span>
            <span>Fin</span>
          </div>
          <div className="pm-project-gantt-right-head">
            <div className="pm-project-gantt-right-label">
              <CalendarRange size={15} strokeWidth={1.9} />
              <span>Linea de tiempo</span>
            </div>
            <div className="pm-project-gantt-markers">
              <div className="pm-project-gantt-track-width" style={{ width: `${timelineRange.totalDays * timelineRange.pxPerDay}px` }}>
                {markers.map((marker) => (
                  <div className="pm-project-gantt-marker" key={marker.key} style={{ width: `${marker.width}px` }}>
                    <strong>{marker.label}</strong>
                    <span>{marker.caption}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="pm-project-gantt-body">
          <div className="pm-project-gantt-left-body">
            {tasksWithDates.map((task) => {
              const visualMeta = getTaskVisualMeta(task);
              const selected = selectedTaskId === task.id;

              return (
                <div
                  className={`pm-project-gantt-left-row ${selected ? "is-selected" : ""}`}
                  key={`left-${task.id}`}
                  onClick={() => handleTaskSelect(task.id)}
                  onDoubleClick={() => onViewTaskDetail?.(task.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleTaskSelect(task.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className="pm-project-gantt-cell is-primary">
                    <strong>{normalizePmCopy(safeDisplayText(task.titulo, "Tarea sin nombre"))}</strong>
                    <span className="pm-project-gantt-secondary-line">{getTaskCompactAlert(task, visualMeta)}</span>
                  </div>
                  <div className="pm-project-gantt-cell">
                    <strong>{safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")}</strong>
                  </div>
                  <div className="pm-project-gantt-cell">
                    <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                  </div>
                  <div className="pm-project-gantt-cell">
                    <strong>{formatPercent(task.porcentaje_avance)}</strong>
                  </div>
                  <div className="pm-project-gantt-cell">
                    <strong>{safeDisplayText(formatDate(task.fecha_inicio), "Sin fecha")}</strong>
                  </div>
                  <div className="pm-project-gantt-cell">
                    <strong>{safeDisplayText(formatDate(task.fecha_vencimiento), "Sin fecha")}</strong>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="pm-project-gantt-right-body">
            <div className="pm-project-gantt-track-width" style={{ width: `${timelineRange.totalDays * timelineRange.pxPerDay}px` }}>
              {tasksWithDates.map((task) => {
                const selected = selectedTaskId === task.id;
                const visualMeta = getTaskVisualMeta(task);
                const activeInteraction = interaction?.taskId === task.id ? interaction : null;
                const barLayout = activeInteraction
                  ? buildBarLayoutFromDates(activeInteraction.nextStart, activeInteraction.nextEnd, timelineRange)
                  : buildBarLayout(task, timelineRange);
                const barLabel = barLayout.width >= 170
                  ? normalizePmCopy(safeDisplayText(task.titulo, "Tarea"))
                  : barLayout.width >= 96
                    ? formatPercent(task.porcentaje_avance)
                    : "";

                return (
                  <div
                    className={`pm-project-gantt-track-row ${selected ? "is-selected" : ""}`}
                    key={`right-${task.id}`}
                    onClick={() => handleTaskSelect(task.id)}
                    onDoubleClick={() => onViewTaskDetail?.(task.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        handleTaskSelect(task.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="pm-project-gantt-gridline">
                      {markers.map((marker) => (
                        <div
                          className="pm-project-gantt-grid-segment"
                          key={`${task.id}-${marker.key}`}
                          style={{ width: `${marker.width}px` }}
                        />
                      ))}
                    </div>
                    <div
                      className={`pm-gantt-bar ${visualMeta.tone} ${visualMeta.blocked ? "is-blocked" : ""} ${task?.es_critica ? "is-critical" : ""} ${visualMeta.outOfSequence ? "is-out-of-sequence" : ""} ${canEditTask ? "is-draggable" : ""} ${activeInteraction ? "is-dragging" : ""}`}
                      onMouseDown={(event) => startInteraction(event, task, "move")}
                      style={{ left: `${barLayout.left}px`, width: `${barLayout.width}px` }}
                    >
                      {canEditTask ? (
                        <button
                          className="pm-project-gantt-handle is-start"
                          onMouseDown={(event) => startInteraction(event, task, "resize-start")}
                          type="button"
                        />
                      ) : null}
                      <div
                        className="pm-gantt-bar-progress"
                        style={{ width: `${Math.max(0, Math.min(100, Number(task.porcentaje_avance ?? 0)))}%` }}
                      />
                      <div className="pm-project-gantt-bar-label">{barLabel}</div>
                      {canEditTask ? (
                        <button
                          className="pm-project-gantt-handle is-end"
                          onMouseDown={(event) => startInteraction(event, task, "resize-end")}
                          type="button"
                        />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {tasksWithoutDates.length > 0 ? (
        <section className="pm-project-gantt-missing">
          <div className="pm-project-gantt-missing-head">
            <strong>Tareas sin fechas</strong>
            <span>Agrega inicio y fecha compromiso para verlas en el cronograma.</span>
          </div>
          <div className="pm-project-gantt-missing-list">
            {tasksWithoutDates.map((task) => {
              const visualMeta = getTaskVisualMeta(task);
              return (
                <article className="mini-card pm-project-gantt-missing-item" key={task.id}>
                  <div>
                    <strong>{normalizePmCopy(safeDisplayText(task.titulo, "Tarea sin nombre"))}</strong>
                    <p className="table-note">
                      {safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")} - {getTaskCompactAlert(task, visualMeta)}
                    </p>
                  </div>
                  <div className="pm-project-gantt-missing-badges">
                    <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                    <StatusBadge tone="neutral">{formatPercent(task.porcentaje_avance)}</StatusBadge>
                    {visualMeta.blocked ? <StatusBadge tone="danger">Bloqueada</StatusBadge> : null}
                    {visualMeta.outOfSequence ? <StatusBadge tone="warning">Fuera de secuencia</StatusBadge> : null}
                  </div>
                  <div className="pm-project-gantt-row-actions">
                    <ActionButton
                      icon={<Eye size={14} strokeWidth={1.9} />}
                      onClick={() => {
                        if (onViewTaskDetail) {
                          onViewTaskDetail(task.id);
                          return;
                        }
                        onSelectTask?.(task.id);
                      }}
                      size="sm"
                      title="Ver detalle"
                      type="button"
                    >
                      Ver
                    </ActionButton>
                    <ActionButton
                      icon={<Gauge size={14} strokeWidth={1.9} />}
                      disabled={!canEditTask}
                      onClick={() => onEditTask?.(task.id)}
                      size="sm"
                      title="Actualizar avance"
                      type="button"
                    >
                      Avance
                    </ActionButton>
                    <ActionButton
                      icon={<Pencil size={14} strokeWidth={1.9} />}
                      disabled={!canEditTask}
                      onClick={() => onEditTaskDates?.(task.id)}
                      size="sm"
                      title="Editar fechas"
                      type="button"
                    >
                      Fechas
                    </ActionButton>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}
    </div>
  );
}

export default function PMProjectGanttLite(props) {
  const { embedded = false } = props;

  if (embedded) {
    return <GanttBody {...props} />;
  }

  return (
    <DataCard
      className="pm-workplan-gantt-wide"
      subtitle="Vista Gantt conectada a tareas reales. Selecciona una tarea o arrastra su barra para ajustar fechas."
      title="Gantt del trabajo"
    >
      <GanttBody {...props} />
    </DataCard>
  );
}
