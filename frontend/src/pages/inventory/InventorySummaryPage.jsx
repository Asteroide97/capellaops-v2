import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { getInventoryMovements, getMaterials, getStock, getWarehouses } from "../../api/client";
import { EmptyState, formatDateTime, formatNumber, ResultMeta } from "./shared";


export default function InventorySummaryPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState({
    warehousesTotal: 0,
    materialsTotal: 0,
    stockTotal: 0,
    lowStockTotal: 0,
    lowStockItems: [],
    recentMovements: [],
  });

  useEffect(() => {
    async function loadSummary() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const [warehouses, materials, stock, lowStock, movements] = await Promise.all([
          getWarehouses({ token, empresaId, filters: { limit: 1, offset: 0 } }),
          getMaterials({ token, empresaId, filters: { limit: 1, offset: 0 } }),
          getStock({ token, empresaId, filters: { limit: 25, offset: 0 } }),
          getStock({ token, empresaId, filters: { stock_bajo: true, limit: 10, offset: 0 } }),
          getInventoryMovements({ token, empresaId, filters: { limit: 10, offset: 0 } }),
        ]);

        setSummary({
          warehousesTotal: warehouses.total,
          materialsTotal: materials.total,
          stockTotal: stock.total,
          lowStockTotal: lowStock.total,
          lowStockItems: lowStock.items,
          recentMovements: movements.items,
        });
      } catch (requestError) {
        setError(requestError.message || "No se pudo cargar el resumen de inventario.");
      } finally {
        setLoading(false);
      }
    }

    loadSummary();
  }, [token, empresaId]);

  if (loading) {
    return <div className="screen-center">Cargando resumen de inventario...</div>;
  }

  return (
    <div className="dashboard-stack">
      {error ? <p className="form-error">{error}</p> : null}

      <div className="hero-grid">
        <article className="metric-card">
          <span>Almacenes</span>
          <strong>{summary.warehousesTotal}</strong>
        </article>
        <article className="metric-card">
          <span>Materiales</span>
          <strong>{summary.materialsTotal}</strong>
        </article>
        <article className="metric-card">
          <span>Existencias</span>
          <strong>{summary.stockTotal}</strong>
        </article>
        <article className="metric-card">
          <span>Stock bajo</span>
          <strong>{summary.lowStockTotal}</strong>
        </article>
      </div>

      <div className="module-board">
        <article className="module-card">
          <div className="module-card-top">
            <h3>Operación diaria</h3>
          </div>
          <p>Consulta existencias, revisa movimientos recientes y entra rápido a las secciones más usadas.</p>
          <div className="inventory-actions">
            <Link className="primary-link" to="/inventario/movimientos">
              Registrar movimiento
            </Link>
            <Link className="ghost-button" to="/inventario/traspasos">
              Ver traspasos
            </Link>
          </div>
        </article>

        <article className="module-card">
          <div className="module-card-top">
            <h3>Compras</h3>
          </div>
          <p>Gestiona proveedores, requisiciones y órdenes de compra conectadas a inventario.</p>
          <div className="inventory-actions">
            <Link className="ghost-button" to="/inventario/proveedores">
              Proveedores
            </Link>
            <Link className="ghost-button" to="/inventario/ordenes-compra">
              Órdenes de compra
            </Link>
          </div>
        </article>
      </div>

      <div className="inventory-grid">
        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Alertas</p>
            <h2>Materiales con stock bajo</h2>
            <ResultMeta label="registros" loaded={summary.lowStockItems.length} total={summary.lowStockTotal} />
          </div>

          {summary.lowStockItems.length === 0 ? (
            <EmptyState
              title="Sin alertas activas."
              note="No hay materiales por debajo de su stock mínimo en este momento."
            />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Almacén</th>
                    <th>SKU</th>
                    <th>Material</th>
                    <th>Cantidad</th>
                    <th>Mínimo</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.lowStockItems.map((item) => (
                    <tr key={item.id}>
                      <td>{item.almacen_nombre}</td>
                      <td>{item.material_sku}</td>
                      <td>{item.material_nombre}</td>
                      <td>{formatNumber(item.cantidad)}</td>
                      <td>{formatNumber(item.stock_minimo)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Auditoría</p>
            <h2>Movimientos recientes</h2>
            <ResultMeta
              label="movimientos"
              loaded={summary.recentMovements.length}
              total={summary.recentMovements.length}
            />
          </div>

          {summary.recentMovements.length === 0 ? (
            <EmptyState
              title="Sin movimientos todavía."
              note="Cuando registres entradas, salidas o ajustes aparecerán aquí."
            />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Material</th>
                    <th>Almacén</th>
                    <th>Cambio</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.recentMovements.map((movement) => (
                    <tr key={movement.id}>
                      <td>{formatDateTime(movement.created_at)}</td>
                      <td>{movement.tipo}</td>
                      <td>{movement.material_nombre}</td>
                      <td>{movement.almacen_nombre}</td>
                      <td>{formatNumber(movement.cantidad)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
