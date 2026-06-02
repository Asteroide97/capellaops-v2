import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarRange,
  CheckSquare,
  Clock3,
  Link2,
  Lock,
  MessageSquare,
  PackageOpen,
  Pencil,
  Plus,
  Route,
  Sparkles,
} from "lucide-react";

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

function isActionPending(taskActionLoading = {}, taskId, action) {
  return Boolean(taskActionLoading?.[`${taskId}:${action}`]);
}

function formatTaskTitleList(items = []) {
  const titles = [...new Set(items.filter(Boolean))];
  if (titles.length === 0) {
    return "";
  }
  if (titles.length === 1) {
    return titles[0];
  }
  if (titles.length === 2) {
    return `${titles[0]} y ${titles[1]}`;
  }
  return `${titles[0]}, ${titles[1]} y ${titles.length - 2} más`;
}

export default function PMTaskDetailPanel({
  empresaId,
  materialConsumptions,
  materialPlans,
  onApplySuggestedDates,
  onDependenciesChanged,
  onEditTask,
  onEditTaskDates,
  onSelectTask,
  projectId,
  taskActionLoading,
  taskDependencyContext,
  taskId,
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
    is_blocked: false,
    dependencies: [],
    blockers: [],
    successors: [],
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
        }));
      }

      setLoading(!(taskSummary?.id === taskId));
      setError("");
      try {
        const taskResponse = await getPmTask({ taskId, token, empresaId });
        if (!cancelled) {
          setTask((current) => ({
            ...current,
            ...taskResponse,
            ...taskSummary,
          }));
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
  }, [taskId, token, empresaId, projectId, taskSummary]);

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
  const dependencyItems = useMemo(() => dependencies?.dependencies ?? [], [dependencies]);
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
  const isBlocked = Boolean(dependencies?.is_blocked ?? dependencies?.blocked ?? pendingBlockers.length > 0) || pendingBlockers.length > 0;
  const completedDependencyTitles = useMemo(
    () => dependencyItems.map((dependency) => normalizePmCopy(safeDisplayText(dependency.resolved_title ?? dependency.depende_de_tarea_titulo))).filter(Boolean),
    [dependencyItems],
  );
  const availablePrerequisiteOptions = useMemo(
    () => (tasks ?? []).filter((candidate) => candidate.id !== taskId && candidate.activo),
    [tasks, taskId],
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

  const scheduleSuggestion = taskSummary?.schedule_suggestion ?? task?.schedule_suggestion ?? null;
  const isCritical = Boolean(taskSummary?.es_critica ?? task?.es_critica);
  const slackDays = taskSummary?.holgura_dias ?? task?.holgura_dias;
  const successors = dependencies?.successors ?? [];
  const applySuggestedLoading = isActionPending(taskActionLoading, taskId, "apply-suggestion");
  const editDatesLoading = isActionPending(taskActionLoading, taskId, "dates");

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
      ...current,
      ...taskResponse,
      ...taskSummary,
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
        <EmptyState
          compact
          note="Aquí verás descripción, checklist, comentarios, horas, materiales y prerrequisitos de la tarea seleccionada."
          title="Sin tarea seleccionada"
        />
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
            <ActionButton disabled={!taskId || editDatesLoading} onClick={() => onEditTaskDates?.(taskId)} type="button">
              {editDatesLoading ? "Guardando..." : "Editar fechas"}
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
        {error || success ? (
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
                  {isCritical ? <StatusBadge tone="danger">En ruta crítica</StatusBadge> : null}
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
                  Completa primero: {pendingBlockers.map((item) => item.titulo).join(", ")}.
                </p>
              </div>
            ) : hasDependencies ? (
              <div className="inventory-form-note inventory-form-note-success">
                <strong>Prerrequisitos completados</strong>
                <p className="table-note">{completedDependencyTitles.join(", ")}</p>
              </div>
            ) : null}

            {isCritical ? (
              <div className="inventory-form-note inventory-form-note-danger">
                <strong>En ruta crítica</strong>
                <p className="table-note">
                  Esta tarea forma parte de la ruta que afecta la fecha final del proyecto.
                  {slackDays !== null && slackDays !== undefined ? ` Holgura: ${slackDays} días.` : ""}
                </p>
              </div>
            ) : null}

            {scheduleSuggestion?.fuera_de_secuencia ? (
              <div className="pm-task-schedule-panel">
                <div className="pm-detail-block-header">
                  <div className="pm-inline-metadata">
                    <CalendarRange size={16} strokeWidth={1.9} />
                    <strong>Fecha sugerida</strong>
                  </div>
                  <div className="inventory-actions inventory-actions-wrap">
                    <ActionButton
                      className={applySuggestedLoading ? "pm-button-loading" : ""}
                      disabled={applySuggestedLoading || editDatesLoading}
                      icon={<Sparkles size={14} strokeWidth={1.9} />}
                      onClick={() => onApplySuggestedDates?.(taskId)}
                      tone="primary"
                      type="button"
                    >
                      {applySuggestedLoading ? "Aplicando..." : "Aplicar fecha sugerida"}
                    </ActionButton>
                    <ActionButton
                      className={editDatesLoading ? "pm-button-loading" : ""}
                      disabled={applySuggestedLoading || editDatesLoading}
                      icon={<Pencil size={14} strokeWidth={1.9} />}
                      onClick={() => onEditTaskDates?.(taskId)}
                      type="button"
                    >
                      {editDatesLoading ? "Guardando..." : "Editar fechas"}
                    </ActionButton>
                  </div>
                </div>
                <p className="table-note">
                  La tarea debería iniciar después de completar sus prerrequisitos.
                </p>
                <div className="pm-task-schedule-grid">
                  <div>
                    <span>Actual</span>
                    <strong>
                      {safeDisplayText(formatDate(task.fecha_inicio), "—")} → {safeDisplayText(formatDate(task.fecha_vencimiento), "—")}
                    </strong>
                  </div>
                  <div>
                    <span>Sugerido</span>
                    <strong>
                      {safeDisplayText(formatDate(scheduleSuggestion.fecha_inicio_sugerida), "—")} → {safeDisplayText(formatDate(scheduleSuggestion.fecha_fin_sugerida), "—")}
                    </strong>
                  </div>
                </div>
                <div className="pm-task-impact-note">
                  <AlertTriangle size={14} strokeWidth={1.9} />
                  <span>
                    {safeDisplayText(scheduleSuggestion.razon, "La tarea inicia antes de que termine su prerrequisito.")}
                  </span>
                </div>
              </div>
            ) : null}

            {successors.length > 0 ? (
              <div className="inventory-form-note">
                <strong>Impacto en dependientes</strong>
                <p className="table-note">
                  Esta tarea desbloquea {successors.length} tareas. Cambiar sus fechas puede afectar tareas dependientes.
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
                          <span>
                            Debe completarse antes · {safeDisplayText(getTaskStatusLabel(dependency.resolved_status ?? dependency.depende_de_tarea_estatus), dependency.resolved_status ?? dependency.depende_de_tarea_estatus)}
                          </span>
                        </div>
                        <div className="table-actions">
                          <ActionButton onClick={() => onSelectTask?.(dependency.depende_de_tarea_id)} size="sm" type="button">
                            Ver tarea
                          </ActionButton>
                          <ActionButton
                            className={savingDependency ? "pm-button-loading" : ""}
                            disabled={savingDependency}
                            onClick={() => handleDeactivateDependency(dependency.id)}
                            size="sm"
                            tone="danger"
                            type="button"
                          >
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
                {successors.length ? (
                  <div className="pm-detail-list">
                    {successors.map((successor) => (
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
                  <EmptyState compact note="Las subtareas aparecerán aquí." title="Sin subtareas" />
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
                  <EmptyState compact note="Los checks operativos aparecerán aquí." title="Sin checklist" />
                )}
              </div>

              <div className="pm-detail-block">
                <div className="pm-detail-block-header">
                  <Clock3 size={16} strokeWidth={1.9} />
                  <strong>Horas asociadas</strong>
                </div>
                {relatedTimeEntries.length ? (
                  <div className="pm-detail-list">
                    {relatedTimeEntries.map((entry) => (
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
                  <EmptyState compact note="No hay horas ligadas a esta tarea todavía." title="Sin horas" />
                )}
              </div>

              <div className="pm-detail-block">
                <div className="pm-detail-block-header">
                  <PackageOpen size={16} strokeWidth={1.9} />
                  <strong>Materiales relacionados</strong>
                </div>
                {relatedMaterialPlans.length || relatedMaterialConsumptions.length ? (
                  <div className="pm-detail-list">
                    {relatedMaterialPlans.map((plan) => (
                      <div className="pm-detail-list-item" key={`plan-${plan.id}`}>
                        <div>
                          <strong>{safeDisplayText(plan.material_nombre_snapshot)}</strong>
                          <span>Planificado · {formatNumber(plan.cantidad_planificada)}</span>
                        </div>
                        <strong>{formatMoney(plan.costo_total_estimado ?? 0)}</strong>
                      </div>
                    ))}
                    {relatedMaterialConsumptions.map((consumption) => (
                      <div className="pm-detail-list-item" key={`consumption-${consumption.id}`}>
                        <div>
                          <strong>{safeDisplayText(consumption.material_nombre_snapshot)}</strong>
                          <span>Consumido · {formatNumber(consumption.cantidad_consumida)}</span>
                        </div>
                        <strong>{formatMoney(consumption.costo_total_snapshot ?? 0)}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState compact note="Todavía no hay materiales ligados a esta tarea." title="Sin materiales" />
                )}
              </div>

              <div className="pm-detail-block">
                <div className="pm-detail-block-header">
                  <MessageSquare size={16} strokeWidth={1.9} />
                  <strong>Comentarios</strong>
                </div>
                {task.comments?.length ? (
                  <div className="pm-detail-list">
                    {task.comments.map((comment) => (
                      <div className="pm-detail-list-item" key={comment.id}>
                        <div>
                          <strong>{safeDisplayText(comment.created_by_nombre_snapshot, "Usuario")}</strong>
                          <span>{safeDisplayText(formatDate(comment.created_at), "—")}</span>
                        </div>
                        <span>{safeDisplayText(comment.body, "Sin comentario")}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState compact note="Los comentarios de tarea aparecerán aquí." title="Sin comentarios" />
                )}
              </div>
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
            <ActionButton disabled={savingDependency} form="pm-add-dependency-form" tone="primary" type="submit">
              {savingDependency ? "Guardando..." : "Guardar prerrequisito"}
            </ActionButton>
          </div>
        )}
        onClose={closeDependencyModal}
        open={dependencyModalOpen}
        size="medium"
        subtitle="Selecciona la tarea que debe completarse antes de iniciar esta."
        title="Agregar prerrequisito"
      >
        <form className="inventory-modal-form" id="pm-add-dependency-form" onSubmit={handleCreateDependency}>
          <FormGrid>
            <Field label="Tarea que debe terminar antes" span={2}>
              {availablePrerequisiteOptions.length === 0 ? (
                <div className="inventory-form-note">
                  <strong>Sin tareas disponibles</strong>
                  <p className="table-note">Aún no hay otras tareas para usar como prerrequisito.</p>
                </div>
              ) : (
                <select
                  onChange={(event) => setDependencyForm((current) => ({ ...current, depende_de_tarea_id: event.target.value }))}
                  required
                  value={dependencyForm.depende_de_tarea_id}
                >
                  {availablePrerequisiteOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {normalizePmCopy(safeDisplayText(option.titulo))} — {getTaskStatusLabel(option.estatus)}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Tipo">
              <input disabled type="text" value="Debe completarse antes de iniciar esta tarea" />
            </Field>
            <Field label="Bloqueante">
              <label className="inventory-checkbox">
                <input
                  checked={dependencyForm.bloqueante}
                  onChange={(event) => setDependencyForm((current) => ({ ...current, bloqueante: event.target.checked }))}
                  type="checkbox"
                />
                <span>Bloquear avance hasta completar prerrequisito</span>
              </label>
            </Field>
            <Field label="Notas" span={2}>
              <textarea
                onChange={(event) => setDependencyForm((current) => ({ ...current, notas: event.target.value }))}
                rows={3}
                value={dependencyForm.notas}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>
    </>
  );
}
