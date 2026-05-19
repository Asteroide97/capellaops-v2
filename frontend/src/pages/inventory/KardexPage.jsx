import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { getMaterialKardex, getMaterials, getWarehouses } from "../../api/client";
import { EmptyState, formatDateTime, formatNumber } from "./shared";


export default function KardexPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [materials, setMaterials] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [filters, setFilters] = useState({
    material_id: "",
    almacen_id: "",
  });
  const [kardex, setKardex] = useState(null);

  async function loadOptions() {
    const [warehouseResponse, materialResponse] = await Promise.all([
      getWarehouses({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
      getMaterials({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
    ]);
    setWarehouses(warehouseResponse.items);
    setMaterials(materialResponse.items);
    return {
      warehouseItems: warehouseResponse.items,
      materialItems: materialResponse.items,
    };
  }

  async function loadKardex(materialId = filters.material_id, warehouseId = filters.almacen_id) {
    if (!materialId) {
      setKardex(null);
      return;
    }

    const response = await getMaterialKardex({
      materialId,
      almacenId: warehouseId || undefined,
      token,
      empresaId,
    });
    setKardex(response);
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
        const defaultMaterialId = options.materialItems[0]?.id || "";
        setFilters({
          material_id: defaultMaterialId,
          almacen_id: "",
        });
        if (defaultMaterialId) {
          await loadKardex(defaultMaterialId, "");
        }
      } catch (requestError) {
        setError(requestError.message || "No se pudo cargar el kardex.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  if (loading) {
    return <div className="screen-center">Cargando kardex...</div>;
  }

  return (
    <div className="inventory-grid">
      <div className="feature-card inventory-form-card">
        <div className="feature-header">
          <p className="eyebrow">Kardex</p>
          <h2>Consulta por material</h2>
          <p>Revisa el historial completo y el stock distribuido por almacén.</p>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
        {success ? <p className="form-success">{success}</p> : null}

        {materials.length === 0 ? (
          <EmptyState
            title="No hay materiales disponibles."
            note="Crea al menos un material para consultar su kardex."
          />
        ) : (
          <>
            <label>
              Material
              <select
                onChange={(event) => setFilters((current) => ({ ...current, material_id: event.target.value }))}
                value={filters.material_id}
              >
                {materials.map((material) => (
                  <option key={material.id} value={material.id}>
                    {material.sku} - {material.nombre}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Almacén (opcional)
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

            <div className="inventory-actions">
              <button
                className="primary-button"
                disabled={submitting}
                onClick={async () => {
                  setSubmitting(true);
                  setError("");
                  setSuccess("");
                  try {
                    await loadKardex();
                    setSuccess("Kardex actualizado.");
                  } catch (requestError) {
                    setError(requestError.message || "No se pudo consultar el kardex.");
                  } finally {
                    setSubmitting(false);
                  }
                }}
                type="button"
              >
                {submitting ? "Consultando..." : "Ver kardex"}
              </button>
              <button
                className="ghost-button"
                disabled={submitting}
                onClick={async () => {
                  setSubmitting(true);
                  setError("");
                  try {
                    await loadKardex();
                  } catch (requestError) {
                    setError(requestError.message || "No se pudo actualizar la consulta.");
                  } finally {
                    setSubmitting(false);
                  }
                }}
                type="button"
              >
                Actualizar
              </button>
            </div>
          </>
        )}
      </div>

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Detalle</p>
          <h2>Kardex del material</h2>
        </div>

        {!kardex ? (
          <EmptyState
            title="Sin consulta activa."
            note="Selecciona un material y presiona Ver kardex."
          />
        ) : (
          <div className="inventory-kardex-stack">
            <div className="module-board">
              <article className="mini-card">
                <span className="eyebrow">Material</span>
                <strong>{kardex.material.sku}</strong>
                <p>{kardex.material.nombre}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Existencia total</span>
                <strong>{formatNumber(kardex.existencia_total)}</strong>
                <p>{kardex.material.unidad}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Stock mínimo</span>
                <strong>{formatNumber(kardex.material.stock_minimo)}</strong>
                <p>{kardex.material.unidad}</p>
              </article>
            </div>

            {kardex.stock_por_almacen.length === 0 ? (
              <EmptyState
                title="Sin stock por almacén."
                note="Este material aún no tiene existencias registradas."
              />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Almacén</th>
                      <th>Código</th>
                      <th>Cantidad</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kardex.stock_por_almacen.map((item) => (
                      <tr key={item.almacen_id}>
                        <td>{item.almacen_nombre}</td>
                        <td>{item.almacen_codigo}</td>
                        <td>{formatNumber(item.cantidad)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {kardex.movements.length === 0 ? (
              <EmptyState
                title="Sin historial."
                note="Aún no hay movimientos para este material."
              />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Tipo</th>
                      <th>Almacén</th>
                      <th>Cantidad</th>
                      <th>Anterior</th>
                      <th>Nueva</th>
                    </tr>
                  </thead>
                  <tbody>
                    {kardex.movements.map((movement) => (
                      <tr key={movement.id}>
                        <td>{formatDateTime(movement.created_at)}</td>
                        <td>{movement.tipo}</td>
                        <td>{movement.almacen_nombre}</td>
                        <td>{formatNumber(movement.cantidad)}</td>
                        <td>{formatNumber(movement.cantidad_anterior)}</td>
                        <td>{formatNumber(movement.cantidad_nueva)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
