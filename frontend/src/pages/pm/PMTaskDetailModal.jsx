import { useEffect, useMemo, useState } from "react";
import { CheckSquare, Link2, ListChecks, Lock, MessageSquare } from "lucide-react";

import {
  createPmChecklistItem,
  createPmSubtask,
  createPmTask,
  createPmTaskComment,
  createPmTaskDependency,
  deactivatePmTaskDependency,
  getPmTask,
  getPmTaskDependencies,
  updatePmChecklistItem,
  updatePmSubtask,
  updatePmTask,
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
  safeDisplayText,
} from "../inventory/shared";
import {
  getPriorityLabel,
  getPriorityTone,
  getTaskStatusLabel,
  getTaskStatusTone,
  priorityOptions,
  taskStatusOptions,
} from "./shared";


const defaultTaskForm = {
  titulo: "",
  descripcion: "",
  estatus: "pendiente",
  prioridad: "media",
  asignado_user_id: "",
  asignado_nombre_snapshot: "",
  fecha_inicio: "",
  fecha_vencimiento: "",
  estimacion_horas: "",
  porcentaje_avance: "0",
  orden: "0",
  bloqueada: false,
  requiere_materiales: false,
  requiere_compra: false,
  requiere_venta_pos: false,
  requiere_factura: false,
};

const emptyDependencyContext = {
  dependencies: [],
  blockers: [],
  successors: [],
  is_blocked: false,
};

const advancedStatuses = new Set(["en_progreso", "en_revision", "completada"]);


function getErrorMessage(error, fallback) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}


function taskToForm(task) {
  if (!task) {
    return defaultTaskForm;
  }

  return {
    titulo: task.titulo ?? "",
    descripcion: task.descripcion ?? "",
    estatus: task.estatus ?? "pendiente",
    prioridad: task.prioridad ?? "media",
    asignado_user_id: task.asignado_user_id ?? "",
    asignado_nombre_snapshot: task.asignado_nombre_snapshot ?? "",
    fecha_inicio: task.fecha_inicio ?? "",
    fecha_vencimiento: task.fecha_vencimiento ?? "",
    estimacion_horas: task.estimacion_horas ?? "0",
    porcentaje_avance: task.porcentaje_avance ?? "0",
    orden: task.orden ?? "0",
    bloqueada: Boolean(task.bloqueada),
    requiere_materiales: Boolean(task.requiere_materiales),
    requiere_compra: Boolean(task.requiere_compra),
    requiere_venta_pos: Boolean(task.requiere_venta_pos),
    requiere_factura: Boolean(task.requiere_factura),
  };
}


function toTaskPayload(form) {
  const assignedId = form.asignado_user_id || null;
  return {
    titulo: form.titulo.trim(),
    descripcion: form.descripcion.trim() || null,
    estatus: form.estatus,
    prioridad: form.prioridad,
    asignado_user_id: assignedId,
    asignado_nombre_snapshot: assignedId ? null : form.asignado_nombre_snapshot.trim() || null,
    fecha_inicio: form.fecha_inicio || null,
    fecha_vencimiento: form.fecha_vencimiento || null,
    estimacion_horas: form.estimacion_horas === "" ? 0 : Number(form.estimacion_horas),
    porcentaje_avance: form.porcentaje_avance === "" ? 0 : Number(form.porcentaje_avance),
    orden: form.orden === "" ? 0 : Number(form.orden),
    bloqueada: Boolean(form.bloqueada),
    requiere_materiales: Boolean(form.requiere_materiales),
    requiere_compra: Boolean(form.requiere_compra),
    requiere_venta_pos: Boolean(form.requiere_venta_pos),
    requiere_factura: Boolean(form.requiere_factura),
    activo: true,
  };
}


export default function PMTaskDetailModal({
  empresaId,
  memberOptions,
  onClose,
  onSaved,
  open,
  projectId,
  taskId,
  tasks = [],
  token,
}) {
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState(defaultTaskForm);
  const [newSubtask, setNewSubtask] = useState("");
  const [newChecklistItem, setNewChecklistItem] = useState("");
  const [newComment, setNewComment] = useState("");
  const [dependencyContext, setDependencyContext] = useState(emptyDependencyContext);
  const [selectedPrerequisiteIds, setSelectedPrerequisiteIds] = useState([]);

  const currentTaskId = task?.id ?? taskId ?? null;

  const memberSelectOptions = useMemo(
    () =>
      (memberOptions ?? []).filter((item) => item.activo).map((item) => ({
        value: item.usuario_id || "",
        label: item.nombre_snapshot
          ? `${item.nombre_snapshot}${item.email ? ` - ${item.email}` : ""}`
          : item.email || "Miembro",
      })),
    [memberOptions],
  );

  const availablePrerequisiteOptions = useMemo(
    () =>
      (tasks ?? [])
        .filter((candidate) => candidate.id !== currentTaskId && candidate.activo)
        .map((candidate) => ({
          ...candidate,
          statusLabel: getTaskStatusLabel(candidate.estatus),
        })),
    [tasks, currentTaskId],
  );

  function syncSelectedPrerequisites(nextDependencyContext) {
    setSelectedPrerequisiteIds(
      (nextDependencyContext?.dependencies ?? [])
        .filter((dependency) => dependency.activo !== false)
        .map((dependency) => dependency.depende_de_tarea_id),
    );
  }

  async function refreshTaskContext(nextTaskId) {
    if (!nextTaskId) {
      return null;
    }

    const [taskResponse, dependencyResponse] = await Promise.all([
      getPmTask({ taskId: nextTaskId, token, empresaId }),
      getPmTaskDependencies({ taskId: nextTaskId, token, empresaId }),
    ]);
    setTask(taskResponse);
    setForm(taskToForm(taskResponse));
    setDependencyContext(dependencyResponse ?? emptyDependencyContext);
    syncSelectedPrerequisites(dependencyResponse ?? emptyDependencyContext);
    return taskResponse;
  }

  useEffect(() => {
    let cancelled = false;

    async function loadTask() {
      if (!open) {
        return;
      }

      setError("");
      setSuccess("");
      setNewSubtask("");
      setNewChecklistItem("");
      setNewComment("");

      if (!taskId) {
        setTask(null);
        setForm(defaultTaskForm);
        setDependencyContext(emptyDependencyContext);
        setSelectedPrerequisiteIds([]);
        return;
      }

      setLoading(true);
      try {
        const [taskResponse, dependencyResponse] = await Promise.all([
          getPmTask({ taskId, token, empresaId }),
          getPmTaskDependencies({ taskId, token, empresaId }),
        ]);
        if (!cancelled) {
          setTask(taskResponse);
          setForm(taskToForm(taskResponse));
          setDependencyContext(dependencyResponse ?? emptyDependencyContext);
          syncSelectedPrerequisites(dependencyResponse ?? emptyDependencyContext);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(getErrorMessage(requestError, "No se pudo cargar la tarea."));
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
  }, [open, taskId, token, empresaId]);

  function togglePrerequisite(taskOptionId) {
    setSelectedPrerequisiteIds((current) => (
      current.includes(taskOptionId)
        ? current.filter((item) => item !== taskOptionId)
        : [...current, taskOptionId]
    ));
  }

  function getPendingSelectedPrerequisites() {
    const selectedIds = new Set(selectedPrerequisiteIds);
    return availablePrerequisiteOptions.filter((candidate) => (
      selectedIds.has(candidate.id) && String(candidate.estatus ?? "").toLowerCase() !== "completada"
    ));
  }

  async function syncTaskDependencies(nextTaskId) {
    if (!nextTaskId) {
      return;
    }

    const activeDependencies = (dependencyContext?.dependencies ?? []).filter((dependency) => dependency.activo !== false);
    const selectedIds = new Set(selectedPrerequisiteIds);
    const existingIds = new Set(activeDependencies.map((dependency) => dependency.depende_de_tarea_id));
    const dependenciesToCreate = [...selectedIds].filter((dependencyTaskId) => !existingIds.has(dependencyTaskId));
    const dependenciesToRemove = activeDependencies.filter((dependency) => !selectedIds.has(dependency.depende_de_tarea_id));

    for (const dependencyTaskId of dependenciesToCreate) {
      await createPmTaskDependency({
        taskId: nextTaskId,
        token,
        empresaId,
        payload: {
          depende_de_tarea_id: dependencyTaskId,
          tipo_dependencia: "finish_to_start",
          lag_dias: 0,
          bloqueante: true,
          notas: null,
        },
      });
    }

    for (const dependency of dependenciesToRemove) {
      await deactivatePmTaskDependency({ dependencyId: dependency.id, token, empresaId });
    }

    const dependencyResponse = await getPmTaskDependencies({ taskId: nextTaskId, token, empresaId });
    setDependencyContext(dependencyResponse ?? emptyDependencyContext);
    syncSelectedPrerequisites(dependencyResponse ?? emptyDependencyContext);
  }

  async function reloadTask(nextTaskId = currentTaskId) {
    const nextTask = await refreshTaskContext(nextTaskId);
    if (nextTask) {
      onSaved?.(nextTask);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const pendingPrerequisites = getPendingSelectedPrerequisites();
    if (advancedStatuses.has(form.estatus) && pendingPrerequisites.length > 0) {
      setError(`No puedes avanzar esta tarea porque depende de ${pendingPrerequisites.map((item) => safeDisplayText(item.titulo)).join(", ")}.`);
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const payload = toTaskPayload(form);
      const response = currentTaskId
        ? await updatePmTask({ taskId: currentTaskId, token, empresaId, payload })
        : await createPmTask({ projectId, token, empresaId, payload });
      const nextTaskId = response?.id ?? currentTaskId;
      if (response?.id) {
        setTask(response);
        setForm(taskToForm(response));
      }
      await syncTaskDependencies(nextTaskId);
      const nextTask = await refreshTaskContext(nextTaskId);
      const hasSelectedPrerequisites = selectedPrerequisiteIds.length > 0;
      setSuccess(
        currentTaskId
          ? hasSelectedPrerequisites
            ? "Tarea y prerrequisitos actualizados."
            : "Tarea actualizada."
          : hasSelectedPrerequisites
            ? "Tarea creada con prerrequisitos."
            : "Tarea creada.",
      );
      onSaved?.(nextTask ?? response);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar la tarea."));
    } finally {
      setSaving(false);
    }
  }

  async function handleAddSubtask() {
    if (!currentTaskId || !newSubtask.trim()) {
      return;
    }

    setSaving(true);
    setError("");
    try {
      await createPmSubtask({
        taskId: currentTaskId,
        token,
        empresaId,
        payload: {
          titulo: newSubtask.trim(),
          estatus: "pendiente",
          orden: task?.subtasks?.length ?? 0,
        },
      });
      setNewSubtask("");
      await reloadTask(currentTaskId);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo agregar la subtarea."));
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleSubtask(subtask) {
    setSaving(true);
    setError("");
    try {
      await updatePmSubtask({
        subtaskId: subtask.id,
        token,
        empresaId,
        payload: {
          estatus: subtask.estatus === "completada" ? "pendiente" : "completada",
        },
      });
      await reloadTask(currentTaskId);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo actualizar la subtarea."));
    } finally {
      setSaving(false);
    }
  }

  async function handleAddChecklistItem() {
    if (!currentTaskId || !newChecklistItem.trim()) {
      return;
    }

    setSaving(true);
    setError("");
    try {
      await createPmChecklistItem({
        taskId: currentTaskId,
        token,
        empresaId,
        payload: {
          titulo: newChecklistItem.trim(),
          completado: false,
          orden: task?.checklist_items?.length ?? 0,
        },
      });
      setNewChecklistItem("");
      await reloadTask(currentTaskId);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo agregar el checklist."));
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleChecklist(item) {
    setSaving(true);
    setError("");
    try {
      await updatePmChecklistItem({
        itemId: item.id,
        token,
        empresaId,
        payload: {
          completado: !item.completado,
        },
      });
      await reloadTask(currentTaskId);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo actualizar el checklist."));
    } finally {
      setSaving(false);
    }
  }

  async function handleAddComment() {
    if (!currentTaskId || !newComment.trim()) {
      return;
    }

    setSaving(true);
    setError("");
    try {
      await createPmTaskComment({
        taskId: currentTaskId,
        token,
        empresaId,
        payload: { body: newComment.trim() },
      });
      setNewComment("");
      await reloadTask(currentTaskId);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar el comentario."));
    } finally {
      setSaving(false);
    }
  }

  const footer = (
    <div className="inventory-actions inventory-actions-wrap">
      <ActionButton disabled={saving} onClick={onClose} type="button">
        Cerrar
      </ActionButton>
      <ActionButton disabled={saving} form="pm-task-form" tone="primary" type="submit">
        {saving ? "Guardando..." : currentTaskId ? "Guardar tarea" : "Crear tarea"}
      </ActionButton>
    </div>
  );

  return (
    <ModalShell
      footer={footer}
      onClose={onClose}
      open={open}
      size="xl"
      subtitle="Tareas, checklist, subtareas, comentarios y prerrequisitos del proyecto."
      title={currentTaskId ? "Detalle de tarea" : "Nueva tarea"}
    >
      {loading ? <div className="table-note">Cargando tarea...</div> : null}

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <form className="inventory-modal-form" id="pm-task-form" onSubmit={handleSubmit}>
        <FormGrid>
          <Field label="Título">
            <input
              onChange={(event) => setForm((current) => ({ ...current, titulo: event.target.value }))}
              required
              type="text"
              value={form.titulo}
            />
          </Field>
          <Field label="Estatus">
            <select
              onChange={(event) => setForm((current) => ({ ...current, estatus: event.target.value }))}
              value={form.estatus}
            >
              {taskStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Prioridad">
            <select
              onChange={(event) => setForm((current) => ({ ...current, prioridad: event.target.value }))}
              value={form.prioridad}
            >
              {priorityOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Asignado">
            <select
              onChange={(event) => setForm((current) => ({ ...current, asignado_user_id: event.target.value }))}
              value={form.asignado_user_id}
            >
              <option value="">Sin usuario vinculado</option>
              {memberSelectOptions.map((option) => (
                <option key={option.value || option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field hint="Usa este campo si la tarea no queda ligada a un usuario interno." label="Asignado manual">
            <input
              onChange={(event) => setForm((current) => ({ ...current, asignado_nombre_snapshot: event.target.value }))}
              type="text"
              value={form.asignado_nombre_snapshot}
            />
          </Field>
          <Field label="Fecha inicio">
            <input
              onChange={(event) => setForm((current) => ({ ...current, fecha_inicio: event.target.value }))}
              type="date"
              value={form.fecha_inicio}
            />
          </Field>
          <Field label="Fecha vencimiento">
            <input
              onChange={(event) => setForm((current) => ({ ...current, fecha_vencimiento: event.target.value }))}
              type="date"
              value={form.fecha_vencimiento}
            />
          </Field>
          <Field label="Estimación horas">
            <input
              min="0"
              onChange={(event) => setForm((current) => ({ ...current, estimacion_horas: event.target.value }))}
              step="0.5"
              type="number"
              value={form.estimacion_horas}
            />
          </Field>
          <Field label="Avance (%)">
            <input
              max="100"
              min="0"
              onChange={(event) => setForm((current) => ({ ...current, porcentaje_avance: event.target.value }))}
              step="1"
              type="number"
              value={form.porcentaje_avance}
            />
          </Field>
          <Field label="Orden">
            <input
              min="0"
              onChange={(event) => setForm((current) => ({ ...current, orden: event.target.value }))}
              step="1"
              type="number"
              value={form.orden}
            />
          </Field>
          <Field label="Descripción" span={2}>
            <textarea
              onChange={(event) => setForm((current) => ({ ...current, descripcion: event.target.value }))}
              rows={4}
              value={form.descripcion}
            />
          </Field>
        </FormGrid>

        <div className="inventory-toggle-row">
          <label className="inventory-inline-checkbox">
            <input
              checked={form.bloqueada}
              onChange={(event) => setForm((current) => ({ ...current, bloqueada: event.target.checked }))}
              type="checkbox"
            />
            Bloqueada
          </label>
          <label className="inventory-inline-checkbox">
            <input
              checked={form.requiere_materiales}
              onChange={(event) => setForm((current) => ({ ...current, requiere_materiales: event.target.checked }))}
              type="checkbox"
            />
            Requiere materiales
          </label>
          <label className="inventory-inline-checkbox">
            <input
              checked={form.requiere_compra}
              onChange={(event) => setForm((current) => ({ ...current, requiere_compra: event.target.checked }))}
              type="checkbox"
            />
            Requiere compra
          </label>
          <label className="inventory-inline-checkbox">
            <input
              checked={form.requiere_venta_pos}
              onChange={(event) => setForm((current) => ({ ...current, requiere_venta_pos: event.target.checked }))}
              type="checkbox"
            />
            Requiere venta POS
          </label>
          <label className="inventory-inline-checkbox">
            <input
              checked={form.requiere_factura}
              onChange={(event) => setForm((current) => ({ ...current, requiere_factura: event.target.checked }))}
              type="checkbox"
            />
            Requiere factura
          </label>
        </div>

        <div className="pm-task-prereq-section">
          <div className="pm-task-prereq-header">
            <div>
              <strong>Prerrequisitos</strong>
              <p className="table-note">Selecciona tareas que deben completarse antes de iniciar esta tarea.</p>
            </div>
            {selectedPrerequisiteIds.length > 0 ? (
              <StatusBadge tone="warning">
                <Lock size={12} strokeWidth={1.9} />
                {selectedPrerequisiteIds.length} seleccionados
              </StatusBadge>
            ) : null}
          </div>

          {availablePrerequisiteOptions.length === 0 ? (
            <EmptyState compact note="Aún no hay otras tareas para usar como prerrequisito." title="Sin prerrequisitos disponibles" />
          ) : (
            <div className="pm-task-prereq-list">
              {availablePrerequisiteOptions.map((candidate) => {
                const checked = selectedPrerequisiteIds.includes(candidate.id);
                return (
                  <label className={`pm-task-prereq-option ${checked ? "is-selected" : ""}`} key={candidate.id}>
                    <input
                      checked={checked}
                      onChange={() => togglePrerequisite(candidate.id)}
                      type="checkbox"
                    />
                    <div className="pm-task-prereq-copy">
                      <strong>{safeDisplayText(candidate.titulo)}</strong>
                      <span>{safeDisplayText(candidate.statusLabel, candidate.estatus)}</span>
                    </div>
                  </label>
                );
              })}
            </div>
          )}

          {selectedPrerequisiteIds.length > 0 ? (
            <div className="inventory-form-note inventory-form-note-warning">
              <strong>La tarea quedará bloqueada</strong>
              <p className="table-note">Completa primero los prerrequisitos seleccionados para poder avanzar esta tarea.</p>
            </div>
          ) : null}
        </div>
      </form>

      {currentTaskId ? (
        <div className="inventory-content-grid inventory-content-grid-2 pm-detail-secondary-grid">
          <DataCard subtitle="Desglose básico de ejecución." title="Resumen">
            <div className="pm-inline-metadata">
              <StatusBadge tone={getTaskStatusTone(task?.estatus)}>{getTaskStatusLabel(task?.estatus)}</StatusBadge>
              <StatusBadge tone={getPriorityTone(task?.prioridad)}>{getPriorityLabel(task?.prioridad)}</StatusBadge>
              {dependencyContext?.is_blocked ? <StatusBadge tone="warning">Bloqueada</StatusBadge> : null}
            </div>
            <div className="pm-meta-list">
              <div>
                <strong>Vence</strong>
                <span>{safeDisplayText(formatDate(task?.fecha_vencimiento), "—")}</span>
              </div>
              <div>
                <strong>Asignado</strong>
                <span>{safeDisplayText(task?.asignado_nombre_snapshot, "Sin asignación")}</span>
              </div>
            </div>
          </DataCard>

          <DataCard
            actions={(
              <ActionButton
                disabled={saving || !newSubtask.trim()}
                onClick={handleAddSubtask}
                size="sm"
                tone="primary"
                type="button"
              >
                Agregar
              </ActionButton>
            )}
            subtitle="Control simple de pendientes hijos."
            title="Subtareas"
          >
            <label className="inventory-search-field">
              <span className="inventory-field-label">Nueva subtarea</span>
              <input
                onChange={(event) => setNewSubtask(event.target.value)}
                placeholder="Descripción breve"
                type="text"
                value={newSubtask}
              />
            </label>
            {task?.subtasks?.length ? (
              <div className="pm-inline-list">
                {task.subtasks.map((subtask) => (
                  <button
                    className="pm-inline-item"
                    key={subtask.id}
                    onClick={() => handleToggleSubtask(subtask)}
                    type="button"
                  >
                    <span className="pm-inline-item-icon">
                      <CheckSquare size={16} strokeWidth={1.9} />
                    </span>
                    <div>
                      <strong>{safeDisplayText(subtask.titulo)}</strong>
                      <div className="inventory-cell-sub">{getTaskStatusLabel(subtask.estatus)}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState compact note="Aún no hay subtareas." title="Sin subtareas" />
            )}
          </DataCard>

          <DataCard
            actions={(
              <ActionButton
                disabled={saving || !newChecklistItem.trim()}
                onClick={handleAddChecklistItem}
                size="sm"
                tone="primary"
                type="button"
              >
                Agregar
              </ActionButton>
            )}
            subtitle="Checklist básico por tarea."
            title="Checklist"
          >
            <label className="inventory-search-field">
              <span className="inventory-field-label">Nuevo ítem</span>
              <input
                onChange={(event) => setNewChecklistItem(event.target.value)}
                placeholder="Actividad a validar"
                type="text"
                value={newChecklistItem}
              />
            </label>
            {task?.checklist_items?.length ? (
              <div className="pm-inline-list">
                {task.checklist_items.map((item) => (
                  <button
                    className="pm-inline-item"
                    key={item.id}
                    onClick={() => handleToggleChecklist(item)}
                    type="button"
                  >
                    <span className="pm-inline-item-icon">
                      <ListChecks size={16} strokeWidth={1.9} />
                    </span>
                    <div>
                      <strong>{safeDisplayText(item.titulo)}</strong>
                      <div className="inventory-cell-sub">{item.completado ? "Completado" : "Pendiente"}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState compact note="Aún no hay checklist." title="Sin checklist" />
            )}
          </DataCard>

          <DataCard
            actions={(
              <ActionButton
                disabled={saving || !newComment.trim()}
                onClick={handleAddComment}
                size="sm"
                tone="primary"
                type="button"
              >
                Comentar
              </ActionButton>
            )}
            subtitle="Conversación operativa asociada a la tarea."
            title="Comentarios"
          >
            <label className="inventory-search-field">
              <span className="inventory-field-label">Nuevo comentario</span>
              <textarea
                onChange={(event) => setNewComment(event.target.value)}
                rows={3}
                value={newComment}
              />
            </label>
            {task?.comments?.length ? (
              <div className="pm-comment-list">
                {task.comments.map((comment) => (
                  <article className="pm-comment-card" key={comment.id}>
                    <div className="pm-comment-head">
                      <span className="pm-inline-item-icon">
                        <MessageSquare size={16} strokeWidth={1.9} />
                      </span>
                      <strong>{safeDisplayText(comment.created_by_nombre_snapshot, "Usuario")}</strong>
                    </div>
                    <p>{safeDisplayText(comment.body, "")}</p>
                    <span className="inventory-cell-sub">{safeDisplayText(formatDate(comment.created_at), "—")}</span>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState compact note="Aún no hay comentarios." title="Sin comentarios" />
            )}
          </DataCard>
        </div>
      ) : (
        <DataCard title="Siguiente paso">
          <p className="table-note">Guarda la tarea para habilitar subtareas, checklist y comentarios.</p>
        </DataCard>
      )}
    </ModalShell>
  );
}
