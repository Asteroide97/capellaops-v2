import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { createSupplier, getSuppliers, updateSupplier } from "../../api/client";
import {
  DEFAULT_PAGE_SIZE,
  EmptyState,
  PaginationControls,
  parseBooleanFilter,
  ResultMeta,
} from "./shared";


const defaultFilters = {
  q: "",
  activo: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
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
  const [form, setForm] = useState({
    id: "",
    nombre: "",
    contacto_nombre: "",
    correo: "",
    telefono: "",
    direccion: "",
    notas: "",
    activo: true,
  });

  async function loadSuppliers(nextFilters = filters) {
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
        await loadSuppliers(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los proveedores.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  function resetForm() {
    setForm({
      id: "",
      nombre: "",
      contacto_nombre: "",
      correo: "",
      telefono: "",
      direccion: "",
      notas: "",
      activo: true,
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        nombre: form.nombre,
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

      resetForm();
      await loadSuppliers(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el proveedor.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando proveedores...</div>;
  }

  return (
    <div className="inventory-grid">
      <form className="feature-card inventory-form-card" onSubmit={handleSubmit}>
        <div className="feature-header">
          <p className="eyebrow">Compras</p>
          <h2>{form.id ? "Editar proveedor" : "Crear proveedor"}</h2>
          <p>Administra el directorio base de proveedores por empresa.</p>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
        {success ? <p className="form-success">{success}</p> : null}

        <div className="inventory-form-grid">
          <label>
            Nombre
            <input
              onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))}
              required
              type="text"
              value={form.nombre}
            />
          </label>

          <label>
            Contacto
            <input
              onChange={(event) => setForm((current) => ({ ...current, contacto_nombre: event.target.value }))}
              type="text"
              value={form.contacto_nombre}
            />
          </label>

          <label>
            Correo
            <input
              onChange={(event) => setForm((current) => ({ ...current, correo: event.target.value }))}
              type="email"
              value={form.correo}
            />
          </label>

          <label>
            Teléfono
            <input
              onChange={(event) => setForm((current) => ({ ...current, telefono: event.target.value }))}
              type="text"
              value={form.telefono}
            />
          </label>

          <label className="inventory-form-span-2">
            Dirección
            <textarea
              onChange={(event) => setForm((current) => ({ ...current, direccion: event.target.value }))}
              rows={3}
              value={form.direccion}
            />
          </label>

          <label className="inventory-form-span-2">
            Notas
            <textarea
              onChange={(event) => setForm((current) => ({ ...current, notas: event.target.value }))}
              rows={3}
              value={form.notas}
            />
          </label>

          <label className="checkbox-row">
            <input
              checked={form.activo}
              onChange={(event) => setForm((current) => ({ ...current, activo: event.target.checked }))}
              type="checkbox"
            />
            Proveedor activo
          </label>
        </div>

        <div className="inventory-actions">
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Guardando..." : form.id ? "Actualizar proveedor" : "Crear proveedor"}
          </button>
          <button className="ghost-button" onClick={resetForm} type="button">
            Nuevo proveedor
          </button>
        </div>
      </form>

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Listado</p>
          <h2>Proveedores registrados</h2>
          <ResultMeta label="proveedores" loaded={suppliers.length} total={meta.total} />
        </div>

        <form
          className="inventory-filter-grid"
          onSubmit={async (event) => {
            event.preventDefault();
            const nextFilters = { ...filters, offset: 0 };
            setFilters(nextFilters);
            try {
              await loadSuppliers(nextFilters);
            } catch (requestError) {
              setError(requestError.message || "No se pudieron filtrar los proveedores.");
            }
          }}
        >
          <label>
            Buscar
            <input
              onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
              placeholder="Nombre, contacto o correo"
              type="text"
              value={filters.q}
            />
          </label>

          <label>
            Estado
            <select
              onChange={(event) => setFilters((current) => ({ ...current, activo: event.target.value }))}
              value={filters.activo}
            >
              <option value="">Todos</option>
              <option value="true">Activos</option>
              <option value="false">Inactivos</option>
            </select>
          </label>

          <div className="inventory-actions">
            <button className="ghost-button" type="submit">
              Aplicar filtros
            </button>
            <button
              className="ghost-button"
              onClick={async () => {
                setFilters(defaultFilters);
                try {
                  await loadSuppliers(defaultFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron reiniciar los filtros.");
                }
              }}
              type="button"
            >
              Limpiar
            </button>
            <button
              className="ghost-button"
              onClick={async () => {
                try {
                  await loadSuppliers(filters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo actualizar el listado.");
                }
              }}
              type="button"
            >
              Actualizar
            </button>
          </div>
        </form>

        {suppliers.length === 0 ? (
          <EmptyState
            title="No hay proveedores."
            note="Crea el primer proveedor para comenzar el flujo de compras."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Proveedor</th>
                    <th>Contacto</th>
                    <th>Canales</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.map((supplier) => (
                    <tr key={supplier.id}>
                      <td>
                        <strong>{supplier.nombre}</strong>
                        <div className="table-note">{supplier.direccion || "Sin dirección"}</div>
                      </td>
                      <td>{supplier.contacto_nombre || "Sin contacto"}</td>
                      <td>
                        <div>{supplier.correo || "Sin correo"}</div>
                        <div className="table-note">{supplier.telefono || "Sin teléfono"}</div>
                      </td>
                      <td>
                        <span className={`status-badge ${supplier.activo ? "enabled" : "pending"}`}>
                          {supplier.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className="inventory-row-actions">
                        <button
                          className="link-button"
                          onClick={() =>
                            setForm({
                              id: supplier.id,
                              nombre: supplier.nombre,
                              contacto_nombre: supplier.contacto_nombre || "",
                              correo: supplier.correo || "",
                              telefono: supplier.telefono || "",
                              direccion: supplier.direccion || "",
                              notas: supplier.notas || "",
                              activo: supplier.activo,
                            })
                          }
                          type="button"
                        >
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PaginationControls
              meta={meta}
              onNext={async () => {
                const nextFilters = { ...filters, offset: meta.offset + meta.limit };
                setFilters(nextFilters);
                try {
                  await loadSuppliers(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadSuppliers(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}
