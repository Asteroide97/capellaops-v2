import { useEffect, useMemo, useState } from "react";
import {
  Ban,
  CheckCheck,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Wallet,
  XCircle,
} from "lucide-react";

import {
  addPmEstimationDetail,
  approvePmEstimation,
  cancelPmEstimation,
  createPmProjectEstimation,
  deactivatePmEstimationDetail,
  getPmEstimation,
  getPmProjectBudget,
  getPmProjectEstimationsSummary,
  listPmProjectChanges,
  listPmProjectEstimationCandidates,
  listPmProjectEstimations,
  markPmEstimationCollected,
  markPmEstimationSent,
  rejectPmEstimation,
  returnPmEstimationToDraft,
  submitPmEstimation,
  updatePmEstimation,
  updatePmEstimationDetail,
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
  formatPercent,
  getEstimationStatusLabel,
  getEstimationStatusTone,
  normalizePmCopy,
} from "./shared";

const defaultEstimationForm = {
  id: null,
  nombre: "",
  periodo_inicio: "",
  periodo_fin: "",
  descripcion: "",
  retencion_pct: "0",
  anticipo_aplicado: "0",
  requiere_aprobacion: true,
  linea_base_id: "",
};

const defaultDetailForm = {
  id: null,
  presupuesto_partida_id: "",
  tarea_id: "",
  avance_anterior_pct: 0,
  avance_actual_pct: "",
  notas: "",
};

const defaultCollectForm = {
  amount: "",
  mode: "collect",
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

function formatEstimationPeriod(item) {
  const start = safeDisplayText(formatDate(item?.periodo_inicio), "");
  const end = safeDisplayText(formatDate(item?.periodo_fin), "");
  if (start && end) {
    return `${start} — ${end}`;
  }
  return start || end || "Sin periodo";
}

function getEstimationStatus(item) {
  return String(item?.estatus ?? "").toLowerCase();
}

function getEstimationActiveDetailsCount(item) {
  if (item?.partidas_activas_count !== undefined && item?.partidas_activas_count !== null) {
    return Number(item.partidas_activas_count || 0);
  }
  return (item?.details ?? []).filter((detail) => detail?.activo !== false).length;
}

function estimationHasActiveDetails(item) {
  return getEstimationActiveDetailsCount(item) > 0;
}

function estimationHasGrossAmount(item) {
  return Number(item?.monto_bruto ?? 0) > 0;
}

function estimationCanSubmit(item) {
  return getEstimationStatus(item) === "borrador" && estimationHasActiveDetails(item) && estimationHasGrossAmount(item);
}

function getEstimationSubmitHelp(item) {
  if (!estimationHasActiveDetails(item)) {
    return "Agrega al menos una partida antes de enviar.";
  }
  if (!estimationHasGrossAmount(item)) {
    return "La estimación necesita monto mayor a $0.00.";
  }
  return "";
}

function getEstimationNextStep(item) {
  const status = getEstimationStatus(item);
  if (status === "borrador") {
    if (!estimationHasActiveDetails(item)) {
      return "Agrega al menos una partida.";
    }
    if (!estimationHasGrossAmount(item)) {
      return "Captura avance mayor a 0% para calcular el monto.";
    }
    return "Envía la estimación a aprobación.";
  }
  if (status === "enviada_aprobacion") {
    return "Espera aprobación o apruébala desde esta pantalla.";
  }
  if (status === "aprobada") {
    if (estimationHasNoPendingBalance(item)) {
      return "Cierra la estimación sin saldo.";
    }
    return "Marca enviada o cobrada.";
  }
  if (status === "enviada_cliente") {
    if (estimationHasNoPendingBalance(item)) {
      return "Cierra la estimación sin saldo.";
    }
    return "Registra el cobro cuando se confirme el pago.";
  }
  if (status === "cobrada") {
    if (estimationShouldShowClosedWithoutBalance(item)) {
      return "La estimación quedó cerrada sin saldo por cobrar.";
    }
    return "La estimación ya quedó cobrada.";
  }
  if (status === "rechazada") {
    return "Revisa el rechazo antes de crear una nueva estimación.";
  }
  if (status === "cancelada") {
    return "La estimación fue cancelada.";
  }
  return "";
}

function estimationCanEdit(item) {
  return getEstimationStatus(item) === "borrador";
}

function estimationCanApprove(item) {
  return getEstimationStatus(item) === "enviada_aprobacion";
}

function estimationCanReject(item) {
  return getEstimationStatus(item) === "enviada_aprobacion";
}

function estimationCanReturnToDraft(item) {
  return getEstimationStatus(item) === "enviada_aprobacion";
}

function estimationCanCancel(item) {
  return ["borrador", "enviada_aprobacion"].includes(getEstimationStatus(item));
}

function estimationCanMarkSent(item) {
  return getEstimationStatus(item) === "aprobada";
}

function estimationCanMarkCollected(item) {
  return ["aprobada", "enviada_cliente"].includes(getEstimationStatus(item));
}

function estimationHasNoPendingBalance(item) {
  return Number(item?.monto_neto ?? 0) <= 0 || Number(item?.saldo_pendiente ?? 0) <= 0;
}

function estimationShouldShowClosedWithoutBalance(item) {
  return (
    getEstimationStatus(item) === "cobrada" &&
    Number(item?.monto_cobrado ?? 0) <= 0 &&
    estimationHasNoPendingBalance(item)
  );
}

function estimationCanCloseWithoutBalance(item) {
  return estimationCanMarkCollected(item) && estimationHasNoPendingBalance(item);
}

function estimationNeedsCollectionAmount(item) {
  return estimationCanMarkCollected(item) && !estimationHasNoPendingBalance(item);
}

function getDisplayedEstimationStatusLabel(item) {
  if (estimationShouldShowClosedWithoutBalance(item)) {
    return "Cerrada sin saldo";
  }
  return getEstimationStatusLabel(item?.estatus);
}

function getDisplayedEstimationStatusTone(item) {
  if (estimationShouldShowClosedWithoutBalance(item)) {
    return "success";
  }
  return getEstimationStatusTone(item?.estatus);
}

function getPrimaryDetailActionLabel(item) {
  return estimationHasActiveDetails(item) ? "Editar partidas" : "Agregar partida";
}

function buildEstimationPayload(form) {
  return {
    nombre: form.nombre.trim(),
    periodo_inicio: form.periodo_inicio || null,
    periodo_fin: form.periodo_fin || null,
    descripcion: form.descripcion.trim() || null,
    retencion_pct: form.retencion_pct === "" ? 0 : Number(form.retencion_pct || 0),
    anticipo_aplicado: form.anticipo_aplicado === "" ? 0 : Number(form.anticipo_aplicado || 0),
    requiere_aprobacion: Boolean(form.requiere_aprobacion),
    linea_base_id: form.linea_base_id || null,
  };
}

function buildDetailPayload(form) {
  return {
    presupuesto_partida_id: form.presupuesto_partida_id || null,
    tarea_id: form.tarea_id || null,
    avance_actual_pct: form.avance_actual_pct === "" ? 0 : Number(form.avance_actual_pct || 0),
    notas: form.notas.trim() || null,
  };
}

function buildDetailPreview(candidate, currentProgress, fallbackPreviousProgress = 0) {
  if (!candidate) {
    return {
      previousProgress: Number(fallbackPreviousProgress || 0),
      currentProgress: Number(currentProgress || 0),
      periodProgress: 0,
      periodAmount: 0,
      accumulatedAmount: 0,
      remainingAmount: 0,
    };
  }
  const previousProgress = Number(fallbackPreviousProgress ?? candidate.avance_estimado_anterior ?? 0);
  const nextProgress = Number(currentProgress || 0);
  const normalizedCurrent = Number.isFinite(nextProgress) ? nextProgress : 0;
  const periodProgress = Math.max(0, normalizedCurrent - previousProgress);
  const budgetAmount = Number(candidate.importe_presupuestado ?? 0);
  const periodAmount = (budgetAmount * periodProgress) / 100;
  const accumulatedAmount = (budgetAmount * normalizedCurrent) / 100;
  const remainingAmount = Math.max(0, budgetAmount - accumulatedAmount);
  return {
    previousProgress,
    currentProgress: normalizedCurrent,
    periodProgress,
    periodAmount,
    accumulatedAmount,
    remainingAmount,
  };
}

export default function PMProjectEstimationsTab({
  canApprove = false,
  canEdit = false,
  canManage = false,
  empresaId,
  onChanged,
  onOpenApprovals,
  onOpenBudget,
  projectEditable = true,
  projectId,
  token,
}) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [budgetBundle, setBudgetBundle] = useState(null);
  const [estimations, setEstimations] = useState([]);
  const [summary, setSummary] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [pendingChanges, setPendingChanges] = useState([]);
  const [estimationModalOpen, setEstimationModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [detailLineModalOpen, setDetailLineModalOpen] = useState(false);
  const [collectModalOpen, setCollectModalOpen] = useState(false);
  const [estimationForm, setEstimationForm] = useState(defaultEstimationForm);
  const [detailForm, setDetailForm] = useState(defaultDetailForm);
  const [collectForm, setCollectForm] = useState(defaultCollectForm);
  const [selectedEstimation, setSelectedEstimation] = useState(null);
  const [collectTarget, setCollectTarget] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [detailSubmitting, setDetailSubmitting] = useState(false);
  const [collectSubmitting, setCollectSubmitting] = useState(false);
  const [collectError, setCollectError] = useState("");
  const [actionLoading, setActionLoading] = useState({});

  const hasBudget = Boolean(budgetBundle?.budget?.id);
  const hasPendingChanges = (pendingChanges?.length ?? 0) > 0;
  const budgetNotApproved = String(budgetBundle?.budget?.estatus ?? "").toLowerCase() !== "aprobado";
  const canEditDrafts = canEdit && projectEditable;
  const canApproveEstimations = canApprove && projectEditable;
  const canManageCommercialFlow = canManage && projectEditable;
  const estimationCanEdit = (item) => getEstimationStatus(item) === "borrador" && canEditDrafts;
  const estimationCanApprove = (item) => getEstimationStatus(item) === "enviada_aprobacion" && canApproveEstimations;
  const estimationCanReject = (item) => getEstimationStatus(item) === "enviada_aprobacion" && canApproveEstimations;
  const estimationCanReturnToDraft = (item) => getEstimationStatus(item) === "enviada_aprobacion" && canEditDrafts;
  const estimationCanCancel = (item) =>
    ["borrador", "enviada_aprobacion"].includes(getEstimationStatus(item)) && canEditDrafts;
  const estimationCanSubmit = (item) =>
    getEstimationStatus(item) === "borrador" &&
    estimationHasActiveDetails(item) &&
    estimationHasGrossAmount(item) &&
    canEditDrafts;
  const estimationCanMarkSent = (item) => getEstimationStatus(item) === "aprobada" && canManageCommercialFlow;
  const estimationCanMarkCollected = (item) =>
    ["aprobada", "enviada_cliente"].includes(getEstimationStatus(item)) && canManageCommercialFlow;
  const estimationCanCloseWithoutBalance = (item) =>
    estimationCanMarkCollected(item) && estimationHasNoPendingBalance(item);
  const estimationNeedsCollectionAmount = (item) =>
    estimationCanMarkCollected(item) && !estimationHasNoPendingBalance(item);

  const selectedCandidate = useMemo(() => {
    if (!detailForm.presupuesto_partida_id) {
      return null;
    }
    const fromCandidates = candidates.find((item) => item.partida_id === detailForm.presupuesto_partida_id);
    if (fromCandidates) {
      return fromCandidates;
    }
    const fromDetail = selectedEstimation?.details?.find(
      (item) => item.presupuesto_partida_id === detailForm.presupuesto_partida_id,
    );
    if (!fromDetail) {
      return null;
    }
    return {
      partida_id: fromDetail.presupuesto_partida_id,
      codigo: fromDetail.codigo_snapshot,
      nombre: fromDetail.concepto_snapshot,
      unidad: fromDetail.unidad_snapshot,
      cantidad: fromDetail.cantidad_presupuestada,
      precio_unitario: fromDetail.precio_unitario_snapshot,
      importe_presupuestado: fromDetail.importe_presupuestado,
      avance_estimado_anterior: fromDetail.avance_anterior_pct,
      saldo_por_estimar: fromDetail.saldo_por_estimar,
    };
  }, [candidates, detailForm.presupuesto_partida_id, selectedEstimation]);

  const detailPreview = useMemo(
    () => buildDetailPreview(selectedCandidate, detailForm.avance_actual_pct, detailForm.avance_anterior_pct),
    [detailForm.avance_actual_pct, detailForm.avance_anterior_pct, selectedCandidate],
  );

  async function loadData({ background = false } = {}) {
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const [budgetResponse, estimationResponse, summaryResponse, candidateResponse, pendingChangeResponse] =
        await Promise.all([
          getPmProjectBudget({ empresaId, projectId, token }),
          listPmProjectEstimations({ empresaId, projectId, token }),
          getPmProjectEstimationsSummary({ empresaId, projectId, token }),
          listPmProjectEstimationCandidates({ empresaId, projectId, token }),
          listPmProjectChanges({
            empresaId,
            projectId,
            token,
            params: { estatus: "pendiente_aprobacion" },
          }),
        ]);
      setBudgetBundle(budgetResponse);
      setEstimations(estimationResponse ?? []);
      setSummary(summaryResponse);
      setCandidates(candidateResponse ?? []);
      setPendingChanges(pendingChangeResponse ?? []);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "No se pudieron cargar las estimaciones del proyecto."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function loadEstimationDetail(estimationId, { open = true } = {}) {
    const detail = await getPmEstimation({ empresaId, estimationId, token });
    setSelectedEstimation(detail);
    if (open) {
      setDetailModalOpen(true);
    }
    return detail;
  }

  useEffect(() => {
    loadData();
  }, [empresaId, projectId, token]);

  function closeEstimationModal(force = false) {
    if (submitting && !force) {
      return;
    }
    setEstimationModalOpen(false);
    setEstimationForm(defaultEstimationForm);
  }

  function openCreateModal() {
    setEstimationForm(defaultEstimationForm);
    setEstimationModalOpen(true);
  }

  function openEditModal(item) {
    setEstimationForm({
      id: item.id,
      nombre: item.nombre ?? "",
      periodo_inicio: item.periodo_inicio ?? "",
      periodo_fin: item.periodo_fin ?? "",
      descripcion: item.descripcion ?? "",
      retencion_pct: String(item.retencion_pct ?? 0),
      anticipo_aplicado: String(item.anticipo_aplicado ?? 0),
      requiere_aprobacion: Boolean(item.requiere_aprobacion),
      linea_base_id: item.linea_base_id ?? "",
    });
    setEstimationModalOpen(true);
  }

  async function handleSaveEstimation() {
    const isEditing = Boolean(estimationForm.id);
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildEstimationPayload(estimationForm);
      const saved = isEditing
        ? await updatePmEstimation({ empresaId, estimationId: estimationForm.id, payload, token })
        : await createPmProjectEstimation({ empresaId, projectId, payload, token });
      closeEstimationModal(true);
      await loadData({ background: true });
      if (!isEditing) {
        await loadEstimationDetail(saved.id);
      }
      setSuccess(
        isEditing
          ? "Estimación actualizada."
          : "Estimación creada. Agrega partidas para calcular el monto.",
      );
      onChanged?.();
    } catch (saveError) {
      setError(getErrorMessage(saveError, "No se pudo guardar la estimación."));
    } finally {
      setSubmitting(false);
    }
  }

  function closeDetailModal() {
    setDetailModalOpen(false);
    setSelectedEstimation(null);
  }

  function closeDetailLineModal(force = false) {
    if (detailSubmitting && !force) {
      return;
    }
    setDetailLineModalOpen(false);
    setDetailForm(defaultDetailForm);
  }

  function openAddDetailModal() {
    setError("");
    setDetailForm(defaultDetailForm);
    setDetailLineModalOpen(true);
  }

  function openEditDetailModal(detail) {
    setError("");
    setDetailForm({
      id: detail.id,
      presupuesto_partida_id: detail.presupuesto_partida_id ?? "",
      tarea_id: detail.tarea_id ?? "",
      avance_anterior_pct: Number(detail.avance_anterior_pct ?? 0),
      avance_actual_pct: String(detail.avance_actual_pct ?? 0),
      notas: detail.notas ?? "",
    });
    setDetailLineModalOpen(true);
  }

  function openPreferredDetailEditor(estimation = selectedEstimation) {
    const activeDetails = (estimation?.details ?? []).filter((detail) => detail?.activo !== false);
    if (activeDetails.length === 0) {
      openAddDetailModal();
      return;
    }
    const detailToEdit =
      activeDetails.find((detail) => Number(detail?.avance_actual_pct ?? 0) <= 0) ?? activeDetails[0];
    openEditDetailModal(detailToEdit);
  }

  function openCollectModal(estimation) {
    if (!estimation?.id) {
      return;
    }
    setError("");
    setCollectError("");
    setCollectTarget(estimation);
    setCollectForm({
      amount: estimationCanCloseWithoutBalance(estimation)
        ? "0"
        : String(Number(estimation?.saldo_pendiente ?? 0) || ""),
      mode: estimationCanCloseWithoutBalance(estimation) ? "close_without_balance" : "collect",
    });
    setCollectModalOpen(true);
  }

  function closeCollectModal(force = false) {
    if (collectSubmitting && !force) {
      return;
    }
    setCollectModalOpen(false);
    setCollectTarget(null);
    setCollectForm(defaultCollectForm);
    setCollectError("");
  }

  async function handleSaveDetail() {
    if (!selectedEstimation?.id) {
      return;
    }
    const estimationId = selectedEstimation.id;
    setDetailSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildDetailPayload(detailForm);
      const currentProgress = Number(payload.avance_actual_pct ?? 0);
      if (detailForm.id) {
        await updatePmEstimationDetail({
          detailId: detailForm.id,
          empresaId,
          payload,
          token,
        });
        setSuccess(
          currentProgress > 0
            ? "Partida actualizada. Ya puedes enviar la estimación a aprobación."
            : "Partida actualizada. Captura avance mayor a 0% para poder enviar a aprobación.",
        );
      } else {
        await addPmEstimationDetail({
          estimationId,
          empresaId,
          payload,
          token,
        });
        setSuccess(
          currentProgress > 0
            ? "Partida agregada. Ya puedes enviar la estimación a aprobación."
            : "Partida agregada. Captura avance mayor a 0% para poder enviar a aprobación.",
        );
      }
      closeDetailLineModal(true);
      await loadEstimationDetail(estimationId);
      await loadData({ background: true });
      onChanged?.();
    } catch (detailError) {
      setError(getErrorMessage(detailError, "No se pudo guardar la partida de la estimación."));
    } finally {
      setDetailSubmitting(false);
    }
  }

  async function handleDeactivateDetail(detailId) {
    if (!selectedEstimation?.id) {
      return;
    }
    const actionKey = `detail:${detailId}:deactivate`;
    setActionLoading((current) => ({ ...current, [actionKey]: true }));
    setError("");
    setSuccess("");
    try {
      await deactivatePmEstimationDetail({ detailId, empresaId, token });
      setSuccess("Partida retirada de la estimación.");
      await Promise.all([loadEstimationDetail(selectedEstimation.id, { open: false }), loadData({ background: true })]);
      onChanged?.();
    } catch (actionError) {
      setError(getErrorMessage(actionError, "No se pudo retirar la partida de la estimación."));
    } finally {
      setActionLoading((current) => ({ ...current, [actionKey]: false }));
    }
  }

  async function handleReturnToDraft(item, { keepDetailOpen = false } = {}) {
    if (!item?.id) {
      return;
    }
    const confirmed = window.confirm(
      "La estimación volverá a borrador para que puedas editar partidas y montos. La aprobación pendiente quedará cancelada o sin efecto.",
    );
    if (!confirmed) {
      return;
    }
    await runEstimationAction(
      item,
      `estimation:${item.id}:return`,
      () => returnPmEstimationToDraft({ empresaId, estimationId: item.id, token }),
      "Estimación regresada a borrador.",
      { reloadDetail: keepDetailOpen, closeDetail: false },
    );
  }

  async function handleConfirmCollection() {
    if (!collectTarget?.id) {
      return;
    }
    const isClosingWithoutBalance = collectForm.mode === "close_without_balance";
    const payload = isClosingWithoutBalance
      ? { monto_cobrado: 0 }
      : { monto_cobrado: Number(collectForm.amount || 0) };
    if (!isClosingWithoutBalance && Number(payload.monto_cobrado) <= 0) {
      setCollectError("Debes capturar un monto cobrado mayor a $0.00.");
      return;
    }

    setCollectSubmitting(true);
    setError("");
    setCollectError("");
    setSuccess("");
    try {
      await markPmEstimationCollected({
        empresaId,
        estimationId: collectTarget.id,
        payload,
        token,
      });
      closeCollectModal(true);
      await loadData({ background: true });
      if (selectedEstimation?.id === collectTarget.id && detailModalOpen) {
        await loadEstimationDetail(collectTarget.id, { open: false });
      }
      setSuccess(
        isClosingWithoutBalance
          ? "Estimación cerrada sin saldo."
          : "Cobranza registrada.",
      );
      onChanged?.();
    } catch (actionError) {
      setCollectError(getErrorMessage(actionError, "No se pudo cerrar la estimación."));
    } finally {
      setCollectSubmitting(false);
    }
  }

  async function runEstimationAction(item, actionKey, operation, successMessage, { reloadDetail = false, closeDetail = false } = {}) {
    setActionLoading((current) => ({ ...current, [actionKey]: true }));
    setError("");
    setSuccess("");
    try {
      await operation();
      setSuccess(successMessage);
      await loadData({ background: true });
      if (reloadDetail && item?.id) {
        await loadEstimationDetail(item.id, { open: !closeDetail });
      }
      if (closeDetail) {
        closeDetailModal();
      }
      onChanged?.();
    } catch (actionError) {
      setError(getErrorMessage(actionError, "No se pudo completar la acción sobre la estimación."));
    } finally {
      setActionLoading((current) => ({ ...current, [actionKey]: false }));
    }
  }

  const summaryCards = [
    { label: "Total estimado", value: formatMoney(summary?.total_estimado ?? 0), tone: "info", meta: "Monto neto registrado" },
    { label: "Total aprobado", value: formatMoney(summary?.total_aprobado ?? 0), tone: "success", meta: "Listo para envío o cobro" },
    { label: "Total cobrado", value: formatMoney(summary?.total_cobrado ?? 0), tone: "success", meta: "Cobranza registrada" },
    { label: "Pendiente por cobrar", value: formatMoney(summary?.pendiente_por_cobrar ?? 0), tone: "warning", meta: "Saldo comercial" },
    { label: "% presupuesto estimado", value: formatPercent(summary?.porcentaje_presupuesto_estimado ?? 0), tone: "neutral", meta: "Sobre venta presupuestada" },
  ];

  if (loading) {
    return (
      <DataCard subtitle="Genera estados de pago internos a partir del avance del presupuesto." title="Estimaciones">
        <p className="table-note">Cargando estimaciones...</p>
      </DataCard>
    );
  }

  if (!hasBudget) {
    return (
      <DataCard subtitle="Genera estados de pago internos a partir del avance del presupuesto." title="Estimaciones">
        <EmptyState
          actions={(
            <ActionButton onClick={onOpenBudget} tone="primary" type="button">
              Ir a Presupuesto
            </ActionButton>
          )}
          note="Para este MVP, las estimaciones se generan sobre partidas activas del presupuesto."
          title="Este proyecto necesita un presupuesto para generar estimaciones."
        />
      </DataCard>
    );
  }

  return (
    <div className="pm-estimations-stack">
      <DataCard
        actions={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={refreshing} onClick={() => loadData({ background: true })} type="button">
              <RefreshCw size={16} />
              {refreshing ? "Actualizando..." : "Actualizar"}
            </ActionButton>
            {canEditDrafts ? (
              <ActionButton onClick={openCreateModal} tone="primary" type="button">
                <Plus size={16} />
                Nueva estimación
              </ActionButton>
            ) : null}
          </div>
        )}
        subtitle="Genera estados de pago internos a partir del avance del presupuesto."
        title="Estimaciones"
      >
        {error ? <div className="inventory-inline-error">{normalizePmCopy(error)}</div> : null}
        {success ? <div className="inventory-inline-success">{normalizePmCopy(success)}</div> : null}

        {hasPendingChanges || budgetNotApproved ? (
          <div className="pm-estimation-warning">
            {hasPendingChanges ? (
              <p className="table-note">
                Hay cambios pendientes de aprobación que podrían afectar esta estimación.
              </p>
            ) : null}
            {budgetNotApproved ? (
              <p className="table-note">
                El presupuesto activo todavía no está aprobado. Puedes estimar, pero conviene revisar el plan comercial antes de enviarla.
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="inventory-metric-grid inventory-metric-grid-5">
          {summaryCards.map((card) => (
            <MetricCard key={card.label} label={card.label} meta={card.meta} tone={card.tone} value={card.value} />
          ))}
        </div>
      </DataCard>

      <DataCard subtitle="Seguimiento comercial por estimación." title="Listado de estimaciones">
        <div className="pm-estimation-guide">
          <strong>Flujo recomendado</strong>
          <div className="pm-estimation-guide-steps">
            {["Crea borrador", "Agrega partidas", "Envía a aprobación", "Aprueba", "Marca enviada o cobrada"].map(
              (step, index) => (
                <div className="pm-estimation-guide-step" key={step}>
                  <span className="pm-estimation-guide-step-number">{index + 1}</span>
                  <span>{step}</span>
                </div>
              ),
            )}
          </div>
        </div>
        {(estimations?.length ?? 0) === 0 ? (
          <EmptyState
            actions={(
            canEditDrafts ? (
              <ActionButton onClick={openCreateModal} tone="primary" type="button">
                Registrar estimación
              </ActionButton>
            ) : null
          )}
          note={canEditDrafts ? "Crea la primera estimación del proyecto para controlar monto aprobado, enviado y cobrado." : "No tienes permiso para crear estimaciones en este proyecto."}
          title="Aún no hay estimaciones registradas"
        />
        ) : (
          <DataTable columns={["Folio / nombre", "Periodo", "Estatus", "Bruto", "Retención", "Neto", "Cobrado", "Pendiente", "Acciones"]}>
            <tbody>
              {estimations.map((item) => {
                const status = getEstimationStatus(item);
                const actionPrefix = `estimation:${item.id}`;
                const hasDetails = estimationHasActiveDetails(item);
                const canSubmit = status === "borrador" && hasDetails && estimationHasGrossAmount(item);
                return (
                  <tr key={item.id}>
                    <td>
                      <div className="pm-estimation-cell-title">
                        <strong>{safeDisplayText(item.folio, "Sin folio")}</strong>
                        <span>{normalizePmCopy(safeDisplayText(item.nombre))}</span>
                      </div>
                    </td>
                    <td>{formatEstimationPeriod(item)}</td>
                    <td>
                      <StatusBadge tone={getDisplayedEstimationStatusTone(item)}>
                        {getDisplayedEstimationStatusLabel(item)}
                      </StatusBadge>
                    </td>
                    <td>{formatMoney(item.monto_bruto ?? 0)}</td>
                    <td>{formatMoney(item.retencion_monto ?? 0)}</td>
                    <td>{formatMoney(item.monto_neto ?? 0)}</td>
                    <td>{formatMoney(item.monto_cobrado ?? 0)}</td>
                    <td>{formatMoney(item.saldo_pendiente ?? 0)}</td>
                    <td>
                      <div className="pm-estimation-actions">
                        <ActionButton onClick={() => loadEstimationDetail(item.id)} type="button">
                          <Eye size={14} />
                          Ver detalle
                        </ActionButton>
                        {estimationCanEdit(item) && canEditDrafts ? (
                          <ActionButton onClick={() => openEditModal(item)} type="button">
                            <Pencil size={14} />
                            Editar
                          </ActionButton>
                        ) : null}
                        {status === "borrador" && canEditDrafts ? (
                          <ActionButton
                            onClick={async () => {
                              await loadEstimationDetail(item.id);
                              if (!hasDetails) {
                                openAddDetailModal();
                              }
                            }}
                            tone="primary"
                            type="button"
                          >
                            <Plus size={14} />
                            {getPrimaryDetailActionLabel(item)}
                          </ActionButton>
                        ) : null}
                        {canSubmit && canEditDrafts ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:submit`])}
                            onClick={() =>
                              runEstimationAction(
                                item,
                                `${actionPrefix}:submit`,
                                () => submitPmEstimation({ empresaId, estimationId: item.id, token }),
                                "Estimación enviada a aprobación.",
                              )
                            }
                            tone="primary"
                            type="button"
                          >
                            <Send size={14} />
                            Enviar a aprobación
                          </ActionButton>
                        ) : null}
                        {status === "enviada_aprobacion" ? (
                          <ActionButton onClick={onOpenApprovals} type="button">
                            <CheckCheck size={14} />
                            Ver aprobación
                          </ActionButton>
                        ) : null}
                        {estimationCanApprove(item) && canApproveEstimations ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:approve`])}
                            onClick={() =>
                              runEstimationAction(
                                item,
                                `${actionPrefix}:approve`,
                                () => approvePmEstimation({ empresaId, estimationId: item.id, token }),
                                "Estimación aprobada.",
                              )
                            }
                            tone="success"
                            type="button"
                          >
                            <CheckCheck size={14} />
                            Aprobar
                          </ActionButton>
                        ) : null}
                        {estimationCanReject(item) && canApproveEstimations ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:reject`])}
                            onClick={() =>
                              runEstimationAction(
                                item,
                                `${actionPrefix}:reject`,
                                () => rejectPmEstimation({ empresaId, estimationId: item.id, token }),
                                "Estimación rechazada.",
                              )
                            }
                            tone="danger"
                            type="button"
                          >
                            <XCircle size={14} />
                            Rechazar
                          </ActionButton>
                        ) : null}
                        {estimationCanReturnToDraft(item) && canEditDrafts ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:return`])}
                            onClick={() => handleReturnToDraft(item)}
                            type="button"
                          >
                            <RefreshCw size={14} />
                            Regresar a borrador
                          </ActionButton>
                        ) : null}
                        {estimationCanMarkSent(item) && canManageCommercialFlow ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:sent`])}
                            onClick={() =>
                              runEstimationAction(
                                item,
                                `${actionPrefix}:sent`,
                                () => markPmEstimationSent({ empresaId, estimationId: item.id, token }),
                                "Estimación marcada como enviada al cliente.",
                              )
                            }
                            type="button"
                          >
                            <Send size={14} />
                            Marcar enviada
                          </ActionButton>
                        ) : null}
                        {estimationNeedsCollectionAmount(item) && canManageCommercialFlow ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:collected`])}
                            onClick={() => openCollectModal(item)}
                            tone="success"
                            type="button"
                          >
                            <Wallet size={14} />
                            Marcar cobrada
                          </ActionButton>
                        ) : null}
                        {estimationCanCloseWithoutBalance(item) && canManageCommercialFlow ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:collected`])}
                            onClick={() => openCollectModal(item)}
                            tone="success"
                            title="Esta estimación no tiene saldo por cobrar porque el anticipo o ajustes cubren el monto neto."
                            type="button"
                          >
                            <Wallet size={14} />
                            Cerrar sin saldo
                          </ActionButton>
                        ) : null}
                        {estimationCanCancel(item) && canEditDrafts ? (
                          <ActionButton
                            disabled={Boolean(actionLoading[`${actionPrefix}:cancel`])}
                            onClick={() =>
                              runEstimationAction(
                                item,
                                `${actionPrefix}:cancel`,
                                () => cancelPmEstimation({ empresaId, estimationId: item.id, token }),
                                "Estimación cancelada.",
                              )
                            }
                            tone="danger"
                            type="button"
                          >
                            <Ban size={14} />
                            Cancelar
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

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeEstimationModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} onClick={handleSaveEstimation} tone="primary" type="button">
              {submitting ? "Guardando..." : estimationForm.id ? "Guardar borrador" : "Crear borrador"}
            </ActionButton>
          </div>
        )}
        onClose={closeEstimationModal}
        open={estimationModalOpen}
        size="wide"
        subtitle="Primero crea el borrador de la estimación. Después agrega partidas y envíala a aprobación."
        title={estimationForm.id ? "Editar estimación" : "Nueva estimación"}
      >
        <form className="inventory-modal-form" onSubmit={(event) => event.preventDefault()}>
          <FormGrid>
            <Field label="Nombre" span={2}>
              <input
                onChange={(event) => setEstimationForm((current) => ({ ...current, nombre: event.target.value }))}
                required
                type="text"
                value={estimationForm.nombre}
              />
            </Field>
            <Field label="Periodo inicio">
              <input
                onChange={(event) => setEstimationForm((current) => ({ ...current, periodo_inicio: event.target.value }))}
                type="date"
                value={estimationForm.periodo_inicio}
              />
            </Field>
            <Field label="Periodo fin">
              <input
                onChange={(event) => setEstimationForm((current) => ({ ...current, periodo_fin: event.target.value }))}
                type="date"
                value={estimationForm.periodo_fin}
              />
            </Field>
            <Field label="Retención %" span={1}>
              <input
                min="0"
                onChange={(event) => setEstimationForm((current) => ({ ...current, retencion_pct: event.target.value }))}
                step="0.01"
                type="number"
                value={estimationForm.retencion_pct}
              />
            </Field>
            <Field label="Anticipo aplicado" span={1}>
              <input
                min="0"
                onChange={(event) => setEstimationForm((current) => ({ ...current, anticipo_aplicado: event.target.value }))}
                step="0.01"
                type="number"
                value={estimationForm.anticipo_aplicado}
              />
            </Field>
            <Field label="Requiere aprobación" span={2}>
              <label className="inventory-checkbox">
                <input
                  checked={estimationForm.requiere_aprobacion}
                  onChange={(event) => setEstimationForm((current) => ({ ...current, requiere_aprobacion: event.target.checked }))}
                  type="checkbox"
                />
                <span>Enviar esta estimación a aprobación antes de marcarla como aprobada</span>
              </label>
            </Field>
            <Field label="Descripción" span={2}>
              <textarea
                onChange={(event) => setEstimationForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={4}
                value={estimationForm.descripcion}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={null}
        onClose={closeDetailModal}
        open={detailModalOpen}
        size="wide"
        subtitle={selectedEstimation ? formatEstimationPeriod(selectedEstimation) : "Detalle de la estimación"}
        title={selectedEstimation ? `${safeDisplayText(selectedEstimation.folio, "Sin folio")} · ${normalizePmCopy(safeDisplayText(selectedEstimation.nombre, "Estimación"))}` : "Detalle de estimación"}
      >
        {selectedEstimation ? (
          <div className="pm-estimation-detail-stack">
            <div className="pm-estimation-detail-header">
              <StatusBadge tone={getDisplayedEstimationStatusTone(selectedEstimation)}>
                {getDisplayedEstimationStatusLabel(selectedEstimation)}
              </StatusBadge>
              <div className="pm-estimation-actions">
                {estimationCanEdit(selectedEstimation) && canEditDrafts ? (
                  <ActionButton onClick={openAddDetailModal} tone="primary" type="button">
                    <Plus size={14} />
                    Agregar partida
                  </ActionButton>
                ) : null}
                {getEstimationStatus(selectedEstimation) === "borrador" && canEditDrafts ? (
                  <ActionButton
                    disabled={!estimationCanSubmit(selectedEstimation) || Boolean(actionLoading[`detail:${selectedEstimation.id}:submit`])}
                    onClick={() =>
                      runEstimationAction(
                        selectedEstimation,
                        `detail:${selectedEstimation.id}:submit`,
                        () => submitPmEstimation({ empresaId, estimationId: selectedEstimation.id, token }),
                        "Estimación enviada a aprobación.",
                        { closeDetail: true },
                      )
                    }
                    tone="primary"
                    title={estimationCanSubmit(selectedEstimation) ? undefined : getEstimationSubmitHelp(selectedEstimation)}
                    type="button"
                  >
                    <Send size={14} />
                    Enviar a aprobación
                  </ActionButton>
                ) : null}
                {String(selectedEstimation.estatus ?? "").toLowerCase() === "enviada_aprobacion" ? (
                  <>
                    <ActionButton onClick={onOpenApprovals} type="button">
                      <CheckCheck size={14} />
                      Ver aprobación
                    </ActionButton>
                    {canApproveEstimations ? (
                      <ActionButton
                        disabled={Boolean(actionLoading[`detail:${selectedEstimation.id}:approve`])}
                        onClick={() =>
                          runEstimationAction(
                            selectedEstimation,
                            `detail:${selectedEstimation.id}:approve`,
                            () => approvePmEstimation({ empresaId, estimationId: selectedEstimation.id, token }),
                            "Estimación aprobada.",
                            { closeDetail: true },
                          )
                        }
                        tone="success"
                        type="button"
                      >
                        Aprobar
                      </ActionButton>
                    ) : null}
                    {canApproveEstimations ? (
                      <ActionButton
                        disabled={Boolean(actionLoading[`detail:${selectedEstimation.id}:reject`])}
                        onClick={() =>
                          runEstimationAction(
                            selectedEstimation,
                            `detail:${selectedEstimation.id}:reject`,
                            () => rejectPmEstimation({ empresaId, estimationId: selectedEstimation.id, token }),
                            "Estimación rechazada.",
                            { closeDetail: true },
                          )
                        }
                        tone="danger"
                        type="button"
                      >
                        Rechazar
                      </ActionButton>
                    ) : null}
                  </>
                ) : null}
                {estimationCanMarkSent(selectedEstimation) ? (
                  <ActionButton
                    disabled={Boolean(actionLoading[`detail:${selectedEstimation.id}:sent`])}
                    onClick={() =>
                      runEstimationAction(
                        selectedEstimation,
                        `detail:${selectedEstimation.id}:sent`,
                        () => markPmEstimationSent({ empresaId, estimationId: selectedEstimation.id, token }),
                        "Estimación marcada como enviada al cliente.",
                        { closeDetail: true },
                      )
                    }
                    type="button"
                  >
                    Marcar enviada
                  </ActionButton>
                ) : null}
                {estimationNeedsCollectionAmount(selectedEstimation) ? (
                  <ActionButton
                    disabled={Boolean(actionLoading[`detail:${selectedEstimation.id}:collected`])}
                    onClick={() => openCollectModal(selectedEstimation)}
                    tone="success"
                    type="button"
                  >
                    Marcar cobrada
                  </ActionButton>
                ) : null}
                {estimationCanCloseWithoutBalance(selectedEstimation) ? (
                  <ActionButton
                    disabled={Boolean(actionLoading[`detail:${selectedEstimation.id}:collected`])}
                    onClick={() => openCollectModal(selectedEstimation)}
                    tone="success"
                    title="Esta estimación no tiene saldo por cobrar porque el anticipo o ajustes cubren el monto neto."
                    type="button"
                  >
                    Cerrar sin saldo
                  </ActionButton>
                ) : null}
              </div>
            </div>

            {estimationCanReturnToDraft(selectedEstimation) ? (
              <div className="inventory-form-note inventory-form-note-warning pm-estimation-warning-block">
                <strong>Esta estimación está en aprobación.</strong>
                <p className="table-note">Para modificarla, regresa la estimación a borrador.</p>
                <ActionButton
                  disabled={Boolean(actionLoading[`estimation:${selectedEstimation.id}:return`])}
                  onClick={() => handleReturnToDraft(selectedEstimation, { keepDetailOpen: true })}
                  type="button"
                >
                  <RefreshCw size={14} />
                  Regresar a borrador
                </ActionButton>
              </div>
            ) : null}
            {selectedEstimation.descripcion ? (
              <p className="table-note">{normalizePmCopy(selectedEstimation.descripcion)}</p>
            ) : null}

            <div className="inventory-form-note">
              <strong>Paso siguiente</strong>
              <p className="table-note">{normalizePmCopy(getEstimationNextStep(selectedEstimation))}</p>
              {getEstimationStatus(selectedEstimation) === "borrador" && !estimationCanSubmit(selectedEstimation) ? (
                <p className="table-note pm-estimation-helper">{normalizePmCopy(getEstimationSubmitHelp(selectedEstimation))}</p>
              ) : null}
            </div>

            {getEstimationStatus(selectedEstimation) === "borrador" && estimationHasActiveDetails(selectedEstimation) && !estimationHasGrossAmount(selectedEstimation) ? (
              <div className="inventory-form-note inventory-form-note-warning pm-estimation-warning-block">
                <strong>No hay monto estimado</strong>
                <p className="table-note">Captura un avance mayor a 0% en al menos una partida para generar importe.</p>
                <ActionButton onClick={() => openPreferredDetailEditor()} type="button">
                  <Pencil size={14} />
                  Editar avance de partida
                </ActionButton>
              </div>
            ) : null}

            {estimationCanCloseWithoutBalance(selectedEstimation) ? (
              <div className="inventory-form-note pm-estimation-zero-balance-note">
                <strong>Sin saldo por cobrar</strong>
                <p className="table-note">Esta estimación no tiene saldo por cobrar porque el anticipo o ajustes cubren el monto neto.</p>
              </div>
            ) : null}

            {(selectedEstimation.details?.length ?? 0) === 0 ? (
              <EmptyState
                actions={estimationCanEdit(selectedEstimation) ? (
                  <ActionButton onClick={openAddDetailModal} tone="primary" type="button">
                    <Plus size={14} />
                    Agregar primera partida
                  </ActionButton>
                ) : null}
                note="Selecciona partidas del presupuesto y captura el avance actual para calcular el monto de la estimación."
                title="Agrega al menos una partida"
              />
            ) : (
              <DataTable
                columns={[
                  "Código",
                  "Concepto",
                  "Unidad",
                  "Importe presupuestado",
                  "Avance anterior %",
                  "Avance actual %",
                  "Avance periodo %",
                  "Importe periodo",
                  "Importe acumulado",
                  "Saldo por estimar",
                  "Acciones",
                ]}
              >
                <tbody>
                  {(selectedEstimation.details ?? []).map((detail) => (
                    <tr key={detail.id}>
                      <td>{safeDisplayText(detail.codigo_snapshot, "—")}</td>
                      <td>{normalizePmCopy(safeDisplayText(detail.concepto_snapshot, "Sin concepto"))}</td>
                      <td>{safeDisplayText(detail.unidad_snapshot, "—")}</td>
                      <td>{formatMoney(detail.importe_presupuestado ?? 0)}</td>
                      <td>{formatPercent(detail.avance_anterior_pct ?? 0)}</td>
                      <td>
                        <div className="pm-estimation-progress-cell">
                          <span>{formatPercent(detail.avance_actual_pct ?? 0)}</span>
                          <StatusBadge tone={Number(detail.avance_actual_pct ?? 0) > 0 ? "success" : "neutral"}>
                            {Number(detail.avance_actual_pct ?? 0) > 0 ? "Con avance" : "Sin avance"}
                          </StatusBadge>
                        </div>
                      </td>
                      <td>{formatPercent(detail.avance_periodo_pct ?? 0)}</td>
                      <td>{formatMoney(detail.importe_periodo ?? 0)}</td>
                      <td>{formatMoney(detail.importe_acumulado ?? 0)}</td>
                      <td>{formatMoney(detail.saldo_por_estimar ?? 0)}</td>
                      <td>
                        {estimationCanEdit(selectedEstimation) ? (
                          <div className="pm-estimation-actions">
                            <ActionButton onClick={() => openEditDetailModal(detail)} type="button">
                              <Pencil size={14} />
                              Editar
                            </ActionButton>
                            <ActionButton
                              disabled={Boolean(actionLoading[`detail:${detail.id}:deactivate`])}
                              onClick={() => handleDeactivateDetail(detail.id)}
                              tone="danger"
                              type="button"
                            >
                              <Ban size={14} />
                              Quitar
                            </ActionButton>
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            )}
            <div className="inventory-metric-grid inventory-metric-grid-4">
              <MetricCard label="Monto bruto" meta="Periodo actual" tone="info" value={formatMoney(selectedEstimation.monto_bruto ?? 0)} />
              <MetricCard label="Anticipo aplicado" meta="Descuento simple" tone="warning" value={formatMoney(selectedEstimation.anticipo_aplicado ?? 0)} />
              <MetricCard label="Retención" meta={`${formatPercent(selectedEstimation.retencion_pct ?? 0)}`} tone="warning" value={formatMoney(selectedEstimation.retencion_monto ?? 0)} />
              <MetricCard label="Monto neto" meta="Estimado del periodo" tone="success" value={formatMoney(selectedEstimation.monto_neto ?? 0)} />
              <MetricCard label="Monto aprobado" meta="Aprobación interna" tone="success" value={formatMoney(selectedEstimation.monto_aprobado ?? 0)} />
              <MetricCard label="Monto cobrado" meta="Cobranza registrada" tone="success" value={formatMoney(selectedEstimation.monto_cobrado ?? 0)} />
              <MetricCard label="Pendiente por cobrar" meta="Saldo comercial" tone="warning" value={formatMoney(selectedEstimation.saldo_pendiente ?? 0)} />
              <MetricCard label="Partidas activas" meta="Dentro de esta estimación" tone="neutral" value={formatNumber(selectedEstimation.details?.length ?? 0)} />
            </div>
          </div>
        ) : null}
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={collectSubmitting} onClick={closeCollectModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              disabled={collectSubmitting}
              onClick={handleConfirmCollection}
              tone="primary"
              type="button"
            >
              {collectSubmitting
                ? "Guardando..."
                : collectForm.mode === "close_without_balance"
                  ? "Cerrar sin saldo"
                  : "Registrar cobro"}
            </ActionButton>
          </div>
        )}
        onClose={closeCollectModal}
        open={collectModalOpen}
        size="wide"
        subtitle={collectTarget ? formatEstimationPeriod(collectTarget) : "Cobro de estimación"}
        title={collectForm.mode === "close_without_balance" ? "Cerrar sin saldo" : "Marcar cobrada"}
      >
        {collectError ? <div className="inventory-inline-error">{normalizePmCopy(collectError)}</div> : null}
        {collectForm.mode === "close_without_balance" ? (
          <div className="inventory-form-note pm-estimation-warning-block">
            <strong>Sin saldo por cobrar</strong>
            <p className="table-note">
              Esta estimación no tiene saldo pendiente. Se cerrará sin registrar cobro adicional.
            </p>
          </div>
        ) : (
          <FormGrid>
            <Field label="Monto cobrado" span={2}>
              <input
                min="0.01"
                onChange={(event) => setCollectForm((current) => ({ ...current, amount: event.target.value }))}
                step="0.01"
                type="number"
                value={collectForm.amount}
              />
            </Field>
            <Field label="Saldo pendiente" span={2}>
              <input
                disabled
                type="text"
                value={collectTarget ? formatMoney(collectTarget.saldo_pendiente ?? 0) : formatMoney(0)}
              />
            </Field>
          </FormGrid>
        )}
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={detailSubmitting} onClick={closeDetailLineModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={detailSubmitting} onClick={handleSaveDetail} tone="primary" type="button">
              {detailSubmitting
                ? "Guardando..."
                : detailForm.id
                  ? "Actualizar partida"
                  : Number(detailForm.avance_actual_pct || 0) > 0
                    ? "Agregar partida"
                    : "Agregar partida sin monto"}
            </ActionButton>
          </div>
        )}
        onClose={closeDetailLineModal}
        open={detailLineModalOpen}
        size="wide"
        subtitle="Captura el avance actual acumulado. Si lo dejas en 0%, la partida se guardará sin monto estimado."
        title={detailForm.id ? "Editar partida de estimación" : "Agregar partida a estimación"}
      >
        <FormGrid>
          <Field label="Partida" span={2}>
            <select
              disabled={Boolean(detailForm.id)}
              onChange={(event) => {
                const candidate = candidates.find((item) => item.partida_id === event.target.value);
                setDetailForm((current) => ({
                  ...current,
                  presupuesto_partida_id: event.target.value,
                  avance_anterior_pct: Number(candidate?.avance_estimado_anterior ?? 0),
                }));
              }}
              value={detailForm.presupuesto_partida_id}
            >
              <option value="">Selecciona una partida</option>
              {candidates.map((candidate) => (
                <option key={candidate.partida_id} value={candidate.partida_id}>
                  {normalizePmCopy(safeDisplayText(candidate.codigo, "SIN-COD"))} · {normalizePmCopy(safeDisplayText(candidate.nombre))}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Importe presupuestado">
            <input disabled type="text" value={selectedCandidate ? formatMoney(selectedCandidate.importe_presupuestado ?? 0) : "—"} />
          </Field>

          <Field label="Avance anterior %">
            <input disabled type="text" value={formatPercent(detailForm.avance_anterior_pct ?? 0)} />
          </Field>

          <Field label="Avance actual %" span={1}>
            <input
              max="100"
              min="0"
              onChange={(event) => setDetailForm((current) => ({ ...current, avance_actual_pct: event.target.value }))}
              step="0.01"
              type="number"
              value={detailForm.avance_actual_pct}
            />
          </Field>

          {Number(detailForm.avance_actual_pct || 0) === 0 ? (
            <Field label="Ayuda" span={2}>
              <div className="inventory-form-note inventory-form-note-warning">
                <strong>Sin monto estimado</strong>
                <p className="table-note">Con 0% no se generará importe para esta partida.</p>
              </div>
            </Field>
          ) : null}

          <Field label="Notas" span={2}>
            <textarea
              onChange={(event) => setDetailForm((current) => ({ ...current, notas: event.target.value }))}
              rows={3}
              value={detailForm.notas}
            />
          </Field>
        </FormGrid>

        <div className="pm-estimation-preview-grid">
          <MetricCard label="Avance periodo" meta="Actual menos anterior" tone="info" value={formatPercent(detailPreview.periodProgress)} />
          <MetricCard label="Importe del periodo" meta="Cobro estimado" tone="success" value={formatMoney(detailPreview.periodAmount)} />
          <MetricCard label="Importe acumulado" meta="Avance total estimado" tone="neutral" value={formatMoney(detailPreview.accumulatedAmount)} />
          <MetricCard label="Saldo restante" meta="Por estimar" tone="warning" value={formatMoney(detailPreview.remainingAmount)} />
        </div>
      </ModalShell>
    </div>
  );
}
