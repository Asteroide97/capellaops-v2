import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { getInventorySummary } from "../../api/client";
import { EmptyState, formatMoney, formatNumber } from "./shared";


const emptySummary = {
  kpis: {
    materiales_bajo_stock: 0,
    ordenes_compra_pendientes: 0,
    requisiciones_pendientes: 0,
    total_materiales: 0,
  },
  indicadores: {
    valor_inventario: 0,
    costo_reposicion: 0,
    ajustes_mes: 0,
    merma_mes: 0,
  },
  productos_core: [],
  baja_rotacion: [],
  materiales_bajo_stock: [],
  alertas: [],
};


function KPIGrid({ summary }) {
  return (
    <div className="hero-grid">
      <article className="metric-card">
        <span>Materiales bajo stock</span>
        <strong>{summary.kpis.materiales_bajo_stock}</strong>
      </article>
      <article className="metric-card">
        <span>OC pendientes</span>
        <strong>{summary.kpis.ordenes_compra_pendientes}</strong>
      </article>
      <article className="metric-card">
        <span>Requisiciones pendientes</span>
        <strong>{summary.kpis.requisiciones_pendientes}</strong>
      </article>
      <article className="metric-card">
        <span>Total de materiales</span>
        <strong>{summary.kpis.total_materiales}</strong>
      </article>
    </div>
  );
}


function IndicatorGrid({ summary }) {
  return (
    <div className="module-board">
      <article className="mini-card">
        <span className="eyebrow">Valor inventario</span>
        <strong>{formatMoney(summary.indicadores.valor_inventario)}</strong>
      </article>
      <article className="mini-card">
        <span className="eyebrow">Costo de reposición</span>
        <strong>{formatMoney(summary.indicadores.costo_reposicion)}</strong>
      </article>
      <article className="mini-card">
        <span className="eyebrow">Ajustes del mes</span>
        <strong>{formatNumber(summary.indicadores.ajustes_mes)}</strong>
      </article>
      <article className="mini-card">
        <span className="eyebrow">Merma del mes</span>
        <strong>{formatMoney(summary.indicadores.merma_mes)}</strong>
      </article>
    </div>
  );
}


export default function InventorySummaryPage() {
  const navigate = useNavigate();
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scannerMessage, setScannerMessage] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [summary, setSummary] = useState(emptySummary);

  async function loadSummary() {
    if (!token || !empresaId) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const response = await getInventorySummary({ token, empresaId });
      setSummary(response);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el panel de control de inventario.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSummary();
  }, [token, empresaId]);

  function handleSearch(event) {
    event.preventDefault();
    const query = searchTerm.trim();
    if (!query) {
      setScannerMessage("Escribe un SKU o nombre de material para continuar.");
      return;
    }

    setScannerMessage("La búsqueda inteligente desde Resumen se conectará en una fase posterior. Te llevamos a Materiales.");
    navigate("/inventario/materiales");
  }

  function handleScanPlaceholder() {
    setScannerMessage("El escaneo QR o código de barras queda pendiente para una fase posterior.");
  }

  if (loading) {
    return <div className="screen-center">Cargando panel de control...</div>;
  }

  return (
    <div className="dashboard-stack">
      <section className="feature-card inventory-summary-header">
        <div className="inventory-summary-title">
          <div>
            <p className="eyebrow">Panel de Control</p>
            <h2>Control de inventario</h2>
            <p className="table-note">
              Monitorea stock, compras y alertas sin duplicar la fuente de verdad del inventario.
            </p>
          </div>

          <div className="inventory-actions">
            <button className="ghost-button" onClick={loadSummary} type="button">
              Actualizar
            </button>
          </div>
        </div>

        <form className="inventory-summary-search" onSubmit={handleSearch}>
          <label className="inventory-summary-search-input">
            Escanea un código o busca por SKU/material
            <input
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="SKU, nombre o palabra clave"
              type="text"
              value={searchTerm}
            />
          </label>

          <div className="inventory-actions">
            <button className="primary-button" type="submit">
              Buscar
            </button>
            <button className="ghost-button" onClick={handleScanPlaceholder} type="button">
              Escanear
            </button>
          </div>
        </form>

        {scannerMessage ? <p className="feature-note">{scannerMessage}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </section>

      <KPIGrid summary={summary} />
      <IndicatorGrid summary={summary} />

      <div className="module-board">
        <article className="module-card">
          <div className="module-card-top">
            <h3>Acciones rápidas</h3>
          </div>
          <p>Atajos operativos para seguir moviendo inventario y compras desde el resumen.</p>
          <div className="inventory-actions">
            <button className="ghost-button" onClick={handleScanPlaceholder} type="button">
              Escanear QR
            </button>
            <Link className="primary-link" to="/inventario/movimientos">
              Nueva entrada
            </Link>
            <Link className="ghost-button" to="/inventario/ordenes-compra">
              Crear OC
            </Link>
            <Link className="ghost-button" to="/inventario/materiales">
              Ver inventario
            </Link>
          </div>
        </article>

        <article className="module-card">
          <div className="module-card-top">
            <h3>Resumen de alertas</h3>
          </div>
          <p>El envío automático de alertas queda pendiente para una fase posterior.</p>
          <div className="inventory-actions">
            <button className="ghost-button" onClick={() => setScannerMessage("El envío por email queda pendiente para una fase posterior.")} type="button">
              Enviar por email
            </button>
          </div>
        </article>
      </div>

      <div className="inventory-grid inventory-summary-grid">
        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Productos Core</p>
            <h2>Top 5 por valor y stock</h2>
          </div>

          {summary.productos_core.length === 0 ? (
            <EmptyState
              title="Sin productos core todavía."
              note="Cuando existan materiales con stock, aquí verás los más relevantes."
            />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Ranking</th>
                    <th>Material</th>
                    <th>Categoría</th>
                    <th>Stock</th>
                    <th>Valor</th>
                    <th>Días sin movimiento</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.productos_core.map((item, index) => (
                    <tr key={item.material_id}>
                      <td>{index + 1}</td>
                      <td>
                        <strong>{item.nombre}</strong>
                        <div className="table-note">{item.sku}</div>
                      </td>
                      <td>{item.categoria || "Sin categoría"}</td>
                      <td>{formatNumber(item.stock_total)}</td>
                      <td>{formatMoney(item.valor_total)}</td>
                      <td>{item.dias_sin_movimiento}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Baja rotación</p>
            <h2>Últimos 30 días</h2>
          </div>

          {summary.baja_rotacion.length === 0 ? (
            <EmptyState
              title="Sin materiales de baja rotación."
              note="Cuando exista stock sin movimiento reciente, aparecerá en esta lista."
            />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Material</th>
                    <th>SKU</th>
                    <th>Stock</th>
                    <th>Valor retenido</th>
                    <th>Días sin movimiento</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.baja_rotacion.map((item) => (
                    <tr key={item.material_id}>
                      <td>{item.nombre}</td>
                      <td>{item.sku}</td>
                      <td>{formatNumber(item.stock_total)}</td>
                      <td>{formatMoney(item.valor_retenido)}</td>
                      <td>{item.dias_sin_movimiento}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="inventory-grid inventory-summary-grid">
        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Bajo stock</p>
            <h2>Materiales que requieren atención</h2>
          </div>

          {summary.materiales_bajo_stock.length === 0 ? (
            <EmptyState
              title="Sin materiales en alerta."
              note="No hay materiales agotados ni por debajo del mínimo en este momento."
            />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Material</th>
                    <th>SKU</th>
                    <th>Stock actual</th>
                    <th>Stock mínimo</th>
                    <th>Faltante</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.materiales_bajo_stock.map((item) => (
                    <tr key={item.material_id}>
                      <td>{item.nombre}</td>
                      <td>{item.sku}</td>
                      <td>{formatNumber(item.stock_total)}</td>
                      <td>{formatNumber(item.stock_minimo)}</td>
                      <td>{formatNumber(item.faltante)}</td>
                      <td>
                        <span className={`status-badge ${item.estado === "Agotado" ? "pending" : "enabled"}`}>
                          {item.estado}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Alertas</p>
            <h2>Resumen operativo</h2>
          </div>

          {summary.alertas.length === 0 ? (
            <EmptyState
              title="Sin alertas calculadas."
              note="Cuando detectemos riesgos operativos, aparecerán aquí."
            />
          ) : (
            <div className="inventory-alert-list">
              {summary.alertas.map((alert, index) => (
                <article className={`inventory-alert-card ${alert.nivel}`} key={`${alert.tipo}-${index}`}>
                  <div className="module-card-top">
                    <strong>{alert.titulo}</strong>
                    <span className={`status-badge ${alert.nivel === "critical" ? "pending" : "enabled"}`}>
                      {alert.nivel}
                    </span>
                  </div>
                  <p>{alert.mensaje}</p>
                  {alert.route ? (
                    <Link className="link-button" to={alert.route}>
                      Abrir sección relacionada
                    </Link>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
