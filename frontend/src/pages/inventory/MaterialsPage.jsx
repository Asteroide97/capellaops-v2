import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { createMaterial, getMaterials, updateMaterial } from "../../api/client";
import {
  DEFAULT_PAGE_SIZE,
  EmptyState,
  formatMoney,
  formatNumber,
  normalizeDecimalInput,
  PaginationControls,
  parseBooleanFilter,
  ResultMeta,
} from "./shared";


const defaultFilters = {
  q: "",
  categoria: "",
  activo: "",
  stock_bajo: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


export default function MaterialsPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [materials, setMaterials] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [form, setForm] = useState({
    id: "",
    sku: "",
    nombre: "",
    descripcion: "",
    categoria: "",
    unidad: "pieza",
    costo_unitario: "0",
    precio_venta: "0",
    stock_minimo: "0",
    activo: true,
  });

  async function loadMaterialsPage(nextFilters = filters) {
    const response = await getMaterials({
      token,
      empresaId,
      filters: {
        ...nextFilters,
        activo: parseBooleanFilter(nextFilters.activo),
        stock_bajo: parseBooleanFilter(nextFilters.stock_bajo),
      },
    });
    setMaterials(response.items);
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
        await loadMaterialsPage(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los materiales.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  function resetForm() {
    setForm({
      id: "",
      sku: "",
      nombre: "",
      descripcion: "",
      categoria: "",
      unidad: "pieza",
      costo_unitario: "0",
      precio_venta: "0",
      stock_minimo: "0",
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
        sku: form.sku,
        nombre: form.nombre,
        descripcion: form.descripcion,
        categoria: form.categoria,
        unidad: form.unidad,
        costo_unitario: form.costo_unitario,
        precio_venta: form.precio_venta,
        stock_minimo: form.stock_minimo,
        activo: form.activo,
      };

      if (form.id) {
        await updateMaterial({ materialId: form.id, token, empresaId, payload });
        setSuccess("Material actualizado correctamente.");
      } else {
        await createMaterial({ token, empresaId, payload });
        setSuccess("Material creado correctamente.");
      }

      resetForm();
      await loadMaterialsPage(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el material.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando materiales...</div>;
  }

  return (
    <div className="inventory-grid">
      <form className="feature-card inventory-form-card" onSubmit={handleSubmit}>
        <div className="feature-header">
          <p className="eyebrow">Catálogo</p>
          <h2>{form.id ? "Editar material" : "Crear material"}</h2>
          <p>Administra SKU, costos, precios y reglas básicas de stock por empresa.</p>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
        {success ? <p className="form-success">{success}</p> : null}

        <div className="inventory-form-grid">
          <label>
            SKU
            <input
              onChange={(event) => setForm((current) => ({ ...current, sku: event.target.value }))}
              required
              type="text"
              value={form.sku}
            />
          </label>

          <label>
            Nombre
            <input
              onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))}
              required
              type="text"
              value={form.nombre}
            />
          </label>

          <label className="inventory-form-span-2">
            Descripción
            <textarea
              onChange={(event) => setForm((current) => ({ ...current, descripcion: event.target.value }))}
              rows={3}
              value={form.descripcion}
            />
          </label>

          <label>
            Categoría
            <input
              onChange={(event) => setForm((current) => ({ ...current, categoria: event.target.value }))}
              type="text"
              value={form.categoria}
            />
          </label>

          <label>
            Unidad
            <input
              onChange={(event) => setForm((current) => ({ ...current, unidad: event.target.value }))}
              required
              type="text"
              value={form.unidad}
            />
          </label>

          <label>
            Costo unitario
            <input
              min="0"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  costo_unitario: normalizeDecimalInput(event.target.value),
                }))
              }
              required
              step="0.0001"
              type="number"
              value={form.costo_unitario}
            />
          </label>

          <label>
            Precio de venta
            <input
              min="0"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  precio_venta: normalizeDecimalInput(event.target.value),
                }))
              }
              required
              step="0.0001"
              type="number"
              value={form.precio_venta}
            />
          </label>

          <label>
            Stock mínimo
            <input
              min="0"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  stock_minimo: normalizeDecimalInput(event.target.value),
                }))
              }
              required
              step="0.0001"
              type="number"
              value={form.stock_minimo}
            />
          </label>

          <label className="checkbox-row">
            <input
              checked={form.activo}
              onChange={(event) => setForm((current) => ({ ...current, activo: event.target.checked }))}
              type="checkbox"
            />
            Material activo
          </label>
        </div>

        <div className="inventory-actions">
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Guardando..." : form.id ? "Actualizar material" : "Crear material"}
          </button>
          <button className="ghost-button" onClick={resetForm} type="button">
            Nuevo material
          </button>
        </div>
      </form>

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Listado</p>
          <h2>Materiales registrados</h2>
          <ResultMeta label="materiales" loaded={materials.length} total={meta.total} />
        </div>

        <form
          className="inventory-filter-grid"
          onSubmit={async (event) => {
            event.preventDefault();
            const nextFilters = { ...filters, offset: 0 };
            setFilters(nextFilters);
            try {
              await loadMaterialsPage(nextFilters);
            } catch (requestError) {
              setError(requestError.message || "No se pudieron filtrar los materiales.");
            }
          }}
        >
          <label>
            Buscar
            <input
              onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
              placeholder="SKU o nombre"
              type="text"
              value={filters.q}
            />
          </label>

          <label>
            Categoría
            <input
              onChange={(event) => setFilters((current) => ({ ...current, categoria: event.target.value }))}
              placeholder="Filtrar por categoría"
              type="text"
              value={filters.categoria}
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

          <label>
            Stock
            <select
              onChange={(event) => setFilters((current) => ({ ...current, stock_bajo: event.target.value }))}
              value={filters.stock_bajo}
            >
              <option value="">Todos</option>
              <option value="true">Solo stock bajo</option>
              <option value="false">Solo stock sano</option>
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
                  await loadMaterialsPage(defaultFilters);
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
                  await loadMaterialsPage(filters);
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

        {materials.length === 0 ? (
          <EmptyState
            title="No hay materiales."
            note="Crea el primer material para comenzar a operar compras, inventario y POS."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Material</th>
                    <th>Categoría</th>
                    <th>Precio</th>
                    <th>Stock mínimo</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {materials.map((material) => (
                    <tr key={material.id}>
                      <td>{material.sku}</td>
                      <td>
                        <strong>{material.nombre}</strong>
                        <div className="table-note">{material.unidad}</div>
                      </td>
                      <td>{material.categoria || "Sin categoría"}</td>
                      <td>
                        <strong>{formatMoney(material.precio_venta)}</strong>
                        <div className="table-note">Costo {formatMoney(material.costo_unitario)}</div>
                      </td>
                      <td>{formatNumber(material.stock_minimo)}</td>
                      <td>
                        <span className={`status-badge ${material.activo ? "enabled" : "pending"}`}>
                          {material.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className="inventory-row-actions">
                        <button
                          className="link-button"
                          onClick={() =>
                            setForm({
                              id: material.id,
                              sku: material.sku,
                              nombre: material.nombre,
                              descripcion: material.descripcion || "",
                              categoria: material.categoria || "",
                              unidad: material.unidad,
                              costo_unitario: String(material.costo_unitario),
                              precio_venta: String(material.precio_venta),
                              stock_minimo: String(material.stock_minimo),
                              activo: material.activo,
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
                  await loadMaterialsPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadMaterialsPage(nextFilters);
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
