import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, RefreshCw, TriangleAlert } from "lucide-react";

import { applyPmBudgetPlan, previewPmBudgetPlan } from "../../api/client";
import {
  ActionButton,
  DataTable,
  EmptyState,
  ModalShell,
  StatusBadge,
  formatDateTime,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";

const budgetStatusLabels = {
  borrador: "Borrador",
  aprobado: "Aprobado",
  sustituido: "Sustituido",
  cancelado: "Cancelado",
};

const actionLabels = {
  create: "Por crear",
  update: "Por actualizar",
  no_change: "Sin cambios",
  orphan: "Huerfana",
  conflict: "Requiere revision",
  skip: "Omitida",
};

const actionTones = {
  create: "success",
  update: "warning",
  no_change: "neutral",
  orphan: "warning",
  conflict: "danger",
  skip: "info",
};

const syncStatusLabels = {
  linked: "Vinculo activo",
  detached: "Vinculo separado",
  orphaned: "Vinculo huerfano",
  conflict: "Vinculo en revision",
};

const fieldLabels = {
  cantidad: "Cantidad",
  codigo: "Codigo",
  costo_unitario: "Costo unitario",
  descripcion: "Descripcion",
  margen_pct: "Margen",
  nombre: "Nombre",
  notas_planificacion: "Notas de planificacion",
  precio_unitario: "Precio unitario",
  precio_unitario_manual: "Precio unitario",
  responsable_sugerido_usuario_id: "Responsable sugerido",
  subtotal_costo: "Subtotal de costo",
  subtotal_venta: "Subtotal de venta",
  task_title: "Nombre de la tarea",
  unidad: "Unidad",
  fecha_inicio_sugerida: "Inicio sugerido",
  fecha_fin_sugerida: "Fin sugerido",
  duracion_dias_sugerida: "Duracion estimada",
};

const moneyFields = new Set([
  "costo_unitario",
  "precio_unitario",
  "precio_unitario_manual",
  "subtotal_costo",
  "subtotal_venta",
]);

const percentFields = new Set(["margen_pct"]);
const numericFields = new Set(["cantidad", "duracion_dias_sugerida"]);
const dateFields = new Set(["fecha_inicio_sugerida", "fecha_fin_sugerida"]);
const dateOnlyFormatter = new Intl.DateTimeFormat("es-MX", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const previewSummaryRows = [
  { key: "create", label: "Tareas por crear" },
  { key: "update", label: "Tareas por actualizar" },
  { key: "no_change", label: "Sin cambios" },
  { key: "conflict", label: "Conflictos" },
  { key: "orphan", label: "Huerfanos" },
  { key: "skip", label: "Omitidas" },
];

const applySummaryRows = [
  { key: "created_tasks", label: "Tareas creadas" },
  { key: "updated_tasks", label: "Tareas actualizadas" },
  { key: "linked", label: "Vinculos confirmados" },
  { key: "no_change", label: "Sin cambios" },
  { key: "skipped", label: "Omitidos" },
  { key: "orphans", label: "Huerfanos" },
  { key: "tasks_with_dates", label: "Tareas con fechas" },
  { key: "tasks_without_dates", label: "Tareas sin fechas" },
  { key: "tasks_with_responsible", label: "Responsables asignados" },
  { key: "tasks_without_responsible", label: "Sin responsable" },
  { key: "dependencies_created", label: "Requisitos creados" },
  { key: "dependencies_skipped", label: "Requisitos omitidos" },
];

function getBudgetStatusLabel(status) {
  return budgetStatusLabels[status] ?? safeDisplayText(status);
}

function getBudgetStatusTone(status) {
  if (status === "aprobado") {
    return "success";
  }
  if (status === "cancelado") {
    return "danger";
  }
  if (status === "borrador") {
    return "warning";
  }
  return "neutral";
}

function getActionLabel(action) {
  return actionLabels[action] ?? safeDisplayText(action);
}

function getActionTone(action) {
  return actionTones[action] ?? "neutral";
}

function buildErrorMessage(error, fallback) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}

function getItemDisplayName(item) {
  const name = safeDisplayText(item?.name, "Sin nombre");
  const code = safeDisplayText(item?.code, "");
  return code ? `${code} - ${name}` : name;
}

function humanizeFieldName(field) {
  return safeDisplayText(
    field
      ?.split("_")
      ?.filter(Boolean)
      ?.map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
      ?.join(" "),
    "Campo",
  );
}

function getChangeLabel(change) {
  return safeDisplayText(change?.label || fieldLabels[change?.field] || humanizeFieldName(change?.field), "Cambio");
}

function formatChangeValue(field, value) {
  if (value === null || value === undefined || value === "") {
    return "Sin dato";
  }
  if (moneyFields.has(field)) {
    return formatMoney(value);
  }
  if (percentFields.has(field)) {
    return `${formatNumber(value)} %`;
  }
  if (dateFields.has(field)) {
    return formatPlanningDate(value);
  }
  if (numericFields.has(field)) {
    return formatNumber(value);
  }
  return safeDisplayText(value, "Sin dato");
}

function formatPlanningDate(value) {
  if (!value) {
    return "Sin fecha";
  }
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return safeDisplayText(value, "Sin fecha");
  }
  return dateOnlyFormatter.format(parsed);
}

function buildPlanningMeta(item) {
  const parts = [];
  if (item?.suggested_start_date) {
    parts.push(`Inicio ${formatPlanningDate(item.suggested_start_date)}`);
  }
  if (item?.suggested_end_date) {
    parts.push(`Fin ${formatPlanningDate(item.suggested_end_date)}`);
  }
  if (item?.suggested_duration_days) {
    parts.push(`Duracion ${formatNumber(item.suggested_duration_days)} d`);
  }
  if (item?.suggested_responsible_name) {
    parts.push(`Responsable ${safeDisplayText(item.suggested_responsible_name)}`);
  }
  if ((item?.suggested_prerequisites?.length ?? 0) > 0) {
    parts.push(`Requisitos ${formatNumber(item.suggested_prerequisites.length)}`);
  }
  return parts;
}

function buildPrerequisiteLabel(prerequisite) {
  const itemLabel = safeDisplayText(
    prerequisite?.code ? `${prerequisite.code} - ${prerequisite.name}` : prerequisite?.name,
    "Partida",
  );
  const chapterLabel = safeDisplayText(prerequisite?.chapter_name, "");
  return chapterLabel ? `${itemLabel} · ${chapterLabel}` : itemLabel;
}

function buildSectionCounts(items) {
  return items.reduce((accumulator, item) => {
    const next = { ...accumulator };
    const key = item?.action ?? "no_change";
    next[key] = (next[key] ?? 0) + 1;
    return next;
  }, {});
}

function buildChapterSummary(items) {
  const counts = buildSectionCounts(items);
  const parts = formatNumber(items.length);
  const detail = [];
  if (counts.conflict) {
    detail.push(`${formatNumber(counts.conflict)} requieren revision`);
  }
  if (counts.create) {
    detail.push(`${formatNumber(counts.create)} por crear`);
  }
  if (counts.update) {
    detail.push(`${formatNumber(counts.update)} por actualizar`);
  }
  if (counts.no_change) {
    detail.push(`${formatNumber(counts.no_change)} sin cambios`);
  }
  if (counts.skip) {
    detail.push(`${formatNumber(counts.skip)} omitidas`);
  }
  return `${parts} partidas${detail.length ? ` | ${detail.join(" | ")}` : ""}`;
}

function getTaskRelationCopy(item) {
  if (item?.generated_from_budget === false) {
    return "Vinculo manual";
  }
  if (item?.generated_from_budget === true) {
    return "Vinculo generado desde presupuesto";
  }
  if (item?.sync_status) {
    return syncStatusLabels[item.sync_status] ?? safeDisplayText(item.sync_status);
  }
  return "";
}

function getApplyActionLabel(summary) {
  const createCount = Number(summary?.create ?? 0);
  const updateCount = Number(summary?.update ?? 0);

  if (createCount > 0) {
    return "Generar plan de trabajo";
  }
  if (createCount === 0 && updateCount > 0) {
    return "Actualizar plan de trabajo";
  }
  return "Plan actualizado";
}

function getErrorText(error) {
  return String(error?.detail?.message || error?.message || "").trim().toLowerCase();
}

function isStalePreviewError(error) {
  return error?.status === 409 && getErrorText(error).includes("estructura cambi");
}

function isBlockingConflictError(error) {
  const text = getErrorText(error);
  return error?.status === 409 && (text.includes("conflict") || text.includes("bloque"));
}

function buildApplyErrorMessage(error) {
  const status = Number(error?.status ?? 0);
  if (status === 401) {
    return "Tu sesion expiro. Vuelve a entrar para continuar.";
  }
  if (status === 403) {
    return "No tienes permiso para generar el plan de trabajo.";
  }
  if (status === 404) {
    return "Este presupuesto ya no esta disponible.";
  }
  if (status === 409) {
    if (isStalePreviewError(error)) {
      return "La estructura cambio desde la ultima revision. Actualizamos el analisis para que puedas revisarlo nuevamente.";
    }
    if (isBlockingConflictError(error)) {
      return "Hay elementos que requieren revision antes de generar el plan.";
    }
    return "La estructura necesita una nueva revision antes de continuar.";
  }
  if (status === 422) {
    return "Revisa la confirmacion y vuelve a intentarlo.";
  }
  if (status >= 500) {
    return "No se pudo generar el plan de trabajo. Intenta nuevamente.";
  }
  return buildErrorMessage(error, "No se pudo generar el plan de trabajo.");
}

function PreviewItemDetail({ item }) {
  const hasProposedChanges = (item?.proposed_changes?.length ?? 0) > 0;
  const hasEconomicChanges = (item?.economic_changes?.length ?? 0) > 0;
  const hasBlocking = (item?.blocking?.length ?? 0) > 0;
  const hasPlanningSuggestions = (item?.planning_suggestions?.length ?? 0) > 0;
  const hasPlanningWarnings = (item?.planning_warnings?.length ?? 0) > 0;
  const hasOperationalConflicts = (item?.operational_conflicts?.length ?? 0) > 0;
  const hasPrerequisites = (item?.suggested_prerequisites?.length ?? 0) > 0;

  if (!hasProposedChanges && !hasEconomicChanges && !hasBlocking && !hasPlanningSuggestions && !hasPlanningWarnings && !hasOperationalConflicts && !hasPrerequisites) {
    return null;
  }

  return (
    <div className="pm-budget-preview-item-detail">
      {hasBlocking ? (
        <div className="pm-budget-preview-change-group">
          <strong>Revision necesaria</strong>
          <div className="pm-budget-preview-notice-list">
            {item.blocking.map((notice, index) => (
              <span className="pm-budget-preview-notice" key={`${item.lineage_id}-notice-${index}`}>
                {safeDisplayText(notice?.message)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {hasPlanningWarnings ? (
        <div className="pm-budget-preview-change-group">
          <strong>Alertas de planificacion</strong>
          <div className="pm-budget-preview-notice-list">
            {item.planning_warnings.map((notice, index) => (
              <span className="pm-budget-preview-notice" key={`${item.lineage_id}-planning-warning-${index}`}>
                {safeDisplayText(notice?.message)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {hasOperationalConflicts ? (
        <div className="pm-budget-preview-change-group">
          <strong>Conflictos operativos</strong>
          <div className="pm-budget-preview-notice-list">
            {item.operational_conflicts.map((notice, index) => (
              <span className="pm-budget-preview-notice" key={`${item.lineage_id}-operational-conflict-${index}`}>
                {safeDisplayText(notice?.message)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {hasPlanningSuggestions ? (
        <div className="pm-budget-preview-change-group">
          <strong>Planificacion sugerida</strong>
          <div className="pm-budget-preview-change-list">
            {item.planning_suggestions.map((change, index) => (
              <div className="pm-budget-preview-change-item" key={`${item.lineage_id}-planning-${change?.field ?? "field"}-${index}`}>
                <span className="pm-budget-preview-change-label">{getChangeLabel(change)}</span>
                <div className="pm-budget-preview-change-values">
                  <span>Actual: {formatChangeValue(change?.field, change?.current_value)}</span>
                  <span>Propuesto: {formatChangeValue(change?.field, change?.proposed_value)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {hasProposedChanges ? (
        <div className="pm-budget-preview-change-group">
          <strong>Cambios propuestos</strong>
          <div className="pm-budget-preview-change-list">
            {item.proposed_changes.map((change, index) => (
              <div className="pm-budget-preview-change-item" key={`${item.lineage_id}-proposed-${change?.field ?? "field"}-${index}`}>
                <span className="pm-budget-preview-change-label">{getChangeLabel(change)}</span>
                <div className="pm-budget-preview-change-values">
                  <span>Actual: {formatChangeValue(change?.field, change?.current_value)}</span>
                  <span>Propuesto: {formatChangeValue(change?.field, change?.proposed_value)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {hasEconomicChanges ? (
        <div className="pm-budget-preview-change-group">
          <strong>Cambios economicos detectados</strong>
          <p className="table-note">
            Estos cambios pertenecen al presupuesto y no modificaran fechas, responsables ni avance de las tareas.
          </p>
          <div className="pm-budget-preview-change-list">
            {item.economic_changes.map((change, index) => (
              <div className="pm-budget-preview-change-item" key={`${item.lineage_id}-economic-${change?.field ?? "field"}-${index}`}>
                <span className="pm-budget-preview-change-label">{getChangeLabel(change)}</span>
                <div className="pm-budget-preview-change-values">
                  <span>Actual: {formatChangeValue(change?.field, change?.current_value)}</span>
                  <span>Propuesto: {formatChangeValue(change?.field, change?.proposed_value)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {hasPrerequisites ? (
        <div className="pm-budget-preview-change-group">
          <strong>Requisitos previos</strong>
          <div className="pm-budget-preview-notice-list">
            {item.suggested_prerequisites.map((prerequisite, index) => (
              <span className="pm-budget-preview-notice" key={`${item.lineage_id}-prerequisite-${index}`}>
                {buildPrerequisiteLabel(prerequisite)}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PreviewItemsTable({ items, emptyTitle, emptyNote }) {
  if (!items.length) {
    return <EmptyState compact note={emptyNote} title={emptyTitle} />;
  }

  return (
    <DataTable
      className="pm-budget-preview-table"
      columns={[
        { key: "code", label: "Codigo" },
        { key: "item", label: "Partida" },
        { key: "result", label: "Resultado" },
        { key: "task", label: "Tarea vinculada" },
        { key: "reason", label: "Motivo" },
      ]}
    >
      <tbody>
        {items.map((item) => {
          const relationCopy = getTaskRelationCopy(item);
          const planningMeta = buildPlanningMeta(item);
          const hasExtra = (item?.proposed_changes?.length ?? 0) > 0
            || (item?.economic_changes?.length ?? 0) > 0
            || (item?.blocking?.length ?? 0) > 0
            || (item?.planning_suggestions?.length ?? 0) > 0
            || (item?.planning_warnings?.length ?? 0) > 0
            || (item?.operational_conflicts?.length ?? 0) > 0
            || (item?.suggested_prerequisites?.length ?? 0) > 0;
          return (
            <Fragment key={item.lineage_id}>
              <tr>
                <td className="pm-budget-preview-cell-code">{safeDisplayText(item?.code, "-")}</td>
                <td>
                  <div className="pm-budget-preview-cell-stack">
                    <strong title={getItemDisplayName(item)}>{getItemDisplayName(item)}</strong>
                    {planningMeta.length ? (
                      <div className="pm-budget-preview-inline-meta">
                        {planningMeta.map((part, index) => (
                          <span key={`${item.lineage_id}-meta-${index}`}>{part}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </td>
                <td>
                  <StatusBadge tone={getActionTone(item?.action)}>{getActionLabel(item?.action)}</StatusBadge>
                </td>
                <td>
                  <div className="pm-budget-preview-cell-stack">
                    <strong title={safeDisplayText(item?.task_title, "Sin tarea vinculada")}>
                      {safeDisplayText(item?.task_title, "Sin tarea vinculada")}
                    </strong>
                    {relationCopy ? <span>{relationCopy}</span> : null}
                  </div>
                </td>
                <td>
                  <div className="pm-budget-preview-cell-stack">
                    <strong title={safeDisplayText(item?.reason, "Sin detalle")}>{safeDisplayText(item?.reason, "Sin detalle")}</strong>
                  </div>
                </td>
              </tr>
              {hasExtra ? (
                <tr className="pm-budget-preview-detail-row">
                  <td colSpan={5}>
                    <PreviewItemDetail item={item} />
                  </td>
                </tr>
              ) : null}
            </Fragment>
          );
        })}
      </tbody>
    </DataTable>
  );
}

export default function PMBudgetPlanPreviewModal({
  budgetId,
  budgetStatus = "",
  empresaId,
  onApplied,
  onClose,
  onOpenWorkPlan,
  open,
  token,
}) {
  const conflictsRef = useRef(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [expandedChapters, setExpandedChapters] = useState([]);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [draftConfirmed, setDraftConfirmed] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [applyInfo, setApplyInfo] = useState("");
  const [applyResult, setApplyResult] = useState(null);
  const [pendingConflictJump, setPendingConflictJump] = useState(false);

  useEffect(() => {
    if (open) {
      return;
    }

    setLoading(false);
    setError("");
    setPreview(null);
    setExpandedChapters([]);
    setShowConfirmation(false);
    setDraftConfirmed(false);
    setApplyLoading(false);
    setApplyError("");
    setApplyInfo("");
    setApplyResult(null);
    setPendingConflictJump(false);
    setReloadKey(0);
  }, [open]);

  useEffect(() => {
    if (!open || !budgetId || !token || !empresaId) {
      return undefined;
    }

    let cancelled = false;

    async function loadPreview() {
      setLoading(true);
      setError("");
      try {
        const response = await previewPmBudgetPlan({ budgetId, token, empresaId });
        if (!cancelled) {
          setPreview(response);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(buildErrorMessage(requestError, "No se pudo cargar la revision de estructura."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadPreview();
    return () => {
      cancelled = true;
    };
  }, [budgetId, empresaId, open, reloadKey, token]);

  useEffect(() => {
    if (!preview) {
      return;
    }
    const suggestedOpen = preview.chapters
      .filter((group) => group.items.some((item) => item.action !== "no_change"))
      .map((group) => group.chapter.lineage_id || group.chapter.id);
    if (!suggestedOpen.length && preview.chapters[0]) {
      suggestedOpen.push(preview.chapters[0].chapter.lineage_id || preview.chapters[0].chapter.id);
    }
    setExpandedChapters(suggestedOpen);
  }, [preview]);

  useEffect(() => {
    if (!pendingConflictJump || !preview) {
      return;
    }
    conflictsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setPendingConflictJump(false);
  }, [pendingConflictJump, preview]);

  const notices = useMemo(() => {
    const next = [];
    if (preview?.warning) {
      next.push({ code: "general_warning", message: preview.warning });
    }
    if ((preview?.budget_status ?? budgetStatus) === "borrador" && !(preview?.warnings ?? []).some((item) => item?.code === "budget_in_draft")) {
      next.push({
        code: "budget_in_draft",
        message: "El presupuesto esta en borrador. La estructura puede cambiar antes de aprobarlo.",
      });
    }
    (preview?.warnings ?? []).forEach((warning) => next.push(warning));
    return next;
  }, [budgetStatus, preview]);

  const summaryCards = useMemo(() => {
    const summary = preview?.summary ?? {};
    return [
      { key: "conflict", label: "Conflictos", value: summary.conflict ?? 0, tone: "danger" },
      { key: "create", label: "Por crear", value: summary.create ?? 0, tone: "success" },
      { key: "update", label: "Por actualizar", value: summary.update ?? 0, tone: "warning" },
      { key: "orphan", label: "Huerfanos", value: summary.orphan ?? 0, tone: "warning" },
      { key: "no_change", label: "Sin cambios", value: summary.no_change ?? 0, tone: "neutral" },
      { key: "skip", label: "Omitidos", value: summary.skip ?? 0, tone: "info" },
      { key: "chapters", label: "Capitulos", value: summary.chapters ?? 0, tone: "neutral" },
      { key: "parts", label: "Partidas", value: summary.parts ?? 0, tone: "neutral" },
    ];
  }, [preview]);

  const previewSummaryData = useMemo(
    () => previewSummaryRows.map((row) => ({ ...row, value: Number(preview?.summary?.[row.key] ?? 0) })),
    [preview],
  );

  const applySummaryData = useMemo(
    () => applySummaryRows.map((row) => ({ ...row, value: Number(applyResult?.summary?.[row.key] ?? 0) })),
    [applyResult],
  );

  const normalizedBudgetStatus = String(preview?.budget_status ?? budgetStatus ?? "").toLowerCase();
  const hasBlockingConflicts = (preview?.conflicts?.length ?? 0) > 0;
  const hasStructuredItems = (preview?.chapters ?? []).some((group) => (group.items?.length ?? 0) > 0);
  const hasAnyItems = hasStructuredItems
    || (preview?.conflicts?.length ?? 0) > 0
    || (preview?.orphans?.length ?? 0) > 0
    || (preview?.unassigned_items?.length ?? 0) > 0;
  const previewToken = preview?.preview_token ?? "";
  const createCount = Number(preview?.summary?.create ?? 0);
  const updateCount = Number(preview?.summary?.update ?? 0);
  const noChangeCount = Number(preview?.summary?.no_change ?? 0);
  const hasActionableChanges = createCount > 0 || updateCount > 0;
  const hasPreviewCandidates = createCount > 0 || updateCount > 0 || noChangeCount > 0;
  const isDraftBudget = normalizedBudgetStatus === "borrador";
  const isCancelledBudget = normalizedBudgetStatus === "cancelado";
  const primaryActionLabel = getApplyActionLabel(preview?.summary);

  function toggleChapter(chapterId) {
    setExpandedChapters((current) => (
      current.includes(chapterId)
        ? current.filter((value) => value !== chapterId)
        : [...current, chapterId]
    ));
  }

  function handleDismiss() {
    if (applyLoading) {
      return;
    }
    onClose?.();
  }

  function handleReload(nextInfo = "", { force = false } = {}) {
    if (applyLoading && !force) {
      return;
    }
    setShowConfirmation(false);
    setDraftConfirmed(false);
    setApplyError("");
    setApplyResult(null);
    setApplyInfo(nextInfo);
    setReloadKey((current) => current + 1);
  }

  function handleOpenConfirmation() {
    if (!previewToken || !hasActionableChanges || hasBlockingConflicts || isCancelledBudget) {
      return;
    }
    setApplyError("");
    setShowConfirmation(true);
  }

  function handleCloseConfirmation() {
    if (applyLoading) {
      return;
    }
    setShowConfirmation(false);
  }

  async function handleConfirmApply() {
    if (applyLoading || !previewToken || !hasActionableChanges || hasBlockingConflicts || isCancelledBudget) {
      return;
    }
    if (isDraftBudget && !draftConfirmed) {
      return;
    }

    setApplyLoading(true);
    setApplyError("");

    try {
      const response = await applyPmBudgetPlan({
        budgetId,
        expectedPreviewToken: previewToken,
        confirm: true,
        allowDraft: isDraftBudget,
        token,
        empresaId,
      });

      setApplyResult(response);
      setApplyInfo("");
      setShowConfirmation(false);
      setDraftConfirmed(false);
      try {
        await onApplied?.(response);
      } catch {
        setApplyInfo("El plan ya fue generado. Si no ves los cambios todavia, actualiza la vista del proyecto.");
      }
    } catch (requestError) {
      const message = buildApplyErrorMessage(requestError);

      if (isStalePreviewError(requestError)) {
        setShowConfirmation(false);
        setDraftConfirmed(false);
        handleReload(
          "La estructura cambio desde la ultima revision. Actualizamos el analisis para que puedas revisarlo nuevamente.",
          { force: true },
        );
      } else if (isBlockingConflictError(requestError)) {
        setShowConfirmation(false);
        setApplyError(message);
        setApplyInfo("Hay elementos que requieren revision antes de generar el plan. Actualizamos el analisis para que puedas revisarlo de nuevo.");
        setPendingConflictJump(true);
        setReloadKey((current) => current + 1);
      } else {
        setApplyError(message);
      }
    } finally {
      setApplyLoading(false);
    }
  }

  async function handleGoToWorkPlan() {
    if (applyLoading) {
      return;
    }
    try {
      await onOpenWorkPlan?.(applyResult);
    } finally {
      handleDismiss();
    }
  }

  const footer = applyResult ? (
    <div className="inventory-actions inventory-actions-wrap">
      <ActionButton disabled={applyLoading} onClick={handleDismiss} type="button">
        Cerrar
      </ActionButton>
      <ActionButton disabled={applyLoading} icon={<CheckCircle2 size={16} strokeWidth={1.9} />} onClick={handleGoToWorkPlan} tone="primary" type="button">
        Ir a Plan de trabajo
      </ActionButton>
    </div>
  ) : (
    <div className="inventory-actions inventory-actions-wrap">
      <ActionButton disabled={loading || applyLoading} onClick={handleDismiss} type="button">
        Cerrar
      </ActionButton>
      <ActionButton
        disabled={loading || applyLoading || !budgetId}
        icon={<RefreshCw size={16} strokeWidth={1.9} />}
        onClick={() => handleReload("")}
        tone="primary"
        type="button"
      >
        {loading ? "Actualizando..." : "Actualizar analisis"}
      </ActionButton>
    </div>
  );

  return (
    <>
      <ModalShell
        footer={footer}
        onClose={handleDismiss}
        open={open}
        size="xl"
        subtitle="Vista previa del plan operativo generado desde presupuesto."
        title="Revision de estructura del proyecto"
      >
        <div className="pm-budget-preview-stack">
          <section className="pm-budget-preview-section pm-budget-preview-hero">
            <div className="pm-budget-preview-hero-head">
              <div className="pm-budget-preview-hero-copy">
                <div className="pm-budget-preview-badges">
                  <StatusBadge tone={getBudgetStatusTone(preview?.budget_status ?? budgetStatus)}>
                    {getBudgetStatusLabel(preview?.budget_status ?? budgetStatus)}
                  </StatusBadge>
                  <StatusBadge tone="info">Version {formatNumber(preview?.budget_version ?? 0)}</StatusBadge>
                  <StatusBadge tone={preview?.is_approved ? "success" : "neutral"}>
                    {preview?.is_approved ? "Presupuesto aprobado" : "Presupuesto en revision"}
                  </StatusBadge>
                </div>
                <p className="table-note">
                  {applyResult
                    ? "El plan de trabajo ya fue generado. Puedes revisar el resultado y pasar al siguiente paso operativo."
                    : "Esta vista muestra como los capitulos y partidas del presupuesto se convertirian en la estructura operativa del proyecto. Todavia no se aplicara ningun cambio."}
                </p>
              </div>
              <div className="pm-budget-preview-meta">
                <span>Fecha de analisis</span>
                <strong>{formatDateTime(preview?.generated_at)}</strong>
              </div>
            </div>

            {loading && preview ? (
              <div className="pm-budget-preview-inline-status">
                <span>Actualizando el analisis sin cerrar esta vista.</span>
              </div>
            ) : null}

            {applyLoading ? (
              <div className="pm-budget-preview-inline-status">
                <span>Generando plan de trabajo...</span>
              </div>
            ) : null}

            {notices.length ? (
              <div className="pm-budget-preview-warning-list">
                {notices.map((notice, index) => (
                  <div className="pm-budget-preview-warning-item" key={`${notice?.code ?? "warning"}-${index}`}>
                    <TriangleAlert size={16} strokeWidth={1.9} />
                    <span>{safeDisplayText(notice?.message)}</span>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="pm-budget-preview-summary-strip">
              {summaryCards.map((card) => (
                <article className={`pm-budget-preview-summary-chip is-${card.tone}`} key={card.key}>
                  <span>{card.label}</span>
                  <strong>{formatNumber(card.value)}</strong>
                </article>
              ))}
            </div>
          </section>

          {loading && !preview ? (
            <section className="pm-budget-preview-section pm-budget-preview-empty">
              <strong>Analizando estructura...</strong>
              <p className="table-note">Estamos revisando como el presupuesto construiria el plan operativo del proyecto.</p>
            </section>
          ) : null}

          {!loading && error && !preview ? (
            <section className="pm-budget-preview-section pm-budget-preview-empty">
              <strong>No se pudo cargar la revision</strong>
              <p className="table-note">{error}</p>
              <div className="inventory-actions">
                <ActionButton icon={<RefreshCw size={16} strokeWidth={1.9} />} onClick={() => handleReload("")} tone="primary" type="button">
                  Reintentar
                </ActionButton>
              </div>
            </section>
          ) : null}

          {!loading && !error && preview && !hasAnyItems ? (
            <section className="pm-budget-preview-section">
              <EmptyState
                compact
                note="Todavia no hay partidas suficientes para construir una estructura operativa."
                title="El presupuesto no tiene elementos para analizar"
              />
            </section>
          ) : null}

          {preview?.conflicts?.length ? (
            <section className="pm-budget-preview-section" ref={conflictsRef}>
              <div className="pm-budget-preview-section-head">
                <div>
                  <h4>Elementos que requieren revision</h4>
                  <p className="table-note">
                    Estos vinculos o tareas necesitan revision manual antes de generar el plan.
                  </p>
                </div>
                <StatusBadge tone="danger">{formatNumber(preview.conflicts.length)} conflictos</StatusBadge>
              </div>
              <PreviewItemsTable
                emptyNote="No hay conflictos detectados."
                emptyTitle="Sin conflictos"
                items={preview.conflicts}
              />
            </section>
          ) : null}

          {preview?.orphans?.length ? (
            <section className="pm-budget-preview-section">
              <div className="pm-budget-preview-section-head">
                <div>
                  <h4>Elementos fuera del presupuesto actual</h4>
                  <p className="table-note">
                    Estas tareas o vinculos existian previamente, pero ya no aparecen en la version seleccionada del presupuesto.
                  </p>
                </div>
                <StatusBadge tone="warning">{formatNumber(preview.orphans.length)} huerfanos</StatusBadge>
              </div>
              <PreviewItemsTable
                emptyNote="No hay elementos fuera del presupuesto actual."
                emptyTitle="Sin huerfanos"
                items={preview.orphans}
              />
            </section>
          ) : null}

          {preview?.chapters?.length ? (
            <section className="pm-budget-preview-section">
              <div className="pm-budget-preview-section-head">
                <div>
                  <h4>Capitulos y partidas</h4>
                  <p className="table-note">Revisa la estructura agrupada por capitulo antes de generar el plan.</p>
                </div>
                <StatusBadge tone="info">{formatNumber(preview.chapters.length)} capitulos</StatusBadge>
              </div>

              <div className="pm-budget-preview-chapter-list">
                {preview.chapters.map((group) => {
                  const chapterId = group.chapter.lineage_id || group.chapter.id;
                  const isExpanded = expandedChapters.includes(chapterId);
                  const chapterPlanningSummary = [
                    group.chapter.target_start_date ? `Inicio ${formatPlanningDate(group.chapter.target_start_date)}` : "",
                    group.chapter.target_end_date ? `Fin ${formatPlanningDate(group.chapter.target_end_date)}` : "",
                  ].filter(Boolean);
                  return (
                    <article className="pm-budget-preview-chapter" key={chapterId}>
                      <button
                        className="pm-budget-preview-chapter-toggle"
                        onClick={() => toggleChapter(chapterId)}
                        type="button"
                      >
                        <div className="pm-budget-preview-chapter-copy">
                          <strong title={safeDisplayText(group.chapter.code ? `${group.chapter.code} - ${group.chapter.name}` : group.chapter.name)}>
                            {safeDisplayText(group.chapter.code ? `${group.chapter.code} - ${group.chapter.name}` : group.chapter.name)}
                          </strong>
                          <span>{buildChapterSummary(group.items)}</span>
                          {chapterPlanningSummary.length ? (
                            <div className="pm-budget-preview-inline-meta">
                              {chapterPlanningSummary.map((entry, index) => (
                                <span key={`${chapterId}-planning-${index}`}>{entry}</span>
                              ))}
                            </div>
                          ) : null}
                          {group.chapter.planning_warnings?.length ? (
                            <div className="pm-budget-preview-notice-list">
                              {group.chapter.planning_warnings.map((notice, index) => (
                                <span className="pm-budget-preview-notice" key={`${chapterId}-warning-${index}`}>
                                  {safeDisplayText(notice?.message)}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </div>
                        <span className="pm-budget-preview-chapter-icon">
                          {isExpanded ? <ChevronDown size={16} strokeWidth={1.9} /> : <ChevronRight size={16} strokeWidth={1.9} />}
                        </span>
                      </button>

                      {isExpanded ? (
                        <PreviewItemsTable
                          emptyNote="Este capitulo todavia no tiene partidas."
                          emptyTitle="Sin partidas"
                          items={group.items}
                        />
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </section>
          ) : null}

          {preview?.unassigned_items?.length ? (
            <section className="pm-budget-preview-section">
              <div className="pm-budget-preview-section-head">
                <div>
                  <h4>Partidas sin capitulo</h4>
                  <p className="table-note">
                    Estas partidas quedaron fuera de un capitulo valido y se muestran aparte para su revision.
                  </p>
                </div>
                <StatusBadge tone="neutral">{formatNumber(preview.unassigned_items.length)} partidas</StatusBadge>
              </div>
              <PreviewItemsTable
                emptyNote="No hay partidas sin capitulo."
                emptyTitle="Sin partidas sueltas"
                items={preview.unassigned_items}
              />
            </section>
          ) : null}

          {error && preview ? (
            <section className="pm-budget-preview-section pm-budget-preview-inline-error">
              <strong>No se pudo refrescar el analisis.</strong>
              <p className="table-note">{error}</p>
            </section>
          ) : null}

          {applyInfo ? (
            <section className="pm-budget-preview-section pm-budget-preview-inline-info">
              <strong>Revision actualizada</strong>
              <p className="table-note">{applyInfo}</p>
            </section>
          ) : null}

          {applyError ? (
            <section className="pm-budget-preview-section pm-budget-preview-inline-error">
              <strong>No se pudo generar el plan</strong>
              <p className="table-note">{applyError}</p>
            </section>
          ) : null}

          {preview ? (
            <section className="pm-budget-preview-section pm-budget-preview-confirmation">
              {applyResult ? (
                <>
                  <div className="pm-budget-preview-section-head">
                    <div>
                      <h4>Plan de trabajo generado</h4>
                      <p className="table-note">
                        Las tareas nuevas ya estan disponibles en Plan de trabajo, Kanban y Gantt. Revisa las tareas sin fechas, confirma responsables y valida dependencias antes de crear una linea base.
                      </p>
                    </div>
                    <StatusBadge tone="success">Listo</StatusBadge>
                  </div>
                  <div className="pm-budget-preview-result-grid">
                    {applySummaryData.map((item) => (
                      <div className="pm-budget-preview-result-item" key={item.key}>
                        <span>{item.label}</span>
                        <strong>{formatNumber(item.value)}</strong>
                      </div>
                    ))}
                  </div>
                </>
              ) : isCancelledBudget ? (
                <>
                  <div className="pm-budget-preview-section-head">
                    <div>
                      <h4>Generacion bloqueada</h4>
                      <p className="table-note">No puedes generar un plan desde un presupuesto cancelado.</p>
                    </div>
                    <StatusBadge tone="danger">Cancelado</StatusBadge>
                  </div>
                </>
              ) : hasBlockingConflicts ? (
                <>
                  <div className="pm-budget-preview-section-head">
                    <div>
                      <h4>Hay elementos que requieren revision antes de generar el plan</h4>
                      <p className="table-note">
                        Revisa los conflictos bloqueantes y vuelve a actualizar el analisis cuando queden resueltos.
                      </p>
                    </div>
                    <StatusBadge tone="danger">Bloqueado</StatusBadge>
                  </div>
                  <div className="inventory-actions inventory-actions-wrap">
                    <ActionButton onClick={() => conflictsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })} tone="primary" type="button">
                      Ver conflictos
                    </ActionButton>
                  </div>
                </>
              ) : hasPreviewCandidates ? (
                <>
                  <div className="pm-budget-preview-section-head">
                    <div>
                      <h4>{hasActionableChanges ? primaryActionLabel : "Plan actualizado"}</h4>
                      <p className="table-note">
                        {hasActionableChanges
                          ? "Capella Ops creara tareas a partir de las partidas del presupuesto. Las tareas nuevas se crearan con esta planificacion y las tareas existentes no seran sobrescritas."
                          : "El analisis no detecta cambios pendientes para generar o actualizar el plan de trabajo."}
                      </p>
                    </div>
                    <StatusBadge tone={hasActionableChanges ? "info" : "success"}>
                      {hasActionableChanges ? "Listo para confirmar" : "Sin cambios pendientes"}
                    </StatusBadge>
                  </div>

                  <div className="pm-budget-preview-result-grid">
                    {previewSummaryData.map((item) => (
                      <div className="pm-budget-preview-result-item" key={item.key}>
                        <span>{item.label}</span>
                        <strong>{formatNumber(item.value)}</strong>
                      </div>
                    ))}
                  </div>

                  {isDraftBudget ? (
                    <div className="pm-budget-preview-draft-note">
                      <TriangleAlert size={16} strokeWidth={1.9} />
                      <span>El presupuesto todavia esta en borrador. Si continuas, el plan podra necesitar una nueva revision cuando cambien las partidas.</span>
                    </div>
                  ) : null}

                  {hasActionableChanges ? (
                    <div className="inventory-actions inventory-actions-wrap">
                      <ActionButton disabled={applyLoading} onClick={handleOpenConfirmation} tone="primary" type="button">
                        {primaryActionLabel}
                      </ActionButton>
                    </div>
                  ) : null}
                </>
              ) : null}
            </section>
          ) : null}
        </div>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={applyLoading} onClick={handleCloseConfirmation} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              autoFocus
              disabled={applyLoading || (isDraftBudget && !draftConfirmed)}
              onClick={handleConfirmApply}
              tone="primary"
              type="button"
            >
              {applyLoading ? "Generando..." : "Confirmar y generar"}
            </ActionButton>
          </div>
        )}
        onClose={handleCloseConfirmation}
        open={showConfirmation}
        size="md"
        subtitle="Confirma la generacion del plan de trabajo desde presupuesto."
        title={primaryActionLabel}
      >
        <div className="pm-budget-preview-stack">
          <section className="pm-budget-preview-section pm-budget-preview-confirm-dialog">
            <p className="table-note">
              Capella Ops creara tareas a partir de las partidas del presupuesto. Los capitulos se usaran como agrupadores. Las tareas nuevas se crearan con la planificacion sugerida y no se modificaran fechas, responsables, avance ni dependencias existentes.
            </p>

            <div className="pm-budget-preview-confirm-grid">
              {previewSummaryData.map((item) => (
                <div className="pm-budget-preview-confirm-item" key={item.key}>
                  <span>{item.label}</span>
                  <strong>{formatNumber(item.value)}</strong>
                </div>
              ))}
            </div>

            {isDraftBudget ? (
              <div className="pm-budget-preview-draft-box">
                <strong>Presupuesto en borrador</strong>
                <p className="table-note">
                  El presupuesto todavia esta en borrador. Si continuas, el plan podra necesitar una nueva revision cuando cambien
                  las partidas.
                </p>
                <label className="pm-inline-checkbox">
                  <input checked={draftConfirmed} onChange={(event) => setDraftConfirmed(event.target.checked)} type="checkbox" />
                  <span>Entiendo que el presupuesto esta en borrador.</span>
                </label>
              </div>
            ) : null}

            {applyError ? (
              <div className="pm-budget-preview-inline-error">
                <strong>No se pudo generar el plan</strong>
                <p className="table-note">{applyError}</p>
              </div>
            ) : null}
          </section>
        </div>
      </ModalShell>
    </>
  );
}
