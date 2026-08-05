import { useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarRange,
  Check,
  Eye,
  Gauge,
  Pencil,
  Sparkles,
  X,
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
  taskStatusOptions,
} from "./shared";

const projectGanttColumns = "2.45fr 1fr 0.95fr 0.82fr 0.8fr 0.8fr";
const inlineEditableTaskStatuses = taskStatusOptions.filter(
  (option) => !["cancelada"].includes(String(option?.value ?? "").toLowerCase()),
);

function clampProgressValue(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return Math.max(0, Math.min(100, parsed));
}

function getMemberDisplayName(member) {
  return safeDisplayText(member?.nombre_snapshot || member?.email || member?.usuario_id, "Sin responsable");
}

function getTaskAssigneeLabel(task, members = []) {
  const assignedMember = members.find((member) => String(member?.usuario_id ?? "") === String(task?.asignado_user_id ?? ""));
  return safeDisplayText(task?.asignado_nombre_snapshot || getMemberDisplayName(assignedMember), "Sin responsable");
}

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
  memberOptions = [],
  onApplySuggestedDates,
  onGanttNotice,
  onEditTask,
  onEditTaskDates,
  onInlineTaskUpdate,
  onPreviewReschedule,
  onSelectTask,
  onSetTaskStatus,
  onViewTaskDetail,
  selectedTaskId,
  taskActionLoading = {},
  tasks = [],
}) {
  const [interaction, setInteraction] = useState(null);
  const [editingCell, setEditingCell] = useState(null);
  const [draftValues, setDraftValues] = useState({});
  const [inlineFeedback, setInlineFeedback] = useState({});
  const feedbackTimersRef = useRef({});
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
  const availableMembers = useMemo(
    () => (memberOptions ?? []).filter((member) => member?.activo !== false && member?.usuario_id),
    [memberOptions],
  );

  useEffect(() => () => {
    Object.values(feedbackTimersRef.current).forEach((timerId) => window.clearTimeout(timerId));
  }, []);

  useEffect(() => {
    if (!editingCell) {
      return;
    }
    const taskStillExists = sortedTasks.some((task) => task.id === editingCell.taskId);
    if (!taskStillExists) {
      setEditingCell(null);
    }
  }, [editingCell, sortedTasks]);

  function getCellKey(taskId, field) {
    return `${taskId}:${field}`;
  }

  function getDraftValue(task, field, fallback = "") {
    const key = getCellKey(task.id, field);
    if (draftValues[key] !== undefined) {
      return draftValues[key];
    }
    if (field === "progress") {
      return String(clampProgressValue(task?.porcentaje_avance ?? 0));
    }
    if (field === "status") {
      return String(task?.estatus ?? "pendiente");
    }
    if (field === "assignee") {
      return String(task?.asignado_user_id ?? "");
    }
    return fallback;
  }

  function clearInlineFeedback(taskId, field) {
    const key = getCellKey(taskId, field);
    if (feedbackTimersRef.current[key]) {
      window.clearTimeout(feedbackTimersRef.current[key]);
      delete feedbackTimersRef.current[key];
    }
    setInlineFeedback((current) => {
      if (!current[key]) {
        return current;
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function setInlineFeedbackState(taskId, field, status, message, { autoClear = status === "saved" } = {}) {
    const key = getCellKey(taskId, field);
    if (feedbackTimersRef.current[key]) {
      window.clearTimeout(feedbackTimersRef.current[key]);
      delete feedbackTimersRef.current[key];
    }
    setInlineFeedback((current) => ({
      ...current,
      [key]: { status, message },
    }));
    if (autoClear) {
      feedbackTimersRef.current[key] = window.setTimeout(() => {
        setInlineFeedback((current) => {
          if (!current[key]) {
            return current;
          }
          const next = { ...current };
          delete next[key];
          return next;
        });
        delete feedbackTimersRef.current[key];
      }, 1600);
    }
  }

  function openInlineEditor(task, field) {
    if (!canEditTask) {
      return;
    }
    const key = getCellKey(task.id, field);
    setEditingCell({ taskId: task.id, field });
    clearInlineFeedback(task.id, field);
    setDraftValues((current) => ({
      ...current,
      [key]: getDraftValue(task, field),
    }));
  }

  function closeInlineEditor(taskId, field) {
    const key = getCellKey(taskId, field);
    setEditingCell((current) => {
      if (current?.taskId === taskId && current?.field === field) {
        return null;
      }
      return current;
    });
    setDraftValues((current) => {
      if (current[key] === undefined) {
        return current;
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  async function commitStatusUpdate(task, nextStatus) {
    if (!task?.id) {
      return;
    }
    if (String(task?.estatus ?? "") === String(nextStatus ?? "")) {
      closeInlineEditor(task.id, "status");
      return;
    }

    setInlineFeedbackState(task.id, "status", "saving", "Guardando...", { autoClear: false });
    const saved = await onSetTaskStatus?.(task, nextStatus);
    if (saved) {
      closeInlineEditor(task.id, "status");
      setInlineFeedbackState(task.id, "status", "saved", "Guardado");
      return;
    }
    setInlineFeedbackState(task.id, "status", "error", "Error al actualizar", { autoClear: false });
  }

  async function commitProgressUpdate(task) {
    if (!task?.id) {
      return;
    }
    const nextProgress = clampProgressValue(getDraftValue(task, "progress", "0"));
    if (nextProgress === clampProgressValue(task?.porcentaje_avance ?? 0)) {
      closeInlineEditor(task.id, "progress");
      return;
    }

    setInlineFeedbackState(task.id, "progress", "saving", "Guardando...", { autoClear: false });
    const saved = await onInlineTaskUpdate?.(
      task.id,
      { porcentaje_avance: nextProgress },
      {
        action: "inline-progress",
        successMessage: "Avance actualizado.",
        errorMessage: "No se pudo actualizar el avance.",
        optimisticPatch: { porcentaje_avance: nextProgress },
      },
    );
    if (saved) {
      closeInlineEditor(task.id, "progress");
      setInlineFeedbackState(task.id, "progress", "saved", "Guardado");
      return;
    }
    setInlineFeedbackState(task.id, "progress", "error", "Error al actualizar", { autoClear: false });
  }

  async function commitAssigneeUpdate(task, nextAssigneeId) {
    if (!task?.id) {
      return;
    }
    if (String(task?.asignado_user_id ?? "") === String(nextAssigneeId ?? "")) {
      closeInlineEditor(task.id, "assignee");
      return;
    }

    const selectedMember = availableMembers.find((member) => String(member.usuario_id) === String(nextAssigneeId));
    setInlineFeedbackState(task.id, "assignee", "saving", "Guardando...", { autoClear: false });
    const saved = await onInlineTaskUpdate?.(
      task.id,
      {
        asignado_user_id: nextAssigneeId || null,
        asignado_nombre_snapshot: nextAssigneeId ? null : null,
      },
      {
        action: "inline-assignee",
        successMessage: "Responsable actualizado.",
        errorMessage: "No se pudo actualizar el responsable.",
        optimisticPatch: {
          asignado_user_id: nextAssigneeId || null,
          asignado_nombre_snapshot: nextAssigneeId ? getMemberDisplayName(selectedMember) : null,
        },
      },
    );
    if (saved) {
      closeInlineEditor(task.id, "assignee");
      setInlineFeedbackState(task.id, "assignee", "saved", "Guardado");
      return;
    }
    setInlineFeedbackState(task.id, "assignee", "error", "Error al actualizar", { autoClear: false });
  }

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

  function renderInlineFeedback(taskId, field) {
    const feedback = inlineFeedback[getCellKey(taskId, field)];
    if (!feedback?.message) {
      return null;
    }
    return <span className={`pm-project-gantt-inline-feedback is-${feedback.status}`}>{feedback.message}</span>;
  }

  function renderStatusCell(task) {
    const isEditing = editingCell?.taskId === task.id && editingCell?.field === "status";
    const draftValue = getDraftValue(task, "status");

    if (isEditing && canEditTask) {
      return (
        <div
          className="pm-project-gantt-inline-editor"
          onClick={(event) => event.stopPropagation()}
          onDoubleClick={(event) => event.stopPropagation()}
        >
          <select
            autoFocus
            className="pm-project-gantt-inline-select"
            onChange={(event) => {
              const nextValue = event.target.value;
              setDraftValues((current) => ({
                ...current,
                [getCellKey(task.id, "status")]: nextValue,
              }));
              void commitStatusUpdate(task, nextValue);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                closeInlineEditor(task.id, "status");
              }
            }}
            value={draftValue}
          >
            {inlineEditableTaskStatuses.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            aria-label="Cancelar edición de estado"
            className="pm-project-gantt-inline-icon"
            onClick={(event) => stopEvent(event, () => closeInlineEditor(task.id, "status"))}
            type="button"
          >
            <X size={12} strokeWidth={2} />
          </button>
          {renderInlineFeedback(task.id, "status")}
        </div>
      );
    }

    return (
      <button
        className="pm-project-gantt-inline-trigger"
        disabled={!canEditTask}
        onClick={(event) => stopEvent(event, () => openInlineEditor(task, "status"))}
        type="button"
      >
        <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
        {renderInlineFeedback(task.id, "status")}
      </button>
    );
  }

  function renderProgressCell(task) {
    const isEditing = editingCell?.taskId === task.id && editingCell?.field === "progress";
    const draftValue = getDraftValue(task, "progress");

    if (isEditing && canEditTask) {
      return (
        <div
          className="pm-project-gantt-inline-editor"
          onClick={(event) => event.stopPropagation()}
          onDoubleClick={(event) => event.stopPropagation()}
        >
          <input
            autoFocus
            className="pm-project-gantt-inline-input"
            max="100"
            min="0"
            onChange={(event) =>
              setDraftValues((current) => ({
                ...current,
                [getCellKey(task.id, "progress")]: event.target.value,
              }))
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void commitProgressUpdate(task);
              }
              if (event.key === "Escape") {
                event.preventDefault();
                closeInlineEditor(task.id, "progress");
              }
            }}
            step="1"
            type="number"
            value={draftValue}
          />
          <div className="pm-project-gantt-inline-actions">
            <button
              aria-label="Guardar avance"
              className="pm-project-gantt-inline-icon is-primary"
              onClick={(event) => stopEvent(event, () => void commitProgressUpdate(task))}
              type="button"
            >
              <Check size={12} strokeWidth={2} />
            </button>
            <button
              aria-label="Cancelar edición de avance"
              className="pm-project-gantt-inline-icon"
              onClick={(event) => stopEvent(event, () => closeInlineEditor(task.id, "progress"))}
              type="button"
            >
              <X size={12} strokeWidth={2} />
            </button>
          </div>
          {renderInlineFeedback(task.id, "progress")}
        </div>
      );
    }

    return (
      <button
        className="pm-project-gantt-inline-trigger"
        disabled={!canEditTask}
        onClick={(event) => stopEvent(event, () => openInlineEditor(task, "progress"))}
        type="button"
      >
        <strong>{formatPercent(task.porcentaje_avance)}</strong>
        {renderInlineFeedback(task.id, "progress")}
      </button>
    );
  }

  function renderAssigneeCell(task) {
    const canEditAssignee = canEditTask && availableMembers.length > 0;
    const isEditing = editingCell?.taskId === task.id && editingCell?.field === "assignee";
    const draftValue = getDraftValue(task, "assignee");

    if (isEditing && canEditAssignee) {
      return (
        <div
          className="pm-project-gantt-inline-editor"
          onClick={(event) => event.stopPropagation()}
          onDoubleClick={(event) => event.stopPropagation()}
        >
          <select
            autoFocus
            className="pm-project-gantt-inline-select"
            onChange={(event) => {
              const nextValue = event.target.value;
              setDraftValues((current) => ({
                ...current,
                [getCellKey(task.id, "assignee")]: nextValue,
              }));
              void commitAssigneeUpdate(task, nextValue);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                closeInlineEditor(task.id, "assignee");
              }
            }}
            value={draftValue}
          >
            <option value="">Sin responsable</option>
            {availableMembers.map((member) => (
              <option key={member.usuario_id} value={member.usuario_id}>
                {getMemberDisplayName(member)}
              </option>
            ))}
          </select>
          <button
            aria-label="Cancelar edición de responsable"
            className="pm-project-gantt-inline-icon"
            onClick={(event) => stopEvent(event, () => closeInlineEditor(task.id, "assignee"))}
            type="button"
          >
            <X size={12} strokeWidth={2} />
          </button>
          {renderInlineFeedback(task.id, "assignee")}
        </div>
      );
    }

    if (!canEditAssignee) {
      return <strong>{getTaskAssigneeLabel(task, availableMembers)}</strong>;
    }

    return (
      <button
        className="pm-project-gantt-inline-trigger"
        disabled={!canEditAssignee}
        onClick={(event) => stopEvent(event, () => openInlineEditor(task, "assignee"))}
        type="button"
      >
        <strong>{getTaskAssigneeLabel(task, availableMembers)}</strong>
        {renderInlineFeedback(task.id, "assignee")}
      </button>
    );
  }

  function renderDateCell(task, field) {
    const value = field === "start" ? task?.fecha_inicio : task?.fecha_vencimiento;
    const label = safeDisplayText(formatDate(value), "Sin fecha");
    const title = field === "start" ? "Editar inicio" : "Editar fecha compromiso";

    return (
      <button
        className="pm-project-gantt-date-trigger"
        disabled={!canEditTask}
        onClick={(event) => stopEvent(event, () => onEditTaskDates?.(task.id))}
        title={title}
        type="button"
      >
        <strong>{label}</strong>
      </button>
    );
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
                    {renderAssigneeCell(task)}
                  </div>
                  <div className="pm-project-gantt-cell">
                    {renderStatusCell(task)}
                  </div>
                  <div className="pm-project-gantt-cell">
                    {renderProgressCell(task)}
                  </div>
                  <div className="pm-project-gantt-cell">
                    {renderDateCell(task, "start")}
                  </div>
                  <div className="pm-project-gantt-cell">
                    {renderDateCell(task, "end")}
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
