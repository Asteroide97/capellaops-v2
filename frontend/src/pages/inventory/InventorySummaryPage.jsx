import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import BarcodeScannerModal from "../../components/BarcodeScannerModal";
import {
  createMaterialRequisition,
  getInventorySummary,
  getWarehouses,
  inventoryLookupMaterial,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  MaterialImage,
  MetricCard,
  PageHeader,
  SearchInput,
  StatusBadge,
  StockBadge,
  buttonClassName,
  formatDateTime,
  formatMoney,
  formatNumber,
  handleScannerEnter,
  safeDisplayText,
} from "./shared";


const emptySummary = {
  kpis: {
    valor_total_inventario: 0,
    materiales_bajo_stock: 0,
    materiales_sin_stock: 0,
    materiales_sin_precio_venta: 0,
    materiales_sin_costo: 0,
    requisiciones_pendientes: 0,
    ordenes_compra_pendientes: 0,
    movimientos_mes: 0,
    total_materiales: 0,
  },
  indicadores: {
    valor_inventario: 0,
    costo_reposicion: 0,
    ajustes_mes: 0,
    merma_mes: 0,
  },
  alertas: [],
  bajo_stock: [],
  sin_precio_venta: [],
  sin_costo: [],
  productos_mas_movidos: [],
  baja_rotacion: [],
  ultimos_movimientos: [],
};

const defaultFilters = {
  almacen_id: "",
  periodo_dias: "60",
  categoria: "",
};


function SummaryKpis({ summary }) {
  const cards = [
    {
      label: "Valor total de inventario",
      value: formatMoney(summary.kpis.valor_total_inventario),
      meta: "Stock valorizado a costo actual",
      tone: "success",
      icon: "VT",
    },
    {
      label: "Materiales bajo stock",
      value: formatNumber(summary.kpis.materiales_bajo_stock),
      meta: "Requieren seguimiento",
      tone: summary.kpis.materiales_bajo_stock > 0 ? "warning" : "success",
      icon: "BS",
    },
    {
      label: "Materiales sin stock",
      value: formatNumber(summary.kpis.materiales_sin_stock),
      meta: "Agotados",
      tone: summary.kpis.materiales_sin_stock > 0 ? "danger" : "success",
      icon: "SS",
    },
    {
      label: "Sin precio de venta",
      value: formatNumber(summary.kpis.materiales_sin_precio_venta),
      meta: "Impacta POS",
      tone: summary.kpis.materiales_sin_precio_venta > 0 ? "warning" : "success",
      icon: "PV",
    },
    {
      label: "Sin costo",
      value: formatNumber(summary.kpis.materiales_sin_costo),
      meta: "Afecta margen",
      tone: summary.kpis.materiales_sin_costo > 0 ? "warning" : "success",
      icon: "CT",
    },
    {
      label: "Requisiciones pendientes",
      value: formatNumber(summary.kpis.requisiciones_pendientes),
      meta: "Por atender",
      tone: summary.kpis.requisiciones_pendientes > 0 ? "info" : "neutral",
      icon: "RQ",
    },
    {
      label: "Ordenes de compra pendientes",
      value: formatNumber(summary.kpis.ordenes_compra_pendientes),
      meta: "Compras abiertas",
      tone: summary.kpis.ordenes_compra_pendientes > 0 ? "warning" : "neutral",
      icon: "OC",
    },
    {
      label: "Movimientos del mes",
      value: formatNumber(summary.kpis.movimientos_mes),
      meta: "Entradas, salidas y ajustes",
      tone: "info",
      icon: "MV",
    },
  ];

  return (
    <div className="inventory-metric-grid inventory-metric-grid-4">
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
  const [warehouses, setWarehouses] = useState([]);
  const [filters, setFilters] = useState(defaultFilters);

  const topAlerts = useMemo(() => summary.alertas.slice(0, 8), [summary.alertas]);

  async function loadSummary(nextFilters = filters) {
    if (!token || !empresaId) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const response = await getInventorySummary({
        token,
        empresaId,
        filters: {
          almacen_id: nextFilters.almacen_id || undefined,
          periodo_dias: nextFilters.periodo_dias || undefined,
          categoria: nextFilters.categoria || undefined,
        },
      });
      setSummary(response);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el reporte operativo de inventario.");
    } finally {
      setLoading(false);
    }
  }

  async function loadWarehouses() {
    if (!token || !empresaId) {
      return;
    }
    try {
      const response = await getWarehouses({
        token,
        empresaId,
        filters: { activo: true, limit: 100, offset: 0 },
      });
      setWarehouses(response.items);
    } catch {
      setWarehouses([]);
    }
  }

  useEffect(() => {
    loadWarehouses();
    loadSummary(filters);
  }, [token, empresaId]);

  function buildMaterialsPath(extraFilters = {}) {
    const params = new URLSearchParams();
    const merged = { ...extraFilters };
    Object.entries(merged).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, String(value));
      }
    });
    const suffix = params.toString();
    return `/inventario/materiales${suffix ? `?${suffix}` : ""}`;
  }

  async function handleCreateRequisition(materialId) {
    if (!materialId) {
      setNotice("No se encontro el material asociado a esta accion.");
      return;
    }

    setError("");
    setNotice("");
    try {
      const response = await createMaterialRequisition({ materialId, token, empresaId });
      setNotice(`Requisicion ${response.folio} creada desde el resumen.`);
      await loadSummary(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo crear la requisicion.");
    }
  }

  function handleAlertAction(alert) {
    if (alert.action === "create_requisition" && alert.material_id) {
      handleCreateRequisition(alert.material_id);
      return;
    }
    if (alert.accion_url) {
      navigate(alert.accion_url);
    }
  }

  async function handleLookup(codeOverride = searchTerm) {
    const query = String(codeOverride || "").trim();
    if (!query) {
      setNotice("Escribe un SKU, codigo de barras o nombre de material para continuar.");
      setLookupResult(null);
      return;
    }

    setError("");
    setNotice("");
    try {
      const response = await inventoryLookupMaterial({ code: query, token, empresaId });
      setLookupResult(response.material);
      setSearchTerm(query);
      setNotice(`Codigo detectado: ${query}`);
    } catch (requestError) {
      setLookupResult(null);
      setError(requestError.message || "No se encontro ningun material con ese SKU o codigo de barras.");
    }
  }

  async function handleSearch(event) {
    event.preventDefault();
    await handleLookup();
  }

  async function handleApplyFilters() {
    await loadSummary(filters);
  }

  async function handleResetFilters() {
    setFilters(defaultFilters);
    await loadSummary(defaultFilters);
  }

  if (loading) {
    return <div className="screen-center">Cargando resumen de inventario...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        actions={
          <>
            <ActionButton onClick={() => loadSummary(filters)} size="sm" type="button">
              Actualizar
            </ActionButton>
            <Link className={buttonClassName({ tone: "ghost", size: "sm" })} to="/inventario/materiales">
              Ver materiales
            </Link>
          </>
        }
        eyebrow="Inventario"
        subtitle="Alertas, valor, rotacion y movimientos para operacion diaria."
        title="Resumen operativo"
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
              hint="Consulta rapida por SKU o codigo de barras."
              label="Busqueda rapida"
              onChange={(event) => setSearchTerm(event.target.value)}
              onKeyDown={(event) => handleScannerEnter(event, handleLookup)}
              placeholder="Escanea un codigo o busca por SKU/material"
              value={searchTerm}
            />
          </form>

          <FormGrid className="inventory-summary-filter-grid">
            <Field label="Almacen">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, almacen_id: event.target.value }))}
                value={filters.almacen_id}
              >
                <option value="">Todos</option>
                {warehouses.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.nombre}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Periodo">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, periodo_dias: event.target.value }))}
                value={filters.periodo_dias}
              >
                <option value="30">Ultimos 30 dias</option>
                <option value="60">Ultimos 60 dias</option>
                <option value="90">Ultimos 90 dias</option>
              </select>
            </Field>

            <Field hint="Opcional" label="Categoria">
              <input
                onChange={(event) => setFilters((current) => ({ ...current, categoria: event.target.value }))}
                placeholder="Filtrar categoria"
                type="text"
                value={filters.categoria}
              />
            </Field>
          </FormGrid>

          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton onClick={handleApplyFilters} size="sm" tone="primary" type="button">
              Aplicar
            </ActionButton>
            <ActionButton onClick={handleResetFilters} size="sm" type="button">
              Limpiar
            </ActionButton>
          </div>

          {notice ? <p className="feature-note">{notice}</p> : null}
          {error ? <p className="form-error">{error}</p> : null}

          {lookupResult ? (
            <div className="inventory-lookup-result">
              <div className="inventory-lookup-result-main">
                <MaterialImage alt={lookupResult.nombre} size="md" src={lookupResult.imagen_url} />
                <div className="inventory-lookup-result-copy">
                  <strong>{lookupResult.nombre}</strong>
                  <div className="inventory-cell-sub">
                    {lookupResult.sku} - {lookupResult.codigo_barras || "Sin codigo de barras"}
                  </div>
                  <div className="inventory-cell-sub">
                    {safeDisplayText(lookupResult.categoria, "Sin categoria")} - Stock total {formatNumber(lookupResult.stock_total)}
                  </div>
                  <div className="inventory-cell-sub">
                    Proveedor principal: {safeDisplayText(lookupResult.proveedor_principal_nombre, "Sin proveedor")}
                  </div>
                </div>
              </div>

              <div className="inventory-actions inventory-actions-wrap">
                <ActionButton
                  onClick={() => navigate(buildMaterialsPath({ q: lookupResult.sku }))}
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
                  Ver movimientos
                </ActionButton>
              </div>

              <div className="inventory-lookup-result-meta">
                <span className="table-note">Ultima actualizacion: {formatDateTime(lookupResult.updated_at)}</span>
              </div>

              {lookupResult.stock_por_almacen?.length ? (
                <DataTable
                  columns={[
                    { key: "almacen", label: "Almacen" },
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
                <EmptyState compact note="Este material aun no tiene existencias registradas por almacen." title="Sin stock por almacen" />
              )}
            </div>
          ) : null}
        </FilterCard>
      </PageHeader>

      <SummaryKpis summary={summary} />

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Incidencias que requieren accion inmediata o de seguimiento." title="Alertas accionables">
          {topAlerts.length === 0 ? (
            <EmptyState compact note="No hay alertas operativas en este periodo." title="Sin alertas activas" />
          ) : (
            <div className="inventory-alert-stack">
              {topAlerts.map((alert, index) => (
                <article className={`inventory-alert-card ${alert.severidad}`} key={`${alert.tipo}-${index}`}>
                  <div className="inventory-alert-card-head">
                    <strong>{alert.titulo}</strong>
                    <StatusBadge tone={alert.severidad === "critical" ? "danger" : alert.severidad === "warning" ? "warning" : "info"}>
                      {alert.severidad}
                    </StatusBadge>
                  </div>
                  <p>{alert.descripcion}</p>
                  {alert.accion_label ? (
                    <div className="inventory-actions">
                      <ActionButton onClick={() => handleAlertAction(alert)} size="sm" type="button">
                        {alert.accion_label}
                      </ActionButton>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </DataCard>

        <DataCard subtitle="Atajos para compras, stock y materiales." title="Acciones rapidas">
          <div className="inventory-action-grid">
            <button className={buttonClassName({ tone: "ghost", size: "sm" })} onClick={() => setScannerOpen(true)} type="button">
              Escanear codigo
            </button>
            <Link className={buttonClassName({ tone: "primary", size: "sm" })} to="/inventario/movimientos">
              Nueva entrada
            </Link>
            <Link className={buttonClassName({ tone: "ghost", size: "sm" })} to="/inventario/requisiciones">
              Ver requisiciones
            </Link>
            <Link className={buttonClassName({ tone: "ghost", size: "sm" })} to="/inventario/ordenes-compra">
              Ver OCs
            </Link>
          </div>
        </DataCard>
      </div>

      <DataCard subtitle="Materiales agotados o por debajo del minimo definido." title="Bajo stock">
        {summary.bajo_stock.length === 0 ? (
          <EmptyState compact note="No hay materiales bajo stock en este momento." title="Sin alertas de stock" />
        ) : (
          <DataTable
            columns={[
              { key: "material", label: "Material" },
              { key: "sku", label: "SKU" },
              { key: "stock", label: "Stock actual" },
              { key: "minimo", label: "Stock minimo" },
              { key: "sugerida", label: "Sugerido pedir" },
              { key: "estado", label: "Estado" },
              { key: "requisicion", label: "Requisicion" },
              { key: "accion", label: "Accion" },
            ]}
          >
            <tbody>
              {summary.bajo_stock.map((item) => (
                <tr key={item.material_id}>
                  <td>
                    <div className="inventory-cell-main">{item.nombre}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(item.categoria, "Sin categoria")}</div>
                  </td>
                  <td>{item.sku}</td>
                  <td>{formatNumber(item.stock_total)}</td>
                  <td>{formatNumber(item.stock_minimo)}</td>
                  <td>{formatNumber(item.cantidad_sugerida)}</td>
                  <td>
                    <StockBadge minimo={item.stock_minimo} okLabel="Sano" stock={item.stock_total} zeroLabel="Agotado" />
                  </td>
                  <td>
                    {item.requisicion_pendiente ? (
                      <StatusBadge tone="info">{item.requisicion_folio || "Requisicion pendiente"}</StatusBadge>
                    ) : (
                      <span className="table-note">Sin requisicion</span>
                    )}
                  </td>
                  <td className="inventory-row-actions">
                    {item.requisicion_pendiente ? (
                      <button className="link-button" onClick={() => navigate("/inventario/requisiciones")} type="button">
                        Ver requisicion
                      </button>
                    ) : (
                      <button className="link-button" onClick={() => handleCreateRequisition(item.material_id)} type="button">
                        Crear requisicion
                      </button>
                    )}
                    <button
                      className="link-button"
                      onClick={() => navigate(buildMaterialsPath({ q: item.sku, stock_bajo: "true" }))}
                      type="button"
                    >
                      Editar material
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Materiales activos que no tienen precio de venta configurado." title="Sin precio de venta">
          {summary.sin_precio_venta.length === 0 ? (
            <EmptyState compact note="Todos los materiales visibles tienen precio de venta." title="Sin pendientes de precio" />
          ) : (
            <DataTable
              columns={[
                { key: "material", label: "Material" },
                { key: "sku", label: "SKU" },
                { key: "stock", label: "Stock" },
                { key: "precio", label: "Precio de venta" },
                { key: "accion", label: "Accion" },
              ]}
            >
              <tbody>
                {summary.sin_precio_venta.map((item) => (
                  <tr key={item.material_id}>
                    <td>{item.nombre}</td>
                    <td>{item.sku}</td>
                    <td>{formatNumber(item.stock_total)}</td>
                    <td>{formatMoney(item.precio_venta)}</td>
                    <td>
                      <button
                        className="link-button"
                        onClick={() => navigate(buildMaterialsPath({ q: item.sku, sin_precio_venta: "true" }))}
                        type="button"
                      >
                        Editar precio
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>

        <DataCard subtitle="Materiales activos sin costo de referencia ni costo promedio." title="Sin costo">
          {summary.sin_costo.length === 0 ? (
            <EmptyState compact note="Todos los materiales visibles tienen costo configurado." title="Sin pendientes de costo" />
          ) : (
            <DataTable
              columns={[
                { key: "material", label: "Material" },
                { key: "sku", label: "SKU" },
                { key: "stock", label: "Stock" },
                { key: "costo", label: "Costo actual" },
                { key: "accion", label: "Accion" },
              ]}
            >
              <tbody>
                {summary.sin_costo.map((item) => (
                  <tr key={item.material_id}>
                    <td>{item.nombre}</td>
                    <td>{item.sku}</td>
                    <td>{formatNumber(item.stock_total)}</td>
                    <td>{formatMoney(item.costo_promedio_actual || item.costo_unitario)}</td>
                    <td>
                      <button
                        className="link-button"
                        onClick={() => navigate(buildMaterialsPath({ q: item.sku, sin_costo: "true" }))}
                        type="button"
                      >
                        Actualizar costo
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      </div>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle={`Entradas y salidas acumuladas en los ultimos ${filters.periodo_dias} dias.`} title="Productos mas movidos">
          {summary.productos_mas_movidos.length === 0 ? (
            <EmptyState compact note="No hay movimientos en este periodo." title="Sin movimientos para este rango" />
          ) : (
            <DataTable
              columns={[
                { key: "material", label: "Material" },
                { key: "sku", label: "SKU" },
                { key: "entradas", label: "Entradas" },
                { key: "salidas", label: "Salidas" },
                { key: "movimientos", label: "Movimientos" },
              ]}
            >
              <tbody>
                {summary.productos_mas_movidos.map((item) => (
                  <tr key={item.material_id}>
                    <td>{item.nombre}</td>
                    <td>{item.sku}</td>
                    <td>{formatNumber(item.cantidad_entrada)}</td>
                    <td>{formatNumber(item.cantidad_salida)}</td>
                    <td>{formatNumber(item.movimientos_count)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>

        <DataCard subtitle={`Materiales con stock sin salidas recientes en ${filters.periodo_dias} dias.`} title="Baja rotacion">
          {summary.baja_rotacion.length === 0 ? (
            <EmptyState compact note="No hay materiales con baja rotacion en este periodo." title="Sin baja rotacion" />
          ) : (
            <DataTable
              columns={[
                { key: "material", label: "Material" },
                { key: "sku", label: "SKU" },
                { key: "stock", label: "Stock" },
                { key: "valor", label: "Valor retenido" },
                { key: "dias", label: "Dias sin salida" },
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

      <DataCard subtitle="Ultimos movimientos confirmados de inventario." title="Ultimos movimientos">
        {summary.ultimos_movimientos.length === 0 ? (
          <EmptyState compact note="No hay movimientos recientes para este filtro." title="Sin movimientos recientes" />
        ) : (
          <DataTable
            columns={[
              { key: "fecha", label: "Fecha" },
              { key: "tipo", label: "Tipo" },
              { key: "material", label: "Material" },
              { key: "almacen", label: "Almacen" },
              { key: "cantidad", label: "Cantidad" },
              { key: "referencia", label: "Referencia" },
              { key: "usuario", label: "Usuario" },
            ]}
          >
            <tbody>
              {summary.ultimos_movimientos.map((movement) => (
                <tr key={movement.id}>
                  <td>{formatDateTime(movement.fecha)}</td>
                  <td>
                    <StatusBadge tone={movement.tipo === "entrada" ? "success" : movement.tipo === "salida" ? "danger" : "warning"}>
                      {movement.tipo}
                    </StatusBadge>
                  </td>
                  <td>
                    <div className="inventory-cell-main">{movement.material_nombre}</div>
                    <div className="inventory-cell-sub">{movement.material_sku}</div>
                  </td>
                  <td>{movement.almacen_nombre}</td>
                  <td>{formatNumber(movement.cantidad)}</td>
                  <td>{safeDisplayText(movement.referencia, "Sin referencia")}</td>
                  <td>{safeDisplayText(movement.usuario, "No registrado")}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <BarcodeScannerModal
        helperText="Apunta la camara al codigo de barras o QR para consultar el material exacto."
        onClose={() => setScannerOpen(false)}
        onDetected={(code) => {
          handleLookup(code).finally(() => setScannerOpen(false));
        }}
        open={scannerOpen}
        title="Escanear codigo"
      />
    </div>
  );
}
