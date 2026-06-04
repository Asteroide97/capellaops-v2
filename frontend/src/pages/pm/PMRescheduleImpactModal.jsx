import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarRange, GitBranch, Lock, Route } from "lucide-react";

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
  allowDirectApply = true,
  baselineChecking = false,
  baselineInfo = null,
  empresaId,
  initialEnd,
  initialStart,
  mode = "edit",
  onClose,
  onSubmit,
  open,
  projectId,
  proposedEnd = null,
  proposedStart = null,
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
  const [applyDependents, setApplyDependents] = useState(false);

  const hasBaseline = Boolean(baselineInfo?.id);
  const effectiveStart =
    proposedStart ||
    (mode === "suggestion" ? suggestionStart || initialStart : initialStart);
  const effectiveEnd =
    proposedEnd ||
    (mode === "suggestion" ? suggestionEnd || initialEnd : initialEnd);

  useEffect(() => {
    if (!open) {
      return;
    }
    setFechaInicio(toDateInput(effectiveStart));
    setFechaFin(toDateInput(effectiveEnd));
    setApplyDependents(false);
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
      if (fechaFin < fechaInicio) {
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
  const hasDependentsImpact = (impact?.total_affected ?? 0) > 0;
  const canSubmit = Boolean(fechaInicio && fechaFin && !saving && !baselineChecking);
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
  const modalTitle = mode === "drag" ? "Confirmar cambio de fechas" : mode === "suggestion" ? "Aplicar fecha sugerida" : "Editar fechas de tarea";

  async function handleAction(strategy) {
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
      strategy,
    });
  }

  const footer = (
    <div className="inventory-actions inventory-actions-wrap">
      <ActionButton disabled={saving} onClick={onClose} type="button">
        Cancelar
      </ActionButton>
      {allowDirectApply ? (
        <ActionButton disabled={!canSubmit} onClick={() => handleAction("direct")} type="button">
          {saving ? "Aplicando..." : "Aplicar cambio"}
        </ActionButton>
      ) : null}
      {hasBaseline ? (
        <>
          <ActionButton disabled={!canSubmit} onClick={() => handleAction("apply-and-register")} type="button">
            {saving ? "Aplicando..." : "Aplicar y registrar cambio"}
          </ActionButton>
          <ActionButton disabled={!canSubmit} onClick={() => handleAction("register-and-submit")} tone="primary" type="button">
            {saving ? "Enviando..." : "Registrar y enviar a aprobación"}
          </ActionButton>
        </>
      ) : null}
      {!allowDirectApply && !hasBaseline ? (
        <ActionButton disabled={!canSubmit} onClick={() => handleAction("direct")} tone="primary" type="button">
          {saving ? "Aplicando..." : "Aplicar cambio"}
        </ActionButton>
      ) : null}
    </div>
  );

  return (
    <ModalShell
      footer={footer}
      onClose={onClose}
      open={open}
      size="wide"
      subtitle="Confirma el rango de fechas y revisa el impacto sobre las tareas dependientes."
      title={modalTitle}
    >
      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>No se pudo calcular el impacto</strong>
          <p className="table-note">{error}</p>
        </div>
      ) : null}

      {baselineChecking ? (
        <div className="inventory-form-note">
          <strong>Validando línea base</strong>
          <p className="table-note">Espera un momento para determinar si este cambio debe registrarse contra la línea base.</p>
        </div>
      ) : null}

      {hasBaseline ? (
        <div className="inventory-form-note inventory-form-note-warning">
          <strong>Este cambio se comparará contra la línea base actual.</strong>
          <p className="table-note">
            Línea base activa: {safeDisplayText(baselineInfo?.nombre, "Línea base principal")}. No se aplicarán fechas silenciosamente.
          </p>
        </div>
      ) : null}

      {task?.es_critica ? (
        <div className="inventory-form-note inventory-form-note-warning">
          <strong>Esta tarea está en la ruta crítica.</strong>
          <p className="table-note">Cambiar sus fechas puede afectar la fecha final del proyecto.</p>
        </div>
      ) : null}

      {task?.dependency_state?.is_blocked ? (
        <div className="inventory-form-note inventory-form-note-warning">
          <strong>Esta tarea sigue bloqueada.</strong>
          <p className="table-note">{safeDisplayText(task?.dependency_state?.detail, "Completa primero sus prerrequisitos.")}</p>
        </div>
      ) : null}

      <div className="pm-reschedule-stack">
        <div className="inventory-form-note">
          <strong>{normalizePmCopy(safeDisplayText(task?.titulo, "Tarea"))}</strong>
          <p className="table-note">Fechas actuales: {currentRangeCopy}</p>
          <p className="table-note">Fechas propuestas: {nextRangeCopy}</p>
          {suggestionStart || suggestionEnd ? (
            <p className="table-note">
              Sugerido por planeación: {safeDisplayText(formatDate(suggestionStart), "—")} → {safeDisplayText(formatDate(suggestionEnd), "—")}
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

        <label className="pm-impact-toggle">
          <input
            checked={applyDependents}
            onChange={(event) => setApplyDependents(event.target.checked)}
            type="checkbox"
          />
          <span>También reprogramar tareas dependientes</span>
        </label>

        <div className="pm-impact-summary-card">
          <div>
            <strong>Este cambio afecta {impact?.total_affected ?? 0} tareas.</strong>
            <p className="table-note">
              {hasDependentsImpact
                ? `Este cambio afecta ${impact?.total_affected ?? 0} tareas dependientes.`
                : "No hay tareas dependientes afectadas."}
            </p>
          </div>
          <div className="pm-inline-metadata">
            <StatusBadge tone={getTaskStatusTone(task?.estatus)}>{getTaskStatusLabel(task?.estatus)}</StatusBadge>
            {impactLoading ? <StatusBadge tone="info">Calculando...</StatusBadge> : null}
          </div>
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

        {hasBaseline ? (
          <div className="inventory-form-note">
            <strong>Control de cambios</strong>
            <p className="table-note">
              Puedes aplicar este ajuste y registrarlo como cambio, o enviarlo a aprobación sin modificar la tarea todavía.
            </p>
          </div>
        ) : null}
      </div>
    </ModalShell>
  );
}
