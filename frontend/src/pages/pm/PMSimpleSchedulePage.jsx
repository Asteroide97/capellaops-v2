import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CalendarRange,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  Clock3,
  History,
  LoaderCircle,
  Search,
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

const timelineScaleOptions = [
  { value: "week", label: "Semana" },
  { value: "month", label: "Mes" },
  { value: "quarter", label: "Trimestre" },
];

const defaultFilters = {
  search: "",
  estado_operativo: "",
  responsable_id: "",
  cliente: "",
  atrasados: "",
  scale: "month",
  limit: 50,
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

const scheduleGridTemplate =
  "2.1fr 1.35fr 1.15fr 0.95fr 0.75fr 0.9fr 1fr 1.35fr 1.1fr 0.9fr 0.95fr 1.25fr";

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

function formatOptionalMoney(value) {
  return value === null || value === undefined || value === "" ? "—" : formatMoney(value);
}

function toDateInputValue(value) {
  if (!value) {
    return "";
  }
  return String(value).slice(0, 10);
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

function parseDateValue(value) {
  if (!value) {
    return null;
  }

  const rawValue = String(value).slice(0, 10);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(rawValue);
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }

  const parsed = new Date(String(value));
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

function addDays(date, days) {
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + days);
  return nextDate;
}

function startOfWeek(date) {
  const nextDate = new Date(date);
  const day = nextDate.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return addDays(nextDate, diff);
}

function endOfWeek(date) {
  return addDays(startOfWeek(date), 6);
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

function diffDays(start, end) {
  const millisecondsPerDay = 1000 * 60 * 60 * 24;
  const startUtc = Date.UTC(start.getFullYear(), start.getMonth(), start.getDate());
  const endUtc = Date.UTC(end.getFullYear(), end.getMonth(), end.getDate());
  return Math.round((endUtc - startUtc) / millisecondsPerDay);
}

function formatMarkerLabel(date, options) {
  return new Intl.DateTimeFormat("es-MX", options).format(date);
}

function buildTimelineMarkers({ scale, rangeStart, rangeEnd, pxPerDay }) {
  const markers = [];

  if (scale === "week") {
    let cursor = new Date(rangeStart);
    while (cursor <= rangeEnd) {
      markers.push({
        key: cursor.toISOString(),
        label: formatMarkerLabel(cursor, { day: "2-digit" }),
        caption: formatMarkerLabel(cursor, { weekday: "short" }),
        width: pxPerDay,
      });
      cursor = addDays(cursor, 1);
    }
    return markers;
  }

  if (scale === "month") {
    let cursor = new Date(rangeStart);
    while (cursor <= rangeEnd) {
      const markerEnd = endOfWeek(cursor) < rangeEnd ? endOfWeek(cursor) : new Date(rangeEnd);
      const days = diffDays(cursor, markerEnd) + 1;
      markers.push({
        key: cursor.toISOString(),
        label: `${formatMarkerLabel(cursor, { day: "2-digit" })}-${formatMarkerLabel(markerEnd, { day: "2-digit" })}`,
        caption: formatMarkerLabel(cursor, { month: "short" }),
        width: days * pxPerDay,
      });
      cursor = addDays(markerEnd, 1);
    }
    return markers;
  }

  let cursor = startOfMonth(rangeStart);
  while (cursor <= rangeEnd) {
    const markerEnd = endOfMonth(cursor) < rangeEnd ? endOfMonth(cursor) : new Date(rangeEnd);
    const days = diffDays(cursor, markerEnd) + 1;
    markers.push({
      key: cursor.toISOString(),
      label: formatMarkerLabel(cursor, { month: "short" }),
      caption: formatMarkerLabel(cursor, { year: "numeric" }),
      width: days * pxPerDay,
    });
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
  }

  return markers;
}

function buildTimelineRange(rows, scale) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const dates = rows.flatMap((row) => {
    const startDate = parseDateValue(row?.fecha_inicio) ?? parseDateValue(row?.created_at);
    const endDate = parseDateValue(row?.fecha_compromiso);
    return [startDate, endDate].filter(Boolean);
  });

  const minDate = dates.length > 0 ? new Date(Math.min(...dates.map((value) => value.getTime()))) : today;
  const maxDate = dates.length > 0 ? new Date(Math.max(...dates.map((value) => value.getTime()))) : addDays(today, 21);

  let rangeStart = new Date(minDate);
  let rangeEnd = new Date(maxDate);

  if (scale === "week") {
    rangeStart = startOfWeek(rangeStart);
    rangeEnd = endOfWeek(rangeEnd);
    if (diffDays(rangeStart, rangeEnd) < 13) {
      rangeEnd = addDays(rangeStart, 13);
    }
  } else if (scale === "month") {
    rangeStart = startOfWeek(rangeStart);
    rangeEnd = endOfWeek(rangeEnd);
    if (diffDays(rangeStart, rangeEnd) < 34) {
      rangeEnd = addDays(rangeStart, 34);
    }
  } else {
    rangeStart = startOfMonth(rangeStart);
    rangeEnd = endOfMonth(rangeEnd);
    if (diffDays(rangeStart, rangeEnd) < 89) {
      rangeEnd = addDays(rangeStart, 89);
    }
  }

  const pxPerDay = scale === "week" ? 42 : scale === "month" ? 20 : 10;
  const totalDays = diffDays(rangeStart, rangeEnd) + 1;
  const markers = buildTimelineMarkers({ scale, rangeStart, rangeEnd, pxPerDay });

  return {
    rangeStart,
    rangeEnd,
    totalDays,
    pxPerDay,
    timelineWidth: totalDays * pxPerDay,
    markers,
  };
}

function getTimelineTone(row) {
  const status = String(row?.estado_operativo ?? "").toLowerCase();
  if (["entregado", "cobrado"].includes(status)) {
    return "info";
  }
  if (row?.semaforo === "atrasado") {
    return "danger";
  }
  if (row?.semaforo === "en_riesgo") {
    return "warning";
  }
  if (row?.semaforo === "a_tiempo") {
    return "success";
  }
  return "neutral";
}

function getTimelineBarData(row, timelineRange) {
  const startDate = parseDateValue(row?.fecha_inicio) ?? parseDateValue(row?.created_at) ?? parseDateValue(row?.fecha_compromiso);
  const endDate = parseDateValue(row?.fecha_compromiso) ?? startDate;

  if (!startDate || !endDate) {
    return {
      hasDates: false,
      left: 0,
      width: timelineRange.pxPerDay * 2,
      tone: getTimelineTone(row),
      startDate: null,
      endDate: null,
    };
  }

  let visualStart = startDate;
  let visualEnd = endDate;
  if (visualStart > visualEnd) {
    visualStart = endDate;
    visualEnd = startDate;
  }

  const startOffset = Math.max(0, diffDays(timelineRange.rangeStart, visualStart));
  const endOffset = Math.min(timelineRange.totalDays, diffDays(timelineRange.rangeStart, visualEnd) + 1);
  const left = startOffset * timelineRange.pxPerDay;
  const width = Math.max(timelineRange.pxPerDay, (endOffset - startOffset) * timelineRange.pxPerDay);

  return {
    hasDates: true,
    left,
    width,
    tone: getTimelineTone(row),
    startDate: visualStart,
    endDate: visualEnd,
  };
}

function getVisualStartLabel(row) {
  return formatDate(row?.fecha_inicio ?? row?.created_at);
}

function stopEvent(event, callback) {
  event.stopPropagation();
  callback();
}

export default function PMSimpleSchedulePage() {
  const navigate = useNavigate();
  const timelineHeaderRef = useRef(null);
  const { empresaId, token, membership, user } = useAuth();
  const canEditProgress = canEditPmProjectRole(membership?.role, Boolean(user?.is_superadmin));

  const [filters, setFilters] = useState(defaultFilters);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(emptySummary);
  const [meta, setMeta] = useState({ total: 0, limit: defaultFilters.limit, offset: 0 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selectedRow, setSelectedRow] = useState(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
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

  const timelineRange = useMemo(
    () => buildTimelineRange(rows, filters.scale || "month"),
    [rows, filters.scale],
  );

  const riskCount = useMemo(
    () => rows.filter((row) => String(row?.semaforo ?? "").toLowerCase() === "en_riesgo").length,
    [rows],
  );

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
      setError(requestError.message || "No se pudo cargar el cronograma de trabajos.");
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

  function openDetailModal(row) {
    resetFeedback();
    setSelectedRow(row);
    setDetailModalOpen(true);
  }

  function closeDetailModal() {
    setDetailModalOpen(false);
  }

  function openProgressModal(row) {
    resetFeedback();
    setProgressProject(row);
    setProgressForm(createProgressFormFromRow(row));
    setSelectedRow(row);
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
    setSelectedRow(row);
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

  function handleTimelineScroll(event) {
    if (timelineHeaderRef.current) {
      timelineHeaderRef.current.scrollLeft = event.currentTarget.scrollLeft;
    }
  }

  const needsCompletionHint =
    Number(progressForm.avance_porcentaje || 0) === 100 &&
    !["listo_entrega", "entregado", "cobrado"].includes(progressForm.estado_operativo);

  return (
    <div className="inventory-shell inventory-screen pm-screen pm-simple-page pm-schedule-page">
      <PageHeader
        eyebrow="PM Simple"
        title="Cronograma"
        subtitle="Seguimiento simple de trabajos con tabla operativa, fechas y avance visual."
        actions={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton onClick={() => navigate("/pm/dashboard")} type="button">
              Resumen
            </ActionButton>
            <ActionButton onClick={() => navigate("/pm/work-progress")} type="button">
              Avance de trabajos
            </ActionButton>
            <ActionButton onClick={() => navigate("/pm/projects")} type="button">
              Lista de trabajos
            </ActionButton>
            <ActionButton onClick={() => navigate("/pm/reports/executive")} type="button">
              Reporte de trabajos
            </ActionButton>
          </div>
        }
      />

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operacion" : "Operacion completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-5 pm-simple-kpi-grid">
        <MetricCard
          icon={<ClipboardList size={18} strokeWidth={1.9} />}
          label="Trabajos totales"
          meta="Base del periodo"
          tone="neutral"
          value={summary.trabajos_totales}
        />
        <MetricCard
          icon={<AlertTriangle size={18} strokeWidth={1.9} />}
          label="Atrasados"
          meta="Requieren seguimiento"
          tone="danger"
          value={summary.atrasados}
        />
        <MetricCard
          icon={<Clock3 size={18} strokeWidth={1.9} />}
          label="En riesgo"
          meta="Vista actual"
          tone="warning"
          value={riskCount}
        />
        <MetricCard
          icon={<CheckCircle2 size={18} strokeWidth={1.9} />}
          label="Entregados"
          meta="Operacion cerrada"
          tone="info"
          value={summary.entregados}
        />
        <MetricCard
          icon={<CircleDollarSign size={18} strokeWidth={1.9} />}
          label="Pendientes de cobro"
          meta="Seguimiento comercial"
          tone="warning"
          value={formatMoney(summary.monto_pendiente_cobro)}
        />
      </section>

      <FilterCard title="Filtros" subtitle="Vista tipo Excel con lectura simple por cliente, responsable, estado y fechas.">
        <form className="inventory-filter-toolbar" onSubmit={handleFilterSubmit}>
          <div className="inventory-toolbar-grid pm-schedule-filter-grid">
            <SearchInput
              action={
                <ActionButton icon={<Search size={16} strokeWidth={1.9} />} size="sm" tone="primary" type="submit">
                  Buscar
                </ActionButton>
              }
              hint="Busca por cliente, trabajo, codigo o proximo paso."
              label="Busqueda"
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Buscar trabajos..."
              value={filters.search}
            />
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
            <Field label="Solo atrasados">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, atrasados: event.target.value }))}
                value={filters.atrasados}
              >
                <option value="">Todos</option>
                <option value="true">Solo atrasados</option>
              </select>
            </Field>
            <Field label="Escala">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, scale: event.target.value }))}
                value={filters.scale}
              >
                {timelineScaleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
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

      <section className="inventory-card">
        <div className="inventory-card-header">
          <div>
            <h2>Cronograma de trabajos</h2>
            <p className="table-note">
              La barra usa fecha de inicio del trabajo cuando existe. Si no, usa la fecha de alta como inicio visual.
            </p>
          </div>
          <div className="inventory-actions inventory-actions-wrap">
            <ResultMeta label="trabajos" loaded={rows.length} total={meta.total} />
            <div className="pm-schedule-legend">
              {Object.entries(trafficLightOptions).map(([key, item]) => (
                <StatusBadge key={key} tone={key === "a_tiempo" ? "success" : item.tone}>
                  {item.label}
                </StatusBadge>
              ))}
              <StatusBadge tone="info">Entregado</StatusBadge>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="table-note">Cargando cronograma de trabajos...</div>
        ) : rows.length === 0 ? (
          <EmptyState note="Ajusta los filtros o registra avances desde el PM operativo." title="No hay trabajos registrados." />
        ) : (
          <>
            <div className="pm-schedule-board" style={{ "--pm-schedule-columns": scheduleGridTemplate }}>
              <div className="pm-schedule-board-head">
                <div className="pm-schedule-left-head">
                  <span>Trabajo</span>
                  <span>Cliente</span>
                  <span>Responsable</span>
                  <span>Estado</span>
                  <span>Avance</span>
                  <span>Fecha inicio</span>
                  <span>Fecha compromiso</span>
                  <span>Proximo paso</span>
                  <span>Bloqueo</span>
                  <span>Importe</span>
                  <span>Pendiente de cobro</span>
                  <span>Acciones</span>
                </div>

                <div className="pm-schedule-right-head">
                  <div className="pm-schedule-right-label">
                    <CalendarRange size={16} strokeWidth={1.9} />
                    <span>Cronograma</span>
                  </div>
                  <div className="pm-schedule-timeline-head" ref={timelineHeaderRef}>
                    <div className="pm-schedule-timeline-width" style={{ width: `${timelineRange.timelineWidth}px` }}>
                      {timelineRange.markers.map((marker) => (
                        <div className="pm-schedule-marker" key={marker.key} style={{ width: `${marker.width}px` }}>
                          <strong>{marker.label}</strong>
                          <span>{marker.caption}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="pm-schedule-board-body">
                <div className="pm-schedule-left-body">
                  {rows.map((row) => {
                    const trafficMeta = getTrafficLightMeta(row.semaforo);
                    const isSelected = selectedRow?.proyecto_id === row.proyecto_id;
                    return (
                      <div
                        className={`pm-schedule-left-row ${isSelected ? "is-selected" : ""}`}
                        key={`left-${row.proyecto_id}`}
                        onClick={() => openDetailModal(row)}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="pm-schedule-cell">
                          <strong>{safeDisplayText(row.nombre, "Trabajo sin nombre")}</strong>
                          <span>{safeDisplayText(row.codigo, "Sin codigo")}</span>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{safeDisplayText(row.cliente_nombre, "Sin cliente")}</strong>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{safeDisplayText(row.responsable_nombre, "Sin responsable")}</strong>
                        </div>
                        <div className="pm-schedule-cell">
                          <StatusBadge tone={getOperationalStatusTone(row.estado_operativo)}>
                            {getOperationalStatusLabel(row.estado_operativo)}
                          </StatusBadge>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{formatPercentValue(row.avance_porcentaje)}</strong>
                          <span>{trafficMeta.label}</span>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{getVisualStartLabel(row)}</strong>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{formatDate(row.fecha_compromiso)}</strong>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{safeDisplayText(row.proximo_paso, "Sin siguiente paso")}</strong>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{safeDisplayText(row.bloqueo_actual, "Sin bloqueo")}</strong>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{formatOptionalMoney(row.presupuesto_estimado)}</strong>
                        </div>
                        <div className="pm-schedule-cell">
                          <strong>{formatOptionalMoney(row.saldo_pendiente)}</strong>
                        </div>
                        <div className="pm-schedule-cell pm-schedule-actions">
                          <ActionButton
                            disabled={!canEditProgress}
                            onClick={(event) => stopEvent(event, () => openProgressModal(row))}
                            size="sm"
                            tone="primary"
                            type="button"
                          >
                            Actualizar avance
                          </ActionButton>
                          <ActionButton
                            icon={<History size={14} strokeWidth={1.9} />}
                            onClick={(event) => stopEvent(event, () => openHistoryModal(row))}
                            size="sm"
                            type="button"
                          >
                            Ver historial
                          </ActionButton>
                          <ActionButton
                            onClick={(event) => stopEvent(event, () => handleDownloadProgressReport(row))}
                            size="sm"
                            type="button"
                          >
                            Descargar reporte
                          </ActionButton>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="pm-schedule-right-body" onScroll={handleTimelineScroll}>
                  <div className="pm-schedule-timeline-width" style={{ width: `${timelineRange.timelineWidth}px` }}>
                    {rows.map((row) => {
                      const barData = getTimelineBarData(row, timelineRange);
                      const isSelected = selectedRow?.proyecto_id === row.proyecto_id;
                      return (
                        <div
                          className={`pm-schedule-timeline-row ${isSelected ? "is-selected" : ""}`}
                          key={`right-${row.proyecto_id}`}
                          onClick={() => openDetailModal(row)}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="pm-schedule-timeline-grid">
                            {timelineRange.markers.map((marker) => (
                              <div
                                className="pm-schedule-track-segment"
                                key={`${row.proyecto_id}-${marker.key}`}
                                style={{ width: `${marker.width}px` }}
                              />
                            ))}
                          </div>

                          {barData.hasDates ? (
                            <div
                              className={`pm-schedule-bar pm-gantt-bar ${barData.tone}`}
                              style={{ left: `${barData.left}px`, width: `${barData.width}px` }}
                            >
                              <div
                                className="pm-gantt-bar-progress"
                                style={{ width: `${Math.max(0, Math.min(100, Number(row.avance_porcentaje ?? 0)))}%` }}
                              />
                              <div className="pm-schedule-bar-label">
                                <strong>{safeDisplayText(row.nombre, "Trabajo")}</strong>
                                <span>{formatPercentValue(row.avance_porcentaje)}</span>
                              </div>
                            </div>
                          ) : (
                            <div className="pm-schedule-no-dates">Sin fechas para dibujar el cronograma.</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            <PaginationControls meta={meta} onNext={() => handlePaginate("next")} onPrevious={() => handlePaginate("previous")} />
          </>
        )}
      </section>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton
              disabled={!selectedRow}
              onClick={() => selectedRow && handleDownloadProgressReport(selectedRow)}
              type="button"
            >
              Descargar reporte
            </ActionButton>
            <ActionButton
              disabled={!selectedRow}
              onClick={() => {
                if (selectedRow) {
                  openHistoryModal(selectedRow);
                }
              }}
              type="button"
            >
              Ver historial
            </ActionButton>
            <ActionButton
              disabled={!selectedRow || !canEditProgress}
              onClick={() => {
                if (selectedRow) {
                  openProgressModal(selectedRow);
                }
              }}
              tone="primary"
              type="button"
            >
              Actualizar avance
            </ActionButton>
            <ActionButton onClick={closeDetailModal} type="button">
              Cerrar
            </ActionButton>
          </div>
        }
        onClose={closeDetailModal}
        open={detailModalOpen}
        size="wide"
        subtitle="Resumen rapido del trabajo y acciones operativas del cronograma."
        title="Detalle del trabajo"
      >
        {selectedRow ? (
          <div className="pm-schedule-detail-grid">
            <div className="pm-schedule-detail-card">
              <span>Trabajo</span>
              <strong>{safeDisplayText(selectedRow.nombre, "Trabajo sin nombre")}</strong>
              <p className="table-note">{safeDisplayText(selectedRow.codigo, "Sin codigo")}</p>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Cliente</span>
              <strong>{safeDisplayText(selectedRow.cliente_nombre, "Sin cliente")}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Responsable</span>
              <strong>{safeDisplayText(selectedRow.responsable_nombre, "Sin responsable")}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Estado</span>
              <div className="inventory-actions inventory-actions-wrap">
                <StatusBadge tone={getOperationalStatusTone(selectedRow.estado_operativo)}>
                  {getOperationalStatusLabel(selectedRow.estado_operativo)}
                </StatusBadge>
                <StatusBadge tone={getTrafficLightMeta(selectedRow.semaforo).tone}>
                  {getTrafficLightMeta(selectedRow.semaforo).label}
                </StatusBadge>
              </div>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Avance</span>
              <strong>{formatPercentValue(selectedRow.avance_porcentaje)}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Fecha inicio</span>
              <strong>{getVisualStartLabel(selectedRow)}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Fecha compromiso</span>
              <strong>{formatDate(selectedRow.fecha_compromiso)}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Proximo paso</span>
              <strong>{safeDisplayText(selectedRow.proximo_paso, "Sin siguiente paso")}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Bloqueo</span>
              <strong>{safeDisplayText(selectedRow.bloqueo_actual, "Sin bloqueo")}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Importe pactado</span>
              <strong>{formatOptionalMoney(selectedRow.presupuesto_estimado)}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Pendiente de cobro</span>
              <strong>{formatOptionalMoney(selectedRow.saldo_pendiente)}</strong>
            </div>
            <div className="pm-schedule-detail-card">
              <span>Ultima actualizacion</span>
              <strong>{formatDateTime(selectedRow.ultima_actualizacion_avance_at)}</strong>
            </div>
          </div>
        ) : null}
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={() => closeProgressModal()} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-simple-schedule-progress-form" tone="primary" type="submit">
              {saving ? "Guardando..." : "Guardar avance"}
            </ActionButton>
          </div>
        }
        onClose={() => closeProgressModal()}
        open={progressModalOpen}
        size="wide"
        subtitle="Actualiza el avance operativo, el proximo paso y cualquier bloqueo actual."
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
            <p className="table-note">Si el trabajo ya termino, conviene marcarlo como listo para entrega o entregado.</p>
          </div>
        ) : null}

        <form className="inventory-modal-form" id="pm-simple-schedule-progress-form" onSubmit={handleSaveProgress}>
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
            <Field label="Estado">
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
            <Field label="Proximo paso">
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
        subtitle="Bitacora simple de avances registrados para este trabajo."
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
          <EmptyState compact note="El historial aparecera en cuanto se registre el primer avance." title="No hay avances registrados." />
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
                    <span>Proximo paso</span>
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
