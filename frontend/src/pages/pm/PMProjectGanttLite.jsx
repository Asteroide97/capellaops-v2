import { useMemo } from "react";
import {
  AlertTriangle,
  CalendarRange,
  Eye,
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

function getTaskDateRange(task) {
  const startValue =
    task?.fecha_inicio ||
    task?.schedule_suggestion?.fecha_inicio_sugerida ||
    task?.fecha_vencimiento;
  const endValue =
    task?.fecha_vencimiento ||
    task?.schedule_suggestion?.fecha_fin_sugerida ||
    task?.fecha_inicio;

  if (!startValue && !endValue) {
    return "Sin fechas definidas";
  }

  return `${safeDisplayText(formatDate(startValue), "—")} → ${safeDisplayText(formatDate(endValue), "—")}`;
}

function getTaskSortValue(task) {
  const rawValue =
    task?.fecha_inicio ||
    task?.fecha_vencimiento ||
    task?.schedule_suggestion?.fecha_inicio_sugerida ||
    task?.schedule_suggestion?.fecha_fin_sugerida;

  if (!rawValue) {
    return Number.MAX_SAFE_INTEGER;
  }

  const timestamp = new Date(rawValue).getTime();
  return Number.isNaN(timestamp) ? Number.MAX_SAFE_INTEGER : timestamp;
}

function getDependencySummary(task) {
  const dependencyState = task?.dependency_state ?? {};
  const blockerTitles = dependencyState?.blockers?.map((item) => normalizePmCopy(safeDisplayText(item?.titulo))).filter(Boolean) ?? [];
  const dependencyTitles = dependencyState?.dependencies
    ?.map((item) => normalizePmCopy(safeDisplayText(item?.resolved_title ?? item?.depende_de_tarea_titulo)))
    .filter(Boolean) ?? [];

  if (blockerTitles.length > 0) {
    return `Depende de: ${blockerTitles.join(", ")}`;
  }

  if (dependencyTitles.length > 0) {
    return `Prerrequisitos completados: ${dependencyTitles.join(", ")}`;
  }

  return "Prerrequisitos completados: —";
}

function getStatusGroupKey(task) {
  const status = String(task?.estatus ?? "").toLowerCase();
  if (status === "completada") {
    return "completed";
  }
  if (status === "en_progreso" || status === "en_revision") {
    return "active";
  }
  return "pending";
}

function getStatusGroups(tasks) {
  const groups = {
    active: {
      key: "active",
      title: "En progreso",
      items: [],
    },
    pending: {
      key: "pending",
      title: "Pendientes",
      items: [],
    },
    completed: {
      key: "completed",
      title: "Completadas",
      items: [],
    },
  };

  tasks.forEach((task) => {
    groups[getStatusGroupKey(task)].items.push(task);
  });

  return Object.values(groups).filter((group) => group.items.length > 0);
}

export default function PMProjectGanttLite({
  onApplySuggestedDates,
  onEditTaskDates,
  onSelectTask,
  onViewTaskDetail,
  selectedTaskId,
  taskActionLoading = {},
  tasks = [],
}) {
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

  const groupedTasks = useMemo(() => getStatusGroups(sortedTasks), [sortedTasks]);

  if (tasks.length === 0) {
    return (
      <DataCard
        className="pm-workplan-gantt-wide"
        subtitle="Aquí verás tareas, fechas, dependencias y sugerencias de reprogramación."
        title="Cronograma del proyecto"
      >
        <EmptyState compact note="Crea la primera tarea para ver el cronograma del proyecto." title="Sin tareas" />
      </DataCard>
    );
  }

  return (
    <DataCard
      className="pm-workplan-gantt-wide"
      subtitle="Consulta fechas, dependencias, ruta crítica, bloqueos y sugerencias de reprogramación."
      title="Cronograma del proyecto"
    >
      <div className="pm-project-timeline">
        {groupedTasks.map((group) => (
          <section className="pm-project-timeline-group" key={group.key}>
            <div className="pm-project-timeline-group-head">
              <strong>{group.title}</strong>
              <span>{group.items.length} tarea{group.items.length === 1 ? "" : "s"}</span>
            </div>

            <div className="pm-project-timeline-grid">
              {group.items.map((task) => {
                const dependencyState = task?.dependency_state ?? {};
                const outOfSequence = Boolean(task?.schedule_suggestion?.fuera_de_secuencia);
                const blocked = Boolean(dependencyState?.is_blocked ?? dependencyState?.blocked);
                const completed = String(task?.estatus ?? "").toLowerCase() === "completada";
                const selected = selectedTaskId === task.id;
                const editingDates = Boolean(taskActionLoading?.[`${task.id}:dates`]);
                const applyingSuggestion = Boolean(taskActionLoading?.[`${task.id}:apply-suggestion`]);
                const timelineTone = completed
                  ? "is-completed"
                  : blocked
                    ? "is-blocked"
                    : task?.es_critica
                      ? "is-critical"
                      : "is-default";

                return (
                  <article
                    className={`pm-project-timeline-card ${timelineTone} ${selected ? "is-selected" : ""}`}
                    key={task.id}
                  >
                    <div className="pm-project-timeline-card-header">
                      <div>
                        <strong>{normalizePmCopy(safeDisplayText(task.titulo))}</strong>
                        <div className="pm-project-timeline-dates">
                          <CalendarRange size={14} strokeWidth={1.9} />
                          <span>{getTaskDateRange(task)}</span>
                        </div>
                      </div>
                      <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                    </div>

                    <div className="pm-project-timeline-badges">
                      <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                      <StatusBadge tone="neutral">{formatPercent(task.porcentaje_avance)}%</StatusBadge>
                      {task?.es_critica ? (
                        <StatusBadge tone="danger">
                          <Route size={12} strokeWidth={1.9} />
                          En ruta crítica
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
                      {!blocked && (dependencyState?.dependencies?.length ?? 0) > 0 ? (
                        <StatusBadge tone="success">Prerrequisitos completados</StatusBadge>
                      ) : null}
                    </div>

                    <div className="pm-project-timeline-dependencies">
                      <Link2 size={14} strokeWidth={1.9} />
                      <span>{getDependencySummary(task)}</span>
                    </div>

                    {outOfSequence ? (
                      <div className="pm-project-timeline-suggestion">
                        <Sparkles size={14} strokeWidth={1.9} />
                        <div>
                          <strong>
                            Sugerido: {safeDisplayText(formatDate(task?.schedule_suggestion?.fecha_inicio_sugerida), "—")} →{" "}
                            {safeDisplayText(formatDate(task?.schedule_suggestion?.fecha_fin_sugerida), "—")}
                          </strong>
                          {task?.schedule_suggestion?.razon ? (
                            <span>{safeDisplayText(task.schedule_suggestion.razon)}</span>
                          ) : null}
                        </div>
                      </div>
                    ) : null}

                    <div className="pm-project-timeline-actions">
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
                        type="button"
                      >
                        Ver detalle
                      </ActionButton>
                      {!completed ? (
                        <ActionButton
                          className={editingDates ? "pm-button-loading" : ""}
                          disabled={editingDates || applyingSuggestion}
                          icon={<Pencil size={14} strokeWidth={1.9} />}
                          onClick={() => onEditTaskDates?.(task.id)}
                          size="sm"
                          type="button"
                        >
                          {editingDates ? "Guardando..." : "Editar fechas"}
                        </ActionButton>
                      ) : null}
                      {outOfSequence ? (
                        <ActionButton
                          className={applyingSuggestion ? "pm-button-loading" : ""}
                          disabled={editingDates || applyingSuggestion}
                          icon={<Sparkles size={14} strokeWidth={1.9} />}
                          onClick={() => onApplySuggestedDates?.(task.id)}
                          size="sm"
                          tone="primary"
                          type="button"
                        >
                          {applyingSuggestion ? "Aplicando..." : "Aplicar sugerencia"}
                        </ActionButton>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </DataCard>
  );
}
