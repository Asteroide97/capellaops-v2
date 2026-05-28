import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import BarcodeScannerModal from "../../components/BarcodeScannerModal";
import { createMaterialRequisition, getInventorySummary, inventoryLookupMaterial } from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  FilterCard,
  MaterialImage,
  MetricCard,
  PageHeader,
  SearchInput,
  StatusBadge,
  formatDateTime,
  StockBadge,
  buttonClassName,
  formatMoney,
  formatNumber,
  handleScannerEnter,
  safeDisplayText,
} from "./shared";


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


function SummaryKpis({ summary }) {
  const cards = [
    {
      label: "Materiales bajo stock",
      value: formatNumber(summary.kpis.materiales_bajo_stock),
      meta: "Alertas activas",
      tone: summary.kpis.materiales_bajo_stock > 0 ? "warning" : "success",
      icon: "BS",
    },
    {
      label: "OTs pendientes",
      value: "0",
      meta: "PM pendiente",
      tone: "neutral",
      icon: "OT",
    },
    {
      label: "OC pendientes",
      value: formatNumber(summary.kpis.ordenes_compra_pendientes),
      meta: "Compras abiertas",
      tone: summary.kpis.ordenes_compra_pendientes > 0 ? "warning" : "neutral",
      icon: "OC",
    },
    {
      label: "Requisiciones pendientes",
      value: formatNumber(summary.kpis.requisiciones_pendientes),
      meta: "Por atender",
      tone: summary.kpis.requisiciones_pendientes > 0 ? "warning" : "neutral",
      icon: "RQ",
    },
    {
      label: "Total de materiales",
      value: formatNumber(summary.kpis.total_materiales),
      meta: "Catálogo activo",
      tone: "info",
      icon: "SK",
    },
  ];

  return (
    <div className="inventory-metric-grid inventory-metric-grid-5">
        {cards.map((card) => (
          <MetricCard
            icon={card.icon}
            key={card.label}
            label={card.label}
            meta={card.meta}
            tone={card.tone}
            value={card.value}
          />
        ))}
    </div>
  );
}


function SummaryIndicators({ summary }) {
  return (
    <div className="inventory-metric-grid inventory-metric-grid-4">
      <MetricCard
        label="Valorización de inventario"
        meta="Stock total x costo actual"
        tone="success"
        value={formatMoney(summary.indicadores.valor_inventario)}
      />
      <MetricCard
        label="Costo de reposición"
        meta="Faltante contra mínimo"
        tone="warning"
        value={formatMoney(summary.indicadores.costo_reposicion)}
      />
      <MetricCard
        label="Ajustes del mes"
        meta="Conteo de ajustes aplicados"
        tone="info"
        value={formatNumber(summary.indicadores.ajustes_mes)}
      />
      <MetricCard
        label="Merma del mes"
        meta="Clasificación formal pendiente"
        tone="neutral"
        value={formatMoney(summary.indicadores.merma_mes)}
      />
    </div>
  );
}


export default function InventorySummaryPage() {
  const navigate = useNavigate();
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [summary, setSummary] = useState(emptySummary);
  const [lookupResult, setLookupResult] = useState(null);
  const [scannerOpen, setScannerOpen] = useState(false);

  const criticalAlerts = useMemo(() => summary.alertas.slice(0, 8), [summary.alertas]);

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

  async function handleCreateRequisition(materialId) {
    if (!materialId) {
      setNotice("No se encontro el material asociado a esta alerta.");
      return;
    }

    setError("");
    setNotice("");
    try {
      const response = await createMaterialRequisition({ materialId, token, empresaId });
      setNotice(`Requisicion ${response.folio} creada desde bajo stock.`);
      await loadSummary();
    } catch (requestError) {
      setError(requestError.message || "No se pudo crear la requisicion.");
    }
  }

  async function handleLookup(codeOverride = searchTerm) {
    const query = String(codeOverride || "").trim();

    if (!query) {
      setNotice("Escribe un SKU, código de barras o nombre de material para continuar.");
      setLookupResult(null);
      return;
    }

    setError("");
    setNotice("");
    try {
      const response = await inventoryLookupMaterial({ code: query, token, empresaId });
      setLookupResult(response.material);
      setSearchTerm(query);
      setNotice(`Código detectado: ${query}`);
    } catch (requestError) {
      setLookupResult(null);
      setError(requestError.message || "No se encontró ningún material con ese SKU o código de barras.");
    }
  }

  async function handleSearch(event) {
    event.preventDefault();
    await handleLookup();
  }

  if (loading) {
    return <div className="screen-center">Cargando panel de control...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        actions={
          <ActionButton onClick={loadSummary} size="sm" type="button">
            Actualizar
          </ActionButton>
        }
        eyebrow="Inventario"
        subtitle="Control de Inventario"
        title="Panel de Control"
      >
        <FilterCard>
          <form className="inventory-summary-search-panel" onSubmit={handleSearch}>
            <SearchInput
              action={
                <div className="inventory-actions">
                  <ActionButton onClick={() => setScannerOpen(true)} size="sm" type="button">
                    Escanear
                  </ActionButton>
                  <ActionButton size="sm" tone="primary" type="submit">
                    Buscar
                  </ActionButton>
                </div>
              }
              hint="Admite lector USB de código de barras como teclado y búsqueda exacta por cámara."
              label="Búsqueda rápida"
              onChange={(event) => setSearchTerm(event.target.value)}
              onKeyDown={(event) => handleScannerEnter(event, handleLookup)}
              placeholder="Escanea un código o busca por SKU/material"
              value={searchTerm}
            />
          </form>
          {notice ? <p className="feature-note">{notice}</p> : null}
          {error ? <p className="form-error">{error}</p> : null}

          {lookupResult ? (
            <div className="inventory-lookup-result">
              <div className="inventory-lookup-result-main">
                <MaterialImage alt={lookupResult.nombre} size="md" src={lookupResult.imagen_url} />
                <div className="inventory-lookup-result-copy">
                  <strong>{lookupResult.nombre}</strong>
                  <div className="inventory-cell-sub">
                    {lookupResult.sku} · {lookupResult.codigo_barras || "Sin código de barras"}
                  </div>
                  <div className="inventory-cell-sub">
                    {safeDisplayText(lookupResult.categoria, "Sin categoría")} · Stock total {formatNumber(lookupResult.stock_total)}
                  </div>
                  <div className="inventory-cell-sub">
                    Proveedor principal: {safeDisplayText(lookupResult.proveedor_principal_nombre, "Sin proveedor")}
                  </div>
                </div>
              </div>

              <div className="inventory-actions inventory-actions-wrap">
                <ActionButton
                  onClick={() => navigate(`/inventario/materiales?q=${encodeURIComponent(lookupResult.sku)}`)}
                  size="sm"
                  tone="primary"
                  type="button"
                >
                  Ver material
                </ActionButton>
                <ActionButton onClick={() => navigate("/inventario/kardex")} size="sm" type="button">
                  Ver Kardex
                </ActionButton>
                <ActionButton onClick={() => navigate("/inventario/movimientos")} size="sm" type="button">
                  Nueva entrada
                </ActionButton>
                <ActionButton onClick={() => navigate("/inventario/movimientos")} size="sm" type="button">
                  Nueva salida
                </ActionButton>
              </div>

              <div className="inventory-lookup-result-meta">
                <span className="table-note">Última actualización: {formatDateTime(lookupResult.updated_at)}</span>
              </div>

              {lookupResult.stock_por_almacen?.length ? (
                <DataTable
                  columns={[
                    { key: "almacen", label: "Almacén" },
                    { key: "stock", label: "Stock actual" },
                  ]}
                >
                  <tbody>
                    {lookupResult.stock_por_almacen.map((item) => (
                      <tr key={item.almacen_id}>
                        <td>{item.almacen_nombre}</td>
                        <td>{formatNumber(item.stock_actual)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              ) : (
                <EmptyState compact note="Este material todavía no tiene existencias registradas por almacén." title="Sin stock por almacén" />
              )}
            </div>
          ) : null}
        </FilterCard>
      </PageHeader>

      <SummaryKpis summary={summary} />
      <SummaryIndicators summary={summary} />

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Atajos operativos del módulo Inventario" title="Acciones rápidas">
          <div className="inventory-action-grid">
            <button className={buttonClassName({ tone: "ghost", size: "sm" })} onClick={handleScanPlaceholder} type="button">
              Escanear QR
            </button>
            <Link className={buttonClassName({ tone: "primary", size: "sm" })} to="/inventario/movimientos">
              Nueva entrada
            </Link>
            <Link className={buttonClassName({ tone: "ghost", size: "sm" })} to="/inventario/ordenes-compra">
              Crear OC
            </Link>
            <Link className={buttonClassName({ tone: "ghost", size: "sm" })} to="/inventario/materiales">
              Ver inventario
            </Link>
          </div>
        </DataCard>

        <DataCard subtitle="El envío automático queda pendiente para una fase posterior." title="Resumen de alertas">
          {criticalAlerts.length === 0 ? (
            <EmptyState compact note="No hay alertas críticas calculadas en este momento." title="Sin alertas activas" />
          ) : (
            <div className="inventory-alert-stack">
              {criticalAlerts.map((alert, index) => (
                <article className={`inventory-alert-card ${alert.nivel}`} key={`${alert.tipo}-${index}`}>
                  <div className="inventory-alert-card-head">
                    <strong>{alert.titulo}</strong>
                    <StatusBadge tone={alert.nivel === "critical" ? "danger" : alert.nivel === "warning" ? "warning" : "info"}>
                      {alert.nivel}
                    </StatusBadge>
                  </div>
                  <p>{alert.mensaje}</p>
                  {alert.tipo === "stock" && alert.material_id ? (
                    <div className="inventory-actions">
                      <ActionButton onClick={() => handleCreateRequisition(alert.material_id)} size="sm" type="button">
                        Crear requisicion
                      </ActionButton>
                    </div>
                  ) : null}
                </article>
              ))}
              <div className="inventory-actions">
                <ActionButton onClick={() => setNotice("El envío automático de alertas por email queda pendiente para una fase posterior.")} size="sm" type="button">
                  Enviar por email
                </ActionButton>
              </div>
            </div>
          )}
        </DataCard>
      </div>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Top 5 por valor operativo y stock visible" title="Productos Core">
          {summary.productos_core.length === 0 ? (
            <EmptyState compact note="Cuando existan materiales con stock aparecerán aquí." title="Sin productos core" />
          ) : (
            <DataTable
              columns={[
                { key: "ranking", label: "#" },
                { key: "material", label: "Material" },
                { key: "categoria", label: "Categoría" },
                { key: "stock", label: "Stock" },
                { key: "valor", label: "Valor" },
                { key: "dias", label: "Días sin movimiento" },
              ]}
            >
              <tbody>
                {summary.productos_core.map((item, index) => (
                  <tr key={item.material_id}>
                    <td>
                      <span className="inventory-rank-pill">{index + 1}</span>
                    </td>
                    <td>
                      <div className="inventory-cell-main">{item.nombre}</div>
                      <div className="inventory-cell-sub">{item.sku}</div>
                    </td>
                    <td>{item.categoria || "—"}</td>
                    <td>{formatNumber(item.stock_total)}</td>
                    <td>{formatMoney(item.valor_total)}</td>
                    <td>{formatNumber(item.dias_sin_movimiento)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>

        <DataCard subtitle="Material inmovilizado durante los últimos 30 días" title="Baja rotación">
          {summary.baja_rotacion.length === 0 ? (
            <EmptyState compact note="Cuando exista stock sin salida reciente aparecerá en esta lista." title="Sin baja rotación" />
          ) : (
            <DataTable
              columns={[
                { key: "material", label: "Material" },
                { key: "sku", label: "SKU" },
                { key: "stock", label: "Stock" },
                { key: "valor", label: "Valor retenido" },
                { key: "dias", label: "Días sin movimiento" },
              ]}
            >
              <tbody>
                {summary.baja_rotacion.map((item) => (
                  <tr key={item.material_id}>
                    <td>{item.nombre}</td>
                    <td>{item.sku}</td>
                    <td>{formatNumber(item.stock_total)}</td>
                    <td>{formatMoney(item.valor_retenido)}</td>
                    <td>{formatNumber(item.dias_sin_movimiento)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      </div>

      <DataCard subtitle="Materiales agotados o por debajo del mínimo definido" title="Materiales bajo stock">
        {summary.materiales_bajo_stock.length === 0 ? (
          <EmptyState compact note="No hay materiales agotados ni por debajo del mínimo en este momento." title="Sin alertas de stock" />
        ) : (
          <DataTable
            columns={[
              { key: "material", label: "Material" },
              { key: "sku", label: "SKU" },
              { key: "stock", label: "Stock actual" },
              { key: "minimo", label: "Stock mínimo" },
              { key: "faltante", label: "Faltante" },
              { key: "estado", label: "Estado" },
              { key: "accion", label: "Accion" },
            ]}
          >
            <tbody>
              {summary.materiales_bajo_stock.map((item) => (
                <tr key={item.material_id}>
                  <td>{item.nombre}</td>
                  <td>{item.sku}</td>
                  <td>{formatNumber(item.stock_total)}</td>
                  <td>{formatNumber(item.stock_minimo)}</td>
                  <td>{formatNumber(item.faltante)}</td>
                  <td>
                    <StockBadge
                      minimo={item.stock_minimo}
                      okLabel="Sano"
                      stock={item.stock_total}
                      zeroLabel="Agotado"
                    />
                  </td>
                  <td>
                    <button
                      className={buttonClassName({ tone: "ghost", size: "sm" })}
                      onClick={() => handleCreateRequisition(item.material_id)}
                      type="button"
                    >
                      Crear requisicion
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <BarcodeScannerModal
        helperText="Apunta la cámara al código de barras o QR para consultar el material exacto."
        onClose={() => setScannerOpen(false)}
        onDetected={(code) => {
          handleLookup(code).finally(() => setScannerOpen(false));
        }}
        open={scannerOpen}
        title="Escanear código"
      />
    </div>
  );
}
