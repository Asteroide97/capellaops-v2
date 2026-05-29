import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { createWarehouse, getWarehouses, updateWarehouse } from "../../api/client";
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


export default function WarehousesPage() {
  const { empresa, token, empresaId, limits, refreshSession } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warehouses, setWarehouses] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [form, setForm] = useState({
    id: "",
    nombre: "",
    codigo: "",
    descripcion: "",
    activo: true,
  });

  const maxWarehouses = limits?.max_almacenes ?? null;
  const activeWarehouses = limits?.almacenes_actuales ?? 0;
  const createLimitReached = !form.id && form.activo && maxWarehouses !== null && activeWarehouses >= maxWarehouses;

  async function loadWarehousesPage(nextFilters = filters) {
    const response = await getWarehouses({
      token,
      empresaId,
      filters: {
        ...nextFilters,
        activo: parseBooleanFilter(nextFilters.activo),
      },
    });
    setWarehouses(response.items);
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
        await loadWarehousesPage(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los almacenes.");
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
      codigo: "",
      descripcion: "",
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
        codigo: form.codigo,
        descripcion: form.descripcion,
        activo: form.activo,
      };

      if (form.id) {
        await updateWarehouse({ warehouseId: form.id, token, empresaId, payload });
        setSuccess("Almacen actualizado correctamente.");
      } else {
        await createWarehouse({ token, empresaId, payload });
        setSuccess("Almacen creado correctamente.");
      }

      await refreshSession();
      resetForm();
      await loadWarehousesPage(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el almacen.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando almacenes...</div>;
  }

  return (
    <div className="inventory-grid">
      <form className="feature-card inventory-form-card" onSubmit={handleSubmit}>
        <div className="feature-header">
          <p className="eyebrow">Configuracion</p>
          <h2>{form.id ? "Editar almacen" : "Crear almacen"}</h2>
          <p>Administra almacenes activos sin salir del modulo Inventario.</p>
          <p className="table-note">
            {empresa?.name || "Empresa activa"} | Almacenes: {activeWarehouses} / {maxWarehouses ?? "Ilimitado"}
          </p>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
        {success ? <p className="form-success">{success}</p> : null}
        {createLimitReached ? (
          <p className="form-error">
            Tu plan permite hasta {maxWarehouses} almacen(es). Actualiza tu plan para agregar mas.
          </p>
        ) : null}

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
            Codigo
            <input
              onChange={(event) => setForm((current) => ({ ...current, codigo: event.target.value }))}
              required
              type="text"
              value={form.codigo}
            />
          </label>

          <label className="inventory-form-span-2">
            Descripcion
            <textarea
              onChange={(event) => setForm((current) => ({ ...current, descripcion: event.target.value }))}
              rows={3}
              value={form.descripcion}
            />
          </label>

          <label className="checkbox-row">
            <input
              checked={form.activo}
              onChange={(event) => setForm((current) => ({ ...current, activo: event.target.checked }))}
              type="checkbox"
            />
            Almacen activo
          </label>
        </div>

        <div className="inventory-actions">
          <button className="primary-button" disabled={submitting || createLimitReached} type="submit">
            {submitting ? "Guardando..." : form.id ? "Actualizar almacen" : "Crear almacen"}
          </button>
          <button className="ghost-button" onClick={resetForm} type="button">
            Nuevo almacen
          </button>
        </div>
      </form>

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Listado</p>
          <h2>Almacenes registrados</h2>
          <ResultMeta label="almacenes" loaded={warehouses.length} total={meta.total} />
        </div>

        <form
          className="inventory-filter-grid"
          onSubmit={async (event) => {
            event.preventDefault();
            const nextFilters = { ...filters, offset: 0 };
            setFilters(nextFilters);
            try {
              await loadWarehousesPage(nextFilters);
            } catch (requestError) {
              setError(requestError.message || "No se pudieron filtrar los almacenes.");
            }
          }}
        >
          <label>
            Buscar
            <input
              onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
              placeholder="Nombre o codigo"
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
                  await loadWarehousesPage(defaultFilters);
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
                  await loadWarehousesPage(filters);
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

        {warehouses.length === 0 ? (
          <EmptyState
            title="No hay almacenes."
            note="Crea el primer almacen para comenzar a operar inventario."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Codigo</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {warehouses.map((warehouse) => (
                    <tr key={warehouse.id}>
                      <td>
                        <strong>{warehouse.nombre}</strong>
                        <div className="table-note">{warehouse.descripcion || "Sin descripcion"}</div>
                      </td>
                      <td>{warehouse.codigo}</td>
                      <td>
                        <span className={`status-badge ${warehouse.activo ? "enabled" : "pending"}`}>
                          {warehouse.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className="inventory-row-actions">
                        <button
                          className="link-button"
                          onClick={() =>
                            setForm({
                              id: warehouse.id,
                              nombre: warehouse.nombre,
                              codigo: warehouse.codigo,
                              descripcion: warehouse.descripcion || "",
                              activo: warehouse.activo,
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
                  await loadWarehousesPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la pagina.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadWarehousesPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la pagina.");
                }
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}
