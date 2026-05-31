import { CalendarRange } from "lucide-react";

import { DataCard, EmptyState, formatDate, safeDisplayText } from "../inventory/shared";
import { formatPercent, getTaskStatusTone } from "./shared";


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
  const startValue = task?.fecha_inicio || task?.fecha_vencimiento;
  const endValue = task?.fecha_vencimiento || task?.fecha_inicio;
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
  const scale = totalDays <= 28 ? "days" : "weeks";

  if (scale === "days") {
    const markers = Array.from({ length: totalDays }, (_, index) => {
      const date = addDays(minDate, index);
      return {
        key: date.toISOString(),
        label: new Intl.DateTimeFormat("es-MX", { day: "2-digit" }).format(date),
        meta: new Intl.DateTimeFormat("es-MX", { month: "short" }).format(date),
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


export default function PMProjectGanttLite({ tasks, selectedTaskId, onSelectTask }) {
  const timeline = buildTimeline(tasks);

  if ((tasks ?? []).length === 0) {
    return (
      <DataCard subtitle="Las barras aparecerán cuando existan tareas." title="Línea de tiempo">
        <EmptyState compact note="Crea la primera tarea para ver la vista tipo Gantt." title="Sin tareas" />
      </DataCard>
    );
  }

  return (
    <DataCard
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
              return (
                <button
                  className={`pm-gantt-row ${isSelected ? "is-selected" : ""}`}
                  key={task.id}
                  onClick={() => onSelectTask?.(task.id)}
                  type="button"
                >
                  <div className="pm-gantt-row-head">
                    <span className={`status-badge ${getTaskStatusTone(task.estatus)}`}>{safeDisplayText(task.titulo)}</span>
                    <span className="table-note">{barStyle ? formatDate(task.fecha_vencimiento || task.fecha_inicio) : "Sin fechas"}</span>
                  </div>
                  <div
                    className={`pm-gantt-track pm-gantt-track-${timeline.scale}`}
                    style={{ gridTemplateColumns: `repeat(${timeline.markers.length}, minmax(${timeline.scale === "days" ? "3.25rem" : "6rem"}, 1fr))` }}
                  >
                    {timeline.markers.map((marker) => (
                      <span className="pm-gantt-cell" key={`${task.id}-${marker.key}`} />
                    ))}
                    {barStyle ? (
                      <div className={`pm-gantt-bar ${getTaskStatusTone(task.estatus)}`} style={barStyle}>
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
                </button>
              );
            })}
          </div>
        </div>
      )}
    </DataCard>
  );
}
