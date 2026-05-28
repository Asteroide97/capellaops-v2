import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import BarcodeScannerModal from "../components/BarcodeScannerModal";
import {
  cancelPosSale,
  createPosSale,
  getPosCatalog,
  getPosSaleDetail,
  getPosSales,
  getPosTicket,
  getWarehouses,
} from "../api/client";


const DEFAULT_PAGE_SIZE = 25;

const paymentMethodOptions = [
  { value: "efectivo", label: "Efectivo" },
  { value: "tarjeta", label: "Tarjeta" },
  { value: "transferencia", label: "Transferencia" },
  { value: "otro", label: "Otro" },
];

const catalogFilterDefaults = {
  q: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const saleFilterDefaults = {
  q: "",
  estatus: "",
  almacen_id: "",
  metodo_pago: "",
  fecha_desde: "",
  fecha_hasta: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


function formatNumber(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    minimumFractionDigits: Number.isInteger(numericValue) ? 0 : 2,
    maximumFractionDigits: 4,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


function formatMoney(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


function normalizeDecimalInput(value) {
  return value.replace(",", ".").replace(/[^\d.]/g, "");
}


function EmptyState({ title, note }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{note}</p>
    </div>
  );
}


function ResultMeta({ loaded, total, label }) {
  return <p className="table-note">Mostrando {loaded} de {total} {label}.</p>;
}


function PaginationControls({ meta, onPrevious, onNext }) {
  const canGoPrevious = meta.offset > 0;
  const canGoNext = meta.offset + meta.limit < meta.total;

  return (
    <div className="inventory-pagination">
      <span className="table-note">
        Página {Math.floor(meta.offset / meta.limit) + 1} de {Math.max(1, Math.ceil(meta.total / meta.limit))}
      </span>
      <div className="inventory-actions">
        <button className="ghost-button" disabled={!canGoPrevious} onClick={onPrevious} type="button">
          Anterior
        </button>
        <button className="ghost-button" disabled={!canGoNext} onClick={onNext} type="button">
          Siguiente
        </button>
      </div>
    </div>
  );
}


export default function POSPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [warehouses, setWarehouses] = useState([]);
  const [selectedWarehouseId, setSelectedWarehouseId] = useState("");

  const [catalogFilters, setCatalogFilters] = useState(catalogFilterDefaults);
  const [catalogItems, setCatalogItems] = useState([]);
  const [catalogMeta, setCatalogMeta] = useState({
    total: 0,
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
  });

  const [saleFilters, setSaleFilters] = useState(saleFilterDefaults);
  const [sales, setSales] = useState([]);
  const [saleMeta, setSaleMeta] = useState({
    total: 0,
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
  });

  const [cart, setCart] = useState([]);
  const [saleForm, setSaleForm] = useState({
    cliente_nombre: "",
    cliente_email: "",
    metodo_pago: "efectivo",
    monto_recibido: "",
    notas: "",
  });
  const [selectedSale, setSelectedSale] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [cancelReason, setCancelReason] = useState("");
  const [scannerOpen, setScannerOpen] = useState(false);

  const cartSubtotal = useMemo(
    () =>
      cart.reduce(
        (total, item) => total + Number(item.precio_unitario || 0) * Number(item.cantidad || 0),
        0,
      ),
    [cart],
  );
  const cartDiscountTotal = useMemo(
    () =>
      cart.reduce(
        (total, item) => total + Number(item.descuento_unitario || 0) * Number(item.cantidad || 0),
        0,
      ),
    [cart],
  );
  const cartTotal = Math.max(0, cartSubtotal - cartDiscountTotal);
  const cashReceived = Number(saleForm.monto_recibido || 0);
  const cashChangePreview =
    saleForm.metodo_pago === "efectivo" && saleForm.monto_recibido !== ""
      ? Math.max(0, cashReceived - cartTotal)
      : 0;

  async function loadWarehousesOptions() {
    const response = await getWarehouses({
      token,
      empresaId,
      filters: { activo: true, limit: 200, offset: 0 },
    });
    setWarehouses(response.items);
    if (!selectedWarehouseId && response.items.length > 0) {
      setSelectedWarehouseId(response.items[0].id);
    }
    return response.items;
  }

  async function loadCatalog(warehouseId = selectedWarehouseId, nextFilters = catalogFilters) {
    if (!warehouseId) {
      setCatalogItems([]);
      setCatalogMeta({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
      return null;
    }

    const response = await getPosCatalog({
      token,
      empresaId,
      almacenId: warehouseId,
      filters: nextFilters,
    });
    setCatalogItems(response.items);
    setCatalogMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    return response;
  }

  async function loadSales(nextFilters = saleFilters) {
    const response = await getPosSales({
      token,
      empresaId,
      filters: nextFilters,
    });
    setSales(response.items);
    setSaleMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    return response;
  }

  async function loadSaleArtifacts(saleId) {
    const [saleDetail, ticket] = await Promise.all([
      getPosSaleDetail({ saleId, token, empresaId }),
      getPosTicket({ saleId, token, empresaId }),
    ]);
    setSelectedSale(saleDetail);
    setSelectedTicket(ticket);
    setCancelReason("");
    return { saleDetail, ticket };
  }

  async function loadPosData() {
    if (!token || !empresaId) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const warehouseItems = await loadWarehousesOptions();
      const nextWarehouseId = selectedWarehouseId || warehouseItems[0]?.id || "";
      await Promise.all([
        loadCatalog(nextWarehouseId, catalogFilters),
        loadSales(saleFilters),
      ]);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar POS.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshPosData({ keepTicket = true } = {}) {
    if (!token || !empresaId) {
      return;
    }

    setRefreshing(true);
    setError("");
    try {
      await Promise.all([
        loadCatalog(selectedWarehouseId, catalogFilters),
        loadSales(saleFilters),
      ]);

      if (keepTicket && selectedSale?.id) {
        await loadSaleArtifacts(selectedSale.id);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar POS.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadPosData();
  }, [token, empresaId]);

  useEffect(() => {
    if (!selectedWarehouseId || loading) {
      return;
    }

    loadCatalog(selectedWarehouseId, catalogFilters).catch((requestError) => {
      setError(requestError.message || "No se pudo cargar el catálogo POS.");
    });
  }, [selectedWarehouseId]);

  function addToCart(item) {
    if (Number(item.existencia) <= 0) {
      setError("No hay existencias disponibles para este producto.");
      return;
    }

    setError("");
    setSuccess("");
    setCart((current) => {
      const existing = current.find((line) => line.material_id === item.material_id);
      if (existing) {
        return current.map((line) =>
          line.material_id === item.material_id
            ? { ...line, cantidad: String(Number(line.cantidad) + 1), existencia: item.existencia }
            : line,
        );
      }

      return [
        ...current,
        {
          material_id: item.material_id,
          sku: item.sku,
          nombre: item.nombre,
          unidad: item.unidad,
          precio_unitario: String(item.precio),
          descuento_unitario: "0",
          cantidad: "1",
          existencia: item.existencia,
          stock_bajo: item.stock_bajo,
        },
      ];
    });
  }

  function updateCartLine(materialId, changes) {
    setCart((current) =>
      current.map((line) =>
        line.material_id === materialId
          ? {
              ...line,
              ...changes,
            }
          : line,
      ),
    );
  }

  function removeCartLine(materialId) {
    setCart((current) => current.filter((line) => line.material_id !== materialId));
  }

  function clearCart() {
    setCart([]);
    setSaleForm({
      cliente_nombre: "",
      cliente_email: "",
      metodo_pago: "efectivo",
      monto_recibido: "",
      notas: "",
    });
  }

  async function handleCreateSale(event) {
    event.preventDefault();
    if (!selectedWarehouseId) {
      setError("Selecciona un almacén para cobrar.");
      return;
    }
    if (cart.length === 0) {
      setError("Agrega al menos un producto al carrito.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      almacen_id: selectedWarehouseId,
      cliente_nombre: saleForm.cliente_nombre || null,
      cliente_email: saleForm.cliente_email || null,
      metodo_pago: saleForm.metodo_pago,
      monto_recibido:
        saleForm.metodo_pago === "efectivo" && saleForm.monto_recibido !== ""
          ? saleForm.monto_recibido
          : null,
      notas: saleForm.notas || null,
      items: cart.map((item) => ({
        material_id: item.material_id,
        cantidad: item.cantidad,
        descuento_unitario: item.descuento_unitario || "0",
      })),
    };

    try {
      const sale = await createPosSale({ token, empresaId, payload });
      await loadSaleArtifacts(sale.id);
      clearCart();
      setSuccess(`Venta ${sale.folio} registrada correctamente.`);
      await refreshPosData({ keepTicket: false });
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar la venta.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancelSale() {
    if (!selectedSale?.id) {
      setError("Selecciona una venta para cancelarla.");
      return;
    }
    if (!cancelReason.trim()) {
      setError("Debes indicar una razón para cancelar la venta.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const sale = await cancelPosSale({
        saleId: selectedSale.id,
        token,
        empresaId,
        payload: { reason: cancelReason },
      });
      await loadSaleArtifacts(sale.id);
      setSuccess(`Venta ${sale.folio} cancelada.`);
      await refreshPosData({ keepTicket: false });
    } catch (requestError) {
      setError(requestError.message || "No se pudo cancelar la venta.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCatalogSearch(event) {
    event.preventDefault();
    setError("");
    try {
      const nextFilters = { ...catalogFilters, offset: 0 };
      setCatalogFilters(nextFilters);
      const response = await loadCatalog(selectedWarehouseId, nextFilters);
      if (nextFilters.q && response?.items?.length === 1) {
        addToCart(response.items[0]);
        setSuccess(`Código detectado: ${nextFilters.q}`);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo filtrar el catálogo.");
    }
  }

  async function handleCatalogScan(codeOverride = catalogFilters.q) {
    const code = String(codeOverride || "").trim();
    if (!code) {
      setError("Escribe o escanea un código para buscar en POS.");
      return;
    }

    setError("");
    setSuccess("");
    const nextFilters = { ...catalogFilters, q: code, offset: 0 };
    setCatalogFilters(nextFilters);

    try {
      const response = await loadCatalog(selectedWarehouseId, nextFilters);
      if (!response || response.items.length === 0) {
        setError("No se encontró ningún material con ese SKU o código de barras.");
        return;
      }

      if (response.items.length === 1) {
        addToCart(response.items[0]);
        setSuccess(`Código detectado: ${code}`);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo buscar el código en POS.");
    }
  }

  async function handleSalesSearch(event) {
    event.preventDefault();
    setError("");
    try {
      const nextFilters = { ...saleFilters, offset: 0 };
      setSaleFilters(nextFilters);
      await loadSales(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo filtrar el historial.");
    }
  }

  async function handleCatalogPageChange(nextOffset) {
    const nextFilters = { ...catalogFilters, offset: nextOffset };
    setCatalogFilters(nextFilters);
    try {
      await loadCatalog(selectedWarehouseId, nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar la página del catálogo.");
    }
  }

  async function handleSalesPageChange(nextOffset) {
    const nextFilters = { ...saleFilters, offset: nextOffset };
    setSaleFilters(nextFilters);
    try {
      await loadSales(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar la página del historial.");
    }
  }

  async function openSale(saleId) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await loadSaleArtifacts(saleId);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar la venta.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando POS...</div>;
  }

  return (
    <section className="inventory-shell">
      <div className="hero-card inventory-hero">
        <div>
          <p className="eyebrow">POS Fase 1</p>
          <h2>Cobro rápido conectado al inventario real</h2>
          <p>
            Cada venta descuenta stock automáticamente en el almacén seleccionado y deja un ticket
            básico auditable. Los pagos mixtos y el corte de caja quedan pendientes para una fase posterior.
          </p>
        </div>

        <div className="hero-grid">
          <article className="metric-card">
            <span>Almacenes activos</span>
            <strong>{warehouses.length}</strong>
          </article>
          <article className="metric-card">
            <span>Productos en catálogo</span>
            <strong>{catalogMeta.total}</strong>
          </article>
          <article className="metric-card">
            <span>Líneas en carrito</span>
            <strong>{cart.length}</strong>
          </article>
          <article className="metric-card">
            <span>Ventas listadas</span>
            <strong>{saleMeta.total}</strong>
          </article>
        </div>

        <div className="inventory-actions">
          <button className="ghost-button" disabled={refreshing} onClick={() => refreshPosData()} type="button">
            {refreshing ? "Actualizando..." : "Actualizar"}
          </button>
        </div>
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}

      {warehouses.length === 0 ? (
        <EmptyState
          title="No hay almacenes disponibles."
          note="Necesitas al menos un almacén activo para operar el punto de venta."
        />
      ) : (
        <div className="pos-grid">
          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Catálogo POS</p>
              <h2>Productos disponibles para venta</h2>
              <ResultMeta label="productos" loaded={catalogItems.length} total={catalogMeta.total} />
            </div>

            <form className="inventory-filter-grid" onSubmit={handleCatalogSearch}>
              <label>
                Almacén
                <select
                  onChange={(event) => {
                    setSelectedWarehouseId(event.target.value);
                    setCart([]);
                    setSelectedSale(null);
                    setSelectedTicket(null);
                  }}
                  value={selectedWarehouseId}
                >
                  {warehouses.map((warehouse) => (
                    <option key={warehouse.id} value={warehouse.id}>
                      {warehouse.nombre} ({warehouse.codigo})
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Buscar producto
                <input
                  onChange={(event) =>
                    setCatalogFilters((current) => ({ ...current, q: event.target.value }))
                  }
                  placeholder="SKU, nombre o código de barras"
                  type="text"
                  value={catalogFilters.q}
                />
              </label>

              <div className="inventory-actions">
                <button className="ghost-button" onClick={() => setScannerOpen(true)} type="button">
                  Escanear
                </button>
                <button className="ghost-button" type="submit">
                  Buscar
                </button>
                <button
                  className="ghost-button"
                  onClick={async () => {
                    setCatalogFilters(catalogFilterDefaults);
                    try {
                      await loadCatalog(selectedWarehouseId, catalogFilterDefaults);
                    } catch (requestError) {
                      setError(requestError.message || "No se pudo reiniciar el catálogo.");
                    }
                  }}
                  type="button"
                >
                  Limpiar
                </button>
              </div>
            </form>

            {catalogItems.length === 0 ? (
              <EmptyState
                title="Sin productos disponibles."
                note="Crea materiales activos con precio y existencia para vender desde POS."
              />
            ) : (
              <>
                <div className="pos-catalog-list">
                  {catalogItems.map((item) => (
                    <article className="mini-card pos-catalog-item" key={item.material_id}>
                      <div className="module-card-top">
                        <div>
                          <strong>{item.nombre}</strong>
                          <div className="table-note">{item.sku}</div>
                        </div>
                        <span className={`status-badge ${item.stock_bajo ? "pending" : "enabled"}`}>
                          {item.stock_bajo ? "Stock bajo" : "Disponible"}
                        </span>
                      </div>

                      <div className="pos-catalog-meta">
                        <span>{formatMoney(item.precio)}</span>
                        <span>
                          Existencia: {formatNumber(item.existencia)} {item.unidad}
                        </span>
                      </div>

                      <button
                        className="ghost-button"
                        disabled={Number(item.existencia) <= 0}
                        onClick={() => addToCart(item)}
                        type="button"
                      >
                        {Number(item.existencia) <= 0 ? "Sin stock" : "Agregar al carrito"}
                      </button>
                    </article>
                  ))}
                </div>

                <PaginationControls
                  meta={catalogMeta}
                  onNext={() => handleCatalogPageChange(catalogMeta.offset + catalogMeta.limit)}
                  onPrevious={() => handleCatalogPageChange(Math.max(0, catalogMeta.offset - catalogMeta.limit))}
                />
              </>
            )}
          </div>

          <div className="inventory-kardex-stack">
            <form className="feature-card inventory-form-card" onSubmit={handleCreateSale}>
              <div className="feature-header">
                <p className="eyebrow">Cobro</p>
                <h2>Carrito y pago</h2>
                <p>El precio unitario se toma del backend y el total final siempre se recalcula del lado servidor.</p>
              </div>

              {cart.length === 0 ? (
                <EmptyState
                  title="Tu carrito está vacío."
                  note="Agrega productos desde el catálogo para crear una venta pagada."
                />
              ) : (
                <>
                  <div className="table-wrap">
                    <table className="inventory-table">
                      <thead>
                        <tr>
                          <th>Producto</th>
                          <th>Cantidad</th>
                          <th>Precio</th>
                          <th>Descuento</th>
                          <th>Total</th>
                          <th>Acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cart.map((item) => (
                          <tr key={item.material_id}>
                            <td>
                              <strong>{item.nombre}</strong>
                              <div className="table-note">{item.sku}</div>
                              <div className="table-note">
                                Disponible: {formatNumber(item.existencia)} {item.unidad}
                              </div>
                            </td>
                            <td>
                              <input
                                min="0.0001"
                                onChange={(event) =>
                                  updateCartLine(item.material_id, {
                                    cantidad: normalizeDecimalInput(event.target.value),
                                  })
                                }
                                step="0.0001"
                                type="number"
                                value={item.cantidad}
                              />
                            </td>
                            <td>{formatMoney(item.precio_unitario)}</td>
                            <td>
                              <input
                                min="0"
                                onChange={(event) =>
                                  updateCartLine(item.material_id, {
                                    descuento_unitario: normalizeDecimalInput(event.target.value),
                                  })
                                }
                                step="0.01"
                                type="number"
                                value={item.descuento_unitario}
                              />
                            </td>
                            <td>
                              {formatMoney(
                                Number(item.cantidad || 0) *
                                  Math.max(
                                    0,
                                    Number(item.precio_unitario || 0) - Number(item.descuento_unitario || 0),
                                  ),
                              )}
                            </td>
                            <td className="inventory-row-actions">
                              <button
                                className="link-button"
                                onClick={() => removeCartLine(item.material_id)}
                                type="button"
                              >
                                Quitar
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="inventory-form-grid">
                    <label>
                      Cliente
                      <input
                        onChange={(event) =>
                          setSaleForm((current) => ({ ...current, cliente_nombre: event.target.value }))
                        }
                        placeholder="Mostrador o nombre del cliente"
                        type="text"
                        value={saleForm.cliente_nombre}
                      />
                    </label>

                    <label>
                      Correo del cliente
                      <input
                        onChange={(event) =>
                          setSaleForm((current) => ({ ...current, cliente_email: event.target.value }))
                        }
                        placeholder="cliente@dominio.com"
                        type="email"
                        value={saleForm.cliente_email}
                      />
                    </label>

                    <label>
                      Método de pago
                      <select
                        onChange={(event) =>
                          setSaleForm((current) => ({
                            ...current,
                            metodo_pago: event.target.value,
                            monto_recibido: event.target.value === "efectivo" ? current.monto_recibido : "",
                          }))
                        }
                        value={saleForm.metodo_pago}
                      >
                        {paymentMethodOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label>
                      Monto recibido
                      <input
                        disabled={saleForm.metodo_pago !== "efectivo"}
                        min="0"
                        onChange={(event) =>
                          setSaleForm((current) => ({
                            ...current,
                            monto_recibido: normalizeDecimalInput(event.target.value),
                          }))
                        }
                        placeholder={saleForm.metodo_pago === "efectivo" ? "0.00" : "Solo para efectivo"}
                        step="0.01"
                        type="number"
                        value={saleForm.monto_recibido}
                      />
                    </label>

                    <label className="inventory-form-span-2">
                      Notas
                      <textarea
                        onChange={(event) =>
                          setSaleForm((current) => ({ ...current, notas: event.target.value }))
                        }
                        rows={3}
                        value={saleForm.notas}
                      />
                    </label>
                  </div>

                  <div className="module-board">
                    <article className="mini-card">
                      <span className="eyebrow">Subtotal</span>
                      <strong>{formatMoney(cartSubtotal)}</strong>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Descuentos</span>
                      <strong>{formatMoney(cartDiscountTotal)}</strong>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Total</span>
                      <strong>{formatMoney(cartTotal)}</strong>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Cambio</span>
                      <strong>{formatMoney(cashChangePreview)}</strong>
                    </article>
                  </div>

                  <div className="inventory-actions">
                    <button className="primary-button" disabled={submitting} type="submit">
                      {submitting ? "Cobrando..." : "Cobrar"}
                    </button>
                    <button className="ghost-button" onClick={clearCart} type="button">
                      Limpiar carrito
                    </button>
                  </div>
                </>
              )}
            </form>

            <div className="feature-card inventory-table-card">
              <div className="feature-header">
                <p className="eyebrow">Ticket</p>
                <h2>Comprobante básico</h2>
              </div>

              {!selectedTicket ? (
                <EmptyState
                  title="Sin ticket activo."
                  note="Cobra una venta o abre una venta del historial para revisar su ticket."
                />
              ) : (
                <div className="inventory-kardex-stack">
                  <div className="module-board">
                    <article className="mini-card">
                      <span className="eyebrow">Folio</span>
                      <strong>{selectedTicket.folio}</strong>
                      <p>{formatDateTime(selectedTicket.fecha)}</p>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Almacén</span>
                      <strong>{selectedTicket.almacen}</strong>
                      <p>{selectedTicket.empresa}</p>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Vendedor</span>
                      <strong>{selectedTicket.vendedor}</strong>
                      <p>{selectedTicket.metodo_pago}</p>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Estatus</span>
                      <strong>{selectedTicket.estatus}</strong>
                      <p>{selectedTicket.cancel_reason || "Operación cerrada"}</p>
                    </article>
                  </div>

                  <div className="table-wrap">
                    <table className="inventory-table">
                      <thead>
                        <tr>
                          <th>SKU</th>
                          <th>Producto</th>
                          <th>Cantidad</th>
                          <th>Precio</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedTicket.productos.map((item, index) => (
                          <tr key={`${item.sku}-${index}`}>
                            <td>{item.sku}</td>
                            <td>
                              <strong>{item.nombre}</strong>
                            </td>
                            <td>{formatNumber(item.cantidad)}</td>
                            <td>{formatMoney(item.precio_unitario)}</td>
                            <td>{formatMoney(item.total_linea)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="module-board">
                    <article className="mini-card">
                      <span className="eyebrow">Subtotal</span>
                      <strong>{formatMoney(selectedTicket.subtotal)}</strong>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Descuento</span>
                      <strong>{formatMoney(selectedTicket.descuento_total)}</strong>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Total</span>
                      <strong>{formatMoney(selectedTicket.total)}</strong>
                    </article>
                    <article className="mini-card">
                      <span className="eyebrow">Cambio</span>
                      <strong>{formatMoney(selectedTicket.cambio)}</strong>
                    </article>
                  </div>

                  {selectedSale?.estatus === "pagada" ? (
                    <div className="feature-card warning">
                      <div className="feature-header">
                        <p className="eyebrow">Cancelación</p>
                        <h2>Cancelar venta</h2>
                        <p>Esta acción devuelve el stock al almacén y no se puede ejecutar dos veces.</p>
                      </div>

                      <label>
                        Razón de cancelación
                        <textarea
                          onChange={(event) => setCancelReason(event.target.value)}
                          rows={3}
                          value={cancelReason}
                        />
                      </label>

                      <button className="ghost-button" disabled={submitting} onClick={handleCancelSale} type="button">
                        {submitting ? "Cancelando..." : "Cancelar venta"}
                      </button>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Historial</p>
          <h2>Ventas registradas</h2>
          <ResultMeta label="ventas" loaded={sales.length} total={saleMeta.total} />
        </div>

        <form className="inventory-filter-grid" onSubmit={handleSalesSearch}>
          <label>
            Buscar
            <input
              onChange={(event) =>
                setSaleFilters((current) => ({ ...current, q: event.target.value }))
              }
              placeholder="Folio, cliente o notas"
              type="text"
              value={saleFilters.q}
            />
          </label>

          <label>
            Estatus
            <select
              onChange={(event) =>
                setSaleFilters((current) => ({ ...current, estatus: event.target.value }))
              }
              value={saleFilters.estatus}
            >
              <option value="">Todos</option>
              <option value="pagada">Pagada</option>
              <option value="cancelada">Cancelada</option>
            </select>
          </label>

          <label>
            Almacén
            <select
              onChange={(event) =>
                setSaleFilters((current) => ({ ...current, almacen_id: event.target.value }))
              }
              value={saleFilters.almacen_id}
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
            Método de pago
            <select
              onChange={(event) =>
                setSaleFilters((current) => ({ ...current, metodo_pago: event.target.value }))
              }
              value={saleFilters.metodo_pago}
            >
              <option value="">Todos</option>
              {paymentMethodOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            Fecha desde
            <input
              onChange={(event) =>
                setSaleFilters((current) => ({ ...current, fecha_desde: event.target.value }))
              }
              type="datetime-local"
              value={saleFilters.fecha_desde}
            />
          </label>

          <label>
            Fecha hasta
            <input
              onChange={(event) =>
                setSaleFilters((current) => ({ ...current, fecha_hasta: event.target.value }))
              }
              type="datetime-local"
              value={saleFilters.fecha_hasta}
            />
          </label>

          <div className="inventory-actions">
            <button className="ghost-button" type="submit">
              Aplicar filtros
            </button>
            <button
              className="ghost-button"
              onClick={async () => {
                setSaleFilters(saleFilterDefaults);
                try {
                  await loadSales(saleFilterDefaults);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo reiniciar el historial.");
                }
              }}
              type="button"
            >
              Limpiar
            </button>
          </div>
        </form>

        {sales.length === 0 ? (
          <EmptyState
            title="No hay ventas registradas."
            note="Las ventas cobradas desde esta pantalla aparecerán aquí."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Fecha</th>
                    <th>Almacén</th>
                    <th>Cliente</th>
                    <th>Total</th>
                    <th>Pago</th>
                    <th>Estatus</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map((sale) => (
                    <tr key={sale.id}>
                      <td>{sale.folio}</td>
                      <td>{formatDateTime(sale.created_at)}</td>
                      <td>{sale.almacen_nombre}</td>
                      <td>{sale.cliente_nombre || "Mostrador"}</td>
                      <td>{formatMoney(sale.total)}</td>
                      <td>{sale.metodo_pago}</td>
                      <td>
                        <span className={`status-badge ${sale.estatus === "pagada" ? "enabled" : "pending"}`}>
                          {sale.estatus}
                        </span>
                      </td>
                      <td className="inventory-row-actions">
                        <button className="link-button" onClick={() => openSale(sale.id)} type="button">
                          Ver ticket
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PaginationControls
              meta={saleMeta}
              onNext={() => handleSalesPageChange(saleMeta.offset + saleMeta.limit)}
              onPrevious={() => handleSalesPageChange(Math.max(0, saleMeta.offset - saleMeta.limit))}
            />
          </>
        )}
      </div>

      <BarcodeScannerModal
        helperText="Apunta la cámara al código para buscar el producto en el catálogo del almacén seleccionado."
        onClose={() => setScannerOpen(false)}
        onDetected={(code) => {
          handleCatalogScan(code).finally(() => setScannerOpen(false));
        }}
        open={scannerOpen}
        title="Escanear producto POS"
      />
    </section>
  );
}
