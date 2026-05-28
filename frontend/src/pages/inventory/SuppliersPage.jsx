import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { createSupplier, getSuppliers, updateSupplier } from "../../api/client";
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
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  parseBooleanFilter,
  safeDisplayText,
} from "./shared";


const defaultFilters = {
  q: "",
  activo: "true",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultForm = {
  id: "",
  nombre: "",
  razon_social: "",
  rfc: "",
  contacto_nombre: "",
  correo: "",
  telefono: "",
  direccion: "",
  notas: "",
  activo: true,
};


export default function SuppliersPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [suppliers, setSuppliers] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(defaultForm);

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
      nombre: supplier.nombre,
      razon_social: supplier.razon_social || "",
      rfc: supplier.rfc || "",
      contacto_nombre: supplier.contacto_nombre || "",
      correo: supplier.correo || "",
      telefono: supplier.telefono || "",
      direccion: supplier.direccion || "",
      notas: supplier.notas || "",
      activo: supplier.activo,
    });
    setError("");
    setSuccess("");
    setModalOpen(true);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const payload = {
        nombre: form.nombre,
        razon_social: form.razon_social || null,
        rfc: form.rfc || null,
        contacto_nombre: form.contacto_nombre || null,
        correo: form.correo || null,
        telefono: form.telefono || null,
        direccion: form.direccion || null,
        notas: form.notas || null,
        activo: form.activo,
      };

      if (form.id) {
        await updateSupplier({ supplierId: form.id, token, empresaId, payload });
        setSuccess("Proveedor actualizado correctamente.");
      } else {
        await createSupplier({ token, empresaId, payload });
        setSuccess("Proveedor creado correctamente.");
      }

      setModalOpen(false);
      resetForm();
      await loadSuppliersPage(filters);
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
      setSuccess(supplier.activo ? "Proveedor desactivado." : "Proveedor activado.");
      await loadSuppliersPage(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el proveedor.");
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
            Agregar Proveedor
          </ActionButton>
        }
        eyebrow="Compras"
        subtitle="Gestión de proveedores de materiales"
        title="Proveedores"
      />

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}

      <FilterCard>
        <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
          <SearchInput
            hint="Busca por nombre, contacto, email o RFC."
            label="Buscar proveedor"
            onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
            onKeyDown={async (event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                const nextFilters = { ...filters, offset: 0 };
                setFilters(nextFilters);
                try {
                  await loadSuppliersPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron aplicar los filtros.");
                }
              }
            }}
            placeholder="Proveedor, RFC, contacto o correo"
            value={filters.q}
          />

          <div className="inventory-toggle-row inventory-toggle-row-compact">
            <label className="inventory-inline-checkbox">
              <input
                checked={filters.activo !== "false"}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    activo: event.target.checked ? "true" : "",
                  }))
                }
                type="checkbox"
              />
              Solo activos
            </label>
          </div>

          <div className="inventory-actions">
            <ActionButton
              onClick={async () => {
                const nextFilters = { ...filters, offset: 0 };
                setFilters(nextFilters);
                try {
                  await loadSuppliersPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron aplicar los filtros.");
                }
              }}
              size="sm"
              tone="primary"
              type="button"
            >
              Buscar
            </ActionButton>
            <ActionButton
              onClick={async () => {
                setFilters(defaultFilters);
                try {
                  await loadSuppliersPage(defaultFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron reiniciar los filtros.");
                }
              }}
              size="sm"
              type="button"
            >
              Limpiar
            </ActionButton>
            <ActionButton
              onClick={async () => {
                try {
                  await loadSuppliersPage(filters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo actualizar el listado.");
                }
              }}
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
        subtitle="Directorio operativo para compras, recepciones y reposición de inventario"
        title="Proveedores registrados"
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
                { key: "email", label: "Email" },
                { key: "telefono", label: "Teléfono" },
                { key: "estatus", label: "Estatus" },
                { key: "acciones", label: "Acciones" },
              ]}
            >
              <tbody>
                {suppliers.map((supplier) => (
                  <tr key={supplier.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(supplier.nombre)}</div>
                      <div className="inventory-cell-sub">
                        {supplier.razon_social || supplier.direccion || "Sin razón social"}
                      </div>
                    </td>
                    <td>{safeDisplayText(supplier.rfc, "Sin RFC")}</td>
                    <td>{safeDisplayText(supplier.contacto_nombre, "Sin contacto")}</td>
                    <td>{safeDisplayText(supplier.correo, "Sin email")}</td>
                    <td>{supplier.telefono || "Sin teléfono"}</td>
                    <td>
                      <StatusBadge tone={supplier.activo ? "success" : "neutral"}>
                        {supplier.activo ? "Activo" : "Inactivo"}
                      </StatusBadge>
                    </td>
                    <td className="inventory-row-actions">
                      <button className="link-button" onClick={() => openEditModal(supplier)} type="button">
                        Editar
                      </button>
                      <button className="link-button" onClick={() => toggleSupplierStatus(supplier)} type="button">
                        {supplier.activo ? "Desactivar" : "Activar"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>

            <PaginationControls
              meta={meta}
              onNext={async () => {
                const nextFilters = { ...filters, offset: meta.offset + meta.limit };
                setFilters(nextFilters);
                try {
                  await loadSuppliersPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadSuppliersPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
            />
          </>
        )}
      </DataCard>

      <ModalShell
        onClose={() => setModalOpen(false)}
        open={modalOpen}
        size="medium"
        subtitle="Registro base de proveedor sin mezclar CRM ni cuentas por pagar."
        title={form.id ? "Editar Proveedor" : "Nuevo Proveedor"}
      >
        <form className="inventory-modal-form" onSubmit={handleSubmit}>
          <section className="inventory-form-section">
            <SectionTitle subtitle="Información comercial y fiscal básica" title="Identificación" />
            <FormGrid>
              <Field label="Nombre">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))}
                  required
                  type="text"
                  value={form.nombre}
                />
              </Field>

              <Field label="Razón social">
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

              <Field label="Contacto">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, contacto_nombre: event.target.value }))}
                  type="text"
                  value={form.contacto_nombre}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Canales de contacto operativos" title="Contacto" />
            <FormGrid>
              <Field label="Teléfono">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, telefono: event.target.value }))}
                  type="text"
                  value={form.telefono}
                />
              </Field>

              <Field label="Email">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, correo: event.target.value }))}
                  type="email"
                  value={form.correo}
                />
              </Field>

              <Field label="Dirección" span={2}>
                <textarea
                  onChange={(event) => setForm((current) => ({ ...current, direccion: event.target.value }))}
                  rows={3}
                  value={form.direccion}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Notas internas de operación" title="Seguimiento" />
            <FormGrid>
              <Field label="Notas" span={2}>
                <textarea
                  onChange={(event) => setForm((current) => ({ ...current, notas: event.target.value }))}
                  rows={4}
                  value={form.notas}
                />
              </Field>

              <Field span={2}>
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
    </div>
  );
}
