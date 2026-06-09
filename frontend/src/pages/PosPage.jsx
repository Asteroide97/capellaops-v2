import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeDollarSign,
  BanknoteArrowDown,
  BanknoteArrowUp,
  CircleDollarSign,
  Clock3,
  CreditCard,
  History,
  LockKeyhole,
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
  closePosShift,
  createPosSale,
  createPosShiftManualIncome,
  createPosShiftManualWithdrawal,
  getPosActiveShift,
  getPosCatalog,
  getPosSaleDetail,
  getPosSales,
  getPosTicket,
  getWarehouses,
  openPosShift,
  paySuspendedPosSale,
  resumePosSale,
  suspendPosSale,
} from "../api/client";


const DEFAULT_PAGE_SIZE = 25;
const POS_VIEWS = ["sell", "history", "tickets", "cash"];

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

const defaultSaleForm = {
  cliente_nombre: "",
  cliente_email: "",
  metodo_pago: "efectivo",
  payment_mode: "simple",
  payments: [],
  monto_recibido: "",
  descuento_global: "",
  notas: "",
};

const defaultOpenShiftForm = {
  fondo_inicial: "",
  notas: "",
};

const defaultShiftMovementForm = {
  monto: "",
  motivo: "",
};

const defaultCloseShiftForm = {
  efectivo_contado: "",
  notas: "",
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


function createPaymentDraft(method = "efectivo", amount = "", reference = "") {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    metodo: method,
    monto: amount,
    referencia: reference,
  };
}


function safeText(value, fallback = "-") {
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
  if (method === "mixto") {
    return "Pago mixto";
  }
  return paymentMethodOptions.find((item) => item.value === method)?.label ?? safeText(method);
}


function getPosUiError(requestError, fallback) {
  const rawMessage = String(requestError?.message ?? "").trim();
  const normalized = rawMessage.toLowerCase();

  if (!rawMessage) {
    return fallback;
  }
  if (requestError?.status === 404) {
    return "No se pudo cargar la información. Intenta actualizar.";
  }
  if (normalized.includes("abre caja")) {
    return "Abre caja para poder cobrar ventas.";
  }
  if (normalized.includes("stock") || normalized.includes("existenc") || normalized.includes("insuficiente")) {
    return "No hay stock suficiente.";
  }
  if (normalized.includes("precio") && normalized.includes("venta")) {
    return "Captura precio de venta para continuar.";
  }
  if (normalized.includes("descuento") && normalized.includes("subtotal")) {
    return "El descuento no puede superar el subtotal.";
  }
  if (normalized.includes("total pagado") || normalized.includes("no cubre")) {
    return "El total pagado no cubre el total de la venta.";
  }
  return rawMessage || fallback;
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


function getSaleDisplayDate(sale) {
  return sale?.paid_at || sale?.created_at || null;
}


function EmptyState({ title, note, action = null, icon = null }) {
  return (
    <div className="empty-state pos-empty-state">
      {icon ? <span className="pos-empty-state-icon">{icon}</span> : null}
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


function PosKpiCard({ icon, label, value, meta = "" }) {
  return (
    <article className="pos-kpi-card">
      <div className="pos-kpi-card-head">
        <span className="pos-kpi-card-icon">{icon}</span>
        <div className="pos-kpi-body">
          <span className="pos-kpi-title">{label}</span>
          <strong className="pos-kpi-number">{value}</strong>
          {meta ? <p className="pos-kpi-help">{meta}</p> : null}
        </div>
      </div>
    </article>
  );
}


function getPaymentState({
  selectedWarehouseId,
  hasActiveShift,
  hasCartItems,
  cartHasMissingPrice,
  cartHasInvalidQuantity,
  cartHasInvalidDiscount,
  cartHasInvalidPayments,
  totalPaid,
  cartTotal,
}) {
  if (!selectedWarehouseId) {
    return {
      tone: "warning",
      title: "Selecciona un almacén",
      note: "Selecciona un almacén para vender.",
      buttonLabel: "Selecciona almacén",
    };
  }

  if (!hasActiveShift) {
    return {
      tone: "warning",
      title: "Sin turno activo",
      note: "Abre caja para poder cobrar ventas.",
      buttonLabel: "Abrir caja primero",
    };
  }

  if (!hasCartItems) {
    return {
      tone: "neutral",
      title: "Carrito vacío",
      note: "Agrega productos al carrito.",
      buttonLabel: "Agrega productos",
    };
  }

  if (cartHasMissingPrice) {
    return {
      tone: "warning",
      title: "Precio pendiente",
      note: "Captura precio de venta para continuar.",
      buttonLabel: "Captura precio",
    };
  }

  if (cartHasInvalidQuantity) {
    return {
      tone: "warning",
      title: "Revisa cantidades",
      note: "Ajusta las cantidades para continuar.",
      buttonLabel: "Revisa cantidades",
    };
  }

  if (cartHasInvalidDiscount) {
    return {
      tone: "warning",
      title: "Descuento inválido",
      note: "El descuento no puede superar el subtotal.",
      buttonLabel: "Revisa descuento",
    };
  }

  if (cartHasInvalidPayments) {
    return {
      tone: "warning",
      title: "Pago incompleto",
      note: "El total pagado no cubre el total de la venta.",
      buttonLabel: "Completa pago",
    };
  }

  if (totalPaid < cartTotal) {
    return {
      tone: "warning",
      title: "Monto incompleto",
      note: "El total pagado no cubre el total de la venta.",
      buttonLabel: "Completa pago",
    };
  }

  return {
    tone: "success",
    title: "Venta lista",
    note: "Venta lista para cobrar.",
    buttonLabel: `Cobrar ${formatMoney(cartTotal)}`,
  };
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
  const [shiftSubmitting, setShiftSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [successContext, setSuccessContext] = useState(null);

  const [warehouses, setWarehouses] = useState([]);
  const [selectedWarehouseId, setSelectedWarehouseId] = useState("");
  const [activeShift, setActiveShift] = useState(null);

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
  const [saleForm, setSaleForm] = useState(defaultSaleForm);
  const [openShiftForm, setOpenShiftForm] = useState(defaultOpenShiftForm);
  const [shiftMovementForm, setShiftMovementForm] = useState(defaultShiftMovementForm);
  const [closeShiftForm, setCloseShiftForm] = useState(defaultCloseShiftForm);
  const [selectedSale, setSelectedSale] = useState(null);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [cancelReason, setCancelReason] = useState("");
  const [scannerOpen, setScannerOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [ticketModalOpen, setTicketModalOpen] = useState(false);
  const [resumedSaleId, setResumedSaleId] = useState("");
  const [shiftMovementModalType, setShiftMovementModalType] = useState("");
  const [closeShiftModalOpen, setCloseShiftModalOpen] = useState(false);

  const selectedWarehouse = useMemo(
    () => warehouses.find((warehouse) => warehouse.id === selectedWarehouseId) ?? null,
    [warehouses, selectedWarehouseId],
  );

  const hasActiveShift = Boolean(activeShift?.id);
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
  const netSubtotalAfterLineDiscounts = Math.max(0, cartSubtotal - cartDiscountTotal);
  const globalDiscount = Number(saleForm.descuento_global || 0);
  const cartTotal = Math.max(0, netSubtotalAfterLineDiscounts - globalDiscount);
  const usesMixedPayments = saleForm.payment_mode === "mixed";
  const paymentRows = useMemo(
    () => (Array.isArray(saleForm.payments) ? saleForm.payments : []),
    [saleForm.payments],
  );
  const cashReceived = Number(saleForm.monto_recibido || 0);
  const mixedPaymentsSummary = useMemo(() => {
    return paymentRows.reduce(
      (summary, payment) => {
        const amount = Number(payment.monto || 0);
        if (Number.isNaN(amount) || amount < 0) {
          summary.hasInvalidRow = true;
          return summary;
        }
        if (amount === 0) {
          return summary;
        }
        summary.totalPaid += amount;
        if (payment.metodo === "efectivo") {
          summary.cashPaid += amount;
        }
        return summary;
      },
      { totalPaid: 0, cashPaid: 0, hasInvalidRow: false },
    );
  }, [paymentRows]);
  const paidPreview = usesMixedPayments
    ? mixedPaymentsSummary.totalPaid
    : saleForm.metodo_pago === "efectivo"
      ? cashReceived
      : cartTotal;
  const paymentOverage = Math.max(0, paidPreview - cartTotal);
  const cashChangePreview =
    paymentOverage > 0 && paymentOverage <= (usesMixedPayments ? mixedPaymentsSummary.cashPaid : cashReceived)
      ? paymentOverage
      : 0;
  const paymentPendingPreview = Math.max(0, cartTotal - Math.min(paidPreview, cartTotal));
  const expectedCash = Number(activeShift?.efectivo_esperado || 0);
  const countedCash = Number(closeShiftForm.efectivo_contado || 0);
  const closeShiftDifference = countedCash - expectedCash;

  const hasCartItems = cart.length > 0;
  const cartHasInvalidQuantity = cart.some((item) => {
    const quantity = Number(item.cantidad || 0);
    return quantity <= 0 || Number.isNaN(quantity) || quantity > Number(item.existencia || 0);
  });
  const cartHasInvalidLineDiscount = cart.some(
    (item) => Number(item.descuento_unitario || 0) > Number(item.precio_unitario || 0),
  );
  const cartHasInvalidGlobalDiscount =
    globalDiscount < 0 || Number.isNaN(globalDiscount) || globalDiscount > netSubtotalAfterLineDiscounts;
  const cartHasInvalidDiscount = cartHasInvalidLineDiscount || cartHasInvalidGlobalDiscount;
  const cartHasMissingPrice = cart.some((item) => Number(item.precio_unitario || 0) <= 0);
  const nonCashOverageWithoutCash =
    usesMixedPayments && paymentOverage > 0 && paymentOverage > mixedPaymentsSummary.cashPaid;
  const hasMixedPaymentRows = paymentRows.length > 0;
  const hasInvalidMixedPaymentAmounts =
    usesMixedPayments &&
    (mixedPaymentsSummary.hasInvalidRow || paymentRows.some((payment) => Number(payment.monto || 0) <= 0));
  const hasInsufficientMixedPayment = usesMixedPayments && paidPreview < cartTotal;
  const cartHasInvalidPayments =
    (usesMixedPayments && (!hasMixedPaymentRows || hasInvalidMixedPaymentAmounts || nonCashOverageWithoutCash)) ||
    hasInsufficientMixedPayment;
  const canCharge =
    Boolean(selectedWarehouseId) &&
    hasActiveShift &&
    hasCartItems &&
    !cartHasInvalidQuantity &&
    !cartHasInvalidDiscount &&
    !cartHasMissingPrice &&
    !cartHasInvalidPayments &&
    paidPreview >= cartTotal &&
    (!usesMixedPayments || !nonCashOverageWithoutCash) &&
    (!usesMixedPayments || hasMixedPaymentRows);
  const paymentState = getPaymentState({
    selectedWarehouseId,
    hasActiveShift,
    hasCartItems,
    cartHasMissingPrice,
    cartHasInvalidQuantity,
    cartHasInvalidDiscount,
    cartHasInvalidPayments,
    totalPaid: paidPreview,
    cartTotal,
  });

  const historyRecords = useMemo(() => sales, [sales]);

  const historySummary = useMemo(() => {
    const records = sales.map((item) => item.estatus);

    return {
      total: records.length,
      pagada: records.filter((status) => status === "pagada").length,
      cancelada: records.filter((status) => status === "cancelada").length,
      suspendida: records.filter((status) => status === "suspendida").length,
    };
  }, [sales]);

  const ticketsList = useMemo(() => sales.filter((item) => ["pagada", "cancelada"].includes(item.estatus)), [sales]);

  function updateView(view) {
    const next = new URLSearchParams(searchParams);
    next.set("view", view);
    setSearchParams(next, { replace: true });
  }

  function clearFeedback() {
    setError("");
    setSuccess("");
    setSuccessContext(null);
  }

  function clearCart() {
    setCart([]);
    setSaleForm(defaultSaleForm);
    setResumedSaleId("");
  }

  function handleNewSale() {
    clearFeedback();
    clearCart();
    setSelectedSale(null);
    setSelectedTicket(null);
    setResumedSaleId("");
    updateView("sell");
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

  async function loadActiveShift(warehouseId = selectedWarehouseId) {
    if (!warehouseId) {
      setActiveShift(null);
      return null;
    }
    try {
      const response = await getPosActiveShift({
        token,
        empresaId,
        warehouseId,
      });
      setActiveShift(response.active_shift ?? null);
      return response.active_shift ?? null;
    } catch (requestError) {
      if (requestError?.status === 404) {
        setActiveShift(null);
        return null;
      }
      throw requestError;
    }
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
        estatus: nextFilters.estatus,
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
    const saleDetail = await getPosSaleDetail({ saleId, token, empresaId });
    const ticket =
      saleDetail.estatus === "suspendida"
        ? null
        : await getPosTicket({ saleId, token, empresaId });
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
    clearFeedback();
    try {
      const warehouseItems = await loadWarehousesOptions();
      const nextWarehouseId = selectedWarehouseId || warehouseItems[0]?.id || "";
      await Promise.all([loadCatalog(nextWarehouseId, catalogFilters), loadSales(saleFilters), loadActiveShift(nextWarehouseId)]);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setLoading(false);
    }
  }

  async function refreshPosData({ keepTicket = true, preserveFeedback = false } = {}) {
    if (!token || !empresaId) {
      return;
    }

    setRefreshing(true);
    if (!preserveFeedback) {
      clearFeedback();
    }
    try {
      await Promise.all([loadCatalog(selectedWarehouseId, catalogFilters), loadSales(saleFilters), loadActiveShift(selectedWarehouseId)]);
      if (keepTicket && selectedSale?.id) {
        await loadSaleArtifacts(selectedSale.id);
      }
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
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

    Promise.all([loadCatalog(selectedWarehouseId, catalogFilters), loadActiveShift(selectedWarehouseId)]).catch(
      (requestError) => {
        setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
      },
    );
  }, [selectedWarehouseId]);

  function addToCart(item) {
    if (Number(item.existencia) <= 0) {
      setError("No hay stock suficiente.");
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
          precio_unitario: String(item.precio ?? 0),
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

        if (field === "precio_unitario") {
          return { ...line, precio_unitario: normalizeDecimalInput(value) };
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

  function enableMixedPayments() {
    setSaleForm((current) => {
      if (current.payment_mode === "mixed") {
        return current;
      }
      return {
        ...current,
        payment_mode: "mixed",
        payments: [
          createPaymentDraft(
            current.metodo_pago === "mixto" ? "efectivo" : current.metodo_pago,
            current.metodo_pago === "efectivo"
              ? current.monto_recibido
              : cartTotal > 0
                ? String(cartTotal.toFixed(2))
                : "",
          ),
        ],
      };
    });
  }

  function disableMixedPayments() {
    setSaleForm((current) => {
      const firstMethod = current.payments?.[0]?.metodo || "efectivo";
      const cashPayment = (current.payments ?? []).find((payment) => payment.metodo === "efectivo");
      return {
        ...current,
        payment_mode: "simple",
        payments: [],
        metodo_pago: firstMethod,
        monto_recibido: firstMethod === "efectivo" ? cashPayment?.monto || "" : "",
      };
    });
  }

  function addPaymentRow() {
    setSaleForm((current) => ({
      ...current,
      payment_mode: "mixed",
      payments: [...(current.payments ?? []), createPaymentDraft("efectivo", "")],
    }));
  }

  function updatePaymentRow(paymentId, field, value) {
    setSaleForm((current) => ({
      ...current,
      payments: (current.payments ?? []).map((payment) =>
        payment.id === paymentId
          ? {
              ...payment,
              [field]: field === "monto" ? normalizeDecimalInput(value) : value,
            }
          : payment,
      ),
    }));
  }

  function removePaymentRow(paymentId) {
    setSaleForm((current) => ({
      ...current,
      payments: (current.payments ?? []).filter((payment) => payment.id !== paymentId),
    }));
  }

  function applyExactToPayment(paymentId) {
    const pendingAmount = paymentPendingPreview;
    setSaleForm((current) => ({
      ...current,
      payment_mode: "mixed",
      payments: (current.payments ?? []).map((payment) => {
        if (payment.id !== paymentId || payment.metodo !== "efectivo") {
          return payment;
        }
        const nextAmount = Number(payment.monto || 0) + pendingAmount;
        return {
          ...payment,
          monto: nextAmount > 0 ? String(nextAmount.toFixed(2)) : payment.monto,
        };
      }),
    }));
  }

  async function handleSuspendSale() {
    if (!selectedWarehouse) {
      setError("Selecciona un almacén para suspender la venta.");
      return;
    }
    if (!hasCartItems) {
      setError("Agrega productos antes de suspender la venta.");
      return;
    }
    if (cartHasInvalidQuantity) {
      setError("No hay stock suficiente.");
      return;
    }
    if (cartHasInvalidDiscount) {
      setError("El descuento no puede superar el subtotal.");
      return;
    }

    setSubmitting(true);
    clearFeedback();
    const payload = {
      almacen_id: selectedWarehouse.id,
      cliente_nombre: saleForm.cliente_nombre || null,
      cliente_email: saleForm.cliente_email || null,
      metodo_pago: usesMixedPayments ? "mixto" : saleForm.metodo_pago,
      monto_recibido: null,
      descuento_global: saleForm.descuento_global === "" ? "0" : saleForm.descuento_global,
      notas: saleForm.notas || null,
      items: cart.map((item) => ({
        material_id: item.material_id,
        cantidad: item.cantidad,
        precio_unitario: item.precio_unitario === "" ? "0" : item.precio_unitario,
        descuento_unitario: item.descuento_unitario || "0",
      })),
      payments: usesMixedPayments
        ? paymentRows
            .filter((payment) => Number(payment.monto || 0) > 0)
            .map((payment) => ({
              metodo: payment.metodo,
              monto: payment.monto,
              referencia: payment.referencia || null,
            }))
        : [],
    };

    try {
      const sale = await suspendPosSale({ token, empresaId, payload });
      clearCart();
      setResumedSaleId("");
      await refreshPosData({ keepTicket: false, preserveFeedback: true });
      setSuccess("Venta suspendida correctamente.");
      setSuccessContext({ type: "suspended", saleId: sale.id });
      updateView("history");
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo completar la acción."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResumeSale(saleId) {
    setSubmitting(true);
    clearFeedback();
    try {
      const sale = await resumePosSale({ saleId, token, empresaId });
      const stockChanged = (sale.details ?? []).some(
        (detail) => Number(detail.stock_actual ?? 0) < Number(detail.cantidad ?? 0),
      );
      setSelectedWarehouseId(sale.almacen_id);
      setCart(
        (sale.details ?? []).map((detail) => ({
          material_id: detail.material_id,
          sku: detail.sku_snapshot,
          nombre: detail.nombre_snapshot,
          unidad: detail.unidad ?? "",
          precio_unitario: String(detail.precio_unitario ?? 0),
          descuento_unitario: String(detail.descuento_unitario ?? 0),
          cantidad: String(detail.cantidad ?? 0),
          existencia: Number(detail.stock_actual ?? 0),
        })),
      );
      setSaleForm({
        cliente_nombre: sale.cliente_nombre ?? "",
        cliente_email: sale.cliente_email ?? "",
        metodo_pago:
          sale.metodo_pago && sale.metodo_pago !== "mixto"
            ? sale.metodo_pago
            : sale.payments?.[0]?.metodo || "efectivo",
        payment_mode: sale.payments?.length > 1 || sale.metodo_pago === "mixto" ? "mixed" : "simple",
        payments:
          sale.payments?.length > 0
            ? sale.payments.map((payment) =>
                createPaymentDraft(
                  payment.metodo,
                  payment.monto != null ? String(payment.monto) : "",
                  payment.referencia ?? "",
                ),
              )
            : sale.metodo_pago === "mixto"
              ? [createPaymentDraft("efectivo", "", "")]
              : [],
        monto_recibido:
          sale.payments?.length === 1 && sale.payments[0].metodo === "efectivo"
            ? String(sale.payments[0].monto ?? "")
            : "",
        descuento_global:
          sale.descuento_global != null && Number(sale.descuento_global) > 0
            ? String(sale.descuento_global)
            : "",
        notas: sale.notas ?? "",
      });
      setResumedSaleId(sale.id);
      setDetailModalOpen(false);
      updateView("sell");
      if (stockChanged) {
        setError("El stock cambió desde que se suspendió la venta.");
      } else {
        setSuccess("Venta reanudada.");
      }
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateSale(event) {
    event.preventDefault();
    if (!selectedWarehouseId) {
      setError("Selecciona un almacén para vender.");
      return;
    }
    if (!hasActiveShift) {
      setError("Abre caja para poder cobrar ventas.");
      return;
    }
    if (!hasCartItems) {
      setError("Agrega productos al carrito antes de cobrar.");
      return;
    }
    if (cartHasInvalidQuantity) {
      setError("No hay stock suficiente.");
      return;
    }
    if (cartHasInvalidDiscount) {
      setError("El descuento no puede superar el subtotal.");
      return;
    }
    if (cartHasMissingPrice) {
      setError("Captura precio de venta para continuar.");
      return;
    }
    if (usesMixedPayments && paymentRows.some((payment) => Number(payment.monto || 0) <= 0)) {
      setError("El monto del pago debe ser mayor a cero.");
      return;
    }
    if (usesMixedPayments && nonCashOverageWithoutCash) {
      setError("El cambio solo puede generarse con efectivo.");
      return;
    }
    if (paidPreview < cartTotal) {
      setError("El total pagado no cubre el total de la venta.");
      return;
    }

    setSubmitting(true);
    clearFeedback();

    const payload = {
      almacen_id: selectedWarehouseId,
      cliente_nombre: saleForm.cliente_nombre || null,
      cliente_email: saleForm.cliente_email || null,
      metodo_pago: usesMixedPayments ? "mixto" : saleForm.metodo_pago,
      monto_recibido:
        !usesMixedPayments && saleForm.metodo_pago === "efectivo" && saleForm.monto_recibido !== ""
          ? saleForm.monto_recibido
          : null,
      descuento_global: saleForm.descuento_global === "" ? "0" : saleForm.descuento_global,
      notas: saleForm.notas || null,
      items: cart.map((item) => ({
        material_id: item.material_id,
        cantidad: item.cantidad,
        precio_unitario: item.precio_unitario === "" ? "0" : item.precio_unitario,
        descuento_unitario: item.descuento_unitario || "0",
      })),
      payments: usesMixedPayments
        ? paymentRows.map((payment) => ({
            metodo: payment.metodo,
            monto: payment.monto,
            referencia: payment.referencia || null,
          }))
        : [],
    };

    try {
      const sale = resumedSaleId
        ? await paySuspendedPosSale({ saleId: resumedSaleId, token, empresaId, payload })
        : await createPosSale({ token, empresaId, payload });
      await loadSaleArtifacts(sale.id);
      clearCart();
      setResumedSaleId("");
      await refreshPosData({ keepTicket: false, preserveFeedback: true });
      setSuccess("Venta cobrada correctamente.");
      setSuccessContext({ type: "sale", saleId: sale.id, folio: sale.folio });
      setTicketModalOpen(false);
      updateView("sell");
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cobrar la venta. Intenta de nuevo."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOpenShift(event) {
    event.preventDefault();
    if (!selectedWarehouseId) {
      setError("Selecciona un almacén para abrir caja.");
      return;
    }

    setShiftSubmitting(true);
    clearFeedback();
    try {
      const shift = await openPosShift({
        token,
        empresaId,
        payload: {
          warehouse_id: selectedWarehouseId,
          fondo_inicial: openShiftForm.fondo_inicial === "" ? "0" : openShiftForm.fondo_inicial,
          notas: openShiftForm.notas || null,
        },
      });
      setActiveShift(shift);
      setOpenShiftForm(defaultOpenShiftForm);
      await refreshPosData({ keepTicket: false, preserveFeedback: true });
      setSuccess("Turno abierto correctamente.");
      updateView("sell");
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setShiftSubmitting(false);
    }
  }

  async function handleShiftMovementSubmit(event) {
    event.preventDefault();
    if (!selectedWarehouseId) {
      setError("Selecciona un almacén para registrar el movimiento.");
      return;
    }

    const payload = {
      warehouse_id: selectedWarehouseId,
      monto: shiftMovementForm.monto,
      motivo: shiftMovementForm.motivo,
    };

    setShiftSubmitting(true);
    clearFeedback();
    try {
      const shift =
        shiftMovementModalType === "ingreso"
          ? await createPosShiftManualIncome({ token, empresaId, payload })
          : await createPosShiftManualWithdrawal({ token, empresaId, payload });
      setActiveShift(shift);
      setShiftMovementForm(defaultShiftMovementForm);
      setShiftMovementModalType("");
      setSuccess(
        shiftMovementModalType === "ingreso"
          ? "Ingreso manual registrado."
          : "Retiro manual registrado.",
      );
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setShiftSubmitting(false);
    }
  }

  async function handleCloseShiftSubmit(event) {
    event.preventDefault();
    if (!selectedWarehouseId) {
      setError("Selecciona un almacén para cerrar caja.");
      return;
    }

    setShiftSubmitting(true);
    clearFeedback();
    try {
      const shift = await closePosShift({
        token,
        empresaId,
        payload: {
          warehouse_id: selectedWarehouseId,
          efectivo_contado: closeShiftForm.efectivo_contado === "" ? "0" : closeShiftForm.efectivo_contado,
          notas: closeShiftForm.notas || null,
        },
      });
      setActiveShift(null);
      setCloseShiftForm(defaultCloseShiftForm);
      setCloseShiftModalOpen(false);
      await refreshPosData({ keepTicket: false, preserveFeedback: true });
      setSuccess("Turno cerrado correctamente.");
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setShiftSubmitting(false);
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
      setSuccess("Venta cancelada correctamente.");
      await refreshPosData({ keepTicket: false, preserveFeedback: true });
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
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
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
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
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
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
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    }
  }

  async function handleCatalogPageChange(nextOffset) {
    const nextFilters = { ...catalogFilters, offset: nextOffset };
    setCatalogFilters(nextFilters);
    try {
      await loadCatalog(selectedWarehouseId, nextFilters);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    }
  }

  async function handleSalesPageChange(nextOffset) {
    const nextFilters = { ...saleFilters, offset: nextOffset };
    setSaleFilters(nextFilters);
    try {
      await loadSales(nextFilters);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    }
  }

  async function openSaleDetail(record) {
    setSubmitting(true);
    clearFeedback();
    try {
      await loadSaleArtifacts(record.id);
      setDetailModalOpen(true);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
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
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setSubmitting(false);
    }
  }

  function printTicket() {
    window.print();
  }

  const historyDetailFooter = selectedSale ? (
    <div className="inventory-actions">
      {selectedSale.estatus !== "suspendida" ? (
        <button className="ghost-button" onClick={() => openTicket(selectedSale.id)} type="button">
          Ver ticket
        </button>
      ) : null}
      {selectedSale.estatus === "suspendida" ? (
        <button className="primary-button" onClick={() => handleResumeSale(selectedSale.id)} type="button">
          Reanudar venta
        </button>
      ) : null}
      {["pagada", "suspendida"].includes(selectedSale.estatus) ? (
        <button className="ghost-button" onClick={handleCancelSale} type="button">
          {submitting ? "Cancelando..." : "Cancelar venta"}
        </button>
      ) : null}
    </div>
  ) : null;

  const activeDetailDate = selectedSale ? formatDateTime(getSaleDisplayDate(selectedSale)) : "";

  if (loading) {
    return <div className="screen-center">Cargando Punto de Venta...</div>;
  }

  return (
    <section className="inventory-shell pos-shell pos-shell-v2">
      <section className="feature-card pos-page-header">
        <div className="pos-page-header-copy">
          <h1>{getViewTitle(activeView)}</h1>
          <p className="table-note">{getViewSubtitle(activeView)}</p>
        </div>

        <div className="pos-toolbar">
          <div className="pos-status-badge">
            <StatusBadge label={hasActiveShift ? "Turno activo" : "Sin turno"} tone={hasActiveShift ? "success" : "warning"} />
          </div>
          <label className="pos-warehouse-selector">
            <span>Almacén activo</span>
            <select
              className="pos-input"
              onChange={(event) => {
                setSelectedWarehouseId(event.target.value);
                clearCart();
                setSelectedSale(null);
                setSelectedTicket(null);
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

      {error ? (
        <div className="pos-warning-box is-error">
          <strong>No se pudo completar la acción</strong>
          <p>{error}</p>
        </div>
      ) : null}
      {success ? (
        <div className="pos-warning-box is-success">
          <strong>Operación completada</strong>
          <p>{success}</p>
          {successContext?.type === "sale" ? (
            <div className="pos-action-row">
              <button className="ghost-button" onClick={() => openTicket(successContext.saleId)} type="button">
                Ver ticket
              </button>
              <button className="primary-button" onClick={handleNewSale} type="button">
                Nueva venta
              </button>
            </div>
          ) : null}
          {successContext?.type === "suspended" ? (
            <div className="pos-action-row">
              <button
                className="ghost-button"
                onClick={async () => {
                  const nextFilters = { ...saleFilterDefaults, estatus: "suspendida" };
                  setSaleFilters(nextFilters);
                  updateView("history");
                  try {
                    await loadSales(nextFilters);
                  } catch (requestError) {
                    setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
                  }
                }}
                type="button"
              >
                Ver suspendidas
              </button>
              <button className="primary-button" onClick={handleNewSale} type="button">
                Nueva venta
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {activeView === "sell" ? (
        <div className="pos-content-grid pos-sell-layout">
          <div className="pos-main-column pos-sell-main">
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
                    className="pos-input pos-search-input"
                    onChange={(event) => setCatalogFilters((current) => ({ ...current, q: event.target.value }))}
                    placeholder="Buscar por nombre, SKU o código de barras..."
                    type="text"
                    value={catalogFilters.q}
                  />
                  <div className="pos-action-row">
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
                    {catalogItems.map((item) => {
                      const hasPrice = Number(item.precio || 0) > 0;
                      return (
                        <article className="pos-product-card pos-catalog-card" key={item.material_id}>
                          <div className="pos-catalog-card-top">
                            <div>
                              <strong>{item.nombre}</strong>
                              <p className="table-note">{item.sku}</p>
                            </div>
                            <div className="inventory-badge-stack">
                              <StatusBadge
                                label={Number(item.existencia || 0) > 0 ? "Disponible" : "Agotado"}
                                tone={
                                  Number(item.existencia || 0) > 0
                                    ? item.stock_bajo
                                      ? "warning"
                                      : "success"
                                    : "danger"
                                }
                              />
                              {!hasPrice ? <StatusBadge label="Sin precio" tone="warning" /> : null}
                            </div>
                          </div>
                          <div className="pos-catalog-card-meta">
                            <span>
                              Stock: {formatNumber(item.existencia)} {item.unidad}
                            </span>
                            <strong>{formatMoney(item.precio)}</strong>
                          </div>
                          {!hasPrice ? (
                            <p className="table-note">Este producto no tiene precio de venta configurado.</p>
                          ) : null}
                          <button
                            className="ghost-button"
                            disabled={Number(item.existencia || 0) <= 0}
                            onClick={() => addToCart(item)}
                            type="button"
                          >
                            Agregar
                          </button>
                        </article>
                      );
                    })}
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
                <div className="pos-cart-total-chip">
                  <span>Total del carrito</span>
                  <strong>{formatMoney(cartTotal)}</strong>
                </div>
              </div>

              {!hasCartItems ? (
                <EmptyState note="Agrega productos desde el buscador" title="El carrito está vacío" />
              ) : (
                <div className="pos-cart-list">
                  {cart.map((item) => {
                    const lineHasStockIssue = Number(item.cantidad || 0) > Number(item.existencia || 0);
                    const lineHasMissingPrice = Number(item.precio_unitario || 0) <= 0;
                    return (
                      <article className="pos-cart-item pos-cart-row" key={item.material_id}>
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
                              className="pos-input"
                              min="0.0001"
                              onChange={(event) => updateCartLine(item.material_id, "cantidad", event.target.value)}
                              step="0.0001"
                              type="number"
                              value={item.cantidad}
                            />
                          </label>
                          <label>
                            Precio
                            <input
                              className={`pos-input ${lineHasMissingPrice ? "is-warning" : ""}`}
                              min="0"
                              onChange={(event) =>
                                updateCartLine(item.material_id, "precio_unitario", event.target.value)
                              }
                              placeholder="0.00"
                              step="0.01"
                              type="number"
                              value={item.precio_unitario}
                            />
                          </label>
                          <label>
                            Descuento
                            <input
                              className="pos-input"
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
                            {lineHasMissingPrice ? (
                              <span className="table-note inventory-value-negative">Captura precio de venta.</span>
                            ) : null}
                            {lineHasStockIssue ? (
                              <span className="form-error">No hay stock suficiente.</span>
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
                  {hasActiveShift
                    ? `Turno activo: ${safeText(activeShift?.folio)}`
                    : "Abre caja para poder cobrar ventas."}
                </p>
              </div>

              <div className={`pos-warning-box ${paymentState.tone === "success" ? "is-success" : "is-warning"}`}>
                <div className="pos-inline-alert">
                  {paymentState.tone === "success" ? <BadgeDollarSign size={18} /> : <LockKeyhole size={18} />}
                  <div>
                    <strong>{paymentState.title}</strong>
                    <p>{paymentState.note}</p>
                  </div>
                </div>
                {!hasActiveShift ? (
                  <button className="ghost-button" onClick={() => updateView("cash")} type="button">
                    Abrir caja
                  </button>
                ) : null}
              </div>

              <div className="pos-payment-summary">
                <div>
                  <span>Subtotal</span>
                  <strong>{formatMoney(cartSubtotal)}</strong>
                </div>
                <div>
                  <span>Descuentos de línea</span>
                  <strong>{formatMoney(cartDiscountTotal)}</strong>
                </div>
                <label className="pos-payment-inline-field">
                  <span>Descuento global</span>
                  <input
                    className={`pos-input ${cartHasInvalidGlobalDiscount ? "is-warning" : ""}`}
                    min="0"
                    onChange={(event) =>
                      setSaleForm((current) => ({
                        ...current,
                        descuento_global: normalizeDecimalInput(event.target.value),
                      }))
                    }
                    placeholder="0.00"
                    step="0.01"
                    type="number"
                    value={saleForm.descuento_global}
                  />
                </label>
                <div className="is-total">
                  <span>Total</span>
                  <strong>{formatMoney(cartTotal)}</strong>
                </div>
              </div>

              {cartHasInvalidGlobalDiscount ? (
                <p className="form-error">El descuento no puede superar el subtotal.</p>
              ) : null}

              <label>
                Cliente
                <input
                  className="pos-input"
                  onChange={(event) => setSaleForm((current) => ({ ...current, cliente_nombre: event.target.value }))}
                  placeholder="Mostrador o nombre del cliente"
                  type="text"
                  value={saleForm.cliente_nombre}
                />
              </label>

              <label>
                Correo del cliente
                <input
                  className="pos-input"
                  onChange={(event) => setSaleForm((current) => ({ ...current, cliente_email: event.target.value }))}
                  placeholder="cliente@dominio.com"
                  type="email"
                  value={saleForm.cliente_email}
                />
              </label>

              <div className="pos-payment-methods">
                <div className="pos-payment-mode-row">
                  <span className="inventory-field-label">Cobro</span>
                  <button
                    className="link-button"
                    onClick={usesMixedPayments ? disableMixedPayments : enableMixedPayments}
                    type="button"
                  >
                    {usesMixedPayments ? "Volver a pago simple" : "Pago mixto"}
                  </button>
                </div>

                {!usesMixedPayments ? (
                  <>
                    <div className="pos-payment-method-grid">
                      {paymentMethodOptions.map((option) => (
                        <button
                          className={`register-step-pill ${saleForm.metodo_pago === option.value ? "is-active" : ""}`}
                          key={option.value}
                          onClick={() =>
                            setSaleForm((current) => ({
                              ...current,
                              metodo_pago: option.value,
                              payment_mode: "simple",
                              payments: [],
                              monto_recibido: option.value === "efectivo" ? current.monto_recibido : "",
                            }))
                          }
                          type="button"
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>

                    <div className="pos-payment-inline">
                      <label>
                        Monto recibido
                        <input
                          className="pos-input"
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
                  </>
                ) : (
                  <div className="pos-mixed-payments">
                    <div className="pos-action-row">
                      <button className="ghost-button" onClick={addPaymentRow} type="button">
                        Agregar pago
                      </button>
                    </div>

                    {(paymentRows ?? []).map((payment) => (
                      <div className="pos-payment-row" key={payment.id}>
                        <div className="pos-payment-grid">
                          <label>
                            Método
                            <select
                              className="pos-input"
                              onChange={(event) => updatePaymentRow(payment.id, "metodo", event.target.value)}
                              value={payment.metodo}
                            >
                              {paymentMethodOptions.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          </label>

                          <label>
                            Monto
                            <input
                              className={`pos-input ${
                                Number(payment.monto || 0) <= 0 ? "is-warning" : ""
                              }`}
                              min="0.01"
                              onChange={(event) => updatePaymentRow(payment.id, "monto", event.target.value)}
                              placeholder="0.00"
                              step="0.01"
                              type="number"
                              value={payment.monto}
                            />
                          </label>

                          <label>
                            Referencia
                            <input
                              className="pos-input"
                              onChange={(event) => updatePaymentRow(payment.id, "referencia", event.target.value)}
                              placeholder="Opcional"
                              type="text"
                              value={payment.referencia}
                            />
                          </label>
                        </div>

                        <div className="pos-action-row">
                          {payment.metodo === "efectivo" ? (
                            <button className="ghost-button" onClick={() => applyExactToPayment(payment.id)} type="button">
                              Exacto
                            </button>
                          ) : null}
                          <button className="link-button" onClick={() => removePaymentRow(payment.id)} type="button">
                            Quitar
                          </button>
                        </div>
                      </div>
                    ))}

                    {nonCashOverageWithoutCash ? (
                      <p className="form-error">El cambio solo puede generarse con efectivo.</p>
                    ) : null}
                  </div>
                )}
              </div>

              <div className="pos-payment-summary pos-payment-secondary">
                <div>
                  <span>Total venta</span>
                  <strong>{formatMoney(cartTotal)}</strong>
                </div>
                <div>
                  <span>Total pagado</span>
                  <strong>{formatMoney(paidPreview)}</strong>
                </div>
                <div>
                  <span>Pendiente</span>
                  <strong>{formatMoney(paymentPendingPreview)}</strong>
                </div>
                <div>
                  <span>Cambio</span>
                  <strong>{formatMoney(cashChangePreview)}</strong>
                </div>
              </div>

              <label>
                Nota de venta
                <textarea
                  className="pos-textarea"
                  onChange={(event) => setSaleForm((current) => ({ ...current, notas: event.target.value }))}
                  placeholder="Opcional"
                  rows={3}
                  value={saleForm.notas}
                />
              </label>

              <button className="primary-button pos-charge-button" disabled={!canCharge || submitting} type="submit">
                {submitting ? "Cobrando..." : canCharge ? `Cobrar ${formatMoney(cartTotal)}` : paymentState.buttonLabel}
              </button>

              <div className="pos-action-row pos-bottom-actions">
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
          <section className="feature-card pos-section-card">
            <div className="feature-header">
              <p className="eyebrow">Resumen</p>
              <p className="table-note">Consulta ventas pagadas, canceladas y suspendidas.</p>
            </div>

            <div className="pos-kpi-grid pos-kpi-grid-compact">
              <PosKpiCard icon={<ReceiptText size={18} />} label="Ventas" meta="Registros visibles" value={historySummary.total} />
              <PosKpiCard icon={<BadgeDollarSign size={18} />} label="Pagadas" meta="Ventas cobradas" value={historySummary.pagada} />
              <PosKpiCard icon={<History size={18} />} label="Canceladas" meta="Ventas revertidas" value={historySummary.cancelada} />
              <PosKpiCard icon={<Clock3 size={18} />} label="Suspendidas" meta="Guardadas para después" value={historySummary.suspendida} />
            </div>
          </section>

          <section className="feature-card pos-section-card">
            <form className="pos-history-filters" onSubmit={handleSalesSearch}>
              <label className="pos-history-search">
                <span>Buscar</span>
                <input
                  className="pos-input"
                  onChange={(event) => setSaleFilters((current) => ({ ...current, q: event.target.value }))}
                  placeholder="Buscar folio, cajero, cliente..."
                  type="text"
                  value={saleFilters.q}
                />
              </label>

              <label>
                <span>Estatus</span>
                <select
                  className="pos-input"
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
                      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
                    }
                  }}
                  type="button"
                >
                  Limpiar
                </button>
              </div>
            </form>

            {historyRecords.length === 0 ? (
              <EmptyState icon={<ReceiptText size={18} />} note="No hay ventas registradas." title="Sin ventas" />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Fecha</th>
                      <th>Cliente o cajero</th>
                      <th>Método</th>
                      <th>Estatus</th>
                      <th>Total</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyRecords.map((record) => (
                      <tr key={record.id}>
                        <td>{record.folio}</td>
                        <td>{formatDateTime(getSaleDisplayDate(record))}</td>
                        <td>
                          <div className="pos-record-copy">
                            <strong>{record.cliente_nombre || "Mostrador"}</strong>
                            <span className="table-note">
                              {record.vendedor_nombre || "Sin cajero"}
                              {record.turno_folio ? ` · ${record.turno_folio}` : ""}
                            </span>
                          </div>
                        </td>
                        <td>{getPaymentMethodLabel(record.metodo_pago)}</td>
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
                          {record.estatus === "suspendida" ? (
                            <button className="link-button" onClick={() => handleResumeSale(record.id)} type="button">
                              Reanudar
                            </button>
                          ) : null}
                          {record.estatus !== "suspendida" ? (
                            <button className="link-button" onClick={() => openTicket(record.id)} type="button">
                              Ver ticket
                            </button>
                          ) : null}
                          {record.estatus === "pagada" ? (
                            <button className="link-button" onClick={() => openSaleDetail(record)} type="button">
                              Cancelar
                            </button>
                          ) : null}
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
          <section className="feature-card pos-section-card">
            <div className="feature-header">
              <p className="eyebrow">Comprobantes</p>
              <p className="table-note">Consulta e imprime comprobantes de venta.</p>
            </div>

            {ticketsList.length === 0 ? (
              <EmptyState
                icon={<Ticket size={18} />}
                note="Cuando cobres ventas, sus tickets aparecerán aquí."
                title="No hay tickets disponibles todavía."
              />
            ) : (
              <div className="pos-ticket-list">
                {ticketsList.map((sale) => (
                  <article className="pos-ticket-row" key={sale.id}>
                    <div>
                      <strong>{sale.folio}</strong>
                      <p className="table-note">{formatDateTime(getSaleDisplayDate(sale))}</p>
                    </div>
                    <div>
                      <span className="table-note">Método</span>
                      <strong>{getPaymentMethodLabel(sale.metodo_pago)}</strong>
                    </div>
                    <div>
                      <span className="table-note">Total</span>
                      <strong>{formatMoney(sale.total)}</strong>
                    </div>
                    <div className="pos-ticket-row-actions">
                      <StatusBadge label={getSaleStatusLabel(sale.estatus)} tone={getSaleStatusTone(sale.estatus)} />
                      <button className="link-button" onClick={() => openTicket(sale.id)} type="button">
                        Ver ticket
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}

      {activeView === "cash" ? (
        <div className="pos-view-stack">
          <section className="feature-card pos-section-card">
            <div className="feature-header">
              <p className="eyebrow">Resumen</p>
              <p className="table-note">Consulta el estado del turno y prepara el flujo de caja.</p>
            </div>

            <div className="pos-kpi-grid pos-kpi-grid-compact">
              <PosKpiCard
                icon={<Clock3 size={18} />}
                label="Estado actual"
                meta={selectedWarehouse?.nombre ? `Almacén: ${selectedWarehouse.nombre}` : "Selecciona un almacén"}
                value={hasActiveShift ? "Turno activo" : "Sin turno"}
              />
              <PosKpiCard
                icon={<Store size={18} />}
                label="Almacén activo"
                meta="Las ventas POS usan este almacén"
                value={selectedWarehouse?.nombre ?? "Sin selección"}
              />
              <PosKpiCard
                icon={<CircleDollarSign size={18} />}
                label="Efectivo esperado"
                meta="Fondo inicial + ventas en efectivo + ingresos - retiros"
                value={hasActiveShift ? formatMoney(activeShift?.efectivo_esperado) : formatMoney(0)}
              />
            </div>
          </section>

          {!selectedWarehouseId ? (
            <section className="feature-card">
              <EmptyState note="Selecciona un almacén para operar caja." title="Sin almacén activo" />
            </section>
          ) : null}

          {selectedWarehouseId && !hasActiveShift ? (
            <section className="pos-cash-empty-layout">
              <article className="feature-card pos-form-card">
                <div className="feature-header">
                  <h2>Sin turno activo</h2>
                  <p className="table-note">Abre caja para poder cobrar ventas.</p>
                </div>
                <div className="pos-warning-box is-warning">
                  <strong>Cobro bloqueado</strong>
                  <p>El catálogo puede consultarse, pero el cobro se habilita hasta abrir caja.</p>
                </div>
                <div className="pos-kpi-grid pos-kpi-grid-compact">
                  <PosKpiCard icon={<Store size={18} />} label="Almacén activo" value={selectedWarehouse?.nombre ?? "Sin selección"} meta="Origen de ventas POS" />
                  <PosKpiCard icon={<CircleDollarSign size={18} />} label="Efectivo esperado" value={formatMoney(0)} meta="Se actualizará al abrir turno" />
                </div>
              </article>

              <article className="feature-card pos-form-card">
                <div className="feature-header">
                  <h2>Abrir caja</h2>
                  <p className="table-note">Define el fondo inicial y una nota opcional de apertura.</p>
                </div>

                <form className="pos-cash-form pos-form-grid" onSubmit={handleOpenShift}>
                  <label>
                    Fondo inicial
                    <input
                      className="pos-input"
                      min="0"
                      onChange={(event) =>
                        setOpenShiftForm((current) => ({
                          ...current,
                          fondo_inicial: normalizeDecimalInput(event.target.value),
                        }))
                      }
                      placeholder="0.00"
                      step="0.01"
                      type="number"
                      value={openShiftForm.fondo_inicial}
                    />
                  </label>

                  <label className="inventory-form-span-2">
                    Notas de apertura
                    <textarea
                      className="pos-textarea"
                      onChange={(event) =>
                        setOpenShiftForm((current) => ({
                          ...current,
                          notas: event.target.value,
                        }))
                      }
                      placeholder="Opcional"
                      rows={4}
                      value={openShiftForm.notas}
                    />
                  </label>

                  <div className="pos-action-row inventory-form-span-2">
                    <button className="primary-button" disabled={shiftSubmitting} type="submit">
                      {shiftSubmitting ? "Abriendo..." : "Abrir turno"}
                    </button>
                  </div>
                </form>
              </article>
            </section>
          ) : null}

          {selectedWarehouseId && hasActiveShift ? (
            <section className="feature-card pos-section-card">
              <div className="feature-header">
                <h2>Turno en curso</h2>
                <p className="table-note">Resumen operativo de la caja actual.</p>
              </div>

              <div className="pos-kpi-grid pos-kpi-grid-compact">
                <PosKpiCard icon={<Wallet size={18} />} label="Fondo inicial" meta={activeShift.folio} value={formatMoney(activeShift.fondo_inicial)} />
                <PosKpiCard icon={<BadgeDollarSign size={18} />} label="Ventas cobradas" meta={`${activeShift.ventas_count} ventas`} value={formatMoney(activeShift.total_bruto)} />
                <PosKpiCard icon={<ReceiptText size={18} />} label="Núm. ventas" meta="Operaciones cobradas" value={formatNumber(activeShift.ventas_count)} />
                <PosKpiCard icon={<Clock3 size={18} />} label="Apertura" meta="Inicio del turno" value={formatDateTime(activeShift.opened_at)} />
                <PosKpiCard
                  icon={<History size={18} />}
                  label="Ventas canceladas"
                  meta={`${formatNumber(activeShift.ventas_canceladas_count)} cancelaciones`}
                  value={formatMoney(activeShift.ventas_canceladas_total)}
                />
                <PosKpiCard
                  icon={<CircleDollarSign size={18} />}
                  label="Total neto"
                  meta="Ventas cobradas menos cancelaciones"
                  value={formatMoney(activeShift.total_neto)}
                />
                <PosKpiCard icon={<BanknoteArrowUp size={18} />} label="Ingresos manuales" meta="Ajustes de caja" value={formatMoney(activeShift.ingresos_manuales)} />
                <PosKpiCard icon={<BanknoteArrowDown size={18} />} label="Retiros manuales" meta="Salidas manuales" value={formatMoney(activeShift.retiros_manuales)} />
              </div>

              <div className="pos-kpi-grid pos-kpi-grid-compact">
                <PosKpiCard icon={<CircleDollarSign size={18} />} label="Efectivo" meta="Ventas en efectivo" value={formatMoney(activeShift.total_efectivo)} />
                <PosKpiCard icon={<CreditCard size={18} />} label="Tarjeta" meta="Ventas con tarjeta" value={formatMoney(activeShift.total_tarjeta)} />
                <PosKpiCard icon={<ReceiptText size={18} />} label="Transferencia" meta="Ventas por transferencia" value={formatMoney(activeShift.total_transferencia)} />
                <PosKpiCard icon={<Ticket size={18} />} label="Otro" meta="Otros cobros" value={formatMoney(activeShift.total_otro)} />
              </div>

              <div className="pos-action-row">
                <button className="ghost-button" onClick={() => setShiftMovementModalType("ingreso")} type="button">
                  <BanknoteArrowUp size={16} />
                  <span>Ingreso manual</span>
                </button>
                <button className="ghost-button" onClick={() => setShiftMovementModalType("retiro")} type="button">
                  <BanknoteArrowDown size={16} />
                  <span>Retiro manual</span>
                </button>
                <button
                  className="primary-button"
                  onClick={() => {
                    setCloseShiftForm((current) => ({
                      ...current,
                      efectivo_contado: expectedCash ? String(expectedCash.toFixed(2)) : "",
                    }));
                    setCloseShiftModalOpen(true);
                  }}
                  type="button"
                >
                  Cerrar turno
                </button>
              </div>

              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Tipo</th>
                      <th>Monto</th>
                      <th>Motivo</th>
                      <th>Usuario</th>
                      <th>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeShift.movimientos.length === 0 ? (
                      <tr>
                        <td colSpan={5}>
                          <p className="table-note">No hay movimientos manuales en este turno.</p>
                        </td>
                      </tr>
                    ) : (
                      activeShift.movimientos.map((movement) => (
                        <tr key={movement.id}>
                          <td>{movement.tipo === "ingreso" ? "Ingreso manual" : "Retiro manual"}</td>
                          <td>{formatMoney(movement.monto)}</td>
                          <td>{movement.motivo}</td>
                          <td>{movement.usuario_nombre}</td>
                          <td>{formatDateTime(movement.created_at)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </div>
      ) : null}

      <PosModal
        footer={historyDetailFooter}
        onClose={() => setDetailModalOpen(false)}
        open={detailModalOpen}
        subtitle={selectedSale ? "Detalle completo de la venta." : ""}
        title={selectedSale?.estatus === "suspendida" ? "Detalle de venta suspendida" : "Detalle de venta"}
      >
        {selectedSale ? (
          <div className="pos-modal-stack">
            <div className="pos-ticket-meta-grid">
              <article className="mini-card">
                <span className="eyebrow">Folio</span>
                <strong>{selectedSale.folio}</strong>
                <p>{activeDetailDate}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Cliente o cajero</span>
                <strong>{selectedSale.cliente_nombre || selectedSale.vendedor_nombre || "Mostrador"}</strong>
                <p>{selectedSale.almacen_nombre || "Sin almacén"}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Estatus</span>
                <strong>{getSaleStatusLabel(selectedSale.estatus)}</strong>
                <p>{getPaymentMethodLabel(selectedSale.metodo_pago)}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Turno / caja</span>
                <strong>{selectedSale.turno_folio || "Sin turno"}</strong>
                <p>{selectedSale.vendedor_nombre || "Mostrador"}</p>
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
                    <th>Descuento</th>
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
                      <td>{formatMoney(item.descuento_unitario)}</td>
                      <td>{formatMoney(item.total_linea)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="module-board">
              <article className="mini-card">
                <span className="eyebrow">Subtotal bruto</span>
                <strong>{formatMoney(selectedSale.subtotal)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Descuentos de línea</span>
                <strong>{formatMoney(selectedSale.descuento_lineas_total)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Descuento global</span>
                <strong>{formatMoney(selectedSale.descuento_global)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Descuento total</span>
                <strong>{formatMoney(selectedSale.descuento_total)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Total</span>
                <strong>{formatMoney(selectedSale.total)}</strong>
              </article>
            </div>

            <section className="feature-card pos-note-card">
              <div className="feature-header">
                <p className="eyebrow">Pagos</p>
                <h3>{selectedSale.metodo_pago === "mixto" ? "Pago mixto" : "Pago registrado"}</h3>
              </div>
              {selectedSale.payments?.length ? (
                <div className="pos-payment-breakdown">
                  {selectedSale.payments.map((payment) => (
                    <div className="pos-payment-breakdown-row" key={payment.id}>
                      <div>
                        <strong>{getPaymentMethodLabel(payment.metodo)}</strong>
                        <p>{payment.referencia || "Sin referencia"}</p>
                      </div>
                      <strong>{formatMoney(payment.monto)}</strong>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="table-note">Esta venta no tiene pagos registrados porque sigue suspendida.</p>
              )}
            </section>

            {selectedSale.notas ? (
              <div className="feature-card pos-note-card">
                <div className="feature-header">
                  <p className="eyebrow">Nota</p>
                  <h3>Nota de venta</h3>
                </div>
                <p>{selectedSale.notas}</p>
              </div>
            ) : null}

            {selectedSale.estatus === "cancelada" && selectedSale.cancel_reason ? (
              <div className="pos-warning-box">
                <strong>Venta cancelada</strong>
                <p>{selectedSale.cancel_reason}</p>
              </div>
            ) : null}

            {["pagada", "suspendida"].includes(selectedSale.estatus) ? (
              <label>
                Motivo de cancelación
                <textarea className="pos-textarea" onChange={(event) => setCancelReason(event.target.value)} rows={3} value={cancelReason} />
              </label>
            ) : null}
          </div>
        ) : null}
      </PosModal>

      <PosModal
        footer={
          selectedTicket ? (
            <div className="inventory-actions">
              <button className="ghost-button" onClick={() => setTicketModalOpen(false)} type="button">
                Cerrar
              </button>
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
            {selectedTicket.estatus === "cancelada" ? (
              <div className="pos-warning-box">
                <strong>VENTA CANCELADA</strong>
                <p>{selectedTicket.cancel_reason || "Esta venta fue cancelada."}</p>
              </div>
            ) : null}
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
              <article className="mini-card">
                <span className="eyebrow">Cliente</span>
                <strong>{selectedTicket.cliente_nombre || "Mostrador"}</strong>
                <p>{selectedTicket.turno_folio || "Sin turno"}</p>
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
                    <th>Descuento</th>
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
                      <td>{formatMoney(item.descuento_unitario)}</td>
                      <td>{formatMoney(item.total_linea)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="module-board">
              <article className="mini-card">
                <span className="eyebrow">Subtotal bruto</span>
                <strong>{formatMoney(selectedTicket.subtotal)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Descuentos de línea</span>
                <strong>{formatMoney(selectedTicket.descuento_lineas_total)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Descuento global</span>
                <strong>{formatMoney(selectedTicket.descuento_global)}</strong>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Descuento total</span>
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

            <section className="feature-card pos-note-card">
              <div className="feature-header">
                <p className="eyebrow">Pagos</p>
                <h3>{selectedTicket.metodo_pago === "mixto" ? "Pago mixto" : "Pago registrado"}</h3>
              </div>
              <div className="pos-payment-breakdown">
                {(selectedTicket.pagos ?? []).map((payment) => (
                  <div className="pos-payment-breakdown-row" key={payment.id}>
                    <div>
                      <strong>{getPaymentMethodLabel(payment.metodo)}</strong>
                      <p>{payment.referencia || "Sin referencia"}</p>
                    </div>
                    <strong>{formatMoney(payment.monto)}</strong>
                  </div>
                ))}
              </div>
            </section>

            {selectedTicket.notas ? (
              <div className="feature-card pos-note-card">
                <div className="feature-header">
                  <p className="eyebrow">Nota</p>
                  <h3>Nota de venta</h3>
                </div>
                <p>{selectedTicket.notas}</p>
              </div>
            ) : null}

            <div className="pos-ticket-thanks">
              <strong>Gracias por su compra</strong>
              <p>Conserve este comprobante para cualquier aclaración.</p>
            </div>
          </div>
        )}
      </PosModal>

      <PosModal
        footer={
          <div className="inventory-actions">
            <button className="ghost-button" onClick={() => setShiftMovementModalType("")} type="button">
              Cancelar
            </button>
            <button className="primary-button" disabled={shiftSubmitting} form="pos-shift-movement-form" type="submit">
              {shiftSubmitting
                ? "Guardando..."
                : shiftMovementModalType === "ingreso"
                  ? "Registrar ingreso"
                  : "Registrar retiro"}
            </button>
          </div>
        }
        onClose={() => setShiftMovementModalType("")}
        open={Boolean(shiftMovementModalType)}
        subtitle="Ajusta caja sin afectar inventario."
        title={shiftMovementModalType === "ingreso" ? "Ingreso manual" : "Retiro manual"}
      >
        <form className="pos-cash-form" id="pos-shift-movement-form" onSubmit={handleShiftMovementSubmit}>
          <label>
            Monto
            <input
              className="pos-input"
              min="0.01"
              onChange={(event) =>
                setShiftMovementForm((current) => ({
                  ...current,
                  monto: normalizeDecimalInput(event.target.value),
                }))
              }
              placeholder="0.00"
              step="0.01"
              type="number"
              value={shiftMovementForm.monto}
            />
          </label>

          <label>
            Motivo
            <textarea
              className="pos-textarea"
              onChange={(event) =>
                setShiftMovementForm((current) => ({
                  ...current,
                  motivo: event.target.value,
                }))
              }
              placeholder="Describe el motivo"
              rows={3}
              value={shiftMovementForm.motivo}
            />
          </label>
        </form>
      </PosModal>

      <PosModal
        footer={
          <div className="inventory-actions">
            <button className="ghost-button" onClick={() => setCloseShiftModalOpen(false)} type="button">
              Cancelar
            </button>
            <button className="primary-button" disabled={shiftSubmitting} form="pos-close-shift-form" type="submit">
              {shiftSubmitting ? "Cerrando..." : "Confirmar cierre"}
            </button>
          </div>
        }
        onClose={() => setCloseShiftModalOpen(false)}
        open={closeShiftModalOpen}
        subtitle="Confirma el efectivo contado y cierra el turno actual."
        title="Cerrar turno"
      >
        <form className="pos-cash-form" id="pos-close-shift-form" onSubmit={handleCloseShiftSubmit}>
          <div className="pos-payment-summary pos-payment-secondary">
            <div>
              <span>Efectivo esperado</span>
              <strong>{formatMoney(expectedCash)}</strong>
            </div>
            <div>
              <span>Efectivo contado</span>
              <strong>{formatMoney(countedCash)}</strong>
            </div>
            <div className={closeShiftDifference === 0 ? "" : closeShiftDifference > 0 ? "inventory-value-positive" : "inventory-value-negative"}>
              <span>Diferencia</span>
              <strong>{formatMoney(closeShiftDifference)}</strong>
            </div>
          </div>

          <label>
            Efectivo contado
            <input
              className="pos-input"
              min="0"
              onChange={(event) =>
                setCloseShiftForm((current) => ({
                  ...current,
                  efectivo_contado: normalizeDecimalInput(event.target.value),
                }))
              }
              placeholder="0.00"
              step="0.01"
              type="number"
              value={closeShiftForm.efectivo_contado}
            />
          </label>

          <label>
            Notas de cierre
            <textarea
              className="pos-textarea"
              onChange={(event) =>
                setCloseShiftForm((current) => ({
                  ...current,
                  notas: event.target.value,
                }))
              }
              placeholder="Opcional"
              rows={3}
              value={closeShiftForm.notas}
            />
          </label>
        </form>
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



