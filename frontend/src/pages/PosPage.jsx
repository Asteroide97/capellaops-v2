import { useEffect, useMemo, useState } from "react";
import {
  BadgeDollarSign,
  Clock3,
  CreditCard,
  History,
  PackageSearch,
  Plus,
  ReceiptText,
  ScanLine,
  ShoppingCart,
  Store,
  Ticket,
  Wallet,
} from "lucide-react";
import { useSearchParams } from "react-router-dom";

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
const POS_VIEWS = ["sell", "history", "tickets", "cash"];
const TURNOS_AVAILABLE = false;

const paymentMethodOptions = [
  { value: "efectivo", label: "Efectivo" },
  { value: "tarjeta", label: "Tarjeta" },
  { value: "transferencia", label: "Transferencia" },
  { value: "otro", label: "Otro" },
];

const viewTabs = [
  { value: "sell", label: "Vender", icon: <ShoppingCart size={16} /> },
  { value: "history", label: "Historial de Ventas", icon: <History size={16} /> },
  { value: "tickets", label: "Tickets", icon: <Ticket size={16} /> },
  { value: "cash", label: "Caja / Turnos", icon: <Wallet size={16} /> },
];

const catalogFilterDefaults = {
  q: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const saleFilterDefaults = {
  q: "",
  estatus: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


function formatMoney(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


function formatNumber(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    minimumFractionDigits: Number.isInteger(numericValue) ? 0 : 2,
    maximumFractionDigits: 4,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


function normalizeDecimalInput(value) {
  return String(value ?? "").replace(",", ".").replace(/[^\d.]/g, "");
}


function safeText(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}


function getViewTitle(view) {
  const titles = {
    sell: "Punto de Venta",
    history: "Historial de Ventas",
    tickets: "Tickets",
    cash: "Caja / Turnos",
  };
  return titles[view] ?? "Punto de Venta";
}


function getViewSubtitle(view) {
  const subtitles = {
    sell: "Cobra desde el almacén activo y descuenta inventario automáticamente.",
    history: "Consulta ventas pagadas, canceladas y suspendidas.",
    tickets: "Consulta e imprime comprobantes de venta.",
    cash: "Consulta el estado del turno y prepara el flujo de caja.",
  };
  return subtitles[view] ?? "Cobra desde el almacén activo y descuenta inventario automáticamente.";
}


function getPaymentMethodLabel(method) {
  return paymentMethodOptions.find((item) => item.value === method)?.label ?? safeText(method);
}


function getSaleStatusLabel(status) {
  const labels = {
    pagada: "Pagada",
    cancelada: "Cancelada",
    suspendida: "Suspendida",
  };
  return labels[String(status ?? "").toLowerCase()] ?? safeText(status, "Sin estatus");
}


function getSaleStatusTone(status) {
  const normalized = String(status ?? "").toLowerCase();
  if (normalized === "pagada") {
    return "success";
  }
  if (normalized === "cancelada") {
    return "danger";
  }
  if (normalized === "suspendida") {
    return "warning";
  }
  return "neutral";
}


function buildDraftStorageKey(empresaId) {
  return `capella_ops_pos_suspended_${empresaId}`;
}


function loadSuspendedDrafts(empresaId) {
  if (!empresaId) {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(buildDraftStorageKey(empresaId));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}


function persistSuspendedDrafts(empresaId, drafts) {
  if (!empresaId) {
    return;
  }

  window.localStorage.setItem(buildDraftStorageKey(empresaId), JSON.stringify(drafts));
}


function buildSuspendedDraft({ cart, saleForm, warehouse, user }) {
  const subtotal = cart.reduce(
    (total, item) => total + Number(item.precio_unitario || 0) * Number(item.cantidad || 0),
    0,
  );
  const descuentoTotal = cart.reduce(
    (total, item) => total + Number(item.descuento_unitario || 0) * Number(item.cantidad || 0),
    0,
  );
  const total = Math.max(0, subtotal - descuentoTotal);
  const createdAt = new Date().toISOString();
  const draftId = `draft-${Date.now()}`;

  return {
    id: draftId,
    source: "draft",
    folio: `SUSP-${draftId.slice(-6).toUpperCase()}`,
    created_at: createdAt,
    estatus: "suspendida",
    almacen_id: warehouse?.id ?? "",
    almacen_nombre: warehouse?.nombre ?? "",
    usuario_id: user?.id ?? "",
    vendedor_nombre: user?.full_name ?? "Usuario actual",
    cliente_nombre: saleForm.cliente_nombre || null,
    cliente_email: saleForm.cliente_email || null,
    subtotal,
    descuento_total: descuentoTotal,
    impuesto_total: 0,
    total,
    metodo_pago: saleForm.metodo_pago,
    monto_recibido: saleForm.monto_recibido || null,
    cambio: null,
    notas: saleForm.notas || null,
    items_count: cart.length,
    details: cart.map((item) => ({
      id: `${draftId}-${item.material_id}`,
      venta_id: draftId,
      material_id: item.material_id,
      sku_snapshot: item.sku,
      nombre_snapshot: item.nombre,
      cantidad: Number(item.cantidad || 0),
      precio_unitario: Number(item.precio_unitario || 0),
      descuento_unitario: Number(item.descuento_unitario || 0),
      subtotal_linea: Number(item.precio_unitario || 0) * Number(item.cantidad || 0),
      total_linea:
        Math.max(0, Number(item.precio_unitario || 0) - Number(item.descuento_unitario || 0)) *
        Number(item.cantidad || 0),
      unidad: item.unidad,
      existencia: item.existencia,
    })),
  };
}


function recordMatchesSearch(record, search) {
  const normalizedSearch = String(search ?? "").trim().toLowerCase();
  if (!normalizedSearch) {
    return true;
  }

  const haystack = [
    record.folio,
    record.cliente_nombre,
    record.cliente_email,
    record.vendedor_nombre,
    record.almacen_nombre,
    record.notas,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return haystack.includes(normalizedSearch);
}


function EmptyState({ title, note, action = null }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{note}</p>
      {action}
    </div>
  );
}


function ResultMeta({ loaded, total, label }) {
  return <p className="table-note">Mostrando {loaded} de {total} {label}.</p>;
}


function StatusBadge({ label, tone }) {
  return <span className={`status-badge ${tone}`}>{label}</span>;
}


function MetricCard({ icon, label, value, meta = "" }) {
  return (
    <article className="inventory-metric-card">
      <div className="inventory-metric-head">
        <span className="inventory-metric-icon neutral">{icon}</span>
        <div className="inventory-metric-copy">
          <span className="inventory-metric-label">{label}</span>
          <strong className="inventory-metric-value">{value}</strong>
        </div>
      </div>
      {meta ? <p className="table-note">{meta}</p> : null}
    </article>
  );
}


function PosModal({ open, title, subtitle, onClose, footer = null, children, size = "wide" }) {
  if (!open) {
    return null;
  }

  return (
    <div className="inventory-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className={`inventory-modal-shell inventory-modal-${size}`}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="inventory-modal-header">
          <div>
            <h3>{title}</h3>
            {subtitle ? <p className="table-note">{subtitle}</p> : null}
          </div>
          <button className="ghost-button" onClick={onClose} type="button">
            Cerrar
          </button>
        </div>
        <div className="inventory-modal-body">{children}</div>
        {footer ? <div className="inventory-modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
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


export default function PosPage() {
  const { token, empresaId, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeView = POS_VIEWS.includes(searchParams.get("view")) ? searchParams.get("view") : "sell";

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
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [ticketModalOpen, setTicketModalOpen] = useState(false);
  const [selectedDraft, setSelectedDraft] = useState(null);
  const [suspendedDrafts, setSuspendedDrafts] = useState([]);

  const selectedWarehouse = useMemo(
    () => warehouses.find((warehouse) => warehouse.id === selectedWarehouseId) ?? null,
    [warehouses, selectedWarehouseId],
  );

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
  const paidPreview = saleForm.metodo_pago === "efectivo" ? cashReceived : cartTotal;
  const cashChangePreview =
    saleForm.metodo_pago === "efectivo" && saleForm.monto_recibido !== ""
      ? Math.max(0, cashReceived - cartTotal)
      : 0;

  const hasCartItems = cart.length > 0;
  const cartHasInvalidQuantity = cart.some((item) => {
    const quantity = Number(item.cantidad || 0);
    return quantity <= 0 || Number.isNaN(quantity) || quantity > Number(item.existencia || 0);
  });
  const canCharge =
    Boolean(selectedWarehouseId) &&
    hasCartItems &&
    !cartHasInvalidQuantity &&
    (saleForm.metodo_pago !== "efectivo" || Number(saleForm.monto_recibido || 0) >= cartTotal);

  const historyRecords = useMemo(() => {
    const suspended = suspendedDrafts
      .filter((draft) => (saleFilters.estatus ? saleFilters.estatus === "suspendida" : true))
      .filter((draft) => recordMatchesSearch(draft, saleFilters.q))
      .map((draft) => ({ ...draft, source: "draft" }));

    const realSales = sales
      .filter((sale) => (saleFilters.estatus === "suspendida" ? false : true))
      .map((sale) => ({ ...sale, source: "sale" }));

    return [...suspended, ...realSales].sort(
      (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    );
  }, [sales, saleFilters.estatus, saleFilters.q, suspendedDrafts]);

  const historySummary = useMemo(() => {
    const records = [
      ...sales.map((item) => item.estatus),
      ...suspendedDrafts.map((item) => item.estatus),
    ];

    return {
      total: records.length,
      pagada: records.filter((status) => status === "pagada").length,
      cancelada: records.filter((status) => status === "cancelada").length,
      suspendida: records.filter((status) => status === "suspendida").length,
    };
  }, [sales, suspendedDrafts]);

  const ticketsList = useMemo(() => sales.filter((item) => ["pagada", "cancelada"].includes(item.estatus)), [sales]);

  function updateView(view) {
    const next = new URLSearchParams(searchParams);
    next.set("view", view);
    setSearchParams(next, { replace: true });
  }

  function clearFeedback() {
    setError("");
    setSuccess("");
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

  function handleNewSale() {
    clearFeedback();
    clearCart();
    setSelectedSale(null);
    setSelectedTicket(null);
    setSelectedDraft(null);
    updateView("sell");
  }

  function syncSuspendedDrafts(nextDrafts) {
    setSuspendedDrafts(nextDrafts);
    persistSuspendedDrafts(empresaId, nextDrafts);
  }

  function removeDraft(draftId) {
    const nextDrafts = suspendedDrafts.filter((draft) => draft.id !== draftId);
    syncSuspendedDrafts(nextDrafts);
  }

  function discardSelectedDraft() {
    if (!selectedDraft?.id) {
      return;
    }
    removeDraft(selectedDraft.id);
    setSelectedDraft(null);
    setDetailModalOpen(false);
    setSuccess("Venta suspendida eliminada.");
  }

  async function loadWarehousesOptions() {
    const response = await getWarehouses({
      token,
      empresaId,
      filters: { activo: true, limit: 200, offset: 0 },
    });
    setWarehouses(response.items ?? []);
    if (!selectedWarehouseId && response.items?.length) {
      setSelectedWarehouseId(response.items[0].id);
    }
    return response.items ?? [];
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

    setCatalogItems(response.items ?? []);
    setCatalogMeta({
      total: response.total ?? 0,
      limit: response.limit ?? DEFAULT_PAGE_SIZE,
      offset: response.offset ?? 0,
    });
    return response;
  }

  async function loadSales(nextFilters = saleFilters) {
    const response = await getPosSales({
      token,
      empresaId,
      filters: {
        q: nextFilters.q,
        estatus: nextFilters.estatus === "suspendida" ? "" : nextFilters.estatus,
        limit: nextFilters.limit,
        offset: nextFilters.offset,
      },
    });

    setSales(response.items ?? []);
    setSaleMeta({
      total: response.total ?? 0,
      limit: response.limit ?? DEFAULT_PAGE_SIZE,
      offset: response.offset ?? 0,
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
    setSelectedDraft(null);
    setCancelReason("");
    return { saleDetail, ticket };
  }

  async function loadPosData() {
    if (!token || !empresaId) {
      return;
    }

    setLoading(true);
    clearFeedback();
    try {
      const warehouseItems = await loadWarehousesOptions();
      const nextWarehouseId = selectedWarehouseId || warehouseItems[0]?.id || "";
      await Promise.all([loadCatalog(nextWarehouseId, catalogFilters), loadSales(saleFilters)]);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar Punto de Venta.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshPosData({ keepTicket = true } = {}) {
    if (!token || !empresaId) {
      return;
    }

    setRefreshing(true);
    clearFeedback();
    try {
      await Promise.all([loadCatalog(selectedWarehouseId, catalogFilters), loadSales(saleFilters)]);
      if (keepTicket && selectedSale?.id) {
        await loadSaleArtifacts(selectedSale.id);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar Punto de Venta.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadPosData();
  }, [token, empresaId]);

  useEffect(() => {
    setSuspendedDrafts(loadSuspendedDrafts(empresaId));
  }, [empresaId]);

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

    clearFeedback();
    setCart((current) => {
      const existing = current.find((line) => line.material_id === item.material_id);
      if (existing) {
        const nextQuantity = Math.min(Number(existing.cantidad || 0) + 1, Number(item.existencia || 0));
        return current.map((line) =>
          line.material_id === item.material_id
            ? { ...line, cantidad: String(nextQuantity), existencia: item.existencia }
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

  function updateCartLine(materialId, field, value) {
    setCart((current) =>
      current.map((line) => {
        if (line.material_id !== materialId) {
          return line;
        }

        if (field === "cantidad") {
          return { ...line, cantidad: normalizeDecimalInput(value) };
        }

        if (field === "descuento_unitario") {
          return { ...line, descuento_unitario: normalizeDecimalInput(value) };
        }

        return line;
      }),
    );
  }

  function removeCartLine(materialId) {
    setCart((current) => current.filter((line) => line.material_id !== materialId));
  }

  function applyExactAmount() {
    setSaleForm((current) => ({ ...current, monto_recibido: cartTotal ? String(cartTotal.toFixed(2)) : "" }));
  }

  function handleSuspendSale() {
    if (!selectedWarehouse) {
      setError("Selecciona un almacén para suspender la venta.");
      return;
    }
    if (!hasCartItems) {
      setError("Agrega productos antes de suspender la venta.");
      return;
    }

    const draft = buildSuspendedDraft({
      cart,
      saleForm,
      warehouse: selectedWarehouse,
      user,
    });
    syncSuspendedDrafts([draft, ...suspendedDrafts]);
    clearCart();
    setSelectedDraft(null);
    setSuccess("Venta suspendida.");
    updateView("history");
  }

  function handleResumeDraft(draft) {
    setSelectedWarehouseId(draft.almacen_id);
    setCart(
      (draft.details ?? []).map((detail) => ({
        material_id: detail.material_id,
        sku: detail.sku_snapshot,
        nombre: detail.nombre_snapshot,
        unidad: detail.unidad ?? "",
        precio_unitario: String(detail.precio_unitario ?? 0),
        descuento_unitario: String(detail.descuento_unitario ?? 0),
        cantidad: String(detail.cantidad ?? 0),
        existencia: detail.existencia ?? detail.cantidad ?? 0,
      })),
    );
    setSaleForm({
      cliente_nombre: draft.cliente_nombre ?? "",
      cliente_email: draft.cliente_email ?? "",
      metodo_pago: draft.metodo_pago ?? "efectivo",
      monto_recibido: draft.monto_recibido ? String(draft.monto_recibido) : "",
      notas: draft.notas ?? "",
    });
    removeDraft(draft.id);
    setDetailModalOpen(false);
    setSuccess(`Venta ${draft.folio} reanudada.`);
    updateView("sell");
  }

  async function handleCreateSale(event) {
    event.preventDefault();
    if (!selectedWarehouseId) {
      setError("Selecciona un almacén para vender.");
      return;
    }
    if (!hasCartItems) {
      setError("Agrega productos al carrito antes de cobrar.");
      return;
    }
    if (cartHasInvalidQuantity) {
      setError("Revisa las cantidades del carrito. No pueden exceder el stock disponible.");
      return;
    }
    if (saleForm.metodo_pago === "efectivo" && cashReceived < cartTotal) {
      setError("El monto recibido debe cubrir el total para pago en efectivo.");
      return;
    }

    setSubmitting(true);
    clearFeedback();

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
      setTicketModalOpen(true);
      updateView("tickets");
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
      setError("Escribe el motivo de cancelación.");
      return;
    }

    setSubmitting(true);
    clearFeedback();
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
    clearFeedback();
    try {
      const nextFilters = { ...catalogFilters, offset: 0 };
      setCatalogFilters(nextFilters);
      await loadCatalog(selectedWarehouseId, nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo buscar en el catálogo.");
    }
  }

  async function handleCatalogScan(codeOverride = catalogFilters.q) {
    const code = String(codeOverride || "").trim();
    if (!code) {
      setError("Escribe o escanea un código para buscar.");
      return;
    }

    clearFeedback();
    const nextFilters = { ...catalogFilters, q: code, offset: 0 };
    setCatalogFilters(nextFilters);

    try {
      const response = await loadCatalog(selectedWarehouseId, nextFilters);
      if (!response || response.items.length === 0) {
        setError("No se encontró ningún producto con ese SKU o código de barras.");
        return;
      }

      if (response.items.length === 1) {
        addToCart(response.items[0]);
        setSuccess(`Producto agregado: ${response.items[0].nombre}`);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo buscar el código en POS.");
    }
  }

  async function handleSalesSearch(event) {
    event.preventDefault();
    clearFeedback();
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

  async function openSaleDetail(record) {
    if (record.source === "draft") {
      setSelectedDraft(record);
      setSelectedSale(null);
      setSelectedTicket(null);
      setDetailModalOpen(true);
      return;
    }

    setSubmitting(true);
    clearFeedback();
    try {
      const { saleDetail, ticket } = await loadSaleArtifacts(record.id);
      setSelectedSale(saleDetail);
      setSelectedTicket(ticket);
      setSelectedDraft(null);
      setDetailModalOpen(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar la venta.");
    } finally {
      setSubmitting(false);
    }
  }

  async function openTicket(saleId) {
    setSubmitting(true);
    clearFeedback();
    try {
      await loadSaleArtifacts(saleId);
      setTicketModalOpen(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el ticket.");
    } finally {
      setSubmitting(false);
    }
  }

  function printTicket() {
    window.print();
  }

  const historyDetailFooter = selectedDraft ? (
    <div className="inventory-actions">
      <button className="primary-button" onClick={() => handleResumeDraft(selectedDraft)} type="button">
        Reanudar venta
      </button>
      <button className="ghost-button" onClick={discardSelectedDraft} type="button">
        Eliminar suspendida
      </button>
    </div>
  ) : selectedSale ? (
    <div className="inventory-actions">
      <button className="ghost-button" onClick={() => openTicket(selectedSale.id)} type="button">
        Ver ticket
      </button>
      {selectedSale.estatus === "pagada" ? (
        <button className="ghost-button" onClick={handleCancelSale} type="button">
          {submitting ? "Cancelando..." : "Cancelar venta"}
        </button>
      ) : null}
    </div>
  ) : null;

  if (loading) {
    return <div className="screen-center">Cargando Punto de Venta...</div>;
  }

  return (
    <section className="inventory-shell pos-shell-v2">
      <section className="feature-card pos-page-header">
        <div className="pos-page-header-copy">
          <h1>{getViewTitle(activeView)}</h1>
          <p className="table-note">{getViewSubtitle(activeView)}</p>
        </div>

        <div className="pos-page-header-meta">
          <StatusBadge
            label={TURNOS_AVAILABLE ? "Turno activo" : "Sin turno"}
            tone={TURNOS_AVAILABLE ? "success" : "warning"}
          />
          <label className="pos-warehouse-selector">
            <span>Almacén activo</span>
            <select
              onChange={(event) => {
                setSelectedWarehouseId(event.target.value);
                clearCart();
                setSelectedSale(null);
                setSelectedTicket(null);
                setSelectedDraft(null);
              }}
              value={selectedWarehouseId}
            >
              {warehouses.length === 0 ? <option value="">Sin almacenes</option> : null}
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.nombre} ({warehouse.codigo})
                </option>
              ))}
            </select>
          </label>
          {activeView === "sell" ? (
            <button className="primary-button" onClick={handleNewSale} type="button">
              <Plus size={16} />
              <span>Nueva venta</span>
            </button>
          ) : null}
          <button className="ghost-button" disabled={refreshing} onClick={() => refreshPosData()} type="button">
            {refreshing ? "Actualizando..." : "Actualizar"}
          </button>
        </div>

        <div className="register-stepper pos-view-nav">
          {viewTabs.map((tab) => (
            <button
              className={`register-step-pill ${activeView === tab.value ? "is-active" : ""}`}
              key={tab.value}
              onClick={() => updateView(tab.value)}
              type="button"
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </section>

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}

      {activeView === "sell" ? (
        <div className="pos-sell-layout">
          <div className="pos-sell-main">
            <section className="feature-card pos-search-card">
              <div className="feature-header">
                <h2>Busca y agrega productos</h2>
                <p className="table-note">El stock y el precio corresponden al almacén activo.</p>
              </div>

              {!selectedWarehouseId ? (
                <EmptyState note="Selecciona un almacén para vender." title="Sin almacén activo" />
              ) : (
                <form className="pos-search-form" onSubmit={handleCatalogSearch}>
                  <input
                    className="pos-search-input"
                    onChange={(event) => setCatalogFilters((current) => ({ ...current, q: event.target.value }))}
                    placeholder="Buscar por nombre, SKU o código de barras..."
                    type="text"
                    value={catalogFilters.q}
                  />
                  <div className="inventory-actions">
                    <button className="ghost-button" onClick={() => setScannerOpen(true)} type="button">
                      <ScanLine size={16} />
                      <span>Escanear</span>
                    </button>
                    <button className="ghost-button" type="submit">
                      <PackageSearch size={16} />
                      <span>Buscar</span>
                    </button>
                  </div>
                </form>
              )}
            </section>

            <section className="feature-card">
              <div className="feature-header">
                <p className="eyebrow">Productos</p>
                <h2>Catálogo disponible</h2>
                <ResultMeta label="productos" loaded={catalogItems.length} total={catalogMeta.total} />
              </div>

              {!selectedWarehouseId ? (
                <EmptyState
                  note="El catálogo del POS se carga cuando eliges un almacén activo."
                  title="Selecciona un almacén"
                />
              ) : catalogItems.length === 0 ? (
                <EmptyState
                  note="Agrega materiales activos con precio y existencias para vender desde POS."
                  title="No hay productos disponibles"
                />
              ) : (
                <>
                  <div className="pos-catalog-grid">
                    {catalogItems.map((item) => (
                      <article className="pos-catalog-card" key={item.material_id}>
                        <div className="pos-catalog-card-top">
                          <div>
                            <strong>{item.nombre}</strong>
                            <p className="table-note">{item.sku}</p>
                          </div>
                          <StatusBadge
                            label={Number(item.existencia || 0) > 0 ? "Disponible" : "Agotado"}
                            tone={Number(item.existencia || 0) > 0 ? (item.stock_bajo ? "warning" : "success") : "danger"}
                          />
                        </div>
                        <div className="pos-catalog-card-meta">
                          <span>{formatMoney(item.precio)}</span>
                          <span>
                            {formatNumber(item.existencia)} {item.unidad}
                          </span>
                        </div>
                        <button
                          className="ghost-button"
                          disabled={Number(item.existencia || 0) <= 0}
                          onClick={() => addToCart(item)}
                          type="button"
                        >
                          Agregar
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
            </section>

            <section className="feature-card">
              <div className="pos-section-header">
                <div>
                  <p className="eyebrow">Carrito</p>
                  <h2>Carrito ({cart.length} productos)</h2>
                </div>
              </div>

              {!hasCartItems ? (
                <EmptyState note="Agrega productos desde el buscador" title="El carrito está vacío" />
              ) : (
                <div className="pos-cart-list">
                  {cart.map((item) => {
                    const lineHasStockIssue = Number(item.cantidad || 0) > Number(item.existencia || 0);
                    return (
                      <article className="pos-cart-row" key={item.material_id}>
                        <div className="pos-cart-main">
                          <div>
                            <strong>{item.nombre}</strong>
                            <p className="table-note">{item.sku}</p>
                          </div>
                          <button className="link-button" onClick={() => removeCartLine(item.material_id)} type="button">
                            Quitar
                          </button>
                        </div>

                        <div className="pos-cart-grid">
                          <label>
                            Cantidad
                            <input
                              min="0.0001"
                              onChange={(event) => updateCartLine(item.material_id, "cantidad", event.target.value)}
                              step="0.0001"
                              type="number"
                              value={item.cantidad}
                            />
                          </label>
                          <label>
                            Precio
                            <input disabled type="text" value={formatMoney(item.precio_unitario)} />
                          </label>
                          <label>
                            Descuento
                            <input
                              min="0"
                              onChange={(event) =>
                                updateCartLine(item.material_id, "descuento_unitario", event.target.value)
                              }
                              step="0.01"
                              type="number"
                              value={item.descuento_unitario}
                            />
                          </label>
                          <div className="pos-cart-inline-meta">
                            <span className="table-note">
                              Disponible: {formatNumber(item.existencia)} {item.unidad}
                            </span>
                            {lineHasStockIssue ? (
                              <span className="form-error">La cantidad excede el stock disponible.</span>
                            ) : null}
                          </div>
                        </div>

                        <div className="pos-cart-total">
                          {formatMoney(
                            Number(item.cantidad || 0) *
                              Math.max(
                                0,
                                Number(item.precio_unitario || 0) - Number(item.descuento_unitario || 0),
                              ),
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

          <aside className="feature-card pos-payment-panel">
            <form className="pos-payment-form" onSubmit={handleCreateSale}>
              <div className="feature-header">
                <p className="eyebrow">Pago</p>
                <h2>Pago</h2>
                <p className="table-note">
                  {TURNOS_AVAILABLE
                    ? "Turno activo para cobrar."
                    : "Esta fase cobra directo desde el almacén activo. Caja / Turnos queda pendiente."}
                </p>
              </div>

              <div className="pos-payment-summary">
                <div>
                  <span>Subtotal</span>
                  <strong>{formatMoney(cartSubtotal)}</strong>
                </div>
                <div>
                  <span>Descuento</span>
                  <strong>{formatMoney(cartDiscountTotal)}</strong>
                </div>
                <div className="is-total">
                  <span>Total</span>
                  <strong>{formatMoney(cartTotal)}</strong>
                </div>
              </div>

              <label>
                Cliente
                <input
                  onChange={(event) => setSaleForm((current) => ({ ...current, cliente_nombre: event.target.value }))}
                  placeholder="Mostrador o nombre del cliente"
                  type="text"
                  value={saleForm.cliente_nombre}
                />
              </label>

              <label>
                Correo del cliente
                <input
                  onChange={(event) => setSaleForm((current) => ({ ...current, cliente_email: event.target.value }))}
                  placeholder="cliente@dominio.com"
                  type="email"
                  value={saleForm.cliente_email}
                />
              </label>

              <div className="pos-payment-methods">
                <span className="inventory-field-label">Método de pago</span>
                <div className="pos-payment-method-grid">
                  {paymentMethodOptions.map((option) => (
                    <button
                      className={`register-step-pill ${saleForm.metodo_pago === option.value ? "is-active" : ""}`}
                      key={option.value}
                      onClick={() =>
                        setSaleForm((current) => ({
                          ...current,
                          metodo_pago: option.value,
                          monto_recibido: option.value === "efectivo" ? current.monto_recibido : "",
                        }))
                      }
                      type="button"
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pos-payment-inline">
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

                <button
                  className="ghost-button"
                  disabled={saleForm.metodo_pago !== "efectivo" || !hasCartItems}
                  onClick={applyExactAmount}
                  type="button"
                >
                  Exacto
                </button>
              </div>

              <div className="pos-payment-summary pos-payment-secondary">
                <div>
                  <span>Total venta</span>
                  <strong>{formatMoney(cartTotal)}</strong>
                </div>
                <div>
                  <span>Pagado</span>
                  <strong>{formatMoney(paidPreview)}</strong>
                </div>
                <div>
                  <span>Cambio</span>
                  <strong>{formatMoney(cashChangePreview)}</strong>
                </div>
              </div>

              <label>
                Nota de venta
                <textarea
                  onChange={(event) => setSaleForm((current) => ({ ...current, notas: event.target.value }))}
                  placeholder="Opcional"
                  rows={3}
                  value={saleForm.notas}
                />
              </label>

              {!selectedWarehouseId ? <p className="form-error">Selecciona un almacén para vender.</p> : null}
              {cartHasInvalidQuantity ? (
                <p className="form-error">Revisa las cantidades del carrito. No pueden exceder el stock disponible.</p>
              ) : null}
              {saleForm.metodo_pago === "efectivo" && hasCartItems && cashReceived < cartTotal ? (
                <p className="form-error">El monto recibido debe cubrir el total de la venta.</p>
              ) : null}

              <button className="primary-button pos-charge-button" disabled={!canCharge || submitting} type="submit">
                {submitting ? "Cobrando..." : `Cobrar ${formatMoney(cartTotal)}`}
              </button>

              <div className="pos-bottom-actions">
                <button className="ghost-button" disabled={!hasCartItems} onClick={handleSuspendSale} type="button">
                  Suspender
                </button>
                <button className="ghost-button" disabled={!hasCartItems} onClick={clearCart} type="button">
                  Cancelar
                </button>
              </div>
            </form>
          </aside>
        </div>
      ) : null}

      {activeView === "history" ? (
        <div className="pos-view-stack">
          <section className="feature-card">
            <div className="feature-header">
              <h2>Historial de Ventas</h2>
              <p className="table-note">Consulta ventas pagadas, canceladas y suspendidas.</p>
            </div>

            <div className="inventory-metric-grid-4">
              <MetricCard icon={<ReceiptText size={18} />} label="Ventas" meta="Registros visibles" value={historySummary.total} />
              <MetricCard icon={<BadgeDollarSign size={18} />} label="Pagadas" meta="Ventas cobradas" value={historySummary.pagada} />
              <MetricCard icon={<History size={18} />} label="Canceladas" meta="Ventas revertidas" value={historySummary.cancelada} />
              <MetricCard icon={<Clock3 size={18} />} label="Suspendidas" meta="Guardadas para después" value={historySummary.suspendida} />
            </div>
          </section>

          <section className="feature-card">
            <form className="pos-history-filters" onSubmit={handleSalesSearch}>
              <label className="pos-history-search">
                <span>Buscar</span>
                <input
                  onChange={(event) => setSaleFilters((current) => ({ ...current, q: event.target.value }))}
                  placeholder="Buscar folio, cajero, cliente..."
                  type="text"
                  value={saleFilters.q}
                />
              </label>

              <label>
                <span>Estatus</span>
                <select
                  onChange={(event) => setSaleFilters((current) => ({ ...current, estatus: event.target.value }))}
                  value={saleFilters.estatus}
                >
                  <option value="">Todos los estados</option>
                  <option value="pagada">Pagada</option>
                  <option value="cancelada">Cancelada</option>
                  <option value="suspendida">Suspendida</option>
                </select>
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

            {historyRecords.length === 0 ? (
              <EmptyState note="No hay ventas registradas." title="Sin ventas todavía" />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Fecha</th>
                      <th>Cliente o cajero</th>
                      <th>Estatus</th>
                      <th>Total</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyRecords.map((record) => (
                      <tr key={`${record.source}-${record.id}`}>
                        <td>{record.folio}</td>
                        <td>{formatDateTime(record.created_at)}</td>
                        <td>{record.cliente_nombre || record.vendedor_nombre || "Mostrador"}</td>
                        <td>
                          <StatusBadge
                            label={getSaleStatusLabel(record.estatus)}
                            tone={getSaleStatusTone(record.estatus)}
                          />
                        </td>
                        <td>{formatMoney(record.total)}</td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openSaleDetail(record)} type="button">
                            Ver detalle
                          </button>
                          {record.source === "sale" ? (
                            <button className="link-button" onClick={() => openTicket(record.id)} type="button">
                              Ver ticket
                            </button>
                          ) : (
                            <button className="link-button" onClick={() => handleResumeDraft(record)} type="button">
                              Reanudar
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <PaginationControls
              meta={saleMeta}
              onNext={() => handleSalesPageChange(saleMeta.offset + saleMeta.limit)}
              onPrevious={() => handleSalesPageChange(Math.max(0, saleMeta.offset - saleMeta.limit))}
            />
          </section>
        </div>
      ) : null}

      {activeView === "tickets" ? (
        <div className="pos-view-stack">
          <section className="feature-card">
            <div className="feature-header">
              <h2>Tickets</h2>
              <p className="table-note">Consulta e imprime comprobantes de venta.</p>
            </div>

            {ticketsList.length === 0 ? (
              <EmptyState note="No hay tickets disponibles todavía." title="Sin tickets" />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Fecha</th>
                      <th>Cliente o cajero</th>
                      <th>Estatus</th>
                      <th>Total</th>
                      <th>Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ticketsList.map((sale) => (
                      <tr key={sale.id}>
                        <td>{sale.folio}</td>
                        <td>{formatDateTime(sale.created_at)}</td>
                        <td>{sale.cliente_nombre || sale.vendedor_nombre || "Mostrador"}</td>
                        <td>
                          <StatusBadge label={getSaleStatusLabel(sale.estatus)} tone={getSaleStatusTone(sale.estatus)} />
                        </td>
                        <td>{formatMoney(sale.total)}</td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openTicket(sale.id)} type="button">
                            Ver ticket
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      ) : null}

      {activeView === "cash" ? (
        <div className="pos-view-stack">
          <section className="feature-card">
            <div className="feature-header">
              <h2>Caja / Turnos</h2>
              <p className="table-note">Consulta el estado del turno y prepara el flujo de caja.</p>
            </div>

            <div className="inventory-metric-grid-3">
              <MetricCard icon={<Clock3 size={18} />} label="Estado actual" meta="Disponible en una fase siguiente" value="Sin turno" />
              <MetricCard icon={<Store size={18} />} label="Almacén activo" meta="Las ventas actuales operan desde este almacén" value={selectedWarehouse?.nombre ?? "Sin selección"} />
              <MetricCard icon={<CreditCard size={18} />} label="Cobro operativo" meta="Ventas directas disponibles hoy" value="Activo" />
            </div>

            <EmptyState
              note="Cuando Caja / Turnos esté disponible, aquí se mostrarán apertura, ingresos, retiros y cierre."
              title="No hay turno activo"
            />
          </section>
        </div>
      ) : null}

      <PosModal
        footer={historyDetailFooter}
        onClose={() => setDetailModalOpen(false)}
        open={detailModalOpen}
        subtitle={
          selectedDraft
            ? "Venta suspendida guardada localmente."
            : selectedSale
              ? "Detalle completo de la venta."
              : ""
        }
        title={selectedDraft ? "Detalle de venta suspendida" : "Detalle de venta"}
      >
        {selectedDraft ? (
          <div className="pos-modal-stack">
            <div className="pos-ticket-meta-grid">
              <article className="mini-card">
                <span className="eyebrow">Folio</span>
                <strong>{selectedDraft.folio}</strong>
                <p>{formatDateTime(selectedDraft.created_at)}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Almacén</span>
                <strong>{selectedDraft.almacen_nombre || "Sin almacén"}</strong>
                <p>{selectedDraft.vendedor_nombre}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Estatus</span>
                <strong>{getSaleStatusLabel(selectedDraft.estatus)}</strong>
                <p>{getPaymentMethodLabel(selectedDraft.metodo_pago)}</p>
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
                  {selectedDraft.details.map((item) => (
                    <tr key={item.id}>
                      <td>{item.sku_snapshot}</td>
                      <td>{item.nombre_snapshot}</td>
                      <td>{formatNumber(item.cantidad)}</td>
                      <td>{formatMoney(item.precio_unitario)}</td>
                      <td>{formatMoney(item.total_linea)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : selectedSale ? (
          <div className="pos-modal-stack">
            <div className="pos-ticket-meta-grid">
              <article className="mini-card">
                <span className="eyebrow">Folio</span>
                <strong>{selectedSale.folio}</strong>
                <p>{formatDateTime(selectedSale.created_at)}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Cliente o cajero</span>
                <strong>{selectedSale.cliente_nombre || selectedSale.vendedor_nombre || "Mostrador"}</strong>
                <p>{selectedSale.almacen_nombre}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Estatus</span>
                <strong>{getSaleStatusLabel(selectedSale.estatus)}</strong>
                <p>{getPaymentMethodLabel(selectedSale.metodo_pago)}</p>
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
                  {selectedSale.details.map((item) => (
                    <tr key={item.id}>
                      <td>{item.sku_snapshot}</td>
                      <td>{item.nombre_snapshot}</td>
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
                <strong>{formatMoney(selectedSale.subtotal)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Descuento</span>
                <strong>{formatMoney(selectedSale.descuento_total)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Total</span>
                <strong>{formatMoney(selectedSale.total)}</strong>
              </article>
            </div>

            {selectedSale.estatus === "pagada" ? (
              <label>
                Motivo de cancelación
                <textarea onChange={(event) => setCancelReason(event.target.value)} rows={3} value={cancelReason} />
              </label>
            ) : null}
          </div>
        ) : null}
      </PosModal>

      <PosModal
        footer={
          selectedTicket ? (
            <div className="inventory-actions">
              <button className="primary-button" onClick={printTicket} type="button">
                Imprimir
              </button>
            </div>
          ) : null
        }
        onClose={() => setTicketModalOpen(false)}
        open={ticketModalOpen}
        size="wide"
        subtitle="Comprobante básico imprimible."
        title="Ticket"
      >
        {!selectedTicket ? (
          <EmptyState note="Selecciona una venta para ver su ticket." title="Sin ticket activo" />
        ) : (
          <div className="pos-modal-stack pos-ticket-printable">
            <div className="pos-ticket-meta-grid">
              <article className="mini-card">
                <span className="eyebrow">Empresa</span>
                <strong>{selectedTicket.empresa}</strong>
                <p>{selectedTicket.almacen}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Folio</span>
                <strong>{selectedTicket.folio}</strong>
                <p>{formatDateTime(selectedTicket.fecha)}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Método de pago</span>
                <strong>{getPaymentMethodLabel(selectedTicket.metodo_pago)}</strong>
                <p>{selectedTicket.vendedor}</p>
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
                      <td>{item.nombre}</td>
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

            {selectedTicket.notas ? (
              <div className="feature-card warning">
                <div className="feature-header">
                  <p className="eyebrow">Nota</p>
                  <h3>Nota de venta</h3>
                </div>
                <p>{selectedTicket.notas}</p>
              </div>
            ) : null}
          </div>
        )}
      </PosModal>

      <BarcodeScannerModal
        helperText="Apunta la cámara al código para buscar el producto en el almacén activo."
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
