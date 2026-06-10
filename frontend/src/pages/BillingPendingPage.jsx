import { useEffect, useMemo, useState } from "react";
import { ClipboardList, ReceiptText } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import FeaturePlaceholder from "../components/FeaturePlaceholder";
import {
  discardBillingPosInvoiceRequest,
  getBillingPosInvoiceRequestDetail,
  getBillingPosInvoiceRequests,
  observeBillingPosInvoiceRequest,
  prepareBillingPosInvoiceRequest,
  reviewBillingPosInvoiceRequest,
  updatePosSaleInvoiceRequest,
} from "../api/client";
import { ActionButton, Field, FormGrid, ModalShell, StatusBadge } from "./inventory/shared";


const DEFAULT_PAGE_SIZE = 25;
const filterDefaults = {
  estado: "",
  fecha_desde: "",
  fecha_hasta: "",
  rfc: "",
  folio: "",
  cliente: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultInvoiceForm = {
  cliente_nombre: "",
  rfc: "",
  razon_social: "",
  email: "",
  uso_cfdi: "G03",
  regimen_fiscal: "616",
  codigo_postal: "",
  notas: "",
};

const invoiceUsageOptions = [
  { value: "G03", label: "G03 - Gastos en general" },
  { value: "G01", label: "G01 - Adquisicion de mercancias" },
  { value: "S01", label: "S01 - Sin efectos fiscales" },
];

const invoiceFiscalRegimeOptions = [
  { value: "601", label: "601 - General de Ley Personas Morales" },
  { value: "612", label: "612 - Personas Fisicas con Actividades Empresariales" },
  { value: "616", label: "616 - Sin obligaciones fiscales" },
];


function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


function formatMoney(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


function getInvoiceStateLabel(value) {
  const labels = {
    pendiente_datos: "Pendiente de datos",
    lista_para_facturar: "Lista para facturar",
    en_revision: "En revision",
    observada: "Observada",
    preparada: "Preparada",
    descartada: "Descartada",
    solicitada: "Solicitada",
    no_solicitada: "No solicitada",
  };
  return labels[String(value ?? "").toLowerCase()] ?? String(value ?? "Sin estado");
}


function getInvoiceStateTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "preparada" || normalized === "lista_para_facturar") {
    return "success";
  }
  if (normalized === "pendiente_datos" || normalized === "en_revision") {
    return "warning";
  }
  if (normalized === "observada" || normalized === "descartada") {
    return "danger";
  }
  return "neutral";
}


function getBillingUiError(requestError, fallback) {
  const rawMessage = String(requestError?.message ?? "").trim();
  const normalized = rawMessage.toLowerCase();

  if (!rawMessage) {
    return fallback;
  }
  if (requestError?.status === 404) {
    return "No se pudo cargar la informacion. Intenta actualizar.";
  }
  if (normalized.includes("rfc")) {
    return "Ingresa un RFC valido.";
  }
  if (normalized.includes("email")) {
    return "Ingresa un email valido.";
  }
  if (normalized.includes("faltan datos fiscales")) {
    return "Faltan datos fiscales.";
  }
  if (normalized.includes("venta cancelada")) {
    return "No puedes preparar una venta cancelada.";
  }
  if (normalized.includes("ventas pagadas")) {
    return "Solo puedes preparar solicitudes de ventas pagadas.";
  }
  return rawMessage || fallback;
}


function buildInvoiceForm(detail) {
  return {
    cliente_nombre: detail?.cliente ?? "",
    rfc: detail?.rfc ?? "",
    razon_social: detail?.razon_social ?? "",
    email: detail?.email ?? "",
    uso_cfdi: detail?.uso_cfdi ?? "G03",
    regimen_fiscal: detail?.regimen_fiscal ?? "616",
    codigo_postal: detail?.codigo_postal ?? "",
    notas: detail?.notas ?? "",
  };
}


function KpiCard({ title, value, note = "" }) {
  return (
    <article className="pos-kpi-card">
      <div className="pos-kpi-card-head">
        <span className="pos-kpi-card-icon">
          <ReceiptText size={16} />
        </span>
        <div className="pos-kpi-body">
          <span className="pos-kpi-title">{title}</span>
          <strong className="pos-kpi-number">{value}</strong>
          {note ? <p className="pos-kpi-help">{note}</p> : null}
        </div>
      </div>
    </article>
  );
}


function PaginationControls({ meta, onPrevious, onNext }) {
  if (!meta) {
    return null;
  }

  return (
    <div className="inventory-pagination">
      <p className="table-note">
        Mostrando {Math.min(meta.total, meta.offset + 1)}-{Math.min(meta.total, meta.offset + meta.limit)} de {meta.total}
      </p>
      <div className="inventory-actions">
        <ActionButton disabled={meta.offset <= 0} onClick={onPrevious} size="sm" type="button">
          Anterior
        </ActionButton>
        <ActionButton
          disabled={meta.offset + meta.limit >= meta.total}
          onClick={onNext}
          size="sm"
          type="button"
        >
          Siguiente
        </ActionButton>
      </div>
    </div>
  );
}


export default function BillingPendingPage() {
  const { token, empresaId, membership, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState(filterDefaults);
  const [requests, setRequests] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [kpis, setKpis] = useState({
    pendientes_datos: 0,
    listas_para_facturar: 0,
    en_revision: 0,
    observadas: 0,
    preparadas: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [invoiceForm, setInvoiceForm] = useState(defaultInvoiceForm);
  const [reviewNote, setReviewNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState("");
  const canManageBillingUi = user?.is_superadmin || ["owner", "admin"].includes(String(membership?.role ?? "").toLowerCase());

  async function loadRequests(nextFilters = filters) {
    if (!token || !empresaId || !canManageBillingUi) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const response = await getBillingPosInvoiceRequests({
        token,
        empresaId,
        filters: {
          ...nextFilters,
          fecha_desde: nextFilters.fecha_desde ? `${nextFilters.fecha_desde}T00:00:00` : "",
          fecha_hasta: nextFilters.fecha_hasta ? `${nextFilters.fecha_hasta}T23:59:59` : "",
        },
      });
      setRequests(response.items ?? []);
      setMeta({
        total: response.total ?? 0,
        limit: response.limit ?? DEFAULT_PAGE_SIZE,
        offset: response.offset ?? 0,
      });
      setKpis(response.kpis ?? {
        pendientes_datos: 0,
        listas_para_facturar: 0,
        en_revision: 0,
        observadas: 0,
        preparadas: 0,
      });
    } catch (requestError) {
      setRequests([]);
      setError(getBillingUiError(requestError, "No se pudo cargar la bandeja fiscal. Intenta actualizar."));
    } finally {
      setLoading(false);
    }
  }

  async function openRequestDetail(saleId, { keepQuery = true } = {}) {
    if (!token || !empresaId || !saleId) {
      return;
    }

    setSubmitting(true);
    setNotice("");
    try {
      const detail = await getBillingPosInvoiceRequestDetail({
        saleId,
        token,
        empresaId,
      });
      setSelectedRequest(detail);
      setInvoiceForm(buildInvoiceForm(detail));
      setReviewNote(detail.factura_revision_notas ?? "");
      setDetailOpen(true);
      if (keepQuery) {
        const next = new URLSearchParams(searchParams);
        next.set("sale_id", saleId);
        setSearchParams(next);
      }
    } catch (requestError) {
      setError(getBillingUiError(requestError, "No se pudo cargar la solicitud fiscal."));
    } finally {
      setSubmitting(false);
    }
  }

  function closeDetailModal() {
    setDetailOpen(false);
    setSelectedRequest(null);
    setReviewNote("");
    const next = new URLSearchParams(searchParams);
    next.delete("sale_id");
    setSearchParams(next);
  }

  async function refreshDetail(saleId, successMessage = "") {
    const detail = await getBillingPosInvoiceRequestDetail({
      saleId,
      token,
      empresaId,
    });
    setSelectedRequest(detail);
    setInvoiceForm(buildInvoiceForm(detail));
    setReviewNote(detail.factura_revision_notas ?? "");
    if (successMessage) {
      setNotice(successMessage);
    }
  }

  async function handleSaveFiscalData(event) {
    event.preventDefault();
    if (!selectedRequest) {
      return;
    }

    setSubmitting(true);
    setNotice("");
    setError("");
    try {
      await updatePosSaleInvoiceRequest({
        saleId: selectedRequest.venta_id,
        token,
        empresaId,
        payload: invoiceForm,
      });
      await refreshDetail(selectedRequest.venta_id, "Solicitud fiscal actualizada.");
      await loadRequests(filters);
    } catch (requestError) {
      setError(getBillingUiError(requestError, "No se pudo guardar la solicitud fiscal."));
    } finally {
      setSubmitting(false);
    }
  }

  async function runDetailAction(action) {
    if (!selectedRequest) {
      return;
    }

    setSubmitting(true);
    setNotice("");
    setError("");
    try {
      if (action === "review") {
        await reviewBillingPosInvoiceRequest({
          saleId: selectedRequest.venta_id,
          token,
          empresaId,
          payload: { nota: reviewNote },
        });
        await refreshDetail(selectedRequest.venta_id, "Solicitud marcada en revision.");
      } else if (action === "observe") {
        await observeBillingPosInvoiceRequest({
          saleId: selectedRequest.venta_id,
          token,
          empresaId,
          payload: { nota: reviewNote },
        });
        await refreshDetail(selectedRequest.venta_id, "Solicitud observada.");
      } else if (action === "prepare") {
        await prepareBillingPosInvoiceRequest({
          saleId: selectedRequest.venta_id,
          token,
          empresaId,
        });
        await refreshDetail(selectedRequest.venta_id, "Solicitud preparada para timbrado futuro.");
      } else if (action === "discard") {
        await discardBillingPosInvoiceRequest({
          saleId: selectedRequest.venta_id,
          token,
          empresaId,
          payload: { nota: reviewNote },
        });
        await refreshDetail(selectedRequest.venta_id, "Solicitud descartada.");
      }
      await loadRequests(filters);
    } catch (requestError) {
      setError(getBillingUiError(requestError, "No se pudo actualizar la solicitud fiscal."));
    } finally {
      setSubmitting(false);
    }
  }

  function handleSearch(event) {
    event.preventDefault();
    const nextFilters = {
      ...filters,
      offset: 0,
    };
    setFilters(nextFilters);
    loadRequests(nextFilters);
  }

  function handleResetFilters() {
    setFilters(filterDefaults);
    loadRequests(filterDefaults);
  }

  function handlePageChange(nextOffset) {
    const nextFilters = {
      ...filters,
      offset: nextOffset,
    };
    setFilters(nextFilters);
    loadRequests(nextFilters);
  }

  useEffect(() => {
    if (!token || !empresaId || !canManageBillingUi) {
      return;
    }
    loadRequests(filterDefaults);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, empresaId, canManageBillingUi]);

  useEffect(() => {
    const saleId = searchParams.get("sale_id");
    if (!saleId || !token || !empresaId || !canManageBillingUi) {
      return;
    }
    if (detailOpen && selectedRequest?.venta_id === saleId) {
      return;
    }
    openRequestDetail(saleId, { keepQuery: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, token, empresaId, canManageBillingUi, detailOpen, selectedRequest]);

  const selectedWarnings = useMemo(() => {
    if (!selectedRequest) {
      return [];
    }
    const warnings = [];
    if (selectedRequest.venta_cancelada) {
      warnings.push("La venta fue cancelada. Esta solicitud ya no puede prepararse.");
    }
    if (selectedRequest.venta_estatus !== "pagada") {
      warnings.push("Solo las ventas pagadas pueden prepararse para timbrado futuro.");
    }
    return warnings;
  }, [selectedRequest]);

  if (!canManageBillingUi) {
    return (
      <FeaturePlaceholder
        title="Facturacion"
        subtitle="Esta bandeja fiscal solo esta disponible para owner, admin o superadmin."
        items={[
          "Solicitudes POS",
          "Revision fiscal basica",
          "Preparacion CFDI futura",
          "Sin timbrado en esta fase",
        ]}
        note="La preparacion fiscal no reemplaza el timbrado real. Esta vista solo organiza solicitudes operativas."
        tone="warning"
      />
    );
  }

  return (
    <>
      <div className="page-shell billing-queue-page">
        <section className="feature-card pos-section-card">
          <div className="feature-header">
            <p className="eyebrow">Facturacion</p>
            <h1>Solicitudes de factura POS</h1>
            <p className="table-note">
              Revisa y prepara solicitudes de factura provenientes del punto de venta. El timbrado CFDI aun esta pendiente.
            </p>
          </div>

          <div className="pos-warning-box is-warning">
            <strong>Esta vista no timbra CFDI.</strong>
            <p>Solo prepara datos para una fase fiscal posterior y deja la solicitud lista para integracion futura.</p>
          </div>
        </section>

        <section className="pos-kpi-grid pos-kpi-grid-compact">
          <KpiCard note="Faltan RFC, email o datos minimos." title="Pendientes de datos" value={kpis.pendientes_datos} />
          <KpiCard note="Completas para pasar a revision." title="Listas para facturar" value={kpis.listas_para_facturar} />
          <KpiCard note="Solicitudes tomadas por el equipo fiscal." title="En revision" value={kpis.en_revision} />
          <KpiCard note="Requieren correccion o aclaracion." title="Observadas" value={kpis.observadas} />
          <KpiCard note="Preparadas para timbrado futuro." title="Preparadas" value={kpis.preparadas} />
        </section>

        <section className="feature-card pos-section-card">
          <form className="pos-report-filters pos-invoice-filters" onSubmit={handleSearch}>
            <Field label="Estado">
              <select
                className="pos-input"
                onChange={(event) => setFilters((current) => ({ ...current, estado: event.target.value }))}
                value={filters.estado}
              >
                <option value="">Todos los estados</option>
                <option value="pendiente_datos">Pendiente de datos</option>
                <option value="lista_para_facturar">Lista para facturar</option>
                <option value="en_revision">En revision</option>
                <option value="observada">Observada</option>
                <option value="preparada">Preparada</option>
                <option value="descartada">Descartada</option>
              </select>
            </Field>

            <Field label="Fecha desde">
              <input
                className="pos-input"
                onChange={(event) => setFilters((current) => ({ ...current, fecha_desde: event.target.value }))}
                type="date"
                value={filters.fecha_desde}
              />
            </Field>

            <Field label="Fecha hasta">
              <input
                className="pos-input"
                onChange={(event) => setFilters((current) => ({ ...current, fecha_hasta: event.target.value }))}
                type="date"
                value={filters.fecha_hasta}
              />
            </Field>

            <Field label="RFC / Folio / Cliente" span={2}>
              <div className="billing-inline-filters">
                <input
                  className="pos-input"
                  onChange={(event) => setFilters((current) => ({ ...current, rfc: event.target.value }))}
                  placeholder="RFC"
                  type="text"
                  value={filters.rfc}
                />
                <input
                  className="pos-input"
                  onChange={(event) => setFilters((current) => ({ ...current, folio: event.target.value }))}
                  placeholder="Folio"
                  type="text"
                  value={filters.folio}
                />
                <input
                  className="pos-input"
                  onChange={(event) => setFilters((current) => ({ ...current, cliente: event.target.value }))}
                  placeholder="Cliente o razon social"
                  type="text"
                  value={filters.cliente}
                />
              </div>
            </Field>

            <div className="pos-action-row">
              <ActionButton tone="primary" type="submit">
                Aplicar
              </ActionButton>
              <ActionButton onClick={handleResetFilters} type="button">
                Limpiar
              </ActionButton>
            </div>
          </form>
        </section>

        <section className="feature-card pos-section-card">
          {error ? (
            <div className="pos-warning-box">
              <strong>No se pudo cargar la bandeja fiscal.</strong>
              <p>{error}</p>
            </div>
          ) : null}

          {loading ? (
            <p className="table-note">Cargando solicitudes fiscales...</p>
          ) : requests.length === 0 ? (
            <div className="empty-state pos-empty-state">
              <span className="pos-empty-state-icon">
                <ClipboardList size={18} />
              </span>
              <strong>No hay solicitudes de factura.</strong>
              <p>Las ventas con solicitud fiscal apareceran aqui para revision y preparacion futura.</p>
            </div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="inventory-table pos-report-table">
                  <thead>
                    <tr>
                      <th>Folio venta</th>
                      <th>Fecha</th>
                      <th>Cliente</th>
                      <th>RFC</th>
                      <th>Total</th>
                      <th>Estado solicitud</th>
                      <th>Estado revision</th>
                      <th>Accion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((item) => (
                      <tr key={item.venta_id}>
                        <td>{item.folio}</td>
                        <td>{formatDateTime(item.fecha_venta)}</td>
                        <td>{item.razon_social || item.cliente || "Mostrador"}</td>
                        <td>{item.rfc || "Sin RFC"}</td>
                        <td>{formatMoney(item.total)}</td>
                        <td>
                          <StatusBadge tone={getInvoiceStateTone(item.estado_solicitud)}>
                            {getInvoiceStateLabel(item.estado_solicitud)}
                          </StatusBadge>
                        </td>
                        <td>
                          <StatusBadge tone={getInvoiceStateTone(item.estado_revision)}>
                            {getInvoiceStateLabel(item.estado_revision)}
                          </StatusBadge>
                        </td>
                        <td className="inventory-row-actions">
                          <ActionButton onClick={() => openRequestDetail(item.venta_id)} size="sm" type="button">
                            Ver / Editar datos
                          </ActionButton>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <PaginationControls
                meta={meta}
                onNext={() => handlePageChange(meta.offset + meta.limit)}
                onPrevious={() => handlePageChange(Math.max(0, meta.offset - meta.limit))}
              />
            </>
          )}
        </section>
      </div>

      <ModalShell
        onClose={closeDetailModal}
        open={detailOpen}
        size="wide"
        subtitle="Preparar para timbrado futuro. Esta vista no timbra CFDI ni genera XML fiscal real."
        title="Detalle de solicitud fiscal"
      >
        {selectedRequest ? (
          <div className="pos-modal-stack billing-detail-stack">
            {notice ? (
              <div className="pos-warning-box is-success">
                <strong>Actualizacion aplicada</strong>
                <p>{notice}</p>
              </div>
            ) : null}

            {error ? (
              <div className="pos-warning-box">
                <strong>No se pudo actualizar la solicitud.</strong>
                <p>{error}</p>
              </div>
            ) : null}

            {selectedWarnings.map((warning) => (
              <div className="pos-warning-box" key={warning}>
                <strong>Advertencia fiscal</strong>
                <p>{warning}</p>
              </div>
            ))}

            <div className="pos-ticket-meta-grid">
              <article className="mini-card">
                <span className="eyebrow">Venta</span>
                <strong>{selectedRequest.folio}</strong>
                <p>{formatDateTime(selectedRequest.fecha_venta)}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Estado venta</span>
                <strong>{selectedRequest.venta_estatus}</strong>
                <p>{formatMoney(selectedRequest.total)}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Estado revision</span>
                <strong>{getInvoiceStateLabel(selectedRequest.estado_revision)}</strong>
                <p>{selectedRequest.revisada_por_nombre || "Sin responsable"}</p>
              </article>
            </div>

            <section className="feature-card pos-section-card">
              <div className="feature-header">
                <p className="eyebrow">Validacion fiscal basica</p>
                <h3>Datos fiscales</h3>
              </div>

              {selectedRequest.validation?.errors?.length ? (
                <ul className="billing-validation-list">
                  {selectedRequest.validation.errors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="table-note">Los datos minimos ya permiten preparar la solicitud para timbrado futuro.</p>
              )}

              <form className="pos-modal-stack" onSubmit={handleSaveFiscalData}>
                <FormGrid className="billing-detail-form">
                  <Field label="Nombre del cliente">
                    <input
                      className="pos-input"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, cliente_nombre: event.target.value }))}
                      type="text"
                      value={invoiceForm.cliente_nombre}
                    />
                  </Field>

                  <Field label="RFC">
                    <input
                      className="pos-input"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, rfc: event.target.value.toUpperCase() }))}
                      type="text"
                      value={invoiceForm.rfc}
                    />
                  </Field>

                  <Field label="Razon social" span={2}>
                    <input
                      className="pos-input"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, razon_social: event.target.value }))}
                      type="text"
                      value={invoiceForm.razon_social}
                    />
                  </Field>

                  <Field label="Email">
                    <input
                      className="pos-input"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, email: event.target.value }))}
                      type="email"
                      value={invoiceForm.email}
                    />
                  </Field>

                  <Field label="Uso CFDI">
                    <select
                      className="pos-input"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, uso_cfdi: event.target.value }))}
                      value={invoiceForm.uso_cfdi}
                    >
                      {invoiceUsageOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Regimen fiscal">
                    <select
                      className="pos-input"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, regimen_fiscal: event.target.value }))}
                      value={invoiceForm.regimen_fiscal}
                    >
                      {invoiceFiscalRegimeOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Codigo postal">
                    <input
                      className="pos-input"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, codigo_postal: event.target.value }))}
                      type="text"
                      value={invoiceForm.codigo_postal}
                    />
                  </Field>

                  <Field label="Notas" span={2}>
                    <textarea
                      className="pos-textarea"
                      onChange={(event) => setInvoiceForm((current) => ({ ...current, notas: event.target.value }))}
                      rows={3}
                      value={invoiceForm.notas}
                    />
                  </Field>
                </FormGrid>

                <div className="pos-action-row">
                  <ActionButton disabled={submitting} tone="primary" type="submit">
                    {submitting ? "Guardando..." : "Guardar datos fiscales"}
                  </ActionButton>
                </div>
              </form>
            </section>

            <section className="feature-card pos-section-card">
              <div className="feature-header">
                <p className="eyebrow">Acciones fiscales</p>
                <h3>Revision operativa</h3>
              </div>
              <label className="inventory-field">
                <span className="inventory-field-label">Nota de revision / observacion / descarte</span>
                <textarea
                  className="pos-textarea"
                  onChange={(event) => setReviewNote(event.target.value)}
                  rows={4}
                  value={reviewNote}
                />
              </label>
              <div className="inventory-actions">
                <ActionButton disabled={submitting} onClick={() => runDetailAction("review")} size="sm" type="button">
                  Marcar en revision
                </ActionButton>
                <ActionButton disabled={submitting} onClick={() => runDetailAction("observe")} size="sm" type="button">
                  Observar
                </ActionButton>
                <ActionButton
                  disabled={submitting || !selectedRequest.validation?.is_valid || selectedRequest.venta_estatus !== "pagada"}
                  onClick={() => runDetailAction("prepare")}
                  size="sm"
                  tone="primary"
                  type="button"
                >
                  Preparar para timbrado futuro
                </ActionButton>
                <ActionButton disabled={submitting} onClick={() => runDetailAction("discard")} size="sm" tone="danger" type="button">
                  Descartar
                </ActionButton>
              </div>
            </section>

            <section className="feature-card pos-section-card">
              <div className="feature-header">
                <p className="eyebrow">Venta</p>
                <h3>Productos</h3>
              </div>
              <div className="table-wrap">
                <table className="inventory-table pos-report-table">
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Producto</th>
                      <th>Cantidad</th>
                      <th>Precio</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRequest.productos.map((item) => (
                      <tr key={item.id}>
                        <td>{item.sku_snapshot}</td>
                        <td>{item.nombre_snapshot}</td>
                        <td>{item.cantidad}</td>
                        <td>{formatMoney(item.precio_unitario)}</td>
                        <td>{formatMoney(item.total_linea)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="feature-card pos-section-card">
              <div className="feature-header">
                <p className="eyebrow">Pagos</p>
                <h3>Desglose de pago</h3>
              </div>
              {selectedRequest.pagos.length === 0 ? (
                <p className="table-note">Esta venta no tiene pagos desglosados disponibles.</p>
              ) : (
                <div className="table-wrap">
                  <table className="inventory-table pos-report-table">
                    <thead>
                      <tr>
                        <th>Metodo</th>
                        <th>Monto</th>
                        <th>Referencia</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRequest.pagos.map((item) => (
                        <tr key={item.id}>
                          <td>{item.metodo}</td>
                          <td>{formatMoney(item.monto)}</td>
                          <td>{item.referencia || "Sin referencia"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        ) : null}
      </ModalShell>
    </>
  );
}
