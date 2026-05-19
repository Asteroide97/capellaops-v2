import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import {
  createInventoryMovement,
  getInventoryMovements,
  getMaterials,
  getWarehouses,
} from "../../api/client";
import {
  DEFAULT_PAGE_SIZE,
  EmptyState,
  formatDateTime,
  formatNumber,
  normalizeDecimalInput,
  PaginationControls,
  ResultMeta,
} from "./shared";


const movementTypes = [
  { value: "entrada", label: "Registrar entrada" },
  { value: "salida", label: "Registrar salida" },
  { value: "ajuste", label: "Registrar ajuste" },
];

const defaultFilters = {
  almacen_id: "",
  material_id: "",
  tipo: "",
  fecha_desde: "",
  fecha_hasta: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


export default function MovementsPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warehouses, setWarehouses] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [movements, setMovements] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [form, setForm] = useState({
    almacen_id: "",
    material_id: "",
    tipo: "entrada",
    cantidad: "",
    cantidad_nueva: "",
    referencia_tipo: "manual",
    referencia_id: "",
    notas: "",
  });

  async function loadOptions() {
    const [warehouseResponse, materialResponse] = await Promise.all([
      getWarehouses({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
      getMaterials({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
    ]);
    setWarehouses(warehouseResponse.items);
    setMaterials(materialResponse.items);
    return {
      warehouses: warehouseResponse.items,
      materials: materialResponse.items,
    };
  }

  async function loadMovementsPage(nextFilters = filters) {
    const response = await getInventoryMovements({ token, empresaId, filters: nextFilters });
    setMovements(response.items);
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
        const options = await loadOptions();
        setForm((current) => ({
          ...current,
          almacen_id: current.almacen_id || options.warehouses[0]?.id || "",
          material_id: current.material_id || options.materials[0]?.id || "",
        }));
        await loadMovementsPage(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los movimientos.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        almacen_id: form.almacen_id,
        material_id: form.material_id,
        tipo: form.tipo,
        referencia_tipo: form.referencia_tipo || "manual",
        referencia_id: form.referencia_id || null,
        notas: form.notas || null,
      };

      if (form.tipo === "ajuste") {
        payload.cantidad_nueva = form.cantidad_nueva;
      } else {
        payload.cantidad = form.cantidad;
      }

      await createInventoryMovement({ token, empresaId, payload });
      setSuccess(
        form.tipo === "entrada"
          ? "Entrada registrada correctamente."
          : form.tipo === "salida"
            ? "Salida registrada correctamente."
            : "Ajuste registrado correctamente.",
      );
      setForm((current) => ({
        ...current,
        cantidad: "",
        cantidad_nueva: "",
        referencia_id: "",
        notas: "",
      }));
      await loadMovementsPage(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar el movimiento.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando movimientos...</div>;
  }

  const currentMovementLabel =
    movementTypes.find((item) => item.value === form.tipo)?.label ?? "Registrar movimiento";

  return (
    <div className="inventory-grid">
      <form className="feature-card inventory-form-card" onSubmit={handleSubmit}>
        <div className="feature-header">
          <p className="eyebrow">Operación diaria</p>
          <h2>{currentMovementLabel}</h2>
          <p>Entradas, salidas y ajustes auditables conectados al stock real de cada almacén.</p>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
        {success ? <p className="form-success">{success}</p> : null}

        {warehouses.length === 0 || materials.length === 0 ? (
          <EmptyState
            title="Faltan datos base."
            note="Necesitas al menos un almacén y un material activo antes de mover inventario."
          />
        ) : (
          <>
            <div className="inventory-toggle-row">
              {movementTypes.map((item) => (
                <button
                  className={`inventory-toggle-button ${form.tipo === item.value ? "active" : ""}`}
                  key={item.value}
                  onClick={() =>
                    setForm((current) => ({
                      ...current,
                      tipo: item.value,
                      cantidad: "",
                      cantidad_nueva: "",
                    }))
                  }
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="inventory-form-grid">
              <label>
                Almacén
                <select
                  onChange={(event) => setForm((current) => ({ ...current, almacen_id: event.target.value }))}
                  required
                  value={form.almacen_id}
                >
                  {warehouses.map((warehouse) => (
                    <option key={warehouse.id} value={warehouse.id}>
                      {warehouse.nombre} ({warehouse.codigo})
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Material
                <select
                  onChange={(event) => setForm((current) => ({ ...current, material_id: event.target.value }))}
                  required
                  value={form.material_id}
                >
                  {materials.map((material) => (
                    <option key={material.id} value={material.id}>
                      {material.sku} - {material.nombre}
                    </option>
                  ))}
                </select>
              </label>

              {form.tipo === "ajuste" ? (
                <label>
                  Cantidad nueva
                  <input
                    min="0"
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        cantidad_nueva: normalizeDecimalInput(event.target.value),
                      }))
                    }
                    required
                    step="0.0001"
                    type="number"
                    value={form.cantidad_nueva}
                  />
                </label>
              ) : (
                <label>
                  Cantidad
                  <input
                    min="0.0001"
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        cantidad: normalizeDecimalInput(event.target.value),
                      }))
                    }
                    required
                    step="0.0001"
                    type="number"
                    value={form.cantidad}
                  />
                </label>
              )}

              <label>
                Referencia tipo
                <input
                  onChange={(event) => setForm((current) => ({ ...current, referencia_tipo: event.target.value }))}
                  type="text"
                  value={form.referencia_tipo}
                />
              </label>

              <label>
                Referencia ID
                <input
                  onChange={(event) => setForm((current) => ({ ...current, referencia_id: event.target.value }))}
                  type="text"
                  value={form.referencia_id}
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
            </div>

            <button className="primary-button" disabled={submitting} type="submit">
              {submitting ? "Registrando..." : currentMovementLabel}
            </button>
          </>
        )}
      </form>

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Auditoría</p>
          <h2>Movimientos recientes</h2>
          <ResultMeta label="movimientos" loaded={movements.length} total={meta.total} />
        </div>

        <form
          className="inventory-filter-grid"
          onSubmit={async (event) => {
            event.preventDefault();
            const nextFilters = { ...filters, offset: 0 };
            setFilters(nextFilters);
            try {
              await loadMovementsPage(nextFilters);
            } catch (requestError) {
              setError(requestError.message || "No se pudieron filtrar los movimientos.");
            }
          }}
        >
          <label>
            Almacén
            <select
              onChange={(event) => setFilters((current) => ({ ...current, almacen_id: event.target.value }))}
              value={filters.almacen_id}
            >
              <option value="">Todos</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.nombre} ({warehouse.codigo})
                </option>
              ))}
            </select>
          </label>

          <label>
            Material
            <select
              onChange={(event) => setFilters((current) => ({ ...current, material_id: event.target.value }))}
              value={filters.material_id}
            >
              <option value="">Todos</option>
              {materials.map((material) => (
                <option key={material.id} value={material.id}>
                  {material.sku} - {material.nombre}
                </option>
              ))}
            </select>
          </label>

          <label>
            Tipo
            <select
              onChange={(event) => setFilters((current) => ({ ...current, tipo: event.target.value }))}
              value={filters.tipo}
            >
              <option value="">Todos</option>
              {movementTypes.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.value}
                </option>
              ))}
            </select>
          </label>

          <label>
            Fecha desde
            <input
              onChange={(event) => setFilters((current) => ({ ...current, fecha_desde: event.target.value }))}
              type="datetime-local"
              value={filters.fecha_desde}
            />
          </label>

          <label>
            Fecha hasta
            <input
              onChange={(event) => setFilters((current) => ({ ...current, fecha_hasta: event.target.value }))}
              type="datetime-local"
              value={filters.fecha_hasta}
            />
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
                  await loadMovementsPage(defaultFilters);
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
                  await loadMovementsPage(filters);
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

        {movements.length === 0 ? (
          <EmptyState
            title="No hay movimientos todavía."
            note="Cuando registres entradas, salidas o ajustes aparecerán aquí."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Material</th>
                    <th>Almacén</th>
                    <th>Cambio</th>
                    <th>Nuevo stock</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.map((movement) => (
                    <tr key={movement.id}>
                      <td>{formatDateTime(movement.created_at)}</td>
                      <td>
                        <span className={`status-badge ${movement.tipo === "salida" ? "pending" : "enabled"}`}>
                          {movement.tipo}
                        </span>
                      </td>
                      <td>
                        <strong>{movement.material_sku}</strong>
                        <div className="table-note">{movement.material_nombre}</div>
                      </td>
                      <td>{movement.almacen_nombre}</td>
                      <td>{formatNumber(movement.cantidad)}</td>
                      <td>{formatNumber(movement.cantidad_nueva)}</td>
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
                  await loadMovementsPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadMovementsPage(nextFilters);
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
