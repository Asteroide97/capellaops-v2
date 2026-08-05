import { Fragment, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, RefreshCw, TriangleAlert } from "lucide-react";

import { previewPmBudgetPlan } from "../../api/client";
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
  precio_unitario: "Precio unitario",
  precio_unitario_manual: "Precio unitario",
  subtotal_costo: "Subtotal de costo",
  subtotal_venta: "Subtotal de venta",
  task_title: "Nombre de la tarea",
  unidad: "Unidad",
};

const moneyFields = new Set([
  "costo_unitario",
  "precio_unitario",
  "precio_unitario_manual",
  "subtotal_costo",
  "subtotal_venta",
]);

const percentFields = new Set(["margen_pct"]);
const numericFields = new Set(["cantidad"]);

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
  if (numericFields.has(field)) {
    return formatNumber(value);
  }
  return safeDisplayText(value, "Sin dato");
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

function PreviewItemDetail({ item }) {
  const hasProposedChanges = (item?.proposed_changes?.length ?? 0) > 0;
  const hasEconomicChanges = (item?.economic_changes?.length ?? 0) > 0;
  const hasBlocking = (item?.blocking?.length ?? 0) > 0;

  if (!hasProposedChanges && !hasEconomicChanges && !hasBlocking) {
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
          const hasExtra = (item?.proposed_changes?.length ?? 0) > 0 || (item?.economic_changes?.length ?? 0) > 0 || (item?.blocking?.length ?? 0) > 0;
          return (
            <Fragment key={item.lineage_id}>
              <tr>
                <td className="pm-budget-preview-cell-code">{safeDisplayText(item?.code, "-")}</td>
                <td>
                  <div className="pm-budget-preview-cell-stack">
                    <strong title={getItemDisplayName(item)}>{getItemDisplayName(item)}</strong>
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
  onClose,
  open,
  token,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [expandedChapters, setExpandedChapters] = useState([]);

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

  function toggleChapter(chapterId) {
    setExpandedChapters((current) => (
      current.includes(chapterId)
        ? current.filter((value) => value !== chapterId)
        : [...current, chapterId]
    ));
  }

  function handleReload() {
    setReloadKey((current) => current + 1);
  }

  const hasStructuredItems = (preview?.chapters ?? []).some((group) => (group.items?.length ?? 0) > 0);
  const hasAnyItems = hasStructuredItems
    || (preview?.conflicts?.length ?? 0) > 0
    || (preview?.orphans?.length ?? 0) > 0
    || (preview?.unassigned_items?.length ?? 0) > 0;

  return (
    <ModalShell
      footer={(
        <div className="inventory-actions inventory-actions-wrap">
          <ActionButton disabled={loading} onClick={onClose} type="button">
            Cerrar
          </ActionButton>
          <ActionButton disabled={loading || !budgetId} icon={<RefreshCw size={16} strokeWidth={1.9} />} onClick={handleReload} tone="primary" type="button">
            {loading ? "Actualizando..." : "Actualizar analisis"}
          </ActionButton>
        </div>
      )}
      onClose={onClose}
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
                Esta vista muestra como los capitulos y partidas del presupuesto se convertirian en la estructura operativa
                del proyecto. Todavia no se aplicara ningun cambio.
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
              <ActionButton icon={<RefreshCw size={16} strokeWidth={1.9} />} onClick={handleReload} tone="primary" type="button">
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
          <section className="pm-budget-preview-section">
            <div className="pm-budget-preview-section-head">
              <div>
                <h4>Elementos que requieren revision</h4>
                <p className="table-note">
                  Estos vinculos o tareas necesitan revision manual antes de una fase futura de generacion.
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
                <p className="table-note">Revisa la estructura agrupada por capitulo antes de una generacion futura del plan.</p>
              </div>
              <StatusBadge tone="info">{formatNumber(preview.chapters.length)} capitulos</StatusBadge>
            </div>

            <div className="pm-budget-preview-chapter-list">
              {preview.chapters.map((group) => {
                const chapterId = group.chapter.lineage_id || group.chapter.id;
                const isExpanded = expandedChapters.includes(chapterId);
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

        <section className="pm-budget-preview-footer-note">
          <strong>Siguiente paso</strong>
          <p>
            Despues de revisar la estructura, podras generar el plan de trabajo. Esta accion se habilitara en una fase
            posterior.
          </p>
        </section>
      </div>
    </ModalShell>
  );
}
