import { useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  CheckCheck,
  Eye,
  Flag,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Slash,
  XCircle,
} from "lucide-react";

import {
  applyPmProjectChange,
  approvePmProjectChange,
  archivePmBaseline,
  cancelPmProjectChange,
  createPmProjectBaseline,
  createPmProjectChange,
  getPmBaseline,
  getPmProjectBaselineVsActual,
  listPmProjectBaselines,
  listPmProjectChanges,
  rejectPmProjectChange,
  setPmBaselineAsMain,
  submitPmProjectChange,
  updatePmProjectChange,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FormGrid,
  MetricCard,
  ModalShell,
  StatusBadge,
  formatDate,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";
import {
  getBaselineStatusLabel,
  getBaselineStatusTone,
  getChangeStatusLabel,
  getChangeStatusTone,
  getChangeTypeLabel,
  normalizePmCopy,
  pmChangeTypeOptions,
} from "./shared";

const defaultBaselineForm = {
  nombre: "",
  descripcion: "",
  es_principal: true,
};

const defaultChangeForm = {
  id: null,
  prefill_mode: "manual",
  linea_base_id: "",
  tipo_cambio: "fecha",
  titulo: "",
  descripcion: "",
  motivo: "",
  requiere_aprobacion: true,
  entidad_tipo: "",
  entidad_id: "",
  impacto_dias: 0,
  impacto_costo: "",
  impacto_venta: "",
  task_id: "",
  fecha_inicio_referencia: "",
  fecha_fin_referencia: "",
  fecha_inicio_objetivo: "",
  fecha_fin_objetivo: "",
};

function getErrorMessage(error, fallback) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}

function formatDeltaDays(value) {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric) || numeric === 0) {
    return "0 días";
  }
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${formatNumber(numeric)} días`;
}

function normalizeChangeDetected(value) {
  return normalizePmCopy(safeDisplayText(value, "Sin cambios")).trim();
}

function hasDetectedDeviation(row) {
  if (!row?.task_id) {
    return false;
  }

  const changeDetected = normalizeChangeDetected(row?.cambio_detectado).toLowerCase();
  const hasDateShift =
    safeDisplayText(row?.fecha_inicio_base, "") !== safeDisplayText(row?.fecha_inicio_actual, "") ||
    safeDisplayText(row?.fecha_fin_base, "") !== safeDisplayText(row?.fecha_fin_actual, "");
  const hasDelta = Number(row?.desviacion_dias_fin ?? 0) !== 0;

  return Boolean(
    row?.added_after_baseline ||
    row?.removed_after_baseline ||
    hasDateShift ||
    hasDelta ||
    (changeDetected && changeDetected !== "sin cambios"),
  );
}

function buildChangeFormFromRecord(change, tasks = []) {
  const before = typeof change?.antes_json === "object" && change?.antes_json ? change.antes_json : {};
  const after = typeof change?.despues_json === "object" && change?.despues_json ? change.despues_json : {};
  const targetTaskId = safeDisplayText(after?.tarea_id ?? before?.tarea_id ?? change?.entidad_id, "");
  const task = tasks.find((item) => item.id === targetTaskId);
  const isDeviationPrefill =
    before?.origen === "desviacion" ||
    before?.fecha_inicio_base !== undefined ||
    before?.fecha_fin_base !== undefined;

  return {
    id: change?.id ?? null,
    prefill_mode: isDeviationPrefill ? "deviation" : "manual",
    linea_base_id: change?.linea_base_id ?? "",
    tipo_cambio: change?.tipo_cambio ?? "fecha",
    titulo: change?.titulo ?? "",
    descripcion: change?.descripcion ?? "",
    motivo: change?.motivo ?? "",
    requiere_aprobacion: Boolean(change?.requiere_aprobacion),
    entidad_tipo: change?.entidad_tipo ?? "",
    entidad_id: change?.entidad_id ?? "",
    impacto_dias: Number(change?.impacto_dias ?? 0),
    impacto_costo: change?.impacto_costo ?? "",
    impacto_venta: change?.impacto_venta ?? "",
    task_id: targetTaskId,
    fecha_inicio_referencia:
      before?.fecha_inicio_base ??
      before?.fecha_inicio_actual ??
      before?.fecha_inicio ??
      task?.fecha_inicio ??
      "",
    fecha_fin_referencia:
      before?.fecha_fin_base ??
      before?.fecha_fin_actual ??
      before?.fecha_fin ??
      task?.fecha_vencimiento ??
      "",
    fecha_inicio_objetivo:
      after?.fecha_inicio_actual ??
      after?.nueva_fecha_inicio ??
      after?.fecha_inicio ??
      "",
    fecha_fin_objetivo:
      after?.fecha_fin_actual ??
      after?.nueva_fecha_fin ??
      after?.fecha_fin ??
      "",
  };
}

function buildChangeFormFromDeviation(row, baselineId = "") {
  const taskTitle = normalizePmCopy(safeDisplayText(row?.tarea_titulo, "Tarea"));
  return {
    ...defaultChangeForm,
    prefill_mode: "deviation",
    linea_base_id: baselineId || "",
    tipo_cambio: "fecha",
    titulo: `Cambio de fechas — ${taskTitle}`,
    descripcion: `La tarea ${taskTitle} cambió respecto a la línea base.`,
    requiere_aprobacion: true,
    entidad_tipo: "tarea",
    entidad_id: row?.task_id ?? "",
    task_id: row?.task_id ?? "",
    impacto_dias: Number(row?.desviacion_dias_fin ?? 0),
    impacto_costo: "0",
    fecha_inicio_referencia: row?.fecha_inicio_base ?? "",
    fecha_fin_referencia: row?.fecha_fin_base ?? "",
    fecha_inicio_objetivo: row?.fecha_inicio_actual ?? "",
    fecha_fin_objetivo: row?.fecha_fin_actual ?? "",
  };
}

function buildChangePayload(changeForm, tasks, action = "draft") {
  const isDateChange = changeForm.tipo_cambio === "fecha";
  const selectedTask = tasks.find((item) => item.id === changeForm.task_id);
  const requiresApproval = action === "submit" ? true : Boolean(changeForm.requiere_aprobacion);
  const isDeviationPrefill = changeForm.prefill_mode === "deviation";

  const beforeJson = isDateChange
    ? isDeviationPrefill
      ? {
        origen: "desviacion",
        tarea_id: changeForm.task_id || null,
        fecha_inicio_base: changeForm.fecha_inicio_referencia || null,
        fecha_fin_base: changeForm.fecha_fin_referencia || null,
        fecha_inicio: changeForm.fecha_inicio_referencia || null,
        fecha_fin: changeForm.fecha_fin_referencia || null,
      }
      : {
        origen: "manual",
        tarea_id: changeForm.task_id || null,
        fecha_inicio_actual: changeForm.fecha_inicio_referencia || null,
        fecha_fin_actual: changeForm.fecha_fin_referencia || null,
        fecha_inicio: changeForm.fecha_inicio_referencia || null,
        fecha_fin: changeForm.fecha_fin_referencia || null,
      }
    : null;

  const afterJson = isDateChange
    ? isDeviationPrefill
      ? {
        tarea_id: changeForm.task_id || null,
        tarea_titulo: selectedTask?.titulo ?? null,
        fecha_inicio_actual: changeForm.fecha_inicio_objetivo || null,
        fecha_fin_actual: changeForm.fecha_fin_objetivo || null,
        fecha_inicio: changeForm.fecha_inicio_objetivo || null,
        fecha_fin: changeForm.fecha_fin_objetivo || null,
      }
      : {
        tarea_id: changeForm.task_id || null,
        tarea_titulo: selectedTask?.titulo ?? null,
        fecha_inicio_actual: changeForm.fecha_inicio_referencia || null,
        fecha_fin_actual: changeForm.fecha_fin_referencia || null,
        fecha_inicio: changeForm.fecha_inicio_objetivo || null,
        fecha_fin: changeForm.fecha_fin_objetivo || null,
        nueva_fecha_inicio: changeForm.fecha_inicio_objetivo || null,
        nueva_fecha_fin: changeForm.fecha_fin_objetivo || null,
      }
    : null;

  return {
    linea_base_id: changeForm.linea_base_id || null,
    tipo_cambio: changeForm.tipo_cambio,
    titulo: changeForm.titulo.trim(),
    descripcion: changeForm.descripcion.trim() || null,
    motivo: changeForm.motivo.trim() || null,
    requiere_aprobacion: requiresApproval,
    entidad_tipo: isDateChange ? "tarea" : (changeForm.entidad_tipo || null),
    entidad_id: isDateChange ? (changeForm.task_id || null) : (changeForm.entidad_id.trim() || null),
    antes_json: beforeJson,
    despues_json: afterJson,
    impacto_dias: Number(changeForm.impacto_dias || 0),
    impacto_costo: changeForm.impacto_costo === "" ? 0 : Number(changeForm.impacto_costo || 0),
    impacto_venta: changeForm.impacto_venta === "" ? 0 : Number(changeForm.impacto_venta || 0),
  };
}

export default function PMProjectBaselineTab({
  canApprove = false,
  canEditChanges = false,
  canManage = false,
  empresaId,
  onComparisonLoaded,
  onOpenApprovals,
  onPlanningChanged,
  projectEditable = true,
  projectId,
  reloadToken = 0,
  tasks = [],
  token,
}) {
  const changeFormRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [baselines, setBaselines] = useState([]);
  const [changes, setChanges] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [selectedBaselineId, setSelectedBaselineId] = useState("");
  const [baselineDetail, setBaselineDetail] = useState(null);
  const [baselineModalOpen, setBaselineModalOpen] = useState(false);
  const [baselineDetailOpen, setBaselineDetailOpen] = useState(false);
  const [changeModalOpen, setChangeModalOpen] = useState(false);
  const [changeModalReadOnly, setChangeModalReadOnly] = useState(false);
  const [changeSubmitMode, setChangeSubmitMode] = useState("draft");
  const [changeForm, setChangeForm] = useState(defaultChangeForm);
  const [baselineForm, setBaselineForm] = useState(defaultBaselineForm);
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const [deviationPickerOpen, setDeviationPickerOpen] = useState(false);
  const [selectedDeviationTaskId, setSelectedDeviationTaskId] = useState("");

  const principalBaseline = useMemo(
    () => baselines.find((item) => item.es_principal) ?? baselines[0] ?? null,
    [baselines],
  );

  const taskChanges = comparison?.task_changes ?? [];

  const associatedChangeByTaskId = useMemo(() => {
    const nextMap = new Map();
    for (const change of changes ?? []) {
      if (String(change?.entidad_tipo ?? "").toLowerCase() !== "tarea") {
        continue;
      }
      const taskId = safeDisplayText(change?.entidad_id, "");
      if (!taskId) {
        continue;
      }
      if (String(change?.estatus ?? "").toLowerCase() === "cancelado") {
        continue;
      }
      nextMap.set(taskId, change);
    }
    return nextMap;
  }, [changes]);

  const deviationRows = useMemo(
    () => taskChanges.filter((row) => hasDetectedDeviation(row)),
    [taskChanges],
  );

  const deviationsWithoutChange = useMemo(
    () => deviationRows.filter((row) => !associatedChangeByTaskId.has(safeDisplayText(row?.task_id, ""))),
    [associatedChangeByTaskId, deviationRows],
  );
  const canManageBaseline = canManage && projectEditable;
  const canDraftChanges = canEditChanges && projectEditable;
  const canApproveChanges = canApprove && projectEditable;

  function setPending(key, value) {
    setActionLoading((current) => {
      if (value) {
        return { ...current, [key]: true };
      }
      if (!current[key]) {
        return current;
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function isPending(key) {
    return Boolean(actionLoading[key]);
  }

  async function loadBaselineData({ background = false, baselineId = null } = {}) {
    if (!token || !empresaId || !projectId) {
      return;
    }

    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError("");

    try {
      const [baselineList, changeList] = await Promise.all([
        listPmProjectBaselines({ projectId, token, empresaId }),
        listPmProjectChanges({ projectId, token, empresaId }),
      ]);

      const nextBaselines = baselineList ?? [];
      const nextChanges = changeList ?? [];
      const nextBaselineId =
        baselineId ??
        selectedBaselineId ??
        nextBaselines.find((item) => item.es_principal)?.id ??
        nextBaselines[0]?.id ??
        "";

      setBaselines(nextBaselines);
      setChanges(nextChanges);
      setSelectedBaselineId(nextBaselineId);

      if (nextBaselineId) {
        const nextComparison = await getPmProjectBaselineVsActual({
          projectId,
          token,
          empresaId,
          params: { baseline_id: nextBaselineId },
        });
        setComparison(nextComparison);
        onComparisonLoaded?.(nextComparison);
      } else {
        setComparison(null);
        onComparisonLoaded?.(null);
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo cargar la línea base del proyecto."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadBaselineData();
  }, [token, empresaId, projectId, reloadToken]);

  function closeBaselineModal(force = false) {
    if (submitting && !force) {
      return;
    }
    setBaselineModalOpen(false);
    setBaselineForm(defaultBaselineForm);
  }

  function closeBaselineDetail() {
    setBaselineDetailOpen(false);
    setBaselineDetail(null);
  }

  function closeChangeModal(force = false) {
    if (submitting && !force) {
      return;
    }
    setChangeModalOpen(false);
    setChangeModalReadOnly(false);
    setChangeSubmitMode("draft");
    setChangeForm(defaultChangeForm);
  }

  function closeDeviationPicker() {
    setDeviationPickerOpen(false);
    setSelectedDeviationTaskId("");
  }

  function openCreateChangeModal({ sendForApproval = false } = {}) {
    const firstTask = tasks[0] ?? null;
    setError("");
    setSuccess("");
    setChangeModalReadOnly(false);
    setChangeSubmitMode(sendForApproval ? "submit" : "draft");
    setChangeForm({
      ...defaultChangeForm,
      linea_base_id: principalBaseline?.id ?? "",
      requiere_aprobacion: sendForApproval ? true : defaultChangeForm.requiere_aprobacion,
      task_id: firstTask?.id ?? "",
      entidad_tipo: firstTask?.id ? "tarea" : "",
      entidad_id: firstTask?.id ?? "",
      fecha_inicio_referencia: firstTask?.fecha_inicio ?? "",
      fecha_fin_referencia: firstTask?.fecha_vencimiento ?? "",
    });
    setChangeModalOpen(true);
  }

  function openEditChangeModal(change) {
    setError("");
    setSuccess("");
    setChangeModalReadOnly(false);
    setChangeSubmitMode("draft");
    setChangeForm(buildChangeFormFromRecord(change, tasks));
    setChangeModalOpen(true);
  }

  function openViewChangeModal(change) {
    setError("");
    setSuccess("");
    setChangeModalReadOnly(true);
    setChangeSubmitMode("draft");
    setChangeForm(buildChangeFormFromRecord(change, tasks));
    setChangeModalOpen(true);
  }

  function openChangeFromDeviation(row, { sendForApproval = false } = {}) {
    if (!row?.task_id) {
      return;
    }
    setError("");
    setSuccess("");
    setChangeModalReadOnly(false);
    setChangeSubmitMode(sendForApproval ? "submit" : "draft");
    setChangeForm({
      ...buildChangeFormFromDeviation(row, selectedBaselineId || principalBaseline?.id || ""),
      requiere_aprobacion: true,
    });
    setChangeModalOpen(true);
  }

  function handleOpenDeviationPicker() {
    if (deviationsWithoutChange.length === 0) {
      return;
    }

    if (deviationsWithoutChange.length === 1) {
      openChangeFromDeviation(deviationsWithoutChange[0]);
      return;
    }

    setSelectedDeviationTaskId(safeDisplayText(deviationsWithoutChange[0]?.task_id, ""));
    setDeviationPickerOpen(true);
  }

  function handleConfirmDeviationPicker() {
    const row = deviationsWithoutChange.find(
      (item) => safeDisplayText(item?.task_id, "") === selectedDeviationTaskId,
    );
    if (!row) {
      setError("Selecciona una desviación para registrarla como cambio.");
      return;
    }
    closeDeviationPicker();
    openChangeFromDeviation(row);
  }

  function handleTaskSelectionForChange(taskId) {
    const selectedTask = tasks.find((item) => item.id === taskId);
    setChangeForm((current) => ({
      ...current,
      task_id: taskId,
      entidad_tipo: taskId ? "tarea" : current.entidad_tipo,
      entidad_id: taskId || current.entidad_id,
      fecha_inicio_referencia: selectedTask?.fecha_inicio ?? "",
      fecha_fin_referencia: selectedTask?.fecha_vencimiento ?? "",
    }));
  }

  async function handleCreateBaseline(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const response = await createPmProjectBaseline({
        projectId,
        token,
        empresaId,
        payload: {
          nombre: baselineForm.nombre.trim(),
          descripcion: baselineForm.descripcion.trim() || null,
          es_principal: baselineForm.es_principal,
        },
      });
      setSuccess("Línea base creada.");
      closeBaselineModal(true);
      await loadBaselineData({ background: true, baselineId: response.id });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo crear la línea base."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleViewBaselineDetail(baselineId) {
    if (!baselineId) {
      return;
    }
    setError("");
    try {
      const detail = await getPmBaseline({ baselineId, token, empresaId });
      setBaselineDetail(detail);
      setBaselineDetailOpen(true);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo cargar el detalle de la línea base."));
    }
  }

  async function handleSetMainBaseline(baselineId) {
    const key = `baseline-main:${baselineId}`;
    if (isPending(key)) {
      return;
    }
    setPending(key, true);
    setError("");
    setSuccess("");

    try {
      await setPmBaselineAsMain({ baselineId, token, empresaId });
      setSuccess("Línea base principal actualizada.");
      await loadBaselineData({ background: true, baselineId });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo actualizar la línea base principal."));
    } finally {
      setPending(key, false);
    }
  }

  async function handleArchiveBaseline(baselineId) {
    if (!window.confirm("La línea base quedará archivada. ¿Deseas continuar?")) {
      return;
    }

    const key = `baseline-archive:${baselineId}`;
    if (isPending(key)) {
      return;
    }
    setPending(key, true);
    setError("");
    setSuccess("");

    try {
      await archivePmBaseline({ baselineId, token, empresaId });
      setSuccess("Línea base archivada.");
      await loadBaselineData({ background: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo archivar la línea base."));
    } finally {
      setPending(key, false);
    }
  }

  async function handleSaveChange(action = "draft") {
    if (changeModalReadOnly) {
      return;
    }

    setChangeSubmitMode(action);

    if (!changeFormRef.current?.reportValidity()) {
      return;
    }

    if (changeForm.tipo_cambio === "fecha") {
      if (!changeForm.task_id) {
        setError("Selecciona una tarea para registrar el cambio de fechas.");
        return;
      }
      if (changeForm.fecha_fin_objetivo && changeForm.fecha_inicio_objetivo) {
        if (changeForm.fecha_fin_objetivo < changeForm.fecha_inicio_objetivo) {
          setError("La fecha final no puede ser anterior a la fecha inicial.");
          return;
        }
      }
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const payload = buildChangePayload(changeForm, tasks, action);
      const savedChange = changeForm.id
        ? await updatePmProjectChange({ changeId: changeForm.id, token, empresaId, payload })
        : await createPmProjectChange({ projectId, token, empresaId, payload });

      if (action === "submit") {
        const submittedChange = await submitPmProjectChange({
          changeId: savedChange.id,
          token,
          empresaId,
          payload: {},
        });
        setSuccess(
          submittedChange.estatus === "aprobado"
            ? "Cambio guardado y aprobado."
            : "Cambio enviado a aprobación.",
        );
      } else {
        setSuccess(changeForm.id ? "Cambio actualizado." : "Cambio registrado.");
      }

      closeChangeModal(true);
      await loadBaselineData({
        background: true,
        baselineId: selectedBaselineId || principalBaseline?.id || null,
      });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar el cambio."));
    } finally {
      setSubmitting(false);
      setChangeSubmitMode("draft");
    }
  }

  async function runChangeAction({
    key,
    action,
    successMessage,
    errorMessage,
    refreshPlanning = false,
  }) {
    if (isPending(key)) {
      return;
    }

    setPending(key, true);
    setError("");
    setSuccess("");

    try {
      await action();
      setSuccess(successMessage);
      await loadBaselineData({
        background: true,
        baselineId: selectedBaselineId || principalBaseline?.id || null,
      });
      if (refreshPlanning) {
        await Promise.resolve(onPlanningChanged?.()).catch(() => {});
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError, errorMessage));
    } finally {
      setPending(key, false);
    }
  }

  function handleOpenApproval(change) {
    if (!change?.aprobacion_id) {
      return;
    }
    onOpenApprovals?.();
  }

  function handleApplyChange(change) {
    if (change.requiere_aprobacion && change.estatus !== "aprobado") {
      setError("Este cambio requiere aprobación antes de aplicarse.");
      return;
    }

    const applyDependents =
      change.tipo_cambio === "fecha"
        ? window.confirm("Si este cambio afecta tareas dependientes, ¿quieres reprogramarlas también?")
        : false;

    runChangeAction({
      key: `change-apply:${change.id}`,
      action: () =>
        applyPmProjectChange({
          changeId: change.id,
          token,
          empresaId,
          payload: { apply_dependents: applyDependents, comentario: null },
        }),
      successMessage: "Cambio aplicado.",
      errorMessage: "No se pudo aplicar el cambio.",
      refreshPlanning: true,
    });
  }

  const controlEmptyState = useMemo(() => {
    if (changes.length > 0) {
      return null;
    }
    if (deviationsWithoutChange.length > 0) {
      return {
        title: "Desviaciones sin formalizar",
        note: "Hay diferencias contra la línea base. Regístralas como cambios para enviarlas a aprobación o documentarlas.",
        showDeviationAction: true,
      };
    }
    return {
      title: "Sin cambios registrados",
      note: "El proyecto no tiene cambios formales ni desviaciones detectadas contra la línea base.",
      showDeviationAction: false,
    };
  }, [changes.length, deviationsWithoutChange.length]);

  if (loading) {
    return <div className="table-note">Cargando línea base del proyecto...</div>;
  }

  return (
    <>
      <section className="pm-baseline-stack">
        {(error || success) ? (
          <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
            <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
            <p className="table-note">{error || success}</p>
          </div>
        ) : null}

        <DataCard
          actions={(
            <div className="inventory-actions inventory-actions-wrap">
              <ActionButton
                icon={<RefreshCw size={16} strokeWidth={1.9} />}
                onClick={() =>
                  loadBaselineData({
                    background: true,
                    baselineId: selectedBaselineId || principalBaseline?.id || null,
                  })
                }
                type="button"
              >
                {refreshing ? "Actualizando..." : "Recalcular comparativo"}
              </ActionButton>
              {canManageBaseline ? (
                <ActionButton
                  icon={<Plus size={16} strokeWidth={1.9} />}
                  onClick={() => {
                    setError("");
                    setSuccess("");
                    setBaselineModalOpen(true);
                  }}
                  tone="primary"
                  type="button"
                >
                  Crear línea base
                </ActionButton>
              ) : null}
            </div>
          )}
          subtitle="Guarda una foto del plan aprobado para comparar tareas, fechas y costos."
          title="Línea base"
        >
          {baselines.length === 0 ? (
            <EmptyState
              action={(
                canManageBaseline ? (
                  <ActionButton onClick={() => setBaselineModalOpen(true)} tone="primary" type="button">
                    Crear línea base
                  </ActionButton>
                ) : null
              )}
              compact
              note="Guarda una foto del plan aprobado para comparar fechas, tareas y costos conforme avance el proyecto."
              title="Este proyecto aún no tiene línea base"
            />
          ) : (
            <>
              <div className="pm-baseline-head">
                <div className="pm-baseline-head-copy">
                  <strong>{safeDisplayText(comparison?.baseline?.nombre ?? principalBaseline?.nombre, "Línea base")}</strong>
                  <span>{safeDisplayText(comparison?.baseline?.descripcion, "Plan aprobado del proyecto.")}</span>
                </div>
                <div className="inventory-actions inventory-actions-wrap">
                  <select
                    onChange={(event) => loadBaselineData({ background: true, baselineId: event.target.value })}
                    value={selectedBaselineId}
                  >
                    {baselines.map((baseline) => (
                      <option key={baseline.id} value={baseline.id}>
                        {baseline.nombre} · v{baseline.version}
                      </option>
                    ))}
                  </select>
                  <ActionButton
                    icon={<Eye size={16} strokeWidth={1.9} />}
                    onClick={() => handleViewBaselineDetail(selectedBaselineId || principalBaseline?.id)}
                    type="button"
                  >
                    Ver detalle
                  </ActionButton>
                </div>
              </div>

              {comparison ? (
                <section className="inventory-metric-grid inventory-metric-grid-4">
                  <MetricCard
                    label="Línea base principal"
                    meta="Versión activa"
                    tone="info"
                    value={comparison.baseline.es_principal ? "Sí" : "No"}
                  />
                  <MetricCard label="Fecha fin base" meta="Plan aprobado" tone="neutral" value={safeDisplayText(formatDate(comparison.deviation.fecha_fin_base), "—")} />
                  <MetricCard label="Fecha fin actual" meta="Estado operativo" tone="warning" value={safeDisplayText(formatDate(comparison.deviation.fecha_fin_actual), "—")} />
                  <MetricCard
                    label="Desviación en días"
                    meta="Fin actual vs línea base"
                    tone={Number(comparison.deviation.desviacion_fecha_fin_dias ?? 0) > 0 ? "danger" : "success"}
                    value={formatDeltaDays(comparison.deviation.desviacion_fecha_fin_dias)}
                  />
                  <MetricCard label="Presupuesto base" meta="Plan aprobado" tone="neutral" value={formatMoney(comparison.deviation.presupuesto_base ?? 0)} />
                  <MetricCard label="Costo real actual" meta="Ejecución acumulada" tone="warning" value={formatMoney(comparison.deviation.costo_real_actual ?? 0)} />
                  <MetricCard
                    label="Variación de costo"
                    meta="Costo real vs base"
                    tone={Number(comparison.deviation.desviacion_costo ?? 0) > 0 ? "danger" : "success"}
                    value={formatMoney(comparison.deviation.desviacion_costo ?? 0)}
                  />
                  <MetricCard label="Tareas agregadas" meta="Fuera del plan base" tone="info" value={formatNumber(comparison.deviation.tareas_agregadas_count ?? 0)} />
                  <MetricCard label="Tareas desviadas" meta="Con cambios detectados" tone="warning" value={formatNumber(comparison.deviation.tareas_desviadas_count ?? 0)} />
                  <MetricCard label="Tareas eliminadas" meta="Desactivadas después de la base" tone="danger" value={formatNumber(comparison.deviation.tareas_eliminadas_count ?? 0)} />
                  <MetricCard label="Cambios pendientes" meta="Esperando aprobación" tone="warning" value={formatNumber(comparison.deviation.cambios_pendientes_count ?? 0)} />
                  <MetricCard label="Críticas desviadas" meta="Riesgo sobre fecha final" tone="danger" value={formatNumber(comparison.deviation.tareas_criticas_desviadas_count ?? 0)} />
                </section>
              ) : null}

              <div className="pm-baseline-list">
                {baselines.map((baseline) => {
                  const isMainPending = isPending(`baseline-main:${baseline.id}`);
                  const isArchivePending = isPending(`baseline-archive:${baseline.id}`);
                  return (
                    <div className="pm-baseline-list-item" key={baseline.id}>
                      <div>
                        <strong>{safeDisplayText(baseline.nombre)}</strong>
                        <span>
                          v{baseline.version} · {safeDisplayText(formatDate(baseline.created_at), "—")}
                        </span>
                      </div>
                      <div className="inventory-actions inventory-actions-wrap">
                        <StatusBadge tone={getBaselineStatusTone(baseline.estatus)}>
                          {getBaselineStatusLabel(baseline.estatus)}
                        </StatusBadge>
                        {baseline.es_principal ? <StatusBadge tone="success">Principal</StatusBadge> : null}
                        {!baseline.es_principal && baseline.estatus === "activa" && canManageBaseline ? (
                          <ActionButton
                            disabled={isMainPending}
                            onClick={() => handleSetMainBaseline(baseline.id)}
                            size="sm"
                            type="button"
                          >
                            {isMainPending ? "Actualizando..." : "Marcar como principal"}
                          </ActionButton>
                        ) : null}
                        {baseline.estatus !== "archivada" && canManageBaseline ? (
                          <ActionButton
                            disabled={isArchivePending}
                            icon={<Archive size={14} strokeWidth={1.9} />}
                            onClick={() => handleArchiveBaseline(baseline.id)}
                            size="sm"
                            tone="danger"
                            type="button"
                          >
                            {isArchivePending ? "Archivando..." : "Archivar"}
                          </ActionButton>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </DataCard>

        {comparison ? (
          <DataCard
            subtitle="Comparación del plan aprobado contra el estado actual del proyecto."
            title="Comparativo"
          >
            <DataTable
              columns={[
                "Tarea",
                "Inicio base",
                "Inicio actual",
                "Fin base",
                "Fin actual",
                "Desviación",
                "Estatus",
                "En ruta crítica",
                "Cambio detectado",
                "Formalización",
                "Acciones",
              ]}
            >
              <tbody>
                {taskChanges.map((row) => {
                  const changeDetected = normalizeChangeDetected(row.cambio_detectado);
                  const associatedChange = associatedChangeByTaskId.get(safeDisplayText(row?.task_id, ""));
                  const rowHasDeviation = hasDetectedDeviation(row);
                  return (
                    <tr key={`${row.task_id ?? "added"}-${row.tarea_titulo}`}>
                      <td>
                        <div className="inventory-cell-main">{normalizePmCopy(safeDisplayText(row.tarea_titulo))}</div>
                        <div className="inventory-cell-sub">
                          {row.added_after_baseline
                            ? "Agregada después de la línea base"
                            : row.removed_after_baseline
                              ? "Desactivada después de la línea base"
                              : "Comparada contra línea base"}
                        </div>
                      </td>
                      <td>{safeDisplayText(formatDate(row.fecha_inicio_base), "—")}</td>
                      <td>{safeDisplayText(formatDate(row.fecha_inicio_actual), "—")}</td>
                      <td>{safeDisplayText(formatDate(row.fecha_fin_base), "—")}</td>
                      <td>{safeDisplayText(formatDate(row.fecha_fin_actual), "—")}</td>
                      <td>{formatDeltaDays(row.desviacion_dias_fin)}</td>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(row.estatus_actual ?? row.estatus_base, "—")}</div>
                        <div className="inventory-cell-sub">Base: {safeDisplayText(row.estatus_base, "—")}</div>
                      </td>
                      <td>
                        {row.es_critica_actual || row.es_critica_base ? (
                          <StatusBadge tone={row.es_critica_actual && row.es_critica_base ? "danger" : "warning"}>
                            {row.es_critica_actual ? "Actual" : "Base"}
                          </StatusBadge>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>{changeDetected}</td>
                      <td>
                        {rowHasDeviation ? (
                          associatedChange ? (
                            <StatusBadge tone="success">Cambio registrado</StatusBadge>
                          ) : (
                            <StatusBadge tone="warning">Sin formalizar</StatusBadge>
                          )
                        ) : (
                          <span className="table-note">Sin desviación</span>
                        )}
                      </td>
                      <td>
                        <div className="inventory-actions inventory-actions-wrap">
                          {associatedChange ? (
                            <ActionButton
                              icon={<Eye size={14} strokeWidth={1.9} />}
                              onClick={() => openViewChangeModal(associatedChange)}
                              size="sm"
                              type="button"
                            >
                              Ver cambio
                            </ActionButton>
                          ) : rowHasDeviation && canDraftChanges ? (
                            <ActionButton
                              icon={<Plus size={14} strokeWidth={1.9} />}
                              onClick={() => openChangeFromDeviation(row)}
                              size="sm"
                              tone="primary"
                              type="button"
                            >
                              Crear cambio
                            </ActionButton>
                          ) : (
                            <span className="table-note">—</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>
          </DataCard>
        ) : null}

        <DataCard
          actions={(
            <div className="inventory-actions inventory-actions-wrap">
              {canDraftChanges ? (
                <ActionButton
                  icon={<Plus size={16} strokeWidth={1.9} />}
                  onClick={() => openCreateChangeModal()}
                  type="button"
                >
                  Registrar cambio manual
                </ActionButton>
              ) : null}
              {canDraftChanges ? (
                <ActionButton
                  disabled={deviationsWithoutChange.length === 0}
                  icon={<Send size={16} strokeWidth={1.9} />}
                  onClick={handleOpenDeviationPicker}
                  tone="primary"
                  type="button"
                >
                  Crear cambio desde desviación
                </ActionButton>
              ) : null}
            </div>
          )}
          subtitle="Registra cambios importantes y su impacto en fechas, alcance o presupuesto."
          title="Control de cambios"
        >
          <div className="pm-baseline-steps">
            <div className="pm-baseline-step">
              <strong>1. Registra el cambio</strong>
              <span>Documenta la desviación contra la línea base.</span>
            </div>
            <div className="pm-baseline-step">
              <strong>2. Envíalo a aprobación</strong>
              <span>Usa la aprobación cuando el cambio deba validarse antes de aplicarlo.</span>
            </div>
            <div className="pm-baseline-step">
              <strong>3. Apruébalo o recházalo</strong>
              <span>El estado del cambio y la aprobación asociada se mantienen alineados.</span>
            </div>
            <div className="pm-baseline-step">
              <strong>4. Aplica el cambio</strong>
              <span>Cuando esté aprobado, actualiza el proyecto y refresca el comparativo.</span>
            </div>
          </div>

          <div className="inventory-form-note">
            <strong>Desviaciones y cambios</strong>
            <p className="table-note">
              Las desviaciones son diferencias detectadas automáticamente. Los cambios son registros formales que pueden enviarse a aprobación.
            </p>
          </div>

          {changes.length === 0 ? (
            <EmptyState
              action={(
                <div className="inventory-actions inventory-actions-wrap">
                  {canDraftChanges ? (
                    <ActionButton onClick={() => openCreateChangeModal()} type="button">
                      Registrar cambio manual
                    </ActionButton>
                  ) : null}
                  {canDraftChanges && controlEmptyState?.showDeviationAction ? (
                    <ActionButton onClick={handleOpenDeviationPicker} tone="primary" type="button">
                      Crear cambio desde desviación
                    </ActionButton>
                  ) : null}
                </div>
              )}
              compact
              note={safeDisplayText(controlEmptyState?.note)}
              title={safeDisplayText(controlEmptyState?.title)}
            />
          ) : (
            <DataTable
              columns={[
                "Cambio",
                "Tipo",
                "Estatus",
                "Impacto días",
                "Impacto costo",
                "Aprobación",
                "Acciones",
              ]}
            >
              <tbody>
                {changes.map((change) => {
                  const submitPending = isPending(`change-submit:${change.id}`);
                  const approvePending = isPending(`change-approve:${change.id}`);
                  const rejectPending = isPending(`change-reject:${change.id}`);
                  const applyPending = isPending(`change-apply:${change.id}`);
                  const cancelPending = isPending(`change-cancel:${change.id}`);
                  const canViewApproval = Boolean(change.aprobacion_id);
                  const canApply = change.requiere_aprobacion
                    ? change.estatus === "aprobado"
                    : ["borrador", "aprobado"].includes(change.estatus);

                  return (
                    <tr key={change.id}>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(change.titulo, "Cambio")}</div>
                        <div className="inventory-cell-sub">
                          {safeDisplayText(change.motivo, change.descripcion || "Sin motivo capturado")}
                        </div>
                        {change.aprobacion_id ? (
                          <div className="inventory-cell-sub">
                            Aprobación asociada: {safeDisplayText(getChangeStatusLabel(change.aprobacion_estatus), "Pendiente")}
                          </div>
                        ) : null}
                      </td>
                      <td>{getChangeTypeLabel(change.tipo_cambio)}</td>
                      <td>
                        <StatusBadge tone={getChangeStatusTone(change.estatus)}>
                          {getChangeStatusLabel(change.estatus)}
                        </StatusBadge>
                      </td>
                      <td>{formatNumber(change.impacto_dias ?? 0)}</td>
                      <td>{formatMoney(change.impacto_costo ?? 0)}</td>
                      <td>
                        {change.requiere_aprobacion ? (
                          <StatusBadge tone={change.aprobacion_id ? getChangeStatusTone(change.aprobacion_estatus) : "warning"}>
                            {change.aprobacion_id
                              ? safeDisplayText(getChangeStatusLabel(change.aprobacion_estatus), "Pendiente")
                              : "Pendiente de envío"}
                          </StatusBadge>
                        ) : (
                          <span className="table-note">No requerida</span>
                        )}
                      </td>
                      <td>
                        <div className="inventory-actions inventory-actions-wrap">
                          {change.estatus === "borrador" ? (
                            <>
                              {canDraftChanges ? (
                                <ActionButton
                                  icon={<Pencil size={14} strokeWidth={1.9} />}
                                  onClick={() => openEditChangeModal(change)}
                                  size="sm"
                                  type="button"
                                >
                                  Editar
                                </ActionButton>
                              ) : null}
                              {canDraftChanges ? (
                                <ActionButton
                                  disabled={submitPending}
                                  icon={<Send size={14} strokeWidth={1.9} />}
                                  onClick={() =>
                                    runChangeAction({
                                      key: `change-submit:${change.id}`,
                                      action: () => submitPmProjectChange({ changeId: change.id, token, empresaId, payload: {} }),
                                      successMessage: "Cambio enviado a aprobación.",
                                      errorMessage: "No se pudo enviar el cambio a aprobación.",
                                    })
                                  }
                                  size="sm"
                                  tone="primary"
                                  type="button"
                                >
                                  {submitPending ? "Enviando..." : "Enviar a aprobación"}
                                </ActionButton>
                              ) : null}
                              {!change.requiere_aprobacion && canApply ? (
                                <ActionButton
                                  disabled={applyPending}
                                  icon={<Flag size={14} strokeWidth={1.9} />}
                                  onClick={() => handleApplyChange(change)}
                                  size="sm"
                                  tone="success"
                                  type="button"
                                >
                                  {applyPending ? "Aplicando..." : "Aplicar cambio"}
                                </ActionButton>
                              ) : null}
                              {canDraftChanges ? (
                                <ActionButton
                                  disabled={cancelPending}
                                  icon={<Slash size={14} strokeWidth={1.9} />}
                                  onClick={() =>
                                    runChangeAction({
                                      key: `change-cancel:${change.id}`,
                                      action: () => cancelPmProjectChange({ changeId: change.id, token, empresaId }),
                                      successMessage: "Cambio cancelado.",
                                      errorMessage: "No se pudo cancelar el cambio.",
                                    })
                                  }
                                  size="sm"
                                  type="button"
                                >
                                  {cancelPending ? "Cancelando..." : "Cancelar"}
                                </ActionButton>
                              ) : null}
                            </>
                          ) : null}

                          {change.estatus === "pendiente_aprobacion" ? (
                            <>
                              {canViewApproval ? (
                                <ActionButton
                                  icon={<Eye size={14} strokeWidth={1.9} />}
                                  onClick={() => handleOpenApproval(change)}
                                  size="sm"
                                  type="button"
                                >
                                  Ver aprobación
                                </ActionButton>
                              ) : null}
                              {canApproveChanges ? (
                                <ActionButton
                                  disabled={approvePending}
                                  icon={<CheckCheck size={14} strokeWidth={1.9} />}
                                  onClick={() =>
                                    runChangeAction({
                                      key: `change-approve:${change.id}`,
                                      action: () => approvePmProjectChange({ changeId: change.id, token, empresaId, payload: {} }),
                                      successMessage: "Cambio aprobado.",
                                      errorMessage: "No se pudo aprobar el cambio.",
                                    })
                                  }
                                  size="sm"
                                  tone="primary"
                                  type="button"
                                >
                                  {approvePending ? "Aprobando..." : "Aprobar"}
                                </ActionButton>
                              ) : null}
                              {canApproveChanges ? (
                                <ActionButton
                                  disabled={rejectPending}
                                  icon={<XCircle size={14} strokeWidth={1.9} />}
                                  onClick={() => {
                                    const comentario = window.prompt("Motivo del rechazo", "") ?? "";
                                    runChangeAction({
                                      key: `change-reject:${change.id}`,
                                      action: () =>
                                        rejectPmProjectChange({
                                          changeId: change.id,
                                          token,
                                          empresaId,
                                          payload: { comentario_resolucion: comentario.trim() || null },
                                        }),
                                      successMessage: "Cambio rechazado.",
                                      errorMessage: "No se pudo rechazar el cambio.",
                                    });
                                  }}
                                  size="sm"
                                  tone="danger"
                                  type="button"
                                >
                                  {rejectPending ? "Rechazando..." : "Rechazar"}
                                </ActionButton>
                              ) : null}
                              {canDraftChanges ? (
                                <ActionButton
                                  disabled={cancelPending}
                                  icon={<Slash size={14} strokeWidth={1.9} />}
                                  onClick={() =>
                                    runChangeAction({
                                      key: `change-cancel:${change.id}`,
                                      action: () => cancelPmProjectChange({ changeId: change.id, token, empresaId }),
                                      successMessage: "Cambio cancelado.",
                                      errorMessage: "No se pudo cancelar el cambio.",
                                    })
                                  }
                                  size="sm"
                                  type="button"
                                >
                                  {cancelPending ? "Cancelando..." : "Cancelar"}
                                </ActionButton>
                              ) : null}
                            </>
                          ) : null}

                          {change.estatus === "aprobado" ? (
                            <>
                              {canViewApproval ? (
                                <ActionButton
                                  icon={<Eye size={14} strokeWidth={1.9} />}
                                  onClick={() => handleOpenApproval(change)}
                                  size="sm"
                                  type="button"
                                >
                                  Ver aprobación
                                </ActionButton>
                              ) : null}
                              {canManageBaseline ? (
                                <ActionButton
                                  disabled={applyPending}
                                  icon={<Flag size={14} strokeWidth={1.9} />}
                                  onClick={() => handleApplyChange(change)}
                                  size="sm"
                                  tone="success"
                                  type="button"
                                >
                                  {applyPending ? "Aplicando..." : "Aplicar cambio"}
                                </ActionButton>
                              ) : null}
                            </>
                          ) : null}

                          {["aplicado", "rechazado", "cancelado"].includes(change.estatus) ? (
                            <ActionButton
                              icon={<Eye size={14} strokeWidth={1.9} />}
                              onClick={() => openViewChangeModal(change)}
                              size="sm"
                              type="button"
                            >
                              Ver detalle
                            </ActionButton>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      </section>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeBaselineModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="pm-baseline-create-form" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Crear línea base"}
            </ActionButton>
          </div>
        )}
        onClose={closeBaselineModal}
        open={baselineModalOpen}
        size="medium"
        subtitle="Se guardarán tareas, fechas, avance, ruta crítica y presupuesto actual."
        title="Crear línea base"
      >
        <form className="inventory-modal-form" id="pm-baseline-create-form" onSubmit={handleCreateBaseline}>
          <FormGrid>
            <Field label="Nombre" span={2}>
              <input
                onChange={(event) => setBaselineForm((current) => ({ ...current, nombre: event.target.value }))}
                required
                type="text"
                value={baselineForm.nombre}
              />
            </Field>
            <Field label="Descripción" span={2}>
              <textarea
                onChange={(event) => setBaselineForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={4}
                value={baselineForm.descripcion}
              />
            </Field>
            <Field label="Principal" span={2}>
              <label className="inventory-checkbox">
                <input
                  checked={baselineForm.es_principal}
                  onChange={(event) => setBaselineForm((current) => ({ ...current, es_principal: event.target.checked }))}
                  type="checkbox"
                />
                <span>Marcar como línea base principal</span>
              </label>
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        onClose={closeBaselineDetail}
        open={baselineDetailOpen}
        size="wide"
        subtitle={safeDisplayText(baselineDetail?.descripcion, "Detalle histórico del plan aprobado.")}
        title={safeDisplayText(baselineDetail?.nombre, "Detalle de línea base")}
      >
        {baselineDetail ? (
          <div className="pm-baseline-detail-stack">
            <div className="inventory-metric-grid inventory-metric-grid-4">
              <MetricCard label="Fecha inicio base" meta="Plan aprobado" tone="neutral" value={safeDisplayText(formatDate(baselineDetail.fecha_inicio_base), "—")} />
              <MetricCard label="Fecha fin base" meta="Plan aprobado" tone="neutral" value={safeDisplayText(formatDate(baselineDetail.fecha_fin_base), "—")} />
              <MetricCard label="Duración base" meta="Días calendario" tone="info" value={formatNumber(baselineDetail.duracion_dias_base ?? 0)} />
              <MetricCard label="Costo base" meta="Costo estimado" tone="warning" value={formatMoney(baselineDetail.costo_estimado_base ?? 0)} />
            </div>
            <DataTable columns={["Tarea", "Inicio base", "Fin base", "Avance", "Ruta crítica"]}>
              <tbody>
                {(baselineDetail.tasks ?? []).map((item) => (
                  <tr key={item.id}>
                    <td>{safeDisplayText(item.tarea_titulo_snapshot)}</td>
                    <td>{safeDisplayText(formatDate(item.fecha_inicio_base), "—")}</td>
                    <td>{safeDisplayText(formatDate(item.fecha_fin_base), "—")}</td>
                    <td>{formatNumber(item.porcentaje_avance_base ?? 0)}%</td>
                    <td>{item.es_critica_base ? "Sí" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        ) : null}
      </ModalShell>

      <ModalShell
        footer={changeModalReadOnly ? null : (
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeChangeModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              disabled={submitting}
              onClick={() => handleSaveChange("draft")}
              type="button"
            >
              {submitting && changeSubmitMode === "draft" ? "Guardando..." : "Guardar borrador"}
            </ActionButton>
            <ActionButton
              disabled={submitting}
              onClick={() => handleSaveChange("submit")}
              tone="primary"
              type="button"
            >
              {submitting && changeSubmitMode === "submit" ? "Enviando..." : "Guardar y enviar a aprobación"}
            </ActionButton>
          </div>
        )}
        onClose={closeChangeModal}
        open={changeModalOpen}
        size="wide"
        subtitle="Documenta la desviación contra la línea base y, si aplica, envíala a aprobación."
        title={changeModalReadOnly ? "Detalle del cambio" : changeForm.id ? "Editar cambio" : "Registrar cambio"}
      >
        <form
          className="inventory-modal-form"
          id="pm-change-form"
          onSubmit={(event) => {
            event.preventDefault();
            handleSaveChange(changeSubmitMode);
          }}
          ref={changeFormRef}
        >
          <div className="inventory-form-note">
            <strong>¿Qué cambio quieres registrar?</strong>
            <p className="table-note">
              Los cambios sirven para documentar desviaciones contra la línea base y, si aplica, pedir aprobación antes de aplicarlos.
            </p>
          </div>

          <FormGrid>
            <Field label="Tipo de cambio">
              <select
                disabled={changeModalReadOnly}
                onChange={(event) => setChangeForm((current) => ({ ...current, tipo_cambio: event.target.value }))}
                value={changeForm.tipo_cambio}
              >
                {pmChangeTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Línea base relacionada">
              <select
                disabled={changeModalReadOnly}
                onChange={(event) => setChangeForm((current) => ({ ...current, linea_base_id: event.target.value }))}
                value={changeForm.linea_base_id}
              >
                <option value="">Sin relación directa</option>
                {baselines.map((baseline) => (
                  <option key={baseline.id} value={baseline.id}>
                    {baseline.nombre} · v{baseline.version}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Título" span={2}>
              <input
                disabled={changeModalReadOnly}
                onChange={(event) => setChangeForm((current) => ({ ...current, titulo: event.target.value }))}
                required
                type="text"
                value={changeForm.titulo}
              />
            </Field>

            <Field label="Motivo" span={2}>
              <textarea
                disabled={changeModalReadOnly}
                onChange={(event) => setChangeForm((current) => ({ ...current, motivo: event.target.value }))}
                rows={3}
                value={changeForm.motivo}
              />
            </Field>

            <Field label="Descripción" span={2}>
              <textarea
                disabled={changeModalReadOnly}
                onChange={(event) => setChangeForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={3}
                value={changeForm.descripcion}
              />
            </Field>

            <Field label="Impacto en días">
              <input
                disabled={changeModalReadOnly}
                onChange={(event) => setChangeForm((current) => ({ ...current, impacto_dias: Number(event.target.value || 0) }))}
                type="number"
                value={changeForm.impacto_dias}
              />
            </Field>

            <Field label="Impacto en costo">
              <input
                disabled={changeModalReadOnly}
                min="0"
                onChange={(event) => setChangeForm((current) => ({ ...current, impacto_costo: event.target.value }))}
                step="0.01"
                type="number"
                value={changeForm.impacto_costo}
              />
            </Field>

            <Field label="Requiere aprobación" span={2}>
              <label className="inventory-checkbox">
                <input
                  checked={changeForm.requiere_aprobacion}
                  disabled={changeModalReadOnly}
                  onChange={(event) => setChangeForm((current) => ({ ...current, requiere_aprobacion: event.target.checked }))}
                  type="checkbox"
                />
                <span>Este cambio debe aprobarse antes de aplicarse</span>
              </label>
            </Field>
          </FormGrid>

          {changeForm.requiere_aprobacion ? (
            <div className="inventory-form-note inventory-form-note-warning">
              <strong>Cambio con aprobación</strong>
              <p className="table-note">Al guardar, podrás enviar este cambio a aprobación.</p>
            </div>
          ) : null}

          {changeForm.tipo_cambio === "fecha" ? (
            <FormGrid>
              <Field label="Tarea" span={2}>
                <select
                  disabled={changeModalReadOnly || changeForm.prefill_mode === "deviation"}
                  onChange={(event) => handleTaskSelectionForChange(event.target.value)}
                  required
                  value={changeForm.task_id}
                >
                  <option value="">Selecciona una tarea</option>
                  {tasks.map((task) => (
                    <option key={task.id} value={task.id}>
                      {normalizePmCopy(safeDisplayText(task.titulo))}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label={changeForm.prefill_mode === "deviation" ? "Fecha inicio base" : "Fecha inicio actual"}>
                <input disabled type="date" value={changeForm.fecha_inicio_referencia || ""} />
              </Field>

              <Field label={changeForm.prefill_mode === "deviation" ? "Fecha fin base" : "Fecha fin actual"}>
                <input disabled type="date" value={changeForm.fecha_fin_referencia || ""} />
              </Field>

              <Field label={changeForm.prefill_mode === "deviation" ? "Fecha inicio actual" : "Nueva fecha inicio"}>
                <input
                  disabled={changeModalReadOnly}
                  onChange={(event) => setChangeForm((current) => ({ ...current, fecha_inicio_objetivo: event.target.value }))}
                  required
                  type="date"
                  value={changeForm.fecha_inicio_objetivo}
                />
              </Field>

              <Field label={changeForm.prefill_mode === "deviation" ? "Fecha fin actual" : "Nueva fecha fin"}>
                <input
                  disabled={changeModalReadOnly}
                  onChange={(event) => setChangeForm((current) => ({ ...current, fecha_fin_objetivo: event.target.value }))}
                  required
                  type="date"
                  value={changeForm.fecha_fin_objetivo}
                />
              </Field>
            </FormGrid>
          ) : (
            <FormGrid>
              <Field label="Entidad relacionada">
                <select
                  disabled={changeModalReadOnly}
                  onChange={(event) => setChangeForm((current) => ({ ...current, entidad_tipo: event.target.value }))}
                  value={changeForm.entidad_tipo}
                >
                  <option value="">Sin relación directa</option>
                  <option value="tarea">Tarea</option>
                  <option value="presupuesto">Presupuesto</option>
                  <option value="documento">Documento</option>
                  <option value="otro">Otro</option>
                </select>
              </Field>

              <Field label="ID relacionado">
                <input
                  disabled={changeModalReadOnly}
                  onChange={(event) => setChangeForm((current) => ({ ...current, entidad_id: event.target.value }))}
                  type="text"
                  value={changeForm.entidad_id}
                />
              </Field>
            </FormGrid>
          )}
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton onClick={closeDeviationPicker} type="button">
              Cancelar
            </ActionButton>
            <ActionButton onClick={handleConfirmDeviationPicker} tone="primary" type="button">
              Crear cambio
            </ActionButton>
          </div>
        )}
        onClose={closeDeviationPicker}
        open={deviationPickerOpen}
        size="medium"
        subtitle="Selecciona una desviación detectada para registrarla como cambio formal."
        title="Crear cambio desde desviación"
      >
        <FormGrid columns={1}>
          <Field
            hint="Se usarán las fechas base y actuales del comparativo para prellenar el cambio."
            label="Desviación detectada"
          >
            <select
              onChange={(event) => setSelectedDeviationTaskId(event.target.value)}
              value={selectedDeviationTaskId}
            >
              {deviationsWithoutChange.map((row) => (
                <option key={safeDisplayText(row?.task_id, "")} value={safeDisplayText(row?.task_id, "")}>
                  {normalizePmCopy(safeDisplayText(row?.tarea_titulo))} — {formatDeltaDays(row?.desviacion_dias_fin)}
                </option>
              ))}
            </select>
          </Field>
        </FormGrid>
      </ModalShell>
    </>
  );
}
