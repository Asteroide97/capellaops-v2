import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  Clock3,
  History,
  LoaderCircle,
  Search,
  TrendingUp,
  Truck,
  Wallet,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  downloadPmSimpleProgressReportPdf,
  getPmSimpleSummary,
  listPmSimpleProjectProgress,
  listPmSimpleWorkProgress,
  updatePmSimpleProjectProgress,
} from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  MetricCard,
  ModalShell,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  StatusBadge,
  formatDate,
  formatDateTime,
  formatMoney,
  safeDisplayText,
  DEFAULT_PAGE_SIZE,
} from "../inventory/shared";
import { canEditPmProjectRole } from "./shared";


const operationalStatusOptions = [
  { value: "nuevo", label: "Nuevo" },
  { value: "cotizado", label: "Cotizado" },
  { value: "autorizado", label: "Autorizado" },
  { value: "en_proceso", label: "En proceso" },
  { value: "pausado", label: "Pausado" },
  { value: "pendiente_cliente", label: "Pendiente de cliente" },
  { value: "listo_entrega", label: "Listo para entrega" },
  { value: "entregado", label: "Entregado" },
  { value: "cobrado", label: "Cobrado" },
  { value: "cancelado", label: "Cancelado" },
];

const trafficLightOptions = {
  a_tiempo: { label: "A tiempo", tone: "success" },
  en_riesgo: { label: "En riesgo", tone: "warning" },
  atrasado: { label: "Atrasado", tone: "danger" },
  sin_fecha: { label: "Sin fecha", tone: "neutral" },
};

const defaultFilters = {
  search: "",
  estado_operativo: "",
  responsable_id: "",
  cliente: "",
  atrasados: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const emptySummary = {
  trabajos_totales: 0,
  en_proceso: 0,
  atrasados: 0,
  pendientes_cliente: 0,
  listos_entrega: 0,
  entregados: 0,
  cobrados: 0,
  avance_promedio: 0,
  monto_total_trabajos: 0,
  monto_pendiente_cobro: 0,
};

const defaultProgressForm = {
  comentario: "",
  avance_porcentaje: "0",
  estado_operativo: "en_proceso",
  proximo_paso: "",
  bloqueo_actual: "",
  fecha_compromiso: "",
  evidencia_url: "",
};

function getOperationalStatusLabel(value) {
  return operationalStatusOptions.find((option) => option.value === value)?.label ?? safeDisplayText(value, "Nuevo");
}

function getOperationalStatusTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (["cobrado", "entregado"].includes(normalized)) {
    return "success";
  }
  if (["en_proceso", "listo_entrega"].includes(normalized)) {
    return "info";
  }
  if (["pendiente_cliente", "pausado", "cotizado", "autorizado"].includes(normalized)) {
    return "warning";
  }
  if (normalized === "cancelado") {
    return "danger";
  }
  return "neutral";
}

function getTrafficLightMeta(value) {
  return trafficLightOptions[value] ?? { label: safeDisplayText(value, "Sin fecha"), tone: "neutral" };
}

function formatPercentValue(value) {
  const numericValue = Number(value ?? 0);
  if (Number.isNaN(numericValue)) {
    return "0%";
  }
  return `${numericValue.toFixed(Number.isInteger(numericValue) ? 0 : 1)}%`;
}

function toDateInputValue(value) {
  if (!value) {
    return "";
  }
  return String(value).slice(0, 10);
}

function createProgressFormFromRow(row) {
  return {
    comentario: "",
    avance_porcentaje: String(row?.avance_porcentaje ?? 0),
    estado_operativo: row?.estado_operativo ?? "en_proceso",
    proximo_paso: row?.proximo_paso ?? "",
    bloqueo_actual: row?.bloqueo_actual ?? "",
    fecha_compromiso: toDateInputValue(row?.fecha_compromiso),
    evidencia_url: "",
  };
}

function hasValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function formatOptionalMoney(value) {
  return hasValue(value) ? formatMoney(value) : "—";
}

function buildProgressPayload(form) {
  return {
    comentario: form.comentario.trim(),
    avance_porcentaje: Number(form.avance_porcentaje || 0),
    estado_operativo: form.estado_operativo || null,
    proximo_paso: form.proximo_paso.trim() || null,
    bloqueo_actual: form.bloqueo_actual.trim() || null,
    fecha_compromiso: form.fecha_compromiso || null,
    evidencia_url: form.evidencia_url.trim() || null,
  };
}

export default function PMSimpleWorkProgressPage() {
  const navigate = useNavigate();
  const { empresaId, token, membership, user } = useAuth();
  const canEditProgress = canEditPmProjectRole(membership?.role, Boolean(user?.is_superadmin));

  const [filters, setFilters] = useState(defaultFilters);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(emptySummary);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [progressModalOpen, setProgressModalOpen] = useState(false);
  const [progressProject, setProgressProject] = useState(null);
  const [progressForm, setProgressForm] = useState(defaultProgressForm);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyProject, setHistoryProject] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const responsibleOptions = useMemo(() => {
    const optionMap = new Map();
    rows.forEach((item) => {
      if (item?.responsable_id && item?.responsable_nombre) {
        optionMap.set(item.responsable_id, item.responsable_nombre);
      }
    });
    return Array.from(optionMap.entries()).map(([value, label]) => ({ value, label }));
  }, [rows]);

  async function loadDashboard(nextFilters = filters) {
    setLoading(true);
    setError("");
    try {
      const [summaryResponse, listResponse] = await Promise.all([
        getPmSimpleSummary({ token, empresaId }),
        listPmSimpleWorkProgress({ token, empresaId, filters: nextFilters }),
      ]);

      setSummary({ ...emptySummary, ...(summaryResponse ?? {}) });
      setRows(listResponse?.items ?? []);
      setMeta({
        total: listResponse?.total ?? 0,
        limit: listResponse?.limit ?? nextFilters.limit,
        offset: listResponse?.offset ?? nextFilters.offset,
      });
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el avance de trabajos.");
    } finally {
      setLoading(false);
    }
  }

  async function loadHistory(projectId) {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const response = await listPmSimpleProjectProgress({ projectId, token, empresaId });
      setHistoryItems(response?.items ?? []);
    } catch (requestError) {
      setHistoryError(requestError.message || "No se pudo cargar el historial de avances.");
      setHistoryItems([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    if (!token || !empresaId) {
      return;
    }
    loadDashboard(filters);
  }, [token, empresaId]);

  function resetFeedback() {
    setError("");
    setSuccess("");
  }

  function openProgressModal(row) {
    resetFeedback();
    setProgressProject(row);
    setProgressForm(createProgressFormFromRow(row));
    setProgressModalOpen(true);
  }

  function closeProgressModal(force = false) {
    if (saving && !force) {
      return;
    }
    setProgressModalOpen(false);
    setProgressProject(null);
    setProgressForm(defaultProgressForm);
  }

  async function openHistoryModal(row) {
    resetFeedback();
    setHistoryProject(row);
    setHistoryModalOpen(true);
    await loadHistory(row.proyecto_id);
  }

  function closeHistoryModal() {
    setHistoryModalOpen(false);
    setHistoryProject(null);
    setHistoryItems([]);
    setHistoryError("");
  }

  async function handleFilterSubmit(event) {
    event.preventDefault();
    const nextFilters = { ...filters, offset: 0 };
    setFilters(nextFilters);
    await loadDashboard(nextFilters);
  }

  async function handleResetFilters() {
    setFilters(defaultFilters);
    await loadDashboard(defaultFilters);
  }

  async function handlePaginate(direction) {
    const nextOffset =
      direction === "next"
        ? filters.offset + filters.limit
        : Math.max(0, filters.offset - filters.limit);
    const nextFilters = { ...filters, offset: nextOffset };
    setFilters(nextFilters);
    await loadDashboard(nextFilters);
  }

  async function handleSaveProgress(event) {
    event.preventDefault();
    if (!progressProject?.proyecto_id) {
      return;
    }

    const trimmedComment = progressForm.comentario.trim();
    const numericProgress = Number(progressForm.avance_porcentaje);

    if (!trimmedComment) {
      setError("Captura un comentario para guardar el avance.");
      return;
    }

    if (!Number.isFinite(numericProgress) || numericProgress < 0 || numericProgress > 100) {
      setError("El avance debe estar entre 0 y 100.");
      return;
    }

    setSaving(true);
    resetFeedback();
    try {
      await updatePmSimpleProjectProgress({
        projectId: progressProject.proyecto_id,
        token,
        empresaId,
        payload: buildProgressPayload(progressForm),
      });

      setSuccess("Avance actualizado.");
      await loadDashboard(filters);
      if (historyModalOpen && historyProject?.proyecto_id === progressProject.proyecto_id) {
        await loadHistory(progressProject.proyecto_id);
      }
      closeProgressModal(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el avance.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDownloadProgressReport(row) {
    if (!row?.proyecto_id) {
      return;
    }
    resetFeedback();
    try {
      await downloadPmSimpleProgressReportPdf({
        projectId: row.proyecto_id,
        token,
        empresaId,
      });
    } catch (requestError) {
      setError(requestError.message || "No se pudo generar el reporte de avance.");
    }
  }

  const needsCompletionHint =
    Number(progressForm.avance_porcentaje || 0) === 100 &&
    !["listo_entrega", "entregado", "cobrado"].includes(progressForm.estado_operativo);

  return (
    <div className="inventory-shell inventory-screen pm-screen pm-simple-page">
      <PageHeader
        eyebrow="PM Simple"
        title="Avance de trabajos"
        subtitle="Seguimiento simple de cotizaciones, trabajos y entregas."
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={() => navigate("/pm/projects")} type="button">
              Proyectos
            </ActionButton>
            <ActionButton onClick={() => navigate("/pm")} type="button">
              Dashboard PM
            </ActionButton>
          </div>
        }
      />

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-5 pm-simple-kpi-grid">
        <MetricCard icon={<ClipboardList size={18} strokeWidth={1.9} />} label="Trabajos totales" meta="Base del periodo" tone="neutral" value={summary.trabajos_totales} />
        <MetricCard icon={<TrendingUp size={18} strokeWidth={1.9} />} label="En proceso" meta="Operación activa" tone="info" value={summary.en_proceso} />
        <MetricCard icon={<AlertTriangle size={18} strokeWidth={1.9} />} label="Atrasados" meta="Requieren seguimiento" tone="warning" value={summary.atrasados} />
        <MetricCard icon={<Clock3 size={18} strokeWidth={1.9} />} label="Pendientes del cliente" meta="Esperando respuesta" tone="warning" value={summary.pendientes_cliente} />
        <MetricCard icon={<Truck size={18} strokeWidth={1.9} />} label="Listos para entrega" meta="Operación inmediata" tone="success" value={summary.listos_entrega} />
        <MetricCard icon={<CheckCircle2 size={18} strokeWidth={1.9} />} label="Entregados" meta="Trabajo completado" tone="success" value={summary.entregados} />
        <MetricCard icon={<Wallet size={18} strokeWidth={1.9} />} label="Cobrados" meta="Cierre operativo" tone="success" value={summary.cobrados} />
        <MetricCard icon={<TrendingUp size={18} strokeWidth={1.9} />} label="Avance promedio" meta="Promedio simple" tone="info" value={formatPercentValue(summary.avance_promedio)} />
        <MetricCard icon={<CircleDollarSign size={18} strokeWidth={1.9} />} label="Monto total trabajos" meta="Importe pactado" tone="neutral" value={formatMoney(summary.monto_total_trabajos)} />
        <MetricCard icon={<CircleDollarSign size={18} strokeWidth={1.9} />} label="Pendiente de cobro" meta="Seguimiento comercial" tone="warning" value={formatMoney(summary.monto_pendiente_cobro)} />
      </section>

      <FilterCard title="Filtros" subtitle="Vista operativa tipo Excel para seguimiento diario.">
        <form className="inventory-filter-toolbar" onSubmit={handleFilterSubmit}>
          <div className="inventory-toolbar-grid pm-simple-filter-grid">
            <SearchInput
              action={
                <ActionButton icon={<Search size={16} strokeWidth={1.9} />} size="sm" tone="primary" type="submit">
                  Buscar
                </ActionButton>
              }
              hint="Busca por cliente, trabajo, código o próximo paso."
              label="Búsqueda"
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Buscar trabajos..."
              value={filters.search}
            />
            <Field label="Estado">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, estado_operativo: event.target.value }))}
                value={filters.estado_operativo}
              >
                <option value="">Todos</option>
                {operationalStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Cliente">
              <input
                onChange={(event) => setFilters((current) => ({ ...current, cliente: event.target.value }))}
                placeholder="Filtrar por cliente"
                type="text"
                value={filters.cliente}
              />
            </Field>
            <Field label="Responsable">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, responsable_id: event.target.value }))}
                value={filters.responsable_id}
              >
                <option value="">Todos</option>
                {responsibleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Atrasados">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, atrasados: event.target.value }))}
                value={filters.atrasados}
              >
                <option value="">Todos</option>
                <option value="true">Solo atrasados</option>
              </select>
            </Field>
            <div className="inventory-actions inventory-actions-end">
              <ActionButton onClick={handleResetFilters} size="sm" type="button">
                Limpiar
              </ActionButton>
              <ActionButton onClick={() => loadDashboard(filters)} size="sm" type="button">
                Actualizar
              </ActionButton>
            </div>
          </div>
        </form>
      </FilterCard>

      <DataCard subtitle="Seguimiento diario con lenguaje operativo para usuarios que vienen de Excel." title="Tabla de avance">
        <ResultMeta label="trabajos" loaded={rows.length} total={meta.total} />
        {loading ? (
          <div className="table-note">Cargando avance de trabajos...</div>
        ) : rows.length === 0 ? (
          <EmptyState note="Ajusta los filtros o registra avances desde el PM operativo." title="No hay trabajos registrados." />
        ) : (
          <>
            <DataTable
              className="pm-simple-table"
              columns={[
                "Cliente",
                "Trabajo / Cotización",
                "Responsable",
                "Estado",
                "Avance %",
                "Fecha compromiso",
                "Próximo paso",
                "Bloqueo actual",
                "Última actualización",
                "Importe pactado",
                "Pendiente de cobro",
                "Semáforo",
                "Acciones",
              ]}
            >
              <tbody>
                {rows.map((row) => {
                  const trafficMeta = getTrafficLightMeta(row.semaforo);
                  return (
                    <tr key={row.proyecto_id}>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(row.cliente_nombre, "Sin cliente")}</div>
                      </td>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(row.nombre, "Trabajo sin nombre")}</div>
                        <div className="inventory-cell-sub">{safeDisplayText(row.codigo, "Sin código")}</div>
                      </td>
                      <td>{safeDisplayText(row.responsable_nombre, "Sin responsable")}</td>
                      <td>
                        <StatusBadge tone={getOperationalStatusTone(row.estado_operativo)}>
                          {getOperationalStatusLabel(row.estado_operativo)}
                        </StatusBadge>
                      </td>
                      <td>{formatPercentValue(row.avance_porcentaje)}</td>
                      <td>{formatDate(row.fecha_compromiso)}</td>
                      <td>{safeDisplayText(row.proximo_paso, "Sin siguiente paso")}</td>
                      <td>{safeDisplayText(row.bloqueo_actual, "Sin bloqueo")}</td>
                      <td>{formatDateTime(row.ultima_actualizacion_avance_at)}</td>
                      <td>{formatOptionalMoney(row.presupuesto_estimado)}</td>
                      <td>{formatOptionalMoney(row.saldo_pendiente)}</td>
                      <td>
                        <StatusBadge tone={trafficMeta.tone}>{trafficMeta.label}</StatusBadge>
                      </td>
                      <td>
                        <div className="inventory-actions pm-simple-row-actions">
                          <ActionButton
                            disabled={!canEditProgress}
                            onClick={() => openProgressModal(row)}
                            size="sm"
                            tone="primary"
                            type="button"
                          >
                            Actualizar avance
                          </ActionButton>
                          <ActionButton
                            icon={<History size={14} strokeWidth={1.9} />}
                            onClick={() => openHistoryModal(row)}
                            size="sm"
                            type="button"
                          >
                            Ver historial
                          </ActionButton>
                          <ActionButton
                            onClick={() => handleDownloadProgressReport(row)}
                            size="sm"
                            type="button"
                          >
                            Descargar reporte
                          </ActionButton>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>
            <PaginationControls meta={meta} onNext={() => handlePaginate("next")} onPrevious={() => handlePaginate("previous")} />
          </>
        )}
      </DataCard>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={() => closeProgressModal()} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-simple-progress-form" tone="primary" type="submit">
              {saving ? "Guardando..." : "Guardar avance"}
            </ActionButton>
          </div>
        }
        onClose={() => closeProgressModal()}
        open={progressModalOpen}
        size="wide"
        subtitle="Actualiza el avance operativo, el próximo paso y cualquier bloqueo actual."
        title="Actualizar avance"
      >
        {progressProject ? (
          <div className="inventory-detail-grid">
            <div>
              <p className="table-note">Trabajo</p>
              <strong>{safeDisplayText(progressProject.nombre, "Trabajo sin nombre")}</strong>
            </div>
            <div>
              <p className="table-note">Cliente</p>
              <strong>{safeDisplayText(progressProject.cliente_nombre, "Sin cliente")}</strong>
            </div>
            <div>
              <p className="table-note">Estado actual</p>
              <strong>{getOperationalStatusLabel(progressProject.estado_operativo)}</strong>
            </div>
            <div>
              <p className="table-note">Avance actual</p>
              <strong>{formatPercentValue(progressProject.avance_porcentaje)}</strong>
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo actualizar el avance</strong>
            <p className="table-note">{error}</p>
          </div>
        ) : null}

        {needsCompletionHint ? (
          <div className="inventory-form-note inventory-form-note-warning">
            <strong>Avance completo</strong>
            <p className="table-note">Si el trabajo ya terminó, conviene marcarlo como listo para entrega o entregado.</p>
          </div>
        ) : null}

        <form className="inventory-modal-form" id="pm-simple-progress-form" onSubmit={handleSaveProgress}>
          <FormGrid>
            <Field hint="Describe el avance real del trabajo." label="Comentario" span={2}>
              <textarea
                onChange={(event) => setProgressForm((current) => ({ ...current, comentario: event.target.value }))}
                required
                rows={4}
                value={progressForm.comentario}
              />
            </Field>
            <Field hint="Valor entre 0 y 100." label="Avance %">
              <input
                max="100"
                min="0"
                onChange={(event) => setProgressForm((current) => ({ ...current, avance_porcentaje: event.target.value }))}
                required
                step="1"
                type="number"
                value={progressForm.avance_porcentaje}
              />
            </Field>
            <Field label="Estado operativo">
              <select
                onChange={(event) => setProgressForm((current) => ({ ...current, estado_operativo: event.target.value }))}
                value={progressForm.estado_operativo}
              >
                {operationalStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Próximo paso">
              <input
                onChange={(event) => setProgressForm((current) => ({ ...current, proximo_paso: event.target.value }))}
                type="text"
                value={progressForm.proximo_paso}
              />
            </Field>
            <Field label="Bloqueo actual">
              <input
                onChange={(event) => setProgressForm((current) => ({ ...current, bloqueo_actual: event.target.value }))}
                type="text"
                value={progressForm.bloqueo_actual}
              />
            </Field>
            <Field label="Fecha compromiso">
              <input
                onChange={(event) => setProgressForm((current) => ({ ...current, fecha_compromiso: event.target.value }))}
                type="date"
                value={progressForm.fecha_compromiso}
              />
            </Field>
            <Field hint="Opcional. Liga a evidencia externa si ya existe." label="Evidencia URL">
              <input
                onChange={(event) => setProgressForm((current) => ({ ...current, evidencia_url: event.target.value }))}
                placeholder="https://..."
                type="url"
                value={progressForm.evidencia_url}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            {historyProject ? (
              <ActionButton onClick={() => handleDownloadProgressReport(historyProject)} type="button">
                Descargar reporte
              </ActionButton>
            ) : null}
            <ActionButton onClick={closeHistoryModal} tone="primary" type="button">
              Cerrar
            </ActionButton>
          </div>
        }
        onClose={closeHistoryModal}
        open={historyModalOpen}
        size="wide"
        subtitle="Bitácora simple de avances registrados para este trabajo."
        title="Ver historial"
      >
        {historyProject ? (
          <div className="inventory-detail-grid">
            <div>
              <p className="table-note">Trabajo</p>
              <strong>{safeDisplayText(historyProject.nombre, "Trabajo sin nombre")}</strong>
            </div>
            <div>
              <p className="table-note">Cliente</p>
              <strong>{safeDisplayText(historyProject.cliente_nombre, "Sin cliente")}</strong>
            </div>
          </div>
        ) : null}

        {historyError ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo cargar el historial</strong>
            <p className="table-note">{historyError}</p>
          </div>
        ) : null}

        {historyLoading ? (
          <div className="pm-simple-history-loading">
            <LoaderCircle className="pm-simple-history-spinner" size={18} strokeWidth={1.9} />
            <span className="table-note">Cargando avances...</span>
          </div>
        ) : historyItems.length === 0 ? (
          <EmptyState compact note="El historial aparecerá en cuanto se registre el primer avance." title="No hay avances registrados." />
        ) : (
          <div className="pm-simple-history-list">
            {historyItems.map((item) => (
              <article className="mini-card pm-simple-history-item" key={item.id}>
                <div className="pm-simple-history-head">
                  <div>
                    <strong>{formatDateTime(item.created_at)}</strong>
                    <p className="table-note">{safeDisplayText(item.usuario_nombre, "Sin usuario")}</p>
                  </div>
                  <div className="pm-simple-history-badges">
                    <StatusBadge tone={getOperationalStatusTone(item.estado_operativo)}>
                      {getOperationalStatusLabel(item.estado_operativo)}
                    </StatusBadge>
                    <StatusBadge tone="info">{formatPercentValue(item.avance_porcentaje)}</StatusBadge>
                  </div>
                </div>
                <p className="pm-simple-history-comment">{safeDisplayText(item.comentario, "Sin comentario")}</p>
                <div className="pm-simple-history-grid">
                  <div>
                    <span>Próximo paso</span>
                    <strong>{safeDisplayText(item.proximo_paso, "Sin siguiente paso")}</strong>
                  </div>
                  <div>
                    <span>Bloqueo</span>
                    <strong>{safeDisplayText(item.bloqueo_actual, "Sin bloqueo")}</strong>
                  </div>
                  <div>
                    <span>Fecha compromiso</span>
                    <strong>{formatDate(item.fecha_compromiso)}</strong>
                  </div>
                  <div>
                    <span>Evidencia</span>
                    {item.evidencia_url ? (
                      <a className="pm-simple-history-link" href={item.evidencia_url} rel="noreferrer" target="_blank">
                        Abrir evidencia
                      </a>
                    ) : (
                      <strong>Sin evidencia</strong>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </ModalShell>
    </div>
  );
}
