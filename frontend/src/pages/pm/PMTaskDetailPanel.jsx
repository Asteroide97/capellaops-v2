import { useEffect, useMemo, useState } from "react";
import { CheckSquare, Clock3, Link2, Lock, MessageSquare, PackageOpen, Plus } from "lucide-react";

import {
  createPmTaskDependency,
  deactivatePmTaskDependency,
  getPmTask,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  EmptyState,
  Field,
  FormGrid,
  ModalShell,
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
  normalizePmCopy,
} from "./shared";


const defaultDependencyForm = {
  depende_de_tarea_id: "",
  tipo_dependencia: "finish_to_start",
  bloqueante: true,
  notas: "",
};


export default function PMTaskDetailPanel({
  empresaId,
  materialConsumptions,
  materialPlans,
  onDependenciesChanged,
  onEditTask,
  onSelectTask,
  projectId,
  taskId,
  taskDependencyContext,
  taskSummary,
  tasks,
  timeEntries,
  token,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [task, setTask] = useState(null);
  const [dependencyModalOpen, setDependencyModalOpen] = useState(false);
  const [dependencyForm, setDependencyForm] = useState(defaultDependencyForm);
  const [savingDependency, setSavingDependency] = useState(false);
  const dependencies = taskDependencyContext ?? {
    blocked: false,
    dependencies: [],
    blockers: [],
    successors: [],
    is_blocked: false,
    title: "",
    detail: "",
  };

  useEffect(() => {
    let cancelled = false;

    async function loadTask() {
      if (!taskId || !token || !empresaId) {
        setTask(null);
        setError("");
        setSuccess("");
        return;
      }

      if (taskSummary?.id === taskId) {
        setTask((current) => ({
          subtasks: current?.id === taskId ? current.subtasks ?? [] : [],
          checklist_items: current?.id === taskId ? current.checklist_items ?? [] : [],
          comments: current?.id === taskId ? current.comments ?? [] : [],
          ...current,
          ...taskSummary,
          is_blocked: taskSummary.is_blocked,
          blockers: taskSummary.blockers ?? [],
        }));
      }

      setLoading(!(taskSummary?.id === taskId));
      setError("");
      try {
        const taskResponse = await getPmTask({ taskId, token, empresaId });
        if (!cancelled) {
          setTask({
            ...taskResponse,
            is_blocked: taskSummary?.is_blocked ?? taskResponse.is_blocked,
            blockers: taskSummary?.blockers ?? taskResponse.blockers ?? [],
          });
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

  useEffect(() => {
    if (!taskSummary?.id) {
      return;
    }
    setTask((current) => {
      if (!current || current.id !== taskSummary.id) {
        return current;
      }
      return {
        ...current,
        titulo: taskSummary.titulo ?? current.titulo,
        descripcion: taskSummary.descripcion ?? current.descripcion,
        estatus: taskSummary.estatus ?? current.estatus,
        prioridad: taskSummary.prioridad ?? current.prioridad,
        porcentaje_avance: taskSummary.porcentaje_avance ?? current.porcentaje_avance,
        asignado_nombre_snapshot: taskSummary.asignado_nombre_snapshot ?? current.asignado_nombre_snapshot,
        fecha_inicio: taskSummary.fecha_inicio ?? current.fecha_inicio,
        fecha_vencimiento: taskSummary.fecha_vencimiento ?? current.fecha_vencimiento,
        estimacion_horas: taskSummary.estimacion_horas ?? current.estimacion_horas,
        is_blocked: taskSummary.is_blocked,
        blockers: taskSummary.blockers ?? [],
      };
    });
  }, [taskSummary]);

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

  const dependencyItems = useMemo(
    () => dependencies?.dependencies ?? [],
    [dependencies],
  );

  const pendingBlockers = useMemo(
    () =>
      dependencyItems
        .filter((dependency) => {
          const status = String(dependency?.resolved_status ?? dependency?.depende_de_tarea_estatus ?? "").toLowerCase();
          return dependency?.bloqueante !== false && status !== "completada";
        })
        .map((dependency) => ({
          tarea_id: dependency.depende_de_tarea_id,
          titulo: normalizePmCopy(safeDisplayText(dependency.resolved_title ?? dependency.depende_de_tarea_titulo)),
          estatus: String(dependency?.resolved_status ?? dependency?.depende_de_tarea_estatus ?? "").toLowerCase(),
        })),
    [dependencyItems],
  );

  const hasDependencies = dependencyItems.length > 0;
  const isBlocked = Boolean(dependencies?.blocked ?? dependencies?.is_blocked ?? pendingBlockers.length > 0) || pendingBlockers.length > 0;
  const completedDependencyTitles = useMemo(
    () => dependencyItems.map((dependency) => normalizePmCopy(safeDisplayText(dependency.resolved_title ?? dependency.depende_de_tarea_titulo))).filter(Boolean),
    [dependencyItems],
  );

  const availablePrerequisiteOptions = useMemo(
    () => (tasks ?? []).filter((candidate) => candidate.id !== taskId && candidate.activo),
    [tasks, taskId],
  );

  const timeSummary = useMemo(
    () => relatedTimeEntries.reduce(
      (accumulator, entry) => ({
        hours: accumulator.hours + Number(entry.horas || 0),
        cost: accumulator.cost + Number(entry.costo_total_snapshot || 0),
      }),
      { hours: 0, cost: 0 },
    ),
    [relatedTimeEntries],
  );

  function closeDependencyModal() {
    if (savingDependency) {
      return;
    }
    setDependencyModalOpen(false);
    setDependencyForm(defaultDependencyForm);
  }

  function openDependencyModal() {
    if (!taskId) {
      setError("Primero crea o selecciona una tarea.");
      return;
    }
    setError("");
    setDependencyForm({
      ...defaultDependencyForm,
      depende_de_tarea_id: availablePrerequisiteOptions[0]?.id ?? "",
    });
    setDependencyModalOpen(true);
  }

  async function refreshDependencyContext() {
    if (!taskId || !token || !empresaId) {
      return;
    }
    const taskResponse = await getPmTask({ taskId, token, empresaId });
    setTask((current) => ({
      ...taskResponse,
      is_blocked: taskSummary?.is_blocked ?? current?.is_blocked ?? taskResponse.is_blocked,
      blockers: taskSummary?.blockers ?? current?.blockers ?? taskResponse.blockers ?? [],
    }));
    await onDependenciesChanged?.();
  }

  async function handleCreateDependency(event) {
    event.preventDefault();
    if (!taskId) {
      return;
    }
    setSavingDependency(true);
    setError("");
    setSuccess("");
    try {
      await createPmTaskDependency({
        taskId,
        token,
        empresaId,
        payload: {
          depende_de_tarea_id: dependencyForm.depende_de_tarea_id,
          tipo_dependencia: "finish_to_start",
          lag_dias: 0,
          bloqueante: Boolean(dependencyForm.bloqueante),
          notas: dependencyForm.notas.trim() || null,
        },
      });
      setSuccess("Prerrequisito agregado.");
      closeDependencyModal();
      await refreshDependencyContext();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el prerrequisito.");
    } finally {
      setSavingDependency(false);
    }
  }

  async function handleDeactivateDependency(dependencyId) {
    setSavingDependency(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmTaskDependency({ dependencyId, token, empresaId });
      setSuccess("Prerrequisito desactivado.");
      await refreshDependencyContext();
    } catch (requestError) {
      setError(requestError.message || "No se pudo quitar el prerrequisito.");
    } finally {
      setSavingDependency(false);
    }
  }

  if (!taskId) {
    return (
      <DataCard subtitle="Selecciona una fila para abrir el contexto operativo." title="Detalle de tarea">
        <EmptyState compact note="Aquí verás descripción, checklist, comentarios, horas, materiales y prerrequisitos de la tarea seleccionada." title="Sin tarea seleccionada" />
      </DataCard>
    );
  }

  return (
    <>
      <DataCard
        actions={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={!taskId} onClick={() => onEditTask?.(taskId)} tone="primary" type="button">
              Editar tarea
            </ActionButton>
            <ActionButton disabled={!taskId} onClick={() => onEditTask?.(taskId)} type="button">
              Editar prerrequisitos
            </ActionButton>
            <ActionButton disabled={!taskId} icon={<Plus size={16} strokeWidth={1.9} />} onClick={openDependencyModal} type="button">
              Agregar prerrequisito
            </ActionButton>
          </div>
        )}
        subtitle="Panel operativo de la tarea seleccionada."
        title="Detalle de tarea"
      >
        {loading ? <div className="table-note">Cargando detalle de tarea...</div> : null}
        {(error || success) ? (
          <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
            <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
            <p className="table-note">{error || success}</p>
          </div>
        ) : null}

        {task ? (
          <div className="pm-task-detail-stack">
            <div className="pm-task-detail-header">
              <div className="pm-task-detail-title">
                <strong>{normalizePmCopy(safeDisplayText(task.titulo))}</strong>
                <div className="pm-inline-metadata">
                  <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                  <StatusBadge tone={getPriorityTone(task.prioridad)}>{getPriorityLabel(task.prioridad)}</StatusBadge>
                  {isBlocked ? <StatusBadge tone="warning">Bloqueada</StatusBadge> : null}
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

            {hasDependencies && pendingBlockers.length > 0 ? (
              <div className="inventory-form-note inventory-form-note-warning">
                <strong>Tarea bloqueada</strong>
                <p className="table-note">
                  {normalizePmCopy(safeDisplayText(task.titulo))} depende de{" "}
                  {pendingBlockers.map((item) => item.titulo).join(", ")}. Completa esos prerrequisitos para desbloquearla.
                </p>
              </div>
            ) : hasDependencies ? (
              <div className="inventory-form-note inventory-form-note-success">
                <strong>Prerrequisitos completados</strong>
                <p className="table-note">
                  {completedDependencyTitles.join(", ")}
                </p>
              </div>
            ) : null}

            <div className="pm-task-meta-grid">
              <div>
                <span>Responsable</span>
                <strong>{safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")}</strong>
              </div>
              <div>
                <span>Inicio</span>
                <strong>{safeDisplayText(formatDate(task.fecha_inicio), "-")}</strong>
              </div>
              <div>
                <span>Fin</span>
                <strong>{safeDisplayText(formatDate(task.fecha_vencimiento), "-")}</strong>
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
                  <Link2 size={16} strokeWidth={1.9} />
                  <strong>Prerrequisitos</strong>
                  <ActionButton onClick={() => onEditTask?.(taskId)} size="sm" type="button">
                    Editar prerrequisitos
                  </ActionButton>
                </div>
                {hasDependencies ? (
                  <div className="pm-detail-list">
                    {dependencyItems.map((dependency) => (
                      <div className="pm-detail-list-item" key={dependency.id}>
                        <div>
                          <strong>{normalizePmCopy(safeDisplayText(dependency.resolved_title ?? dependency.depende_de_tarea_titulo))}</strong>
                          <span>Debe completarse antes · {safeDisplayText(getTaskStatusLabel(dependency.resolved_status ?? dependency.depende_de_tarea_estatus), dependency.resolved_status ?? dependency.depende_de_tarea_estatus)}</span>
                        </div>
                        <div className="table-actions">
                          <ActionButton onClick={() => onSelectTask?.(dependency.depende_de_tarea_id)} size="sm" type="button">
                            Ver tarea
                          </ActionButton>
                          <ActionButton className={savingDependency ? "pm-button-loading" : ""} disabled={savingDependency} onClick={() => handleDeactivateDependency(dependency.id)} size="sm" tone="danger" type="button">
                            {savingDependency ? "Quitando..." : "Quitar"}
                          </ActionButton>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState compact note="Esta tarea no tiene prerrequisitos." title="Sin prerrequisitos" />
                )}
              </div>

              <div className="pm-detail-block">
                <div className="pm-detail-block-header">
                  <Lock size={16} strokeWidth={1.9} />
                  <strong>Esta tarea desbloquea</strong>
                </div>
                {(dependencies?.successors?.length ?? 0) ? (
                  <div className="pm-detail-list">
                    {dependencies.successors.map((successor) => (
                      <div className="pm-detail-list-item" key={successor.tarea_id}>
                        <div>
                          <strong>{normalizePmCopy(safeDisplayText(successor.titulo))}</strong>
                          <span>{safeDisplayText(getTaskStatusLabel(successor.estatus), successor.estatus)}</span>
                        </div>
                        <ActionButton onClick={() => onSelectTask?.(successor.tarea_id)} size="sm" type="button">
                          Ver tarea
                        </ActionButton>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState compact note="Ninguna tarea depende todavía de esta." title="Sin sucesoras" />
                )}
              </div>

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
                  <EmptyState compact note="La tarea todavía no tiene subtareas." title="Sin subtareas" />
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
                          <span>{safeDisplayText(formatDate(entry.fecha), "-")} · {formatNumber(entry.horas)} h</span>
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
                          <span>Consumido: {formatNumber(consumption.cantidad_consumida)} · {safeDisplayText(formatDate(consumption.created_at), "-")}</span>
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
                        <span className="inventory-cell-sub">{safeDisplayText(formatDate(comment.created_at), "-")}</span>
                      </div>
                      <p>{safeDisplayText(comment.body, "")}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState compact note="La tarea todavía no tiene comentarios." title="Sin comentarios" />
              )}
            </div>
          </div>
        ) : null}
      </DataCard>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={savingDependency} onClick={closeDependencyModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              disabled={savingDependency || !dependencyForm.depende_de_tarea_id}
              form="pm-task-dependency-form"
              tone="primary"
              type="submit"
            >
              {savingDependency ? "Guardando..." : "Guardar prerrequisito"}
            </ActionButton>
          </div>
        )}
        onClose={closeDependencyModal}
        open={dependencyModalOpen}
        size="medium"
        subtitle="La tarea seleccionada quedará bloqueada hasta que el prerrequisito esté completado."
        title="Agregar prerrequisito"
      >
        <form className="inventory-modal-form" id="pm-task-dependency-form" onSubmit={handleCreateDependency}>
          <FormGrid>
            <Field label="Tarea que debe terminar antes">
              <select
                onChange={(event) => setDependencyForm((current) => ({ ...current, depende_de_tarea_id: event.target.value }))}
                required
                value={dependencyForm.depende_de_tarea_id}
              >
                <option value="">Selecciona una tarea</option>
                {availablePrerequisiteOptions.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {safeDisplayText(candidate.titulo)} · {safeDisplayText(getTaskStatusLabel(candidate.estatus), candidate.estatus)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tipo">
              <input disabled value="Debe completarse antes de iniciar esta tarea" />
            </Field>
            <Field label="Bloqueante">
              <label className="inventory-checkbox">
                <input
                  checked={dependencyForm.bloqueante}
                  onChange={(event) => setDependencyForm((current) => ({ ...current, bloqueante: event.target.checked }))}
                  type="checkbox"
                />
                <span>Impedir avance si el prerrequisito no está completado</span>
              </label>
            </Field>
            <Field label="Notas">
              <textarea
                onChange={(event) => setDependencyForm((current) => ({ ...current, notas: event.target.value }))}
                rows={4}
                value={dependencyForm.notas}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>
    </>
  );
}
