import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarRange, Route } from "lucide-react";

import { getPmTaskRescheduleImpact } from "../../api/client";
import {
  ActionButton,
  EmptyState,
  Field,
  ModalShell,
  StatusBadge,
  formatDate,
  safeDisplayText,
} from "../inventory/shared";
import { getTaskStatusLabel, getTaskStatusTone, normalizePmCopy } from "./shared";

function toDateInput(value) {
  return value ? String(value).slice(0, 10) : "";
}

export default function PMRescheduleImpactModal({
  empresaId,
  initialEnd,
  initialStart,
  mode = "edit",
  onClose,
  onSubmit,
  open,
  projectId,
  saving = false,
  suggestionEnd,
  suggestionStart,
  task,
  token,
}) {
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");
  const [impact, setImpact] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [error, setError] = useState("");

  const effectiveStart = mode === "suggestion" ? (suggestionStart || initialStart) : initialStart;
  const effectiveEnd = mode === "suggestion" ? (suggestionEnd || initialEnd) : initialEnd;

  useEffect(() => {
    if (!open) {
      return;
    }
    setFechaInicio(toDateInput(effectiveStart));
    setFechaFin(toDateInput(effectiveEnd));
    setImpact(null);
    setError("");
  }, [effectiveEnd, effectiveStart, open]);

  useEffect(() => {
    let cancelled = false;

    async function loadImpact() {
      if (!open || !projectId || !task?.id || !token || !empresaId || !fechaInicio || !fechaFin) {
        setImpact(null);
        return;
      }
      setImpactLoading(true);
      setError("");
      try {
        const response = await getPmTaskRescheduleImpact({
          projectId,
          taskId: task.id,
          token,
          empresaId,
          params: {
            fecha_inicio: fechaInicio,
            fecha_fin: fechaFin,
          },
        });
        if (!cancelled) {
          setImpact(response);
        }
      } catch (requestError) {
        if (!cancelled) {
          setImpact(null);
          setError(requestError.message || "No se pudo calcular el impacto.");
        }
      } finally {
        if (!cancelled) {
          setImpactLoading(false);
        }
      }
    }

    loadImpact();
    return () => {
      cancelled = true;
    };
  }, [open, projectId, task?.id, token, empresaId, fechaInicio, fechaFin]);

  const affectedTasks = impact?.affected_tasks ?? [];
  const warnings = impact?.warnings ?? [];
  const canSubmit = Boolean(fechaInicio && fechaFin && !saving);
  const hasDependentsImpact = (impact?.total_affected ?? 0) > 0;
  const modalTitle = mode === "suggestion" ? "Aplicar fecha sugerida" : "Editar fechas de tarea";

  const currentRangeCopy = useMemo(() => {
    const startLabel = safeDisplayText(formatDate(initialStart), "—");
    const endLabel = safeDisplayText(formatDate(initialEnd), "—");
    return `${startLabel} → ${endLabel}`;
  }, [initialEnd, initialStart]);

  const nextRangeCopy = useMemo(() => {
    const startLabel = safeDisplayText(formatDate(fechaInicio), "—");
    const endLabel = safeDisplayText(formatDate(fechaFin), "—");
    return `${startLabel} → ${endLabel}`;
  }, [fechaFin, fechaInicio]);

  async function handleApply(applyDependents) {
    if (!canSubmit) {
      return;
    }
    if (fechaFin < fechaInicio) {
      setError("La fecha final no puede ser anterior a la fecha de inicio.");
      return;
    }
    setError("");
    await onSubmit?.({
      taskId: task.id,
      fecha_inicio: fechaInicio,
      fecha_fin: fechaFin,
      applyDependents,
      mode,
    });
  }

  const footer = (
    <div className="inventory-actions inventory-actions-wrap">
      <ActionButton disabled={saving} onClick={onClose} type="button">
        Cancelar
      </ActionButton>
      <ActionButton disabled={!canSubmit} onClick={() => handleApply(false)} type="button">
        {saving ? "Guardando..." : "Aplicar solo esta tarea"}
      </ActionButton>
      {hasDependentsImpact ? (
        <ActionButton disabled={!canSubmit} onClick={() => handleApply(true)} tone="primary" type="button">
          {saving ? "Aplicando..." : "Aplicar tarea y dependientes"}
        </ActionButton>
      ) : null}
    </div>
  );

  return (
    <ModalShell
      footer={footer}
      onClose={onClose}
      open={open}
      size="lg"
      subtitle="Confirma el rango de fechas y revisa el impacto sobre las tareas dependientes."
      title={modalTitle}
    >
      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>No se pudo calcular el impacto</strong>
          <p className="table-note">{error}</p>
        </div>
      ) : null}

      <div className="pm-reschedule-stack">
        <div className="inventory-form-note">
          <strong>{normalizePmCopy(safeDisplayText(task?.titulo, "Tarea"))}</strong>
          <p className="table-note">Actual: {currentRangeCopy}</p>
          {suggestionStart || suggestionEnd ? (
            <p className="table-note">
              Sugerido: {safeDisplayText(formatDate(suggestionStart), "—")} → {safeDisplayText(formatDate(suggestionEnd), "—")}
            </p>
          ) : null}
        </div>

        <div className="inventory-content-grid inventory-content-grid-2">
          <Field label="Inicio">
            <input onChange={(event) => setFechaInicio(event.target.value)} type="date" value={fechaInicio} />
          </Field>
          <Field label="Fin">
            <input onChange={(event) => setFechaFin(event.target.value)} type="date" value={fechaFin} />
          </Field>
        </div>

        <div className="inventory-form-note">
          <strong>Nuevas fechas</strong>
          <p className="table-note">{nextRangeCopy}</p>
        </div>

        <div className="pm-impact-summary-card">
          <div>
            <strong>Este cambio afecta {impact?.total_affected ?? 0} tareas.</strong>
            <p className="table-note">
              {hasDependentsImpact
                ? `Este cambio afecta ${impact?.total_affected ?? 0} tareas dependientes.`
                : "No hay tareas dependientes afectadas."}
            </p>
          </div>
          {impactLoading ? <StatusBadge tone="info">Calculando...</StatusBadge> : null}
        </div>

        {warnings.length > 0 ? (
          <div className="inventory-form-note inventory-form-note-warning">
            <strong>Advertencias</strong>
            <div className="pm-warning-list">
              {warnings.map((warning) => (
                <div className="pm-warning-list-item" key={warning}>
                  <AlertTriangle size={14} strokeWidth={1.9} />
                  <span>{warning}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="pm-impact-list">
          <div className="pm-detail-block-header">
            <Route size={16} strokeWidth={1.9} />
            <strong>Tareas afectadas</strong>
          </div>
          {impactLoading ? (
            <div className="table-note">Calculando impacto...</div>
          ) : affectedTasks.length === 0 ? (
            <EmptyState compact note="No hay tareas dependientes que deban moverse." title="Sin impacto adicional" />
          ) : (
            <div className="pm-detail-list">
              {affectedTasks.map((item) => (
                <div className="pm-detail-list-item" key={item.task_id}>
                  <div>
                    <strong>{normalizePmCopy(safeDisplayText(item.titulo))}</strong>
                    <span>
                      {safeDisplayText(formatDate(item.fecha_inicio_actual), "—")} → {safeDisplayText(formatDate(item.fecha_fin_actual), "—")}
                      {" · "}
                      Sugerido: {safeDisplayText(formatDate(item.fecha_inicio_sugerida), "—")} → {safeDisplayText(formatDate(item.fecha_fin_sugerida), "—")}
                    </span>
                  </div>
                  <div className="pm-inline-metadata">
                    <StatusBadge tone={getTaskStatusTone(item.estatus)}>{getTaskStatusLabel(item.estatus)}</StatusBadge>
                    <StatusBadge tone="warning">
                      <CalendarRange size={12} strokeWidth={1.9} />
                      Reprogramar
                    </StatusBadge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </ModalShell>
  );
}
