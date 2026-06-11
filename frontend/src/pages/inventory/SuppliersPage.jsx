import { useEffect, useMemo, useState } from "react";
import {
  Banknote,
  Building2,
  Clock3,
  PackageSearch,
  ShoppingCart,
  Store,
} from "lucide-react";

import { useAuth } from "../../auth/AuthContext";
import {
  createSupplier,
  getSupplierMaterials,
  getSupplierPurchaseOrders,
  getSupplierReceipts,
  getSupplierSummary,
  getSuppliers,
  updateSupplier,
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
  MetricCard,
  ModalShell,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  formatDateTime,
  formatMoney,
  formatNumber,
  parseBooleanFilter,
  safeDisplayText,
} from "./shared";


const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const RFC_REGEX = /^([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}|XAXX010101000)$/i;
const POSTAL_CODE_REGEX = /^\d{5}$/;

const defaultFilters = {
  q: "",
  activo: "true",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultForm = {
  id: "",
  nombre_comercial: "",
  razon_social: "",
  rfc: "",
  activo: true,
  contacto_principal: "",
  email: "",
  telefono: "",
  sitio_web: "",
  direccion: "",
  ciudad: "",
  estado: "",
  pais: "",
  codigo_postal: "",
  telefono_contacto: "",
  email_contacto: "",
  moneda_preferida: "",
  condiciones_pago: "",
  dias_credito: "0",
  lead_time_dias: "0",
  metodo_pago_preferido: "",
  banco: "",
  cuenta_bancaria: "",
  clabe: "",
  notas: "",
};


function normalizeOptionalText(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed : null;
}


function normalizeIntegerInput(value) {
  return String(value ?? "").replace(/[^\d]/g, "");
}


function supplierDisplayName(supplier) {
  return supplier?.nombre_comercial || supplier?.nombre || supplier?.razon_social || "Sin nombre";
}


function supplierEmail(supplier) {
  return supplier?.email || supplier?.correo || supplier?.email_contacto || "";
}


function supplierPrimaryContact(supplier) {
  return supplier?.contacto_principal || supplier?.contacto_nombre || "";
}


function supplierPrimaryPhone(supplier) {
  return supplier?.telefono_contacto || supplier?.telefono || "";
}


function supplierAddress(supplier) {
  const parts = [
    supplier?.direccion,
    supplier?.ciudad,
    supplier?.estado,
    supplier?.codigo_postal,
    supplier?.pais,
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : "Sin direccion registrada";
}


function receiptItemsPreview(receipt) {
  const items = Array.isArray(receipt?.items) ? receipt.items : [];
  if (!items.length) {
    return "Sin partidas";
  }
  const names = items
    .slice(0, 2)
    .map((item) => item.material_nombre)
    .filter(Boolean);
  if (!names.length) {
    return `${formatNumber(items.length)} materiales`;
  }
  return items.length > 2 ? `${names.join(", ")} +${items.length - 2}` : names.join(", ");
}


function validateSupplierForm(form) {
  if (!String(form.nombre_comercial ?? "").trim()) {
    return "Captura el nombre comercial del proveedor.";
  }

  if (normalizeOptionalText(form.email) && !EMAIL_REGEX.test(String(form.email).trim())) {
    return "Ingresa un email valido.";
  }

  if (normalizeOptionalText(form.email_contacto) && !EMAIL_REGEX.test(String(form.email_contacto).trim())) {
    return "Ingresa un email valido.";
  }

  if (normalizeOptionalText(form.rfc) && !RFC_REGEX.test(String(form.rfc).trim().toUpperCase())) {
    return "Ingresa un RFC valido.";
  }

  if (normalizeOptionalText(form.codigo_postal) && !POSTAL_CODE_REGEX.test(String(form.codigo_postal).trim())) {
    return "Ingresa un codigo postal valido.";
  }

  const creditDays = Number(form.dias_credito || 0);
  if (Number.isNaN(creditDays) || creditDays < 0) {
    return "Los dias de credito no pueden ser negativos.";
  }

  const leadTimeDays = Number(form.lead_time_dias || 0);
  if (Number.isNaN(leadTimeDays) || leadTimeDays < 0) {
    return "El lead time no puede ser negativo.";
  }

  return "";
}


function buildSupplierPayload(form) {
  const nombreComercial = String(form.nombre_comercial ?? "").trim();
  const contactoPrincipal = normalizeOptionalText(form.contacto_principal);
  const email = normalizeOptionalText(form.email);

  return {
    nombre: nombreComercial,
    nombre_comercial: nombreComercial,
    razon_social: normalizeOptionalText(form.razon_social),
    rfc: normalizeOptionalText(form.rfc)?.toUpperCase() || null,
    contacto_nombre: contactoPrincipal,
    contacto_principal: contactoPrincipal,
    correo: email,
    email,
    telefono: normalizeOptionalText(form.telefono),
    sitio_web: normalizeOptionalText(form.sitio_web),
    direccion: normalizeOptionalText(form.direccion),
    ciudad: normalizeOptionalText(form.ciudad),
    estado: normalizeOptionalText(form.estado),
    pais: normalizeOptionalText(form.pais),
    codigo_postal: normalizeOptionalText(form.codigo_postal),
    telefono_contacto: normalizeOptionalText(form.telefono_contacto),
    email_contacto: normalizeOptionalText(form.email_contacto),
    moneda_preferida: normalizeOptionalText(form.moneda_preferida),
    condiciones_pago: normalizeOptionalText(form.condiciones_pago),
    dias_credito: Number(form.dias_credito || 0),
    lead_time_dias: Number(form.lead_time_dias || 0),
    metodo_pago_preferido: normalizeOptionalText(form.metodo_pago_preferido),
    banco: normalizeOptionalText(form.banco),
    cuenta_bancaria: normalizeOptionalText(form.cuenta_bancaria),
    clabe: normalizeOptionalText(form.clabe),
    notas: normalizeOptionalText(form.notas),
    activo: Boolean(form.activo),
  };
}


export default function SuppliersPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [suppliers, setSuppliers] = useState([]);
  const [supplierSummaries, setSupplierSummaries] = useState({});
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [modalOpen, setModalOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [form, setForm] = useState(defaultForm);
  const [detailSupplierId, setDetailSupplierId] = useState("");
  const [detailSummary, setDetailSummary] = useState(null);
  const [detailOrders, setDetailOrders] = useState([]);
  const [detailReceipts, setDetailReceipts] = useState([]);
  const [detailMaterials, setDetailMaterials] = useState([]);

  const detailSupplier = useMemo(() => {
    return (
      detailSummary?.proveedor ||
      suppliers.find((supplier) => supplier.id === detailSupplierId) ||
      null
    );
  }, [detailSummary, detailSupplierId, suppliers]);

  const kpis = useMemo(() => {
    return suppliers.reduce(
      (accumulator, supplier) => {
        const summary = supplierSummaries[supplier.id];
        if (supplier.activo) {
          accumulator.activos += 1;
        }
        if (summary?.ordenes_abiertas) {
          accumulator.conOrdenesAbiertas += 1;
        }
        accumulator.pendiente += Number(summary?.monto_pendiente_por_recibir || 0);
        accumulator.totalComprado += Number(summary?.monto_total_comprado || 0);
        return accumulator;
      },
      {
        activos: 0,
        conOrdenesAbiertas: 0,
        pendiente: 0,
        totalComprado: 0,
      },
    );
  }, [supplierSummaries, suppliers]);

  async function loadSupplierSummarySnapshot(items) {
    if (!items.length) {
      setSupplierSummaries({});
      return;
    }

    const results = await Promise.allSettled(
      items.map((supplier) =>
        getSupplierSummary({
          supplierId: supplier.id,
          token,
          empresaId,
        }),
      ),
    );

    const nextSummaries = {};
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        nextSummaries[items[index].id] = result.value;
      }
    });
    setSupplierSummaries(nextSummaries);
  }

  async function loadSuppliersPage(nextFilters = filters) {
    const response = await getSuppliers({
      token,
      empresaId,
      filters: {
        ...nextFilters,
        activo: parseBooleanFilter(nextFilters.activo),
      },
    });
    setSuppliers(response.items);
    setMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    await loadSupplierSummarySnapshot(response.items);
  }

  async function loadSupplierDetailBundle(supplierId) {
    const [summaryResponse, ordersResponse, receiptsResponse, materialsResponse] = await Promise.all([
      getSupplierSummary({ supplierId, token, empresaId }),
      getSupplierPurchaseOrders({
        supplierId,
        token,
        empresaId,
        filters: { limit: 5, offset: 0 },
      }),
      getSupplierReceipts({
        supplierId,
        token,
        empresaId,
        filters: { limit: 5, offset: 0 },
      }),
      getSupplierMaterials({
        supplierId,
        token,
        empresaId,
        filters: { limit: 8, offset: 0 },
      }),
    ]);

    setDetailSummary(summaryResponse);
    setDetailOrders(ordersResponse.items || []);
    setDetailReceipts(receiptsResponse.items || []);
    setDetailMaterials(materialsResponse.items || []);
    setSupplierSummaries((current) => ({
      ...current,
      [supplierId]: summaryResponse,
    }));
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        await loadSuppliersPage(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los proveedores.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  function resetForm() {
    setForm(defaultForm);
  }

  function openCreateModal() {
    resetForm();
    setError("");
    setSuccess("");
    setModalOpen(true);
  }

  function openEditModal(supplier) {
    setForm({
      id: supplier.id,
      nombre_comercial: supplier.nombre_comercial || supplier.nombre || "",
      razon_social: supplier.razon_social || "",
      rfc: supplier.rfc || "",
      activo: supplier.activo,
      contacto_principal: supplier.contacto_principal || supplier.contacto_nombre || "",
      email: supplier.email || supplier.correo || "",
      telefono: supplier.telefono || "",
      sitio_web: supplier.sitio_web || "",
      direccion: supplier.direccion || "",
      ciudad: supplier.ciudad || "",
      estado: supplier.estado || "",
      pais: supplier.pais || "",
      codigo_postal: supplier.codigo_postal || "",
      telefono_contacto: supplier.telefono_contacto || "",
      email_contacto: supplier.email_contacto || "",
      moneda_preferida: supplier.moneda_preferida || "",
      condiciones_pago: supplier.condiciones_pago || "",
      dias_credito: String(supplier.dias_credito ?? 0),
      lead_time_dias: String(supplier.lead_time_dias ?? 0),
      metodo_pago_preferido: supplier.metodo_pago_preferido || "",
      banco: supplier.banco || "",
      cuenta_bancaria: supplier.cuenta_bancaria || "",
      clabe: supplier.clabe || "",
      notas: supplier.notas || "",
    });
    setError("");
    setSuccess("");
    setModalOpen(true);
  }

  async function openDetailModal(supplierId) {
    setDetailSupplierId(supplierId);
    setDetailSummary(supplierSummaries[supplierId] || null);
    setDetailOrders([]);
    setDetailReceipts([]);
    setDetailMaterials([]);
    setDetailOpen(true);
    setDetailLoading(true);
    setError("");

    try {
      await loadSupplierDetailBundle(supplierId);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle del proveedor.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const validationMessage = validateSupplierForm(form);
      if (validationMessage) {
        setError(validationMessage);
        return;
      }

      const payload = buildSupplierPayload(form);
      let savedSupplier = null;

      if (form.id) {
        savedSupplier = await updateSupplier({ supplierId: form.id, token, empresaId, payload });
        setSuccess("Proveedor actualizado correctamente.");
      } else {
        savedSupplier = await createSupplier({ token, empresaId, payload });
        setSuccess("Proveedor creado correctamente.");
      }

      setModalOpen(false);
      resetForm();
      await loadSuppliersPage(filters);
      if (detailOpen && detailSupplierId && savedSupplier?.id === detailSupplierId) {
        await loadSupplierDetailBundle(detailSupplierId);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el proveedor.");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleSupplierStatus(supplier) {
    setError("");
    setSuccess("");
    try {
      await updateSupplier({
        supplierId: supplier.id,
        token,
        empresaId,
        payload: { activo: !supplier.activo },
      });
      setSuccess(supplier.activo ? "Proveedor desactivado." : "Proveedor reactivado.");
      await loadSuppliersPage(filters);
      if (detailOpen && detailSupplierId === supplier.id) {
        await loadSupplierDetailBundle(supplier.id);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el proveedor.");
    }
  }

  async function applyListFilters(nextFilters, fallbackMessage) {
    setFilters(nextFilters);
    setError("");
    try {
      await loadSuppliersPage(nextFilters);
    } catch (requestError) {
      setError(requestError.message || fallbackMessage);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando proveedores...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        actions={
          <ActionButton onClick={openCreateModal} size="sm" tone="primary" type="button">
            Agregar proveedor
          </ActionButton>
        }
        eyebrow="Compras"
        subtitle="Perfil comercial del proveedor conectado con ordenes de compra, recepciones y condiciones operativas."
        title="Proveedores"
      />

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard
          icon={<Store size={16} />}
          label="Proveedores activos"
          meta="Pagina actual segun filtros"
          tone="success"
          value={formatNumber(kpis.activos)}
        />
        <MetricCard
          icon={<ShoppingCart size={16} />}
          label="Con ordenes abiertas"
          meta="Borrador, emitida o parcial"
          tone="warning"
          value={formatNumber(kpis.conOrdenesAbiertas)}
        />
        <MetricCard
          icon={<Clock3 size={16} />}
          label="Pendiente por recibir"
          meta="Monto estimado"
          tone="warning"
          value={formatMoney(kpis.pendiente)}
        />
        <MetricCard
          icon={<Banknote size={16} />}
          label="Total comprado"
          meta="Acumulado visible"
          tone="info"
          value={formatMoney(kpis.totalComprado)}
        />
      </section>

      <FilterCard>
        <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
          <SearchInput
            hint="Busca por proveedor, RFC, contacto, email o telefono."
            label="Buscar proveedor"
            onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
            onKeyDown={async (event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                await applyListFilters({ ...filters, offset: 0 }, "No se pudieron aplicar los filtros.");
              }
            }}
            placeholder="Proveedor, RFC, contacto o email"
            value={filters.q}
          />

          <FormGrid>
            <Field label="Estatus">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, activo: event.target.value }))}
                value={filters.activo}
              >
                <option value="true">Activos</option>
                <option value="false">Inactivos</option>
                <option value="">Todos</option>
              </select>
            </Field>
          </FormGrid>

          <div className="inventory-actions">
            <ActionButton
              onClick={() => applyListFilters({ ...filters, offset: 0 }, "No se pudieron aplicar los filtros.")}
              size="sm"
              tone="primary"
              type="button"
            >
              Buscar
            </ActionButton>
            <ActionButton
              onClick={() => applyListFilters(defaultFilters, "No se pudieron reiniciar los filtros.")}
              size="sm"
              type="button"
            >
              Limpiar
            </ActionButton>
            <ActionButton
              onClick={() => applyListFilters(filters, "No se pudo actualizar el listado.")}
              size="sm"
              type="button"
            >
              Actualizar
            </ActionButton>
          </div>
        </div>
      </FilterCard>

      <DataCard
        actions={<ResultMeta label="proveedores" loaded={suppliers.length} total={meta.total} />}
        subtitle="Condiciones comerciales, ordenes abiertas y pendiente por recibir por proveedor."
        title="Directorio de proveedores"
      >
        {suppliers.length === 0 ? (
          <EmptyState
            note="Agrega el primer proveedor para comenzar el flujo de compras."
            title="No hay proveedores registrados"
          />
        ) : (
          <>
            <DataTable
              columns={[
                { key: "proveedor", label: "Proveedor" },
                { key: "rfc", label: "RFC" },
                { key: "contacto", label: "Contacto" },
                { key: "condiciones", label: "Condiciones de pago" },
                { key: "ordenes", label: "Ordenes abiertas" },
                { key: "pendiente", label: "Pendiente por recibir" },
                { key: "estatus", label: "Activo" },
                { key: "acciones", label: "Acciones" },
              ]}
            >
              <tbody>
                {suppliers.map((supplier) => {
                  const summary = supplierSummaries[supplier.id];
                  return (
                    <tr key={supplier.id}>
                      <td>
                        <div className="inventory-cell-main">{supplierDisplayName(supplier)}</div>
                        <div className="inventory-cell-sub">{supplier.razon_social || supplierAddress(supplier)}</div>
                      </td>
                      <td>{safeDisplayText(supplier.rfc, "Sin RFC")}</td>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(supplierPrimaryContact(supplier), "Sin contacto")}</div>
                        <div className="inventory-cell-sub">
                          {safeDisplayText(supplierEmail(supplier), "Sin email")} · {safeDisplayText(supplierPrimaryPhone(supplier), "Sin telefono")}
                        </div>
                      </td>
                      <td>
                        <div className="inventory-cell-main">
                          {safeDisplayText(supplier.condiciones_pago, "Sin definir")}
                        </div>
                        <div className="inventory-cell-sub">
                          {Number(supplier.dias_credito || 0) > 0
                            ? `${formatNumber(supplier.dias_credito)} dias de credito`
                            : "Sin credito"}
                          {supplier.moneda_preferida ? ` · ${supplier.moneda_preferida}` : ""}
                        </div>
                      </td>
                      <td>
                        <div className="inventory-cell-main">
                          {summary ? formatNumber(summary.ordenes_abiertas) : "—"}
                        </div>
                        <div className="inventory-cell-sub">
                          {summary ? `${formatNumber(summary.ordenes_totales)} ordenes totales` : "Sin resumen"}
                        </div>
                      </td>
                      <td>
                        <div className="inventory-cell-main">
                          {summary ? formatMoney(summary.monto_pendiente_por_recibir) : "—"}
                        </div>
                        <div className="inventory-cell-sub">
                          {summary ? `${formatNumber(summary.recepciones_totales)} recepciones` : "Sin resumen"}
                        </div>
                      </td>
                      <td>
                        <StatusBadge tone={supplier.activo ? "success" : "neutral"}>
                          {supplier.activo ? "Activo" : "Inactivo"}
                        </StatusBadge>
                      </td>
                      <td className="inventory-row-actions">
                        <button className="link-button" onClick={() => openDetailModal(supplier.id)} type="button">
                          Ver detalle
                        </button>
                        <button className="link-button" onClick={() => openEditModal(supplier)} type="button">
                          Editar
                        </button>
                        <button className="link-button" onClick={() => toggleSupplierStatus(supplier)} type="button">
                          {supplier.activo ? "Desactivar" : "Reactivar"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>

            <PaginationControls
              meta={meta}
              onNext={() =>
                applyListFilters(
                  { ...filters, offset: meta.offset + meta.limit },
                  "No se pudo cambiar la pagina.",
                )
              }
              onPrevious={() =>
                applyListFilters(
                  { ...filters, offset: Math.max(0, meta.offset - meta.limit) },
                  "No se pudo cambiar la pagina.",
                )
              }
            />
          </>
        )}
      </DataCard>

      <ModalShell
        onClose={() => setModalOpen(false)}
        open={modalOpen}
        size="xl"
        subtitle="Datos operativos y comerciales del proveedor sin mezclar cuentas por pagar."
        title={form.id ? "Editar proveedor" : "Nuevo proveedor"}
      >
        <form className="inventory-modal-form" onSubmit={handleSubmit}>
          <section className="inventory-form-section">
            <SectionTitle subtitle="Nombre comercial, razon social y RFC para compras." title="Datos generales" />
            <FormGrid>
              <Field label="Nombre comercial">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, nombre_comercial: event.target.value }))}
                  required
                  type="text"
                  value={form.nombre_comercial}
                />
              </Field>

              <Field label="Razon social">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, razon_social: event.target.value }))}
                  type="text"
                  value={form.razon_social}
                />
              </Field>

              <Field label="RFC">
                <input
                  onChange={(event) =>
                    setForm((current) => ({ ...current, rfc: event.target.value.toUpperCase() }))
                  }
                  type="text"
                  value={form.rfc}
                />
              </Field>

              <Field>
                <label className="inventory-inline-checkbox">
                  <input
                    checked={form.activo}
                    onChange={(event) => setForm((current) => ({ ...current, activo: event.target.checked }))}
                    type="checkbox"
                  />
                  Proveedor activo
                </label>
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Canales de contacto principales para el proveedor." title="Contacto" />
            <FormGrid>
              <Field label="Contacto principal">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, contacto_principal: event.target.value }))}
                  type="text"
                  value={form.contacto_principal}
                />
              </Field>

              <Field label="Email">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                  type="email"
                  value={form.email}
                />
              </Field>

              <Field label="Telefono">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, telefono: event.target.value }))}
                  type="text"
                  value={form.telefono}
                />
              </Field>

              <Field label="Sitio web">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, sitio_web: event.target.value }))}
                  placeholder="https://proveedor.com"
                  type="text"
                  value={form.sitio_web}
                />
              </Field>

              <Field label="Telefono de contacto">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, telefono_contacto: event.target.value }))}
                  type="text"
                  value={form.telefono_contacto}
                />
              </Field>

              <Field label="Email de contacto">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, email_contacto: event.target.value }))}
                  type="email"
                  value={form.email_contacto}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Direccion para ordenes y recepciones." title="Direccion" />
            <FormGrid>
              <Field label="Direccion" span={2}>
                <textarea
                  onChange={(event) => setForm((current) => ({ ...current, direccion: event.target.value }))}
                  rows={3}
                  value={form.direccion}
                />
              </Field>

              <Field label="Ciudad">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, ciudad: event.target.value }))}
                  type="text"
                  value={form.ciudad}
                />
              </Field>

              <Field label="Estado">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, estado: event.target.value }))}
                  type="text"
                  value={form.estado}
                />
              </Field>

              <Field label="Pais">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, pais: event.target.value }))}
                  type="text"
                  value={form.pais}
                />
              </Field>

              <Field label="Codigo postal">
                <input
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      codigo_postal: normalizeIntegerInput(event.target.value).slice(0, 5),
                    }))
                  }
                  inputMode="numeric"
                  type="text"
                  value={form.codigo_postal}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Moneda, credito y preferencias de pago." title="Condiciones comerciales" />
            <FormGrid>
              <Field label="Moneda preferida">
                <input
                  onChange={(event) =>
                    setForm((current) => ({ ...current, moneda_preferida: event.target.value.toUpperCase() }))
                  }
                  placeholder="MXN"
                  type="text"
                  value={form.moneda_preferida}
                />
              </Field>

              <Field label="Metodo de pago preferido">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, metodo_pago_preferido: event.target.value }))}
                  placeholder="Transferencia, SPEI, cheque"
                  type="text"
                  value={form.metodo_pago_preferido}
                />
              </Field>

              <Field label="Dias de credito">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      dias_credito: normalizeIntegerInput(event.target.value),
                    }))
                  }
                  step="1"
                  type="number"
                  value={form.dias_credito}
                />
              </Field>

              <Field label="Lead time (dias)">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      lead_time_dias: normalizeIntegerInput(event.target.value),
                    }))
                  }
                  step="1"
                  type="number"
                  value={form.lead_time_dias}
                />
              </Field>

              <Field label="Condiciones de pago" span={2}>
                <textarea
                  onChange={(event) => setForm((current) => ({ ...current, condiciones_pago: event.target.value }))}
                  rows={3}
                  value={form.condiciones_pago}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Datos bancarios opcionales para operacion interna." title="Datos bancarios" />
            <FormGrid>
              <Field label="Banco">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, banco: event.target.value }))}
                  type="text"
                  value={form.banco}
                />
              </Field>

              <Field label="Cuenta bancaria">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, cuenta_bancaria: event.target.value }))}
                  type="text"
                  value={form.cuenta_bancaria}
                />
              </Field>

              <Field label="CLABE">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, clabe: event.target.value }))}
                  type="text"
                  value={form.clabe}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Notas internas para seguimiento de compras." title="Notas" />
            <FormGrid>
              <Field label="Notas" span={2}>
                <textarea
                  onChange={(event) => setForm((current) => ({ ...current, notas: event.target.value }))}
                  rows={4}
                  value={form.notas}
                />
              </Field>
            </FormGrid>
          </section>

          <div className="inventory-actions inventory-actions-end">
            <ActionButton disabled={submitting} tone="primary" type="submit">
              {submitting ? "Guardando..." : form.id ? "Guardar cambios" : "Crear proveedor"}
            </ActionButton>
            <ActionButton
              onClick={() => {
                resetForm();
                setModalOpen(false);
              }}
              type="button"
            >
              Cancelar
            </ActionButton>
          </div>
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <>
            {detailSupplier ? (
              <ActionButton
                onClick={() => {
                  setDetailOpen(false);
                  openEditModal(detailSupplier);
                }}
                type="button"
              >
                Editar
              </ActionButton>
            ) : null}
            <ActionButton onClick={() => setDetailOpen(false)} type="button">
              Cerrar
            </ActionButton>
          </>
        }
        onClose={() => setDetailOpen(false)}
        open={detailOpen}
        size="xl"
        subtitle="Resumen comercial, ordenes de compra, recepciones y materiales relacionados."
        title={detailSupplier ? supplierDisplayName(detailSupplier) : "Detalle del proveedor"}
      >
        {!detailSupplier && detailLoading ? (
          <div className="screen-center">Cargando detalle del proveedor...</div>
        ) : !detailSupplier ? (
          <EmptyState note="Selecciona un proveedor para revisar su historial comercial." title="Sin proveedor seleccionado" />
        ) : (
          <div className="inventory-modal-form">
            <section className="inventory-form-section">
              <SectionTitle
                actions={
                  <StatusBadge tone={detailSupplier.activo ? "success" : "neutral"}>
                    {detailSupplier.activo ? "Activo" : "Inactivo"}
                  </StatusBadge>
                }
                subtitle="Perfil comercial y datos de contacto del proveedor."
                title="Perfil del proveedor"
              />
              <div className="inventory-detail-grid">
                <div>
                  <strong>Nombre comercial</strong>
                  <p>{supplierDisplayName(detailSupplier)}</p>
                </div>
                <div>
                  <strong>Razon social</strong>
                  <p>{safeDisplayText(detailSupplier.razon_social, "No registrada")}</p>
                </div>
                <div>
                  <strong>RFC</strong>
                  <p>{safeDisplayText(detailSupplier.rfc, "Sin RFC")}</p>
                </div>
                <div>
                  <strong>Contacto principal</strong>
                  <p>{safeDisplayText(supplierPrimaryContact(detailSupplier), "Sin contacto")}</p>
                </div>
                <div>
                  <strong>Email</strong>
                  <p>{safeDisplayText(supplierEmail(detailSupplier), "Sin email")}</p>
                </div>
                <div>
                  <strong>Telefono</strong>
                  <p>{safeDisplayText(supplierPrimaryPhone(detailSupplier), "Sin telefono")}</p>
                </div>
                <div>
                  <strong>Sitio web</strong>
                  <p>{safeDisplayText(detailSupplier.sitio_web, "No registrado")}</p>
                </div>
                <div className="inventory-form-span-2">
                  <strong>Direccion</strong>
                  <p>{supplierAddress(detailSupplier)}</p>
                </div>
                <div>
                  <strong>Moneda preferida</strong>
                  <p>{safeDisplayText(detailSupplier.moneda_preferida, "No definida")}</p>
                </div>
                <div>
                  <strong>Metodo de pago preferido</strong>
                  <p>{safeDisplayText(detailSupplier.metodo_pago_preferido, "No definido")}</p>
                </div>
                <div>
                  <strong>Dias de credito</strong>
                  <p>{formatNumber(detailSupplier.dias_credito || 0)}</p>
                </div>
                <div>
                  <strong>Lead time</strong>
                  <p>{formatNumber(detailSupplier.lead_time_dias || 0)} dias</p>
                </div>
                <div className="inventory-form-span-2">
                  <strong>Condiciones de pago</strong>
                  <p>{safeDisplayText(detailSupplier.condiciones_pago, "Sin condiciones registradas")}</p>
                </div>
                <div>
                  <strong>Banco</strong>
                  <p>{safeDisplayText(detailSupplier.banco, "No registrado")}</p>
                </div>
                <div>
                  <strong>Cuenta bancaria</strong>
                  <p>{safeDisplayText(detailSupplier.cuenta_bancaria, "No registrada")}</p>
                </div>
                <div>
                  <strong>CLABE</strong>
                  <p>{safeDisplayText(detailSupplier.clabe, "No registrada")}</p>
                </div>
                <div className="inventory-form-span-2">
                  <strong>Notas</strong>
                  <p>{safeDisplayText(detailSupplier.notas, "Sin notas")}</p>
                </div>
              </div>
            </section>

            <section className="inventory-metric-grid inventory-metric-grid-4">
              <MetricCard
                icon={<ShoppingCart size={16} />}
                label="Ordenes totales"
                value={formatNumber(detailSummary?.ordenes_totales || 0)}
              />
              <MetricCard
                icon={<Clock3 size={16} />}
                label="Ordenes abiertas"
                tone="warning"
                value={formatNumber(detailSummary?.ordenes_abiertas || 0)}
              />
              <MetricCard
                icon={<Building2 size={16} />}
                label="Ordenes recibidas"
                tone="success"
                value={formatNumber(detailSummary?.ordenes_recibidas || 0)}
              />
              <MetricCard
                icon={<Banknote size={16} />}
                label="Monto total comprado"
                tone="info"
                value={formatMoney(detailSummary?.monto_total_comprado || 0)}
              />
            </section>

            <section className="inventory-metric-grid inventory-metric-grid-3">
              <MetricCard
                icon={<Clock3 size={16} />}
                label="Pendiente por recibir"
                tone="warning"
                value={formatMoney(detailSummary?.monto_pendiente_por_recibir || 0)}
              />
              <MetricCard
                icon={<PackageSearch size={16} />}
                label="Recepciones totales"
                tone="success"
                value={formatNumber(detailSummary?.recepciones_totales || 0)}
              />
              <MetricCard
                icon={<Store size={16} />}
                label="Materiales asociados"
                value={formatNumber(detailSummary?.materiales_asociados || 0)}
              />
            </section>

            <section className="inventory-form-section">
              <SectionTitle subtitle="Ultimas ordenes emitidas o recibidas con este proveedor." title="Ordenes recientes" />
              {detailLoading && detailOrders.length === 0 ? (
                <div className="inventory-form-note">
                  <strong>Cargando ordenes</strong>
                  <p>Consultando historial comercial del proveedor.</p>
                </div>
              ) : detailOrders.length === 0 ? (
                <EmptyState compact note="Aun no hay ordenes ligadas a este proveedor." title="Sin ordenes recientes" />
              ) : (
                <DataTable
                  columns={[
                    { key: "folio", label: "Folio" },
                    { key: "fecha", label: "Fecha" },
                    { key: "estatus", label: "Estatus" },
                    { key: "total", label: "Total" },
                    { key: "pendiente", label: "Pendiente" },
                  ]}
                >
                  <tbody>
                    {detailOrders.map((order) => (
                      <tr key={order.id}>
                        <td>{order.folio}</td>
                        <td>{formatDateTime(order.fecha_emitida || order.created_at)}</td>
                        <td>
                          <StatusBadge>{order.estatus}</StatusBadge>
                        </td>
                        <td>{formatMoney(order.total)}</td>
                        <td>{formatMoney(order.valor_total_pendiente || 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </section>

            <section className="inventory-form-section">
              <SectionTitle subtitle="Recepciones registradas y entradas relacionadas al proveedor." title="Recepciones recientes" />
              {detailLoading && detailReceipts.length === 0 ? (
                <div className="inventory-form-note">
                  <strong>Cargando recepciones</strong>
                  <p>Consultando recepciones recientes del proveedor.</p>
                </div>
              ) : detailReceipts.length === 0 ? (
                <EmptyState compact note="Este proveedor aun no tiene recepciones registradas." title="Sin recepciones recientes" />
              ) : (
                <DataTable
                  columns={[
                    { key: "fecha", label: "Fecha" },
                    { key: "almacen", label: "Almacen" },
                    { key: "documento", label: "Documento / remision" },
                    { key: "usuario", label: "Registrado por" },
                    { key: "materiales", label: "Materiales" },
                  ]}
                >
                  <tbody>
                    {detailReceipts.map((receipt) => (
                      <tr key={receipt.id}>
                        <td>{formatDateTime(receipt.created_at)}</td>
                        <td>{safeDisplayText(receipt.almacen_nombre, "Sin almacen")}</td>
                        <td>{safeDisplayText(receipt.documento_referencia, "Sin documento")}</td>
                        <td>{safeDisplayText(receipt.recibido_por_nombre, "No registrado")}</td>
                        <td>{receiptItemsPreview(receipt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </section>

            <section className="inventory-form-section">
              <SectionTitle subtitle="Materiales relacionados a ordenes y recepciones de este proveedor." title="Materiales asociados" />
              {detailLoading && detailMaterials.length === 0 ? (
                <div className="inventory-form-note">
                  <strong>Cargando materiales</strong>
                  <p>Consultando materiales asociados al proveedor.</p>
                </div>
              ) : detailMaterials.length === 0 ? (
                <EmptyState compact note="No hay materiales relacionados aun." title="Sin materiales asociados" />
              ) : (
                <DataTable
                  columns={[
                    { key: "material", label: "Material" },
                    { key: "sku", label: "SKU" },
                    { key: "ordenes", label: "Ordenes" },
                    { key: "recibido", label: "Total recibido" },
                    { key: "comprado", label: "Total comprado" },
                    { key: "ultima", label: "Ultima orden" },
                  ]}
                >
                  <tbody>
                    {detailMaterials.map((material) => (
                      <tr key={material.material_id}>
                        <td>
                          <div className="inventory-cell-main">{material.nombre}</div>
                          <div className="inventory-cell-sub">
                            {material.es_proveedor_principal ? "Proveedor principal" : "Proveedor relacionado"}
                          </div>
                        </td>
                        <td>{safeDisplayText(material.sku, "Sin SKU")}</td>
                        <td>{formatNumber(material.ordenes_count)}</td>
                        <td>{formatNumber(material.total_recibido)}</td>
                        <td>{formatMoney(material.monto_total_comprado)}</td>
                        <td>{formatDateTime(material.ultima_orden_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </section>
          </div>
        )}
      </ModalShell>
    </div>
  );
}
