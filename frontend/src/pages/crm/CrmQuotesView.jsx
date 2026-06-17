import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Eye,
  Plus,
  RefreshCw,
  Send,
  XCircle,
} from "lucide-react";

import {
  acceptCrmQuote,
  cancelCrmQuote,
  createCrmQuote,
  downloadCrmQuotePdf,
  getCrmQuote,
  listCrmQuotes,
  rejectCrmQuote,
  sendCrmQuote,
  updateCrmQuote,
} from "../../api/client";
import {
  ActionButton,
  DEFAULT_PAGE_SIZE,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  ModalShell,
  PaginationControls,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  formatDate,
  formatMoney,
  formatNumber,
  normalizeDecimalInput,
  safeDisplayText,
} from "../inventory/shared";


const EMPTY_META = { total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 };

const defaultQuoteFilters = {
  search: "",
  estatus: "",
  cliente_id: "",
  oportunidad_id: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

function createLocalQuoteItem() {
  return {
    local_id: `quote-item-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    descripcion: "",
    cantidad: "1",
    precio_unitario: "0",
    descuento: "0",
    impuesto_tasa: "0",
  };
}

const defaultQuoteForm = {
  id: "",
  cliente_id: "",
  contacto_id: "",
  oportunidad_id: "",
  titulo: "",
  descripcion: "",
  fecha_vencimiento: "",
  condiciones_pago: "",
  notas: "",
  items: [createLocalQuoteItem()],
};

function normalizeOptionalText(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed : null;
}

function parseQuoteNumber(value) {
  const sanitized = normalizeDecimalInput(String(value ?? ""));
  const parsed = Number(sanitized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function buildQuotePayload(form) {
  return {
    cliente_id: form.cliente_id,
    contacto_id: normalizeOptionalText(form.contacto_id),
    oportunidad_id: normalizeOptionalText(form.oportunidad_id),
    titulo: String(form.titulo ?? "").trim(),
    descripcion: normalizeOptionalText(form.descripcion),
    fecha_vencimiento: form.fecha_vencimiento || null,
    condiciones_pago: normalizeOptionalText(form.condiciones_pago),
    notas: normalizeOptionalText(form.notas),
    items: (form.items || []).map((item, index) => ({
      descripcion: String(item.descripcion ?? "").trim(),
      cantidad: normalizeDecimalInput(String(item.cantidad ?? "")) || "0",
      precio_unitario: normalizeDecimalInput(String(item.precio_unitario ?? "")) || "0",
      descuento: normalizeDecimalInput(String(item.descuento ?? "")) || "0",
      impuesto_tasa: normalizeDecimalInput(String(item.impuesto_tasa ?? "")) || "0",
      orden: index,
    })),
  };
}

function validateQuoteForm(form) {
  if (!form.cliente_id) {
    return "Selecciona un cliente para la cotizacion.";
  }
  if (!String(form.titulo ?? "").trim()) {
    return "Captura el titulo de la cotizacion.";
  }
  if (!Array.isArray(form.items) || form.items.length === 0) {
    return "Agrega al menos una partida.";
  }
  for (const item of form.items) {
    if (!String(item.descripcion ?? "").trim()) {
      return "Cada partida debe tener descripcion.";
    }
    if (parseQuoteNumber(item.cantidad) <= 0) {
      return "La cantidad de cada partida debe ser mayor a cero.";
    }
    if (parseQuoteNumber(item.precio_unitario) < 0) {
      return "El precio unitario no puede ser negativo.";
    }
    if (parseQuoteNumber(item.descuento) < 0) {
      return "El descuento no puede ser negativo.";
    }
    if (parseQuoteNumber(item.impuesto_tasa) < 0) {
      return "La tasa de impuesto no puede ser negativa.";
    }
  }
  return "";
}

function quoteStatusTone(status) {
  switch (status) {
    case "aceptada":
      return "success";
    case "rechazada":
    case "cancelada":
      return "danger";
    case "enviada":
      return "info";
    case "vencida":
      return "warning";
    case "borrador":
    default:
      return "neutral";
  }
}

function quoteStatusLabel(status) {
  if (!status) {
    return "Sin estatus";
  }
  return String(status)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function mapQuoteResponseToForm(quote) {
  return {
    id: quote.id,
    cliente_id: quote.cliente_id || "",
    contacto_id: quote.contacto_id || "",
    oportunidad_id: quote.oportunidad_id || "",
    titulo: quote.titulo || "",
    descripcion: quote.descripcion || "",
    fecha_vencimiento: quote.fecha_vencimiento || "",
    condiciones_pago: quote.condiciones_pago || "",
    notas: quote.notas || "",
    items: Array.isArray(quote.items) && quote.items.length > 0
      ? quote.items.map((item) => ({
          local_id: item.id || createLocalQuoteItem().local_id,
          descripcion: item.descripcion || "",
          cantidad: String(item.cantidad ?? "0"),
          precio_unitario: String(item.precio_unitario ?? "0"),
          descuento: String(item.descuento ?? "0"),
          impuesto_tasa: String(item.impuesto_tasa ?? "0"),
        }))
      : [createLocalQuoteItem()],
  };
}

function translateQuoteEditError(message, isEditing) {
  if (
    isEditing &&
    /editar cotizaciones en borrador|ya no permite|no puede editarse/i.test(String(message || ""))
  ) {
    return "La cotizacion ya no puede editarse por su estatus.";
  }
  return message || "No se pudo guardar la cotizacion.";
}

export default function CrmQuotesView({
  token,
  empresaId,
  clientOptions,
  opportunityOptions,
  contactOptionsByClient,
  loadClientContactOptions,
  onQuotesChanged,
}) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [quotes, setQuotes] = useState([]);
  const [quoteMeta, setQuoteMeta] = useState(EMPTY_META);
  const [quoteFilters, setQuoteFilters] = useState(defaultQuoteFilters);

  const [quoteFormOpen, setQuoteFormOpen] = useState(false);
  const [quoteForm, setQuoteForm] = useState(defaultQuoteForm);

  const [quoteDetailOpen, setQuoteDetailOpen] = useState(false);
  const [quoteDetail, setQuoteDetail] = useState(null);

  const currentQuoteContacts = useMemo(
    () => contactOptionsByClient[quoteForm.cliente_id] || [],
    [contactOptionsByClient, quoteForm.cliente_id],
  );

  const currentQuoteOpportunities = useMemo(() => {
    if (!quoteForm.cliente_id) {
      return opportunityOptions;
    }
    return opportunityOptions.filter((item) => item.cliente_id === quoteForm.cliente_id);
  }, [opportunityOptions, quoteForm.cliente_id]);

  const filteredQuoteOpportunities = useMemo(() => {
    if (!quoteFilters.cliente_id) {
      return opportunityOptions;
    }
    return opportunityOptions.filter((item) => item.cliente_id === quoteFilters.cliente_id);
  }, [opportunityOptions, quoteFilters.cliente_id]);

  const quoteTotals = useMemo(() => {
    return (quoteForm.items || []).reduce(
      (accumulator, item) => {
        const cantidad = parseQuoteNumber(item.cantidad);
        const precioUnitario = parseQuoteNumber(item.precio_unitario);
        const descuento = parseQuoteNumber(item.descuento);
        const impuestoTasa = parseQuoteNumber(item.impuesto_tasa);
        const bruto = cantidad * precioUnitario;
        const subtotal = Math.max(bruto - descuento, 0);
        const impuesto = subtotal * impuestoTasa;
        return {
          subtotal: accumulator.subtotal + subtotal,
          descuento: accumulator.descuento + descuento,
          impuesto: accumulator.impuesto + impuesto,
          total: accumulator.total + subtotal + impuesto,
        };
      },
      {
        subtotal: 0,
        descuento: 0,
        impuesto: 0,
        total: 0,
      },
    );
  }, [quoteForm.items]);

  async function loadQuotesPage(nextFilters = quoteFilters) {
    const response = await listCrmQuotes({
      token,
      empresaId,
      filters: nextFilters,
    });
    setQuotes(response.items || []);
    setQuoteMeta({
      total: response.total || 0,
      limit: response.limit || nextFilters.limit,
      offset: response.offset || nextFilters.offset,
    });
    return response;
  }

  async function loadQuoteDetail(quoteId) {
    const response = await getCrmQuote({ quoteId, token, empresaId });
    setQuoteDetail(response);
    return response;
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }
      setLoading(true);
      setError("");
      try {
        await loadQuotesPage(defaultQuoteFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar las cotizaciones.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  function resetQuoteForm(nextClientId = "") {
    setQuoteForm({
      ...defaultQuoteForm,
      cliente_id: nextClientId || "",
      items: [createLocalQuoteItem()],
    });
  }

  async function applyQuoteFilters(nextFilters) {
    setQuoteFilters(nextFilters);
    setError("");
    try {
      await loadQuotesPage(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar los filtros de cotizaciones.");
    }
  }

  async function refreshQuotesSection(message = "Cotizaciones actualizadas.") {
    setError("");
    try {
      await loadQuotesPage(quoteFilters);
      setSuccess(message);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron actualizar las cotizaciones.");
    }
  }

  async function openQuoteCreateModal() {
    if (!clientOptions.length) {
      setError("Agrega al menos un cliente antes de crear cotizaciones.");
      return;
    }
    resetQuoteForm();
    setQuoteFormOpen(true);
    setError("");
    setSuccess("");
  }

  async function openQuoteEditModal(quoteId) {
    setSubmitting(true);
    setError("");
    try {
      const response = await getCrmQuote({ quoteId, token, empresaId });
      if (response.cliente_id) {
        await loadClientContactOptions(response.cliente_id, { force: true });
      }
      setQuoteForm(mapQuoteResponseToForm(response));
      setQuoteFormOpen(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar la cotizacion.");
    } finally {
      setSubmitting(false);
    }
  }

  async function openQuoteDetailModal(quoteId) {
    setQuoteDetailOpen(true);
    setQuoteDetail(null);
    setDetailLoading(true);
    setError("");
    try {
      await loadQuoteDetail(quoteId);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle de la cotizacion.");
    } finally {
      setDetailLoading(false);
    }
  }

  function closeQuoteDetailModal() {
    setQuoteDetailOpen(false);
    setQuoteDetail(null);
  }

  function updateQuoteItem(localId, fieldName, value) {
    setQuoteForm((current) => ({
      ...current,
      items: current.items.map((item) => (
        item.local_id === localId
          ? {
              ...item,
              [fieldName]: value,
            }
          : item
      )),
    }));
  }

  function addQuoteItem() {
    setQuoteForm((current) => ({
      ...current,
      items: [...current.items, createLocalQuoteItem()],
    }));
  }

  function removeQuoteItem(localId) {
    setQuoteForm((current) => {
      if (current.items.length <= 1) {
        return current;
      }
      return {
        ...current,
        items: current.items.filter((item) => item.local_id !== localId),
      };
    });
  }

  async function handleQuoteSubmit(event) {
    event.preventDefault();
    const validationMessage = validateQuoteForm(quoteForm);
    if (validationMessage) {
      setError(validationMessage);
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildQuotePayload(quoteForm);
      const targetQuoteId = quoteForm.id;
      const targetClientId = quoteForm.cliente_id;
      const response = quoteForm.id
        ? await updateCrmQuote({ quoteId: quoteForm.id, token, empresaId, payload })
        : await createCrmQuote({ token, empresaId, payload });

      setQuoteFormOpen(false);
      resetQuoteForm();
      await loadQuotesPage(quoteFilters);
      if (targetQuoteId && quoteDetailOpen && quoteDetail?.id === targetQuoteId) {
        await loadQuoteDetail(targetQuoteId);
      }
      if (typeof onQuotesChanged === "function") {
        await onQuotesChanged(response.cliente_id || targetClientId);
      }
      setSuccess(quoteForm.id ? "Cotizacion actualizada correctamente." : "Cotizacion creada correctamente.");
    } catch (requestError) {
      setError(translateQuoteEditError(requestError.message, Boolean(quoteForm.id)));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleQuoteStatusAction(action, quote) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const targetClientId = quote.cliente_id || quote.clienteId || "";
      let response;
      if (action === "send") {
        response = await sendCrmQuote({ quoteId: quote.id, token, empresaId });
      } else if (action === "accept") {
        response = await acceptCrmQuote({ quoteId: quote.id, token, empresaId });
      } else if (action === "reject") {
        response = await rejectCrmQuote({ quoteId: quote.id, token, empresaId });
      } else {
        response = await cancelCrmQuote({ quoteId: quote.id, token, empresaId });
      }

      await loadQuotesPage(quoteFilters);
      if (quoteDetailOpen && quoteDetail?.id === quote.id) {
        await loadQuoteDetail(quote.id);
      }
      if (typeof onQuotesChanged === "function") {
        await onQuotesChanged(response?.cliente_id || targetClientId);
      }

      const successMap = {
        send: "Cotizacion enviada.",
        accept: "Cotizacion aceptada.",
        reject: "Cotizacion rechazada.",
        cancel: "Cotizacion cancelada.",
      };
      setSuccess(successMap[action] || "Cotizacion actualizada.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar la cotizacion.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDownloadQuotePdf(quoteId) {
    setSubmitting(true);
    setError("");
    try {
      await downloadCrmQuotePdf({ quoteId, token, empresaId });
    } catch {
      setError("No se pudo generar el PDF de la cotizacion.");
    } finally {
      setSubmitting(false);
    }
  }

  const quoteDetailFooter = quoteDetail ? (
    <div className="inventory-actions">
      <ActionButton
        disabled={submitting}
        onClick={() => handleDownloadQuotePdf(quoteDetail.id)}
        size="sm"
        type="button"
      >
        Descargar PDF
      </ActionButton>
      <ActionButton onClick={closeQuoteDetailModal} size="sm" type="button">
        Cerrar
      </ActionButton>
      {quoteDetail.estatus === "borrador" ? (
        <>
          <ActionButton
            disabled={submitting}
            icon={<Eye size={16} />}
            onClick={() => openQuoteEditModal(quoteDetail.id)}
            size="sm"
            type="button"
          >
            Editar
          </ActionButton>
          <ActionButton
            disabled={submitting}
            icon={<Send size={16} />}
            onClick={() => handleQuoteStatusAction("send", quoteDetail)}
            size="sm"
            tone="primary"
            type="button"
          >
            Enviar
          </ActionButton>
          <ActionButton
            disabled={submitting}
            icon={<XCircle size={16} />}
            onClick={() => handleQuoteStatusAction("cancel", quoteDetail)}
            size="sm"
            tone="danger"
            type="button"
          >
            Cancelar
          </ActionButton>
        </>
      ) : null}
      {quoteDetail.estatus === "enviada" ? (
        <>
          <ActionButton
            disabled={submitting}
            icon={<CheckCircle2 size={16} />}
            onClick={() => handleQuoteStatusAction("accept", quoteDetail)}
            size="sm"
            tone="primary"
            type="button"
          >
            Aceptar
          </ActionButton>
          <ActionButton
            disabled={submitting}
            icon={<XCircle size={16} />}
            onClick={() => handleQuoteStatusAction("reject", quoteDetail)}
            size="sm"
            tone="danger"
            type="button"
          >
            Rechazar
          </ActionButton>
          <ActionButton
            disabled={submitting}
            onClick={() => handleQuoteStatusAction("cancel", quoteDetail)}
            size="sm"
            tone="danger"
            type="button"
          >
            Cancelar
          </ActionButton>
        </>
      ) : null}
    </div>
  ) : null;

  if (loading) {
    return <div className="screen-center">Cargando cotizaciones...</div>;
  }

  return (
    <div className="crm-view-stack">
      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>Error operativo</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {success ? (
        <div className="inventory-form-note inventory-form-note-success">
          <strong>Operacion completada</strong>
          <p>{success}</p>
        </div>
      ) : null}

      <FilterCard
        actions={(
          <div className="inventory-actions">
            <ActionButton icon={<Plus size={16} />} onClick={openQuoteCreateModal} size="sm" tone="primary" type="button">
              Nueva cotizacion
            </ActionButton>
            <ActionButton onClick={() => applyQuoteFilters({ ...quoteFilters, offset: 0 })} size="sm" tone="primary" type="button">
              Aplicar
            </ActionButton>
            <ActionButton onClick={() => applyQuoteFilters(defaultQuoteFilters)} size="sm" type="button">
              Limpiar
            </ActionButton>
            <ActionButton icon={<RefreshCw size={16} />} onClick={() => refreshQuotesSection()} size="sm" type="button">
              Actualizar
            </ActionButton>
          </div>
        )}
        title="Filtros de cotizaciones"
      >
        <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
          <SearchInput
            hint="Busca por folio, titulo, cliente u oportunidad."
            label="Buscar cotizacion"
            onChange={(event) => setQuoteFilters((current) => ({ ...current, search: event.target.value }))}
            onKeyDown={async (event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                await applyQuoteFilters({ ...quoteFilters, offset: 0 });
              }
            }}
            placeholder="Folio, cliente o oportunidad"
            value={quoteFilters.search}
          />

          <FormGrid>
            <Field label="Estatus">
              <select onChange={(event) => setQuoteFilters((current) => ({ ...current, estatus: event.target.value }))} value={quoteFilters.estatus}>
                <option value="">Todos</option>
                <option value="borrador">Borrador</option>
                <option value="enviada">Enviada</option>
                <option value="aceptada">Aceptada</option>
                <option value="rechazada">Rechazada</option>
                <option value="cancelada">Cancelada</option>
                <option value="vencida">Vencida</option>
              </select>
            </Field>
            <Field label="Cliente">
              <select
                onChange={(event) => setQuoteFilters((current) => ({
                  ...current,
                  cliente_id: event.target.value,
                  oportunidad_id: "",
                }))}
                value={quoteFilters.cliente_id}
              >
                <option value="">Todos</option>
                {clientOptions.map((client) => (
                  <option key={client.id} value={client.id}>
                    {safeDisplayText(client.nombre_comercial, "Sin cliente")}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Oportunidad">
              <select
                onChange={(event) => setQuoteFilters((current) => ({ ...current, oportunidad_id: event.target.value }))}
                value={quoteFilters.oportunidad_id}
              >
                <option value="">Todas</option>
                {filteredQuoteOpportunities.map((opportunity) => (
                  <option key={opportunity.id} value={opportunity.id}>
                    {safeDisplayText(opportunity.titulo, "Sin oportunidad")}
                  </option>
                ))}
              </select>
            </Field>
          </FormGrid>
        </div>
      </FilterCard>

      <DataCard
        actions={<ResultMeta label="cotizaciones" loaded={quotes.length} total={quoteMeta.total} />}
        subtitle="Cotizaciones comerciales ligadas a clientes y oportunidades del CRM."
        title="Cotizaciones"
      >
        {quotes.length === 0 ? (
          <EmptyState note="No hay cotizaciones registradas." title="Sin cotizaciones" />
        ) : (
          <>
            <DataTable
              columns={[
                { key: "folio", label: "Folio" },
                { key: "titulo", label: "Titulo" },
                { key: "cliente", label: "Cliente" },
                { key: "oportunidad", label: "Oportunidad" },
                { key: "estatus", label: "Estatus" },
                { key: "fechas", label: "Fechas" },
                { key: "total", label: "Total" },
                { key: "acciones", label: "Acciones" },
              ]}
            >
              <tbody>
                {quotes.map((quote) => (
                  <tr key={quote.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(quote.folio)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(quote.moneda, "MXN")}</div>
                    </td>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(quote.titulo)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(quote.descripcion, "Sin descripcion")}</div>
                    </td>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(quote.cliente_nombre_comercial, "Sin cliente")}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(quote.contacto_nombre, "Sin contacto")}</div>
                    </td>
                    <td>{safeDisplayText(quote.oportunidad_titulo, "Sin oportunidad")}</td>
                    <td>
                      <StatusBadge tone={quoteStatusTone(quote.estatus)}>
                        {quoteStatusLabel(quote.estatus)}
                      </StatusBadge>
                    </td>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(quote.fecha_emision ? formatDate(quote.fecha_emision) : "Sin emision")}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(quote.fecha_vencimiento ? formatDate(quote.fecha_vencimiento) : "Sin vencimiento")}</div>
                    </td>
                    <td>{formatMoney(quote.total)}</td>
                    <td className="inventory-row-actions">
                      <button className="link-button" onClick={() => openQuoteDetailModal(quote.id)} type="button">
                        Ver detalle
                      </button>
                      {quote.estatus === "borrador" ? (
                        <button className="link-button" onClick={() => openQuoteEditModal(quote.id)} type="button">
                          Editar
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>

            <PaginationControls
              meta={quoteMeta}
              onNext={() => applyQuoteFilters({ ...quoteFilters, offset: quoteMeta.offset + quoteMeta.limit })}
              onPrevious={() => applyQuoteFilters({ ...quoteFilters, offset: Math.max(0, quoteMeta.offset - quoteMeta.limit) })}
            />
          </>
        )}
      </DataCard>

      <ModalShell
        footer={(
          <div className="inventory-actions">
            <ActionButton onClick={() => setQuoteFormOpen(false)} size="sm" type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="crm-quote-form" size="sm" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Guardar cotizacion"}
            </ActionButton>
          </div>
        )}
        onClose={() => setQuoteFormOpen(false)}
        open={quoteFormOpen}
        size="xl"
        subtitle="Arma las partidas y captura condiciones comerciales. El backend recalcula los totales finales."
        title={quoteForm.id ? "Editar cotizacion" : "Nueva cotizacion"}
      >
        <form className="inventory-modal-form" id="crm-quote-form" onSubmit={handleQuoteSubmit}>
          <section className="inventory-form-section">
            <SectionTitle title="Datos generales" />
            <FormGrid>
              <Field label="Cliente CRM">
                <select
                  onChange={async (event) => {
                    const nextClientId = event.target.value;
                    setQuoteForm((current) => ({
                      ...current,
                      cliente_id: nextClientId,
                      contacto_id: "",
                      oportunidad_id: "",
                    }));
                    if (nextClientId) {
                      await loadClientContactOptions(nextClientId, { force: true });
                    }
                  }}
                  value={quoteForm.cliente_id}
                >
                  <option value="">Selecciona un cliente</option>
                  {clientOptions.map((client) => (
                    <option key={client.id} value={client.id}>
                      {safeDisplayText(client.nombre_comercial, "Sin cliente")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Contacto">
                <select onChange={(event) => setQuoteForm((current) => ({ ...current, contacto_id: event.target.value }))} value={quoteForm.contacto_id}>
                  <option value="">Sin contacto</option>
                  {currentQuoteContacts.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {safeDisplayText(contact.nombre, "Sin contacto")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Oportunidad">
                <select
                  onChange={(event) => {
                    const nextOpportunityId = event.target.value;
                    const selectedOpportunity = currentQuoteOpportunities.find((item) => item.id === nextOpportunityId);
                    setQuoteForm((current) => ({
                      ...current,
                      oportunidad_id: nextOpportunityId,
                      contacto_id: selectedOpportunity?.contacto_id || current.contacto_id,
                    }));
                  }}
                  value={quoteForm.oportunidad_id}
                >
                  <option value="">Sin oportunidad</option>
                  {currentQuoteOpportunities.map((opportunity) => (
                    <option key={opportunity.id} value={opportunity.id}>
                      {safeDisplayText(opportunity.titulo, "Sin oportunidad")}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Titulo" span={2}>
                <input
                  onChange={(event) => setQuoteForm((current) => ({ ...current, titulo: event.target.value }))}
                  required
                  type="text"
                  value={quoteForm.titulo}
                />
              </Field>
              <Field label="Descripcion" span={2}>
                <textarea
                  onChange={(event) => setQuoteForm((current) => ({ ...current, descripcion: event.target.value }))}
                  rows={3}
                  value={quoteForm.descripcion}
                />
              </Field>
              <Field label="Fecha vencimiento">
                <input
                  onChange={(event) => setQuoteForm((current) => ({ ...current, fecha_vencimiento: event.target.value }))}
                  type="date"
                  value={quoteForm.fecha_vencimiento}
                />
              </Field>
              <Field label="Condiciones de pago" span={2}>
                <textarea
                  onChange={(event) => setQuoteForm((current) => ({ ...current, condiciones_pago: event.target.value }))}
                  rows={3}
                  value={quoteForm.condiciones_pago}
                />
              </Field>
              <Field label="Notas" span={2}>
                <textarea
                  onChange={(event) => setQuoteForm((current) => ({ ...current, notas: event.target.value }))}
                  rows={3}
                  value={quoteForm.notas}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle
              actions={(
                <ActionButton icon={<Plus size={16} />} onClick={addQuoteItem} size="sm" type="button">
                  Agregar partida
                </ActionButton>
              )}
              title="Partidas"
            />
            <div className="crm-quote-item-list">
              {quoteForm.items.map((item, index) => (
                <article className="crm-quote-item-card" key={item.local_id}>
                  <div className="crm-quote-item-card-head">
                    <strong>Partida {index + 1}</strong>
                    <ActionButton
                      disabled={quoteForm.items.length <= 1}
                      onClick={() => removeQuoteItem(item.local_id)}
                      size="sm"
                      tone="danger"
                      type="button"
                    >
                      Quitar
                    </ActionButton>
                  </div>
                  <FormGrid>
                    <Field label="Descripcion" span={2}>
                      <input
                        onChange={(event) => updateQuoteItem(item.local_id, "descripcion", event.target.value)}
                        type="text"
                        value={item.descripcion}
                      />
                    </Field>
                    <Field label="Cantidad">
                      <input
                        onChange={(event) => updateQuoteItem(item.local_id, "cantidad", normalizeDecimalInput(event.target.value))}
                        type="text"
                        value={item.cantidad}
                      />
                    </Field>
                    <Field label="Precio unitario">
                      <input
                        onChange={(event) => updateQuoteItem(item.local_id, "precio_unitario", normalizeDecimalInput(event.target.value))}
                        type="text"
                        value={item.precio_unitario}
                      />
                    </Field>
                    <Field label="Descuento">
                      <input
                        onChange={(event) => updateQuoteItem(item.local_id, "descuento", normalizeDecimalInput(event.target.value))}
                        type="text"
                        value={item.descuento}
                      />
                    </Field>
                    <Field label="Impuesto tasa">
                      <input
                        onChange={(event) => updateQuoteItem(item.local_id, "impuesto_tasa", normalizeDecimalInput(event.target.value))}
                        placeholder="0.16"
                        type="text"
                        value={item.impuesto_tasa}
                      />
                    </Field>
                  </FormGrid>
                </article>
              ))}
            </div>
          </section>

          <section className="inventory-form-section">
            <SectionTitle title="Totales estimados" />
            <div className="crm-quote-totals-grid">
              <article className="crm-stage-summary-card tone-info">
                <div>
                  <strong>Subtotal</strong>
                  <span>Antes de impuestos</span>
                </div>
                <b>{formatMoney(quoteTotals.subtotal)}</b>
              </article>
              <article className="crm-stage-summary-card tone-warning">
                <div>
                  <strong>Descuento</strong>
                  <span>Descuento total capturado</span>
                </div>
                <b>{formatMoney(quoteTotals.descuento)}</b>
              </article>
              <article className="crm-stage-summary-card tone-info">
                <div>
                  <strong>Impuesto</strong>
                  <span>Calculado en pantalla</span>
                </div>
                <b>{formatMoney(quoteTotals.impuesto)}</b>
              </article>
              <article className="crm-stage-summary-card tone-success">
                <div>
                  <strong>Total</strong>
                  <span>El backend confirmara el total final</span>
                </div>
                <b>{formatMoney(quoteTotals.total)}</b>
              </article>
            </div>
          </section>
        </form>
      </ModalShell>

      <ModalShell
        footer={quoteDetailFooter}
        onClose={closeQuoteDetailModal}
        open={quoteDetailOpen}
        size="xl"
        subtitle="Detalle comercial de la cotizacion con descarga PDF y acciones segun el estatus."
        title="Detalle de cotizacion"
      >
        {detailLoading ? (
          <div className="screen-center">Cargando detalle...</div>
        ) : quoteDetail ? (
          <div className="inventory-modal-form">
            <section className="inventory-form-section">
              <SectionTitle title={safeDisplayText(quoteDetail.folio, "Cotizacion")} />
              <div className="inventory-detail-grid">
                <p><strong>Estatus:</strong> <StatusBadge tone={quoteStatusTone(quoteDetail.estatus)}>{quoteStatusLabel(quoteDetail.estatus)}</StatusBadge></p>
                <p><strong>Cliente:</strong> {safeDisplayText(quoteDetail.cliente_nombre_comercial, "Sin cliente")}</p>
                <p><strong>Contacto:</strong> {safeDisplayText(quoteDetail.contacto_nombre, "Sin contacto")}</p>
                <p><strong>Oportunidad:</strong> {safeDisplayText(quoteDetail.oportunidad_titulo, "Sin oportunidad")}</p>
                <p><strong>Fecha emision:</strong> {safeDisplayText(quoteDetail.fecha_emision ? formatDate(quoteDetail.fecha_emision) : "Sin emision")}</p>
                <p><strong>Fecha vencimiento:</strong> {safeDisplayText(quoteDetail.fecha_vencimiento ? formatDate(quoteDetail.fecha_vencimiento) : "Sin vencimiento")}</p>
                <p><strong>Moneda:</strong> {safeDisplayText(quoteDetail.moneda, "MXN")}</p>
                <p><strong>Titulo:</strong> {safeDisplayText(quoteDetail.titulo, "Sin titulo")}</p>
                <p className="inventory-form-span-2"><strong>Descripcion:</strong> {safeDisplayText(quoteDetail.descripcion, "Sin descripcion")}</p>
                <p className="inventory-form-span-2"><strong>Condiciones de pago:</strong> {safeDisplayText(quoteDetail.condiciones_pago, "Sin condiciones de pago")}</p>
                <p className="inventory-form-span-2"><strong>Notas:</strong> {safeDisplayText(quoteDetail.notas, "Sin notas")}</p>
              </div>
            </section>

            <DataCard subtitle="Partidas registradas en la cotizacion." title="Partidas">
              {quoteDetail.items?.length ? (
                <DataTable
                  columns={[
                    { key: "descripcion", label: "Descripcion" },
                    { key: "cantidad", label: "Cantidad" },
                    { key: "precio", label: "Precio unitario" },
                    { key: "descuento", label: "Descuento" },
                    { key: "impuesto", label: "Impuesto" },
                    { key: "total", label: "Total" },
                  ]}
                >
                  <tbody>
                    {quoteDetail.items.map((item) => (
                      <tr key={item.id}>
                        <td>{safeDisplayText(item.descripcion)}</td>
                        <td>{formatNumber(item.cantidad)}</td>
                        <td>{formatMoney(item.precio_unitario)}</td>
                        <td>{formatMoney(item.descuento)}</td>
                        <td>{formatMoney(item.impuesto)}</td>
                        <td>{formatMoney(item.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              ) : (
                <EmptyState compact note="La cotizacion no tiene partidas registradas." title="Sin partidas" />
              )}
            </DataCard>

            <DataCard subtitle="Totales confirmados por backend." title="Totales">
              <div className="crm-quote-totals-grid">
                <article className="crm-stage-summary-card tone-info">
                  <div>
                    <strong>Subtotal</strong>
                    <span>Subtotal bruto neto</span>
                  </div>
                  <b>{formatMoney(quoteDetail.subtotal)}</b>
                </article>
                <article className="crm-stage-summary-card tone-warning">
                  <div>
                    <strong>Descuento</strong>
                    <span>Descuento total</span>
                  </div>
                  <b>{formatMoney(quoteDetail.descuento_total)}</b>
                </article>
                <article className="crm-stage-summary-card tone-info">
                  <div>
                    <strong>Impuesto</strong>
                    <span>Impuesto total</span>
                  </div>
                  <b>{formatMoney(quoteDetail.impuesto_total)}</b>
                </article>
                <article className="crm-stage-summary-card tone-success">
                  <div>
                    <strong>Total</strong>
                    <span>Total final de la cotizacion</span>
                  </div>
                  <b>{formatMoney(quoteDetail.total)}</b>
                </article>
              </div>
            </DataCard>
          </div>
        ) : (
          <EmptyState note="No se encontro informacion de la cotizacion." title="Sin detalle disponible" />
        )}
      </ModalShell>
    </div>
  );
}
