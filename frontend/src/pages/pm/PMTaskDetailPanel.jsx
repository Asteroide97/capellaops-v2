import { useEffect, useMemo, useState } from "react";
import { CheckSquare, Clock3, MessageSquare, PackageOpen } from "lucide-react";

import { getPmTask } from "../../api/client";
import {
  ActionButton,
  DataCard,
  EmptyState,
  StatusBadge,
  formatDate,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";
import {
  formatPercent,
  getPriorityLabel,
  getPriorityTone,
  getTaskStatusLabel,
  getTaskStatusTone,
} from "./shared";


export default function PMTaskDetailPanel({
  empresaId,
  materialConsumptions,
  materialPlans,
  onEditTask,
  projectId,
  taskId,
  timeEntries,
  token,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [task, setTask] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadTask() {
      if (!taskId || !token || !empresaId) {
        setTask(null);
        setError("");
        return;
      }

      setLoading(true);
      setError("");
      try {
        const response = await getPmTask({ taskId, token, empresaId });
        if (!cancelled) {
          setTask(response);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message || "No se pudo cargar el detalle de la tarea.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadTask();
    return () => {
      cancelled = true;
    };
  }, [taskId, token, empresaId, projectId]);

  const relatedTimeEntries = useMemo(
    () => (timeEntries ?? []).filter((entry) => entry.tarea_id === taskId),
    [timeEntries, taskId],
  );

  const relatedMaterialPlans = useMemo(
    () => (materialPlans ?? []).filter((plan) => plan.tarea_id === taskId && plan.activo),
    [materialPlans, taskId],
  );

  const relatedMaterialConsumptions = useMemo(
    () => (materialConsumptions ?? []).filter((consumption) => consumption.tarea_id === taskId && consumption.activo),
    [materialConsumptions, taskId],
  );

  const timeSummary = useMemo(
    () =>
      relatedTimeEntries.reduce(
        (accumulator, entry) => ({
          hours: accumulator.hours + Number(entry.horas || 0),
          cost: accumulator.cost + Number(entry.costo_total_snapshot || 0),
        }),
        { hours: 0, cost: 0 },
      ),
    [relatedTimeEntries],
  );

  if (!taskId) {
    return (
      <DataCard subtitle="Selecciona una fila para abrir el contexto operativo." title="Detalle de tarea">
        <EmptyState compact note="Aquí verás subtareas, checklist, comentarios, horas y materiales de la tarea seleccionada." title="Sin tarea seleccionada" />
      </DataCard>
    );
  }

  return (
    <DataCard
      actions={
        <ActionButton disabled={!taskId} onClick={() => onEditTask?.(taskId)} tone="primary" type="button">
          Editar tarea
        </ActionButton>
      }
      subtitle="Panel operativo de la tarea seleccionada."
      title="Detalle de tarea"
    >
      {loading ? <div className="table-note">Cargando detalle de tarea...</div> : null}
      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>No se pudo cargar la tarea</strong>
          <p className="table-note">{error}</p>
        </div>
      ) : null}

      {task ? (
        <div className="pm-task-detail-stack">
          <div className="pm-task-detail-header">
            <div className="pm-task-detail-title">
              <strong>{safeDisplayText(task.titulo)}</strong>
              <div className="pm-inline-metadata">
                <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                <StatusBadge tone={getPriorityTone(task.prioridad)}>{getPriorityLabel(task.prioridad)}</StatusBadge>
                {task.bloqueada ? <StatusBadge tone="danger">Bloqueada</StatusBadge> : null}
              </div>
            </div>
            <div className="pm-task-detail-metrics">
              <div>
                <span>Avance</span>
                <strong>{formatPercent(task.porcentaje_avance)}</strong>
              </div>
              <div>
                <span>Horas reales</span>
                <strong>{formatNumber(timeSummary.hours)}</strong>
              </div>
              <div>
                <span>Costo real</span>
                <strong>{formatMoney(timeSummary.cost)}</strong>
              </div>
            </div>
          </div>

          <div className="pm-task-meta-grid">
            <div>
              <span>Responsable</span>
              <strong>{safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")}</strong>
            </div>
            <div>
              <span>Inicio</span>
              <strong>{safeDisplayText(formatDate(task.fecha_inicio), "—")}</strong>
            </div>
            <div>
              <span>Fin</span>
              <strong>{safeDisplayText(formatDate(task.fecha_vencimiento), "—")}</strong>
            </div>
            <div>
              <span>Horas estimadas</span>
              <strong>{formatNumber(task.estimacion_horas ?? 0)}</strong>
            </div>
          </div>

          <div className="inventory-form-note">
            <strong>Descripción</strong>
            <p className="table-note">{safeDisplayText(task.descripcion, "Sin descripción operativa.")}</p>
          </div>

          <div className="inventory-content-grid inventory-content-grid-2">
            <div className="pm-detail-block">
              <div className="pm-detail-block-header">
                <CheckSquare size={16} strokeWidth={1.9} />
                <strong>Subtareas</strong>
              </div>
              {task.subtasks?.length ? (
                <div className="pm-detail-list">
                  {task.subtasks.map((subtask) => (
                    <div className="pm-detail-list-item" key={subtask.id}>
                      <div>
                        <strong>{safeDisplayText(subtask.titulo)}</strong>
                        <span>{subtask.estatus === "completada" ? "Completada" : "Pendiente"}</span>
                      </div>
                      <StatusBadge tone={subtask.estatus === "completada" ? "success" : "neutral"}>
                        {subtask.estatus === "completada" ? "Completada" : "Pendiente"}
                      </StatusBadge>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState compact note="La tarea aún no tiene subtareas." title="Sin subtareas" />
              )}
            </div>

            <div className="pm-detail-block">
              <div className="pm-detail-block-header">
                <CheckSquare size={16} strokeWidth={1.9} />
                <strong>Checklist</strong>
              </div>
              {task.checklist_items?.length ? (
                <div className="pm-detail-list">
                  {task.checklist_items.map((item) => (
                    <div className="pm-detail-list-item" key={item.id}>
                      <div>
                        <strong>{safeDisplayText(item.titulo)}</strong>
                        <span>{item.completado ? "Completado" : "Pendiente"}</span>
                      </div>
                      <StatusBadge tone={item.completado ? "success" : "neutral"}>
                        {item.completado ? "Completado" : "Pendiente"}
                      </StatusBadge>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState compact note="No hay checklist registrado para esta tarea." title="Sin checklist" />
              )}
            </div>

            <div className="pm-detail-block">
              <div className="pm-detail-block-header">
                <Clock3 size={16} strokeWidth={1.9} />
                <strong>Horas asociadas</strong>
              </div>
              {relatedTimeEntries.length ? (
                <div className="pm-detail-list">
                  {relatedTimeEntries.slice(0, 5).map((entry) => (
                    <div className="pm-detail-list-item" key={entry.id}>
                      <div>
                        <strong>{safeDisplayText(entry.usuario_nombre_snapshot, "Registro manual")}</strong>
                        <span>{safeDisplayText(formatDate(entry.fecha), "—")} · {formatNumber(entry.horas)} h</span>
                      </div>
                      <strong>{formatMoney(entry.costo_total_snapshot)}</strong>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState compact note="Todavía no hay horas registradas para esta tarea." title="Sin horas" />
              )}
            </div>

            <div className="pm-detail-block">
              <div className="pm-detail-block-header">
                <PackageOpen size={16} strokeWidth={1.9} />
                <strong>Materiales relacionados</strong>
              </div>
              {relatedMaterialPlans.length || relatedMaterialConsumptions.length ? (
                <div className="pm-detail-list">
                  {relatedMaterialPlans.slice(0, 3).map((plan) => (
                    <div className="pm-detail-list-item" key={`plan-${plan.id}`}>
                      <div>
                        <strong>{safeDisplayText(plan.material_nombre_snapshot)}</strong>
                        <span>Planificado: {formatNumber(plan.cantidad_planificada)} · Pendiente: {formatNumber(plan.cantidad_pendiente)}</span>
                      </div>
                      <strong>{formatMoney(plan.costo_total_estimado)}</strong>
                    </div>
                  ))}
                  {relatedMaterialConsumptions.slice(0, 3).map((consumption) => (
                    <div className="pm-detail-list-item" key={`consumption-${consumption.id}`}>
                      <div>
                        <strong>{safeDisplayText(consumption.material_nombre_snapshot)}</strong>
                        <span>Consumido: {formatNumber(consumption.cantidad_consumida)} · {safeDisplayText(formatDate(consumption.created_at), "—")}</span>
                      </div>
                      <strong>{formatMoney(consumption.costo_total_snapshot)}</strong>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState compact note="No hay materiales ligados a esta tarea. La relación por tarea sigue siendo gradual." title="Sin materiales" />
              )}
            </div>
          </div>

          <div className="pm-detail-block">
            <div className="pm-detail-block-header">
              <MessageSquare size={16} strokeWidth={1.9} />
              <strong>Comentarios</strong>
            </div>
            {task.comments?.length ? (
              <div className="pm-comment-list">
                {task.comments.map((comment) => (
                  <article className="pm-comment-card" key={comment.id}>
                    <div className="pm-comment-head">
                      <strong>{safeDisplayText(comment.created_by_nombre_snapshot, "Usuario")}</strong>
                      <span className="inventory-cell-sub">{safeDisplayText(formatDate(comment.created_at), "—")}</span>
                    </div>
                    <p>{safeDisplayText(comment.body, "")}</p>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState compact note="La tarea aún no tiene comentarios." title="Sin comentarios" />
            )}
          </div>
        </div>
      ) : null}
    </DataCard>
  );
}
