import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
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
  Printer,
  ReceiptText,
  ScanLine,
  ShoppingCart,
  Store,
  Ticket,
  Wallet,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

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
  getPosInvoiceRequests,
  getPosReportSummary,
  getPosSaleDetail,
  getPosSaleInvoiceRequest,
  getPosSales,
  getPosShiftReport,
  getPosShifts,
  getPosTicket,
  getWarehouses,
  openPosShift,
  paySuspendedPosSale,
  requestPosSaleInvoice,
  resumePosSale,
  suspendPosSale,
  updatePosSaleInvoiceRequest,
} from "../api/client";


const DEFAULT_PAGE_SIZE = 25;
const POS_VIEWS = ["sell", "history", "tickets", "cash", "reports", "invoicing"];

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
  { value: "reports", label: "Reportes", icon: <BarChart3 size={16} /> },
  { value: "invoicing", label: "Facturación", icon: <ReceiptText size={16} /> },
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

const shiftHistoryFilterDefaults = {
  almacen_id: "",
  estatus: "",
  fecha_desde: "",
  fecha_hasta: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const reportFilterDefaults = {
  fecha_desde: "",
  fecha_hasta: "",
  almacen_id: "",
  usuario_id: "",
  estatus: "",
  agrupacion: "day",
};

const invoiceRequestFilterDefaults = {
  estado: "",
  fecha_desde: "",
  fecha_hasta: "",
  rfc: "",
  folio: "",
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

const defaultInvoiceRequestForm = {
  cliente_nombre: "",
  rfc: "",
  razon_social: "",
  email: "",
  uso_cfdi: "G03",
  regimen_fiscal: "616",
  codigo_postal: "",
  notas: "",
};

const invoiceUsageOptions = [
  { value: "G03", label: "G03 - Gastos en general" },
  { value: "G01", label: "G01 - Adquisición de mercancías" },
  { value: "S01", label: "S01 - Sin efectos fiscales" },
];

const invoiceFiscalRegimeOptions = [
  { value: "601", label: "601 - General de Ley Personas Morales" },
  { value: "612", label: "612 - Personas Físicas con Actividades Empresariales" },
  { value: "616", label: "616 - Sin obligaciones fiscales" },
];


function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


function formatDurationLabel(totalSeconds) {
  const safeSeconds = Math.max(0, Number(totalSeconds || 0));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);

  if (hours <= 0) {
    return `${minutes} min`;
  }
  return `${hours} h ${minutes} min`;
}


function formatDateOnly(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "medium",
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


function toReportDateStart(value) {
  return value ? `${value}T00:00:00` : "";
}


function toReportDateEnd(value) {
  return value ? `${value}T23:59:59` : "";
}


function escapeCsvValue(value) {
  const stringValue = String(value ?? "");
  if (/[",\n]/.test(stringValue)) {
    return `"${stringValue.replace(/"/g, '""')}"`;
  }
  return stringValue;
}


function downloadCsvFile(filename, rows) {
  const csvContent = rows.map((row) => row.map(escapeCsvValue).join(",")).join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}


function getViewTitle(view) {
  const titles = {
    sell: "Punto de Venta",
    history: "Historial de Ventas",
    tickets: "Tickets",
    cash: "Caja / Turnos",
    reports: "Reportes POS",
    invoicing: "Facturación POS",
  };
  return titles[view] ?? "Punto de Venta";
}


function getViewSubtitle(view) {
  const subtitles = {
    sell: "Cobra desde el almacén activo y descuenta inventario automáticamente.",
    history: "Consulta ventas pagadas, canceladas y suspendidas.",
    tickets: "Consulta e imprime comprobantes de venta.",
    cash: "Consulta el estado del turno y prepara el flujo de caja.",
    reports: "Analiza ventas, pagos, descuentos, cancelaciones y utilidad estimada.",
    invoicing: "Revisa ventas con solicitud de factura pendientes de timbrado.",
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
  if (normalized.includes("rfc")) {
    return "Ingresa un RFC válido.";
  }
  if (normalized.includes("email")) {
    return "Ingresa un email válido.";
  }
  if (normalized.includes("solo puedes solicitar factura")) {
    return "Solo puedes solicitar factura de una venta pagada.";
  }
  if (normalized.includes("no puedes solicitar factura de una venta cancelada")) {
    return "No puedes solicitar factura de una venta cancelada.";
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


function getInvoiceStatusLabel(status) {
  const labels = {
    no_solicitada: "No solicitada",
    solicitada: "Solicitada",
    pendiente_datos: "Pendiente de datos",
    lista_para_facturar: "Lista para facturar",
    en_revision: "En revision",
    observada: "Observada",
    preparada: "Preparada",
    descartada: "Descartada",
    facturada: "Facturada",
    cancelada: "Cancelada",
  };
  return labels[String(status ?? "").toLowerCase()] ?? safeText(status, "Sin estado");
}


function getInvoiceStatusTone(status) {
  const normalized = String(status ?? "").toLowerCase();
  if (normalized === "lista_para_facturar" || normalized === "preparada") {
    return "success";
  }
  if (normalized === "pendiente_datos" || normalized === "solicitada" || normalized === "en_revision") {
    return "warning";
  }
  if (normalized === "cancelada" || normalized === "observada" || normalized === "descartada") {
    return "danger";
  }
  return "neutral";
}


function buildInvoiceRequestForm(requestData) {
  return {
    cliente_nombre: requestData?.cliente_nombre ?? "",
    rfc: requestData?.rfc ?? "",
    razon_social: requestData?.razon_social ?? "",
    email: requestData?.email ?? "",
    uso_cfdi: requestData?.uso_cfdi ?? "G03",
    regimen_fiscal: requestData?.regimen_fiscal ?? "616",
    codigo_postal: requestData?.codigo_postal ?? "",
    notas: requestData?.notas ?? "",
  };
}


function hasPreparedInvoiceRequest(sale) {
  const status = String(sale?.factura_estado ?? "").toLowerCase();
  return status && status !== "no_solicitada";
}


function getSaleDisplayDate(sale) {
  return sale?.paid_at || sale?.created_at || null;
}


function getShiftDifferenceClass(value) {
  const numericValue = Number(value || 0);
  if (Number.isNaN(numericValue)) {
    return "";
  }
  if (numericValue === 0) {
    return "pos-difference-zero";
  }
  if (numericValue > 0) {
    return "pos-difference-positive";
  }
  return "pos-difference-negative";
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
  const { token, empresaId, membership, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeView = POS_VIEWS.includes(searchParams.get("view")) ? searchParams.get("view") : "sell";
  const canOpenBillingQueue = user?.is_superadmin || ["owner", "admin"].includes(String(membership?.role ?? "").toLowerCase());

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
  const [shiftHistoryFilters, setShiftHistoryFilters] = useState(shiftHistoryFilterDefaults);
  const [shiftHistory, setShiftHistory] = useState([]);
  const [shiftHistoryMeta, setShiftHistoryMeta] = useState({
    total: 0,
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
  });
  const [reportFilters, setReportFilters] = useState(reportFilterDefaults);
  const [reportData, setReportData] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [invoiceRequestFilters, setInvoiceRequestFilters] = useState(invoiceRequestFilterDefaults);
  const [invoiceRequests, setInvoiceRequests] = useState([]);
  const [invoiceRequestMeta, setInvoiceRequestMeta] = useState({
    total: 0,
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
  });
  const [invoiceSubmitting, setInvoiceSubmitting] = useState(false);

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
  const [shiftReportModalOpen, setShiftReportModalOpen] = useState(false);
  const [selectedShiftReport, setSelectedShiftReport] = useState(null);
  const [invoiceRequestModalOpen, setInvoiceRequestModalOpen] = useState(false);
  const [selectedInvoiceRequest, setSelectedInvoiceRequest] = useState(null);
  const [invoiceRequestForm, setInvoiceRequestForm] = useState(defaultInvoiceRequestForm);
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
  const activeShiftDurationLabel = useMemo(
    () => (activeShift?.opened_at ? formatDurationLabel((Date.now() - new Date(activeShift.opened_at).getTime()) / 1000) : "-"),
    [activeShift?.opened_at],
  );
  const reportCashierOptions = useMemo(() => {
    const baseOptions = (reportData?.ventas_por_cajero ?? []).map((item) => ({
      value: item.usuario_id,
      label: item.nombre,
    }));

    if (
      reportFilters.usuario_id &&
      !baseOptions.some((option) => option.value === reportFilters.usuario_id)
    ) {
      baseOptions.push({
        value: reportFilters.usuario_id,
        label: "Cajero seleccionado",
      });
    }

    return baseOptions.filter((option) => option.value);
  }, [reportData?.ventas_por_cajero, reportFilters.usuario_id]);
  const hasReportSales = Number(reportData?.kpis?.ventas_count || 0) > 0;

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

  async function loadShiftHistory(nextFilters = shiftHistoryFilters) {
    const response = await getPosShifts({
      token,
      empresaId,
      filters: {
        almacen_id: nextFilters.almacen_id,
        estatus: nextFilters.estatus,
        fecha_desde: nextFilters.fecha_desde,
        fecha_hasta: nextFilters.fecha_hasta,
        limit: nextFilters.limit,
        offset: nextFilters.offset,
      },
    });

    setShiftHistory(response.items ?? []);
    setShiftHistoryMeta({
      total: response.total ?? 0,
      limit: response.limit ?? DEFAULT_PAGE_SIZE,
      offset: response.offset ?? 0,
    });
    return response;
  }

  async function loadPosReport(nextFilters = reportFilters) {
    setReportLoading(true);
    try {
      const response = await getPosReportSummary({
        token,
        empresaId,
        filters: {
          fecha_desde: toReportDateStart(nextFilters.fecha_desde),
          fecha_hasta: toReportDateEnd(nextFilters.fecha_hasta),
          almacen_id: nextFilters.almacen_id,
          usuario_id: nextFilters.usuario_id,
          estatus: nextFilters.estatus,
          agrupacion: nextFilters.agrupacion || "day",
        },
      });
      setReportData(response);
      return response;
    } finally {
      setReportLoading(false);
    }
  }

  async function loadInvoiceRequests(nextFilters = invoiceRequestFilters) {
    const response = await getPosInvoiceRequests({
      token,
      empresaId,
      filters: {
        estado: nextFilters.estado,
        fecha_desde: toReportDateStart(nextFilters.fecha_desde),
        fecha_hasta: toReportDateEnd(nextFilters.fecha_hasta),
        rfc: nextFilters.rfc,
        folio: nextFilters.folio,
        limit: nextFilters.limit,
        offset: nextFilters.offset,
      },
    });

    setInvoiceRequests(response.items ?? []);
    setInvoiceRequestMeta({
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
      const requests = [
        loadCatalog(nextWarehouseId, catalogFilters),
        loadSales(saleFilters),
        loadActiveShift(nextWarehouseId),
        loadShiftHistory(shiftHistoryFilters),
      ];
      if (activeView === "reports") {
        requests.push(loadPosReport(reportFilters));
      }
      if (activeView === "invoicing") {
        requests.push(loadInvoiceRequests(invoiceRequestFilters));
      }
      await Promise.all(requests);
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
      const requests = [
        loadCatalog(selectedWarehouseId, catalogFilters),
        loadSales(saleFilters),
        loadActiveShift(selectedWarehouseId),
        loadShiftHistory(shiftHistoryFilters),
      ];
      if (activeView === "reports") {
        requests.push(loadPosReport(reportFilters));
      }
      if (activeView === "invoicing") {
        requests.push(loadInvoiceRequests(invoiceRequestFilters));
      }
      await Promise.all(requests);
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

  useEffect(() => {
    if (activeView !== "reports" || !token || !empresaId) {
      return;
    }

    loadPosReport(reportFilters).catch((requestError) => {
      setError(getPosUiError(requestError, "No se pudo cargar el reporte. Intenta actualizar."));
    });
  }, [activeView, token, empresaId]);

  useEffect(() => {
    if (activeView !== "invoicing" || !token || !empresaId) {
      return;
    }

    loadInvoiceRequests(invoiceRequestFilters).catch((requestError) => {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    });
  }, [activeView, token, empresaId]);

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
      await loadShiftHistory(shiftHistoryFilters);
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
      setSuccessContext({ type: "shift-closed", shiftId: shift.id });
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

  async function handleShiftHistorySearch(event) {
    event.preventDefault();
    clearFeedback();
    try {
      const nextFilters = { ...shiftHistoryFilters, offset: 0 };
      setShiftHistoryFilters(nextFilters);
      await loadShiftHistory(nextFilters);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    }
  }

  async function handleReportSearch(event) {
    event.preventDefault();
    clearFeedback();
    try {
      await loadPosReport(reportFilters);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar el reporte. Intenta actualizar."));
    }
  }

  async function handleReportReset() {
    clearFeedback();
    setReportFilters(reportFilterDefaults);
    try {
      await loadPosReport(reportFilterDefaults);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar el reporte. Intenta actualizar."));
    }
  }

  function handleExportReportCsv() {
    if (!reportData) {
      return;
    }

    const rows = [
      ["Seccion", "Campo", "Valor"],
      ["KPIs", "Ventas netas", reportData.kpis.total_neto],
      ["KPIs", "Ventas cobradas", reportData.kpis.ventas_pagadas_count],
      ["KPIs", "Cancelaciones", reportData.kpis.ventas_canceladas_count],
      ["KPIs", "Ticket promedio", reportData.kpis.ticket_promedio],
      ["KPIs", "Descuentos", reportData.kpis.total_descuentos],
      ["KPIs", "Utilidad estimada", reportData.kpis.utilidad_estimada],
      [],
      ["Ventas por día"],
      ["Fecha", "Ventas", "Total neto", "Cancelado"],
      ...(reportData.ventas_por_dia ?? []).map((item) => [
        item.fecha,
        item.ventas_count,
        item.total_neto,
        item.cancelado,
      ]),
      [],
      ["Productos más vendidos"],
      ["SKU", "Producto", "Cantidad", "Total vendido", "Costo estimado", "Utilidad estimada"],
      ...(reportData.productos_mas_vendidos ?? []).map((item) => [
        item.sku,
        item.nombre,
        item.cantidad,
        item.total_venta,
        item.costo_estimado,
        item.utilidad_estimada,
      ]),
    ];

    downloadCsvFile("pos-reportes.csv", rows);
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

  async function handleShiftHistoryPageChange(nextOffset) {
    const nextFilters = { ...shiftHistoryFilters, offset: nextOffset };
    setShiftHistoryFilters(nextFilters);
    try {
      await loadShiftHistory(nextFilters);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    }
  }

  async function handleInvoiceRequestSearch(event) {
    event.preventDefault();
    clearFeedback();
    try {
      const nextFilters = { ...invoiceRequestFilters, offset: 0 };
      setInvoiceRequestFilters(nextFilters);
      await loadInvoiceRequests(nextFilters);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    }
  }

  async function handleInvoiceRequestReset() {
    clearFeedback();
    setInvoiceRequestFilters(invoiceRequestFilterDefaults);
    try {
      await loadInvoiceRequests(invoiceRequestFilterDefaults);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    }
  }

  async function handleInvoiceRequestPageChange(nextOffset) {
    const nextFilters = { ...invoiceRequestFilters, offset: nextOffset };
    setInvoiceRequestFilters(nextFilters);
    try {
      await loadInvoiceRequests(nextFilters);
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
      setShiftReportModalOpen(false);
      setTicketModalOpen(true);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setSubmitting(false);
    }
  }

  async function openInvoiceRequestModal(saleId) {
    setInvoiceSubmitting(true);
    clearFeedback();
    try {
      const requestData = await getPosSaleInvoiceRequest({ saleId, token, empresaId });
      setSelectedInvoiceRequest(requestData);
      setInvoiceRequestForm(buildInvoiceRequestForm(requestData));
      setInvoiceRequestModalOpen(true);
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setInvoiceSubmitting(false);
    }
  }

  async function handleSaveInvoiceRequest(event) {
    event.preventDefault();
    if (!selectedInvoiceRequest?.venta_id) {
      setError("Selecciona una venta para solicitar factura.");
      return;
    }

    setInvoiceSubmitting(true);
    clearFeedback();
    const payload = {
      cliente_nombre: invoiceRequestForm.cliente_nombre || null,
      rfc: invoiceRequestForm.rfc || null,
      razon_social: invoiceRequestForm.razon_social || null,
      email: invoiceRequestForm.email || null,
      uso_cfdi: invoiceRequestForm.uso_cfdi || null,
      regimen_fiscal: invoiceRequestForm.regimen_fiscal || null,
      codigo_postal: invoiceRequestForm.codigo_postal || null,
      notas: invoiceRequestForm.notas || null,
    };

    try {
      const alreadyRequested =
        selectedInvoiceRequest.factura_estado &&
        selectedInvoiceRequest.factura_estado !== "no_solicitada";
      const response = alreadyRequested
        ? await updatePosSaleInvoiceRequest({
            saleId: selectedInvoiceRequest.venta_id,
            token,
            empresaId,
            payload,
          })
        : await requestPosSaleInvoice({
            saleId: selectedInvoiceRequest.venta_id,
            token,
            empresaId,
            payload,
          });

      setSelectedInvoiceRequest(response);
      setInvoiceRequestForm(buildInvoiceRequestForm(response));
      if (selectedSale?.id === response.venta_id) {
        await loadSaleArtifacts(response.venta_id);
      }
      await loadSales(saleFilters);
      if (activeView === "invoicing") {
        await loadInvoiceRequests(invoiceRequestFilters);
      }
      setInvoiceRequestModalOpen(false);
      setSuccess(
        response.factura_estado === "lista_para_facturar"
          ? "Solicitud lista para facturar."
          : "Solicitud guardada con datos pendientes.",
      );
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo guardar la solicitud de factura."));
    } finally {
      setInvoiceSubmitting(false);
    }
  }

  async function openShiftReport(shiftId, options = {}) {
    setSubmitting(true);
    clearFeedback();
    try {
      const report = await getPosShiftReport({ shiftId, token, empresaId });
      setSelectedShiftReport(report);
      setTicketModalOpen(false);
      setDetailModalOpen(false);
      setShiftReportModalOpen(true);
      if (options.printAfterOpen) {
        window.setTimeout(() => {
          window.print();
        }, 80);
      }
    } catch (requestError) {
      setError(getPosUiError(requestError, "No se pudo cargar la información. Intenta actualizar."));
    } finally {
      setSubmitting(false);
    }
  }

  function printTicket() {
    window.print();
  }

  function printShiftReport() {
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
          {successContext?.type === "shift-closed" ? (
            <div className="pos-action-row">
              <button className="ghost-button" onClick={() => openShiftReport(successContext.shiftId)} type="button">
                Ver corte
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
                            <button className="link-button" onClick={() => openInvoiceRequestModal(record.id)} type="button">
                              {hasPreparedInvoiceRequest(record) ? "Editar factura" : "Solicitar factura"}
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
                <p className="table-note">Resumen operativo del turno actual y acceso al corte preliminar.</p>
              </div>

              <div className="pos-kpi-grid pos-kpi-grid-compact">
                <PosKpiCard icon={<Wallet size={18} />} label="Turno" meta="Folio de caja" value={activeShift.folio} />
                <PosKpiCard icon={<Clock3 size={18} />} label="Apertura" meta="Inicio del turno" value={formatDateTime(activeShift.opened_at)} />
                <PosKpiCard icon={<History size={18} />} label="Duración" meta="Tiempo acumulado" value={activeShiftDurationLabel} />
                <PosKpiCard icon={<CircleDollarSign size={18} />} label="Fondo inicial" meta="Base de caja" value={formatMoney(activeShift.fondo_inicial)} />
                <PosKpiCard icon={<BadgeDollarSign size={18} />} label="Ventas cobradas" meta={`${activeShift.ventas_count} ventas`} value={formatMoney(activeShift.total_bruto)} />
                <PosKpiCard
                  icon={<ReceiptText size={18} />}
                  label="Ventas netas"
                  meta="Ventas cobradas menos cancelaciones"
                  value={formatMoney(activeShift.total_neto)}
                />
                <PosKpiCard
                  icon={<History size={18} />}
                  label="Ventas canceladas"
                  meta={`${formatNumber(activeShift.ventas_canceladas_count)} cancelaciones`}
                  value={formatMoney(activeShift.ventas_canceladas_total)}
                />
                <PosKpiCard
                  icon={<CircleDollarSign size={18} />}
                  label="Efectivo esperado"
                  meta="Fondo inicial + efectivo + ingresos - retiros"
                  value={formatMoney(activeShift.efectivo_esperado)}
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
                <button className="ghost-button" onClick={() => openShiftReport(activeShift.id)} type="button">
                  <ReceiptText size={16} />
                  <span>Ver corte preliminar</span>
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

          <section className="feature-card pos-section-card">
            <div className="feature-header">
              <h2>Historial de turnos</h2>
              <p className="table-note">Consulta turnos abiertos y cerrados, y revisa su corte de caja.</p>
            </div>

            <form className="pos-shift-history-filters" onSubmit={handleShiftHistorySearch}>
              <label>
                Almacén
                <select
                  className="pos-input"
                  onChange={(event) =>
                    setShiftHistoryFilters((current) => ({
                      ...current,
                      almacen_id: event.target.value,
                    }))
                  }
                  value={shiftHistoryFilters.almacen_id}
                >
                  <option value="">Todos los almacenes</option>
                  {warehouses.map((warehouse) => (
                    <option key={warehouse.id} value={warehouse.id}>
                      {warehouse.nombre}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Estatus
                <select
                  className="pos-input"
                  onChange={(event) =>
                    setShiftHistoryFilters((current) => ({
                      ...current,
                      estatus: event.target.value,
                    }))
                  }
                  value={shiftHistoryFilters.estatus}
                >
                  <option value="">Todos</option>
                  <option value="abierta">Abierta</option>
                  <option value="cerrada">Cerrada</option>
                  <option value="cancelada">Cancelada</option>
                </select>
              </label>

              <label>
                Fecha desde
                <input
                  className="pos-input"
                  onChange={(event) =>
                    setShiftHistoryFilters((current) => ({
                      ...current,
                      fecha_desde: event.target.value,
                    }))
                  }
                  type="date"
                  value={shiftHistoryFilters.fecha_desde}
                />
              </label>

              <label>
                Fecha hasta
                <input
                  className="pos-input"
                  onChange={(event) =>
                    setShiftHistoryFilters((current) => ({
                      ...current,
                      fecha_hasta: event.target.value,
                    }))
                  }
                  type="date"
                  value={shiftHistoryFilters.fecha_hasta}
                />
              </label>

              <div className="pos-action-row">
                <button className="ghost-button" type="submit">
                  Filtrar
                </button>
              </div>
            </form>

            {shiftHistory.length === 0 ? (
              <EmptyState note="Abre y cierra turnos para construir el historial operativo de caja." title="No hay turnos registrados." />
            ) : (
              <>
                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>Apertura</th>
                        <th>Cierre</th>
                        <th>Almacén</th>
                        <th>Usuario</th>
                        <th>Estatus</th>
                        <th>Ventas netas</th>
                        <th>Efectivo esperado</th>
                        <th>Efectivo contado</th>
                        <th>Diferencia</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shiftHistory.map((shift) => (
                        <tr key={shift.id}>
                          <td>{formatDateTime(shift.opened_at)}</td>
                          <td>{shift.closed_at ? formatDateTime(shift.closed_at) : "Sin cierre contado"}</td>
                          <td>{shift.almacen_nombre}</td>
                          <td>{shift.usuario_apertura_nombre}</td>
                          <td>
                            <StatusBadge
                              label={shift.estatus === "abierta" ? "Abierta" : shift.estatus === "cerrada" ? "Cerrada" : "Cancelada"}
                              tone={shift.estatus === "abierta" ? "warning" : shift.estatus === "cerrada" ? "success" : "danger"}
                            />
                          </td>
                          <td>{formatMoney(shift.total_neto)}</td>
                          <td>{formatMoney(shift.efectivo_esperado)}</td>
                          <td>{shift.efectivo_contado != null ? formatMoney(shift.efectivo_contado) : "Sin cierre contado"}</td>
                          <td className={shift.diferencia == null ? "" : getShiftDifferenceClass(shift.diferencia)}>
                            {shift.diferencia != null ? formatMoney(shift.diferencia) : "No registrado"}
                          </td>
                          <td>
                            <div className="inventory-actions">
                              <button className="link-button" onClick={() => openShiftReport(shift.id)} type="button">
                                Ver corte
                              </button>
                              <button className="link-button" onClick={() => openShiftReport(shift.id, { printAfterOpen: true })} type="button">
                                Imprimir corte
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <PaginationControls
                  meta={shiftHistoryMeta}
                  onNext={() => handleShiftHistoryPageChange(shiftHistoryMeta.offset + shiftHistoryMeta.limit)}
                  onPrevious={() => handleShiftHistoryPageChange(Math.max(0, shiftHistoryMeta.offset - shiftHistoryMeta.limit))}
                />
              </>
            )}
          </section>
        </div>
      ) : null}

      {activeView === "reports" ? (
        <div className="pos-view-stack pos-report-page">
          <section className="feature-card pos-section-card">
            <div className="feature-header">
              <p className="eyebrow">Análisis</p>
              <p className="table-note">Analiza ventas, pagos, descuentos, cancelaciones y utilidad estimada.</p>
            </div>

            <form className="pos-report-filters" onSubmit={handleReportSearch}>
              <label>
                Fecha desde
                <input
                  className="pos-input"
                  onChange={(event) =>
                    setReportFilters((current) => ({
                      ...current,
                      fecha_desde: event.target.value,
                    }))
                  }
                  type="date"
                  value={reportFilters.fecha_desde}
                />
              </label>

              <label>
                Fecha hasta
                <input
                  className="pos-input"
                  onChange={(event) =>
                    setReportFilters((current) => ({
                      ...current,
                      fecha_hasta: event.target.value,
                    }))
                  }
                  type="date"
                  value={reportFilters.fecha_hasta}
                />
              </label>

              <label>
                Almacén
                <select
                  className="pos-input"
                  onChange={(event) =>
                    setReportFilters((current) => ({
                      ...current,
                      almacen_id: event.target.value,
                    }))
                  }
                  value={reportFilters.almacen_id}
                >
                  <option value="">Todos los almacenes</option>
                  {warehouses.map((warehouse) => (
                    <option key={warehouse.id} value={warehouse.id}>
                      {warehouse.nombre}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Cajero
                <select
                  className="pos-input"
                  onChange={(event) =>
                    setReportFilters((current) => ({
                      ...current,
                      usuario_id: event.target.value,
                    }))
                  }
                  value={reportFilters.usuario_id}
                >
                  <option value="">Todos los cajeros</option>
                  {reportCashierOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Estatus
                <select
                  className="pos-input"
                  onChange={(event) =>
                    setReportFilters((current) => ({
                      ...current,
                      estatus: event.target.value,
                    }))
                  }
                  value={reportFilters.estatus}
                >
                  <option value="">Todos</option>
                  <option value="pagada">Pagada</option>
                  <option value="cancelada">Cancelada</option>
                  <option value="suspendida">Suspendida</option>
                </select>
              </label>

              <label>
                Agrupación
                <select
                  className="pos-input"
                  onChange={(event) =>
                    setReportFilters((current) => ({
                      ...current,
                      agrupacion: event.target.value,
                    }))
                  }
                  value={reportFilters.agrupacion}
                >
                  <option value="day">Día</option>
                  <option value="week">Semana</option>
                  <option value="month">Mes</option>
                </select>
              </label>

              <div className="pos-action-row">
                <button className="ghost-button" disabled={reportLoading} type="submit">
                  {reportLoading ? "Cargando..." : "Aplicar"}
                </button>
                <button className="ghost-button" onClick={handleReportReset} type="button">
                  Limpiar
                </button>
                <button
                  className="primary-button"
                  disabled={reportLoading || !reportData}
                  onClick={handleExportReportCsv}
                  type="button"
                >
                  Exportar CSV
                </button>
              </div>
            </form>
          </section>

          {reportLoading ? (
            <section className="feature-card pos-section-card">
              <p className="table-note">Cargando reporte...</p>
            </section>
          ) : !hasReportSales ? (
            <section className="feature-card pos-section-card">
              <EmptyState
                icon={<BarChart3 size={18} />}
                note="Ajusta los filtros o registra ventas para ver el resumen del POS."
                title="No hay ventas en este periodo."
              />
            </section>
          ) : (
            <>
              <section className="feature-card pos-section-card">
                <div className="pos-kpi-grid pos-kpi-grid-compact">
                  <PosKpiCard
                    icon={<BadgeDollarSign size={18} />}
                    label="Ventas netas"
                    meta="Ventas pagadas menos cancelaciones"
                    value={formatMoney(reportData.kpis.total_neto)}
                  />
                  <PosKpiCard
                    icon={<ReceiptText size={18} />}
                    label="Ventas cobradas"
                    meta={formatMoney(reportData.kpis.total_bruto)}
                    value={reportData.kpis.ventas_pagadas_count}
                  />
                  <PosKpiCard
                    icon={<History size={18} />}
                    label="Cancelaciones"
                    meta={formatMoney(reportData.kpis.total_cancelado)}
                    value={reportData.kpis.ventas_canceladas_count}
                  />
                  <PosKpiCard
                    icon={<CircleDollarSign size={18} />}
                    label="Ticket promedio"
                    meta={`${reportData.kpis.ventas_count} ventas en el periodo`}
                    value={formatMoney(reportData.kpis.ticket_promedio)}
                  />
                  <PosKpiCard
                    icon={<BadgeDollarSign size={18} />}
                    label="Descuentos"
                    meta="Línea y global"
                    value={formatMoney(reportData.kpis.total_descuentos)}
                  />
                  <PosKpiCard
                    icon={<BarChart3 size={18} />}
                    label="Utilidad estimada"
                    meta="Basada en costo estimado"
                    value={formatMoney(reportData.kpis.utilidad_estimada)}
                  />
                </div>
              </section>

              <section className="pos-report-grid">
                <article className="feature-card pos-section-card pos-report-card">
                  <div className="feature-header">
                    <p className="eyebrow">Ventas por día</p>
                    <p className="table-note">Comportamiento del periodo filtrado.</p>
                  </div>
                  <div className="table-wrap">
                    <table className="inventory-table pos-report-table">
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Ventas</th>
                          <th>Total neto</th>
                          <th>Cancelado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(reportData.ventas_por_dia ?? []).map((item) => (
                          <tr key={item.fecha}>
                            <td>{item.fecha}</td>
                            <td>{formatNumber(item.ventas_count)}</td>
                            <td>{formatMoney(item.total_neto)}</td>
                            <td>{formatMoney(item.cancelado)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>

                <article className="feature-card pos-section-card pos-report-card">
                  <div className="feature-header">
                    <p className="eyebrow">Métodos de pago</p>
                    <p className="table-note">Desglose neto por forma de cobro.</p>
                  </div>
                  <div className="pos-report-grid pos-report-grid-mini">
                    {(reportData.metodos_pago ?? []).map((item) => (
                      <div className="mini-card" key={item.metodo}>
                        <span className="eyebrow">{getPaymentMethodLabel(item.metodo)}</span>
                        <strong>{formatMoney(item.total)}</strong>
                        <p>{formatNumber(item.ventas_count)} ventas</p>
                      </div>
                    ))}
                  </div>
                </article>
              </section>

              <section className="pos-report-grid">
                <article className="feature-card pos-section-card pos-report-card">
                  <div className="feature-header">
                    <p className="eyebrow">Productos más vendidos</p>
                    <p className="table-note">Incluye utilidad estimada según costo disponible.</p>
                  </div>
                  <div className="table-wrap">
                    <table className="inventory-table pos-report-table">
                      <thead>
                        <tr>
                          <th>Producto</th>
                          <th>SKU</th>
                          <th>Cantidad</th>
                          <th>Total vendido</th>
                          <th>Utilidad estimada</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(reportData.productos_mas_vendidos ?? []).map((item) => (
                          <tr key={item.material_id}>
                            <td>{item.nombre}</td>
                            <td>{item.sku}</td>
                            <td>{formatNumber(item.cantidad)}</td>
                            <td>{formatMoney(item.total_venta)}</td>
                            <td>{formatMoney(item.utilidad_estimada)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>

                <article className="feature-card pos-section-card pos-report-card">
                  <div className="feature-header">
                    <p className="eyebrow">Descuentos</p>
                    <p className="table-note">Resumen otorgado en el periodo.</p>
                  </div>
                  <div className="pos-kpi-grid pos-kpi-grid-compact">
                    <PosKpiCard
                      icon={<BadgeDollarSign size={18} />}
                      label="Descuentos de línea"
                      meta="Aplicados por producto"
                      value={formatMoney(reportData.descuentos.descuento_lineas_total)}
                    />
                    <PosKpiCard
                      icon={<BadgeDollarSign size={18} />}
                      label="Descuento global"
                      meta="Aplicado a la venta"
                      value={formatMoney(reportData.descuentos.descuento_global_total)}
                    />
                    <PosKpiCard
                      icon={<BadgeDollarSign size={18} />}
                      label="Descuento total"
                      meta="Impacto total del periodo"
                      value={formatMoney(reportData.descuentos.descuento_total)}
                    />
                  </div>
                </article>
              </section>

              <section className="pos-report-grid">
                <article className="feature-card pos-section-card pos-report-card">
                  <div className="feature-header">
                    <p className="eyebrow">Ventas por cajero</p>
                    <p className="table-note">Desempeño neto por usuario.</p>
                  </div>
                  <div className="table-wrap">
                    <table className="inventory-table pos-report-table">
                      <thead>
                        <tr>
                          <th>Cajero</th>
                          <th>Ventas</th>
                          <th>Total neto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(reportData.ventas_por_cajero ?? []).map((item, index) => (
                          <tr key={item.usuario_id || `cashier-${index}`}>
                            <td>{item.nombre}</td>
                            <td>{formatNumber(item.ventas_count)}</td>
                            <td>{formatMoney(item.total_neto)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>

                <article className="feature-card pos-section-card pos-report-card">
                  <div className="feature-header">
                    <p className="eyebrow">Ventas por almacén</p>
                    <p className="table-note">Comparativo neto por origen de venta.</p>
                  </div>
                  <div className="table-wrap">
                    <table className="inventory-table pos-report-table">
                      <thead>
                        <tr>
                          <th>Almacén</th>
                          <th>Ventas</th>
                          <th>Total neto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(reportData.ventas_por_almacen ?? []).map((item, index) => (
                          <tr key={item.almacen_id || `warehouse-${index}`}>
                            <td>{item.nombre}</td>
                            <td>{formatNumber(item.ventas_count)}</td>
                            <td>{formatMoney(item.total_neto)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              </section>

              <section className="feature-card pos-section-card pos-report-card">
                <div className="feature-header">
                  <p className="eyebrow">Cancelaciones recientes</p>
                  <p className="table-note">Últimas cancelaciones dentro del periodo filtrado.</p>
                </div>
                {(reportData.cancelaciones ?? []).length === 0 ? (
                  <EmptyState
                    icon={<History size={18} />}
                    note="No hay cancelaciones registradas en este periodo."
                    title="Sin cancelaciones"
                  />
                ) : (
                  <div className="table-wrap">
                    <table className="inventory-table pos-report-table">
                      <thead>
                        <tr>
                          <th>Folio</th>
                          <th>Fecha</th>
                          <th>Total</th>
                          <th>Motivo</th>
                          <th>Usuario</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reportData.cancelaciones.map((item) => (
                          <tr key={item.venta_id}>
                            <td>{item.folio}</td>
                            <td>{formatDateTime(item.fecha)}</td>
                            <td>{formatMoney(item.total)}</td>
                            <td>{item.motivo || "Sin motivo"}</td>
                            <td>{item.usuario || "No registrado"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      ) : null}

      {activeView === "invoicing" ? (
        <div className="pos-view-stack pos-report-page">
          <section className="feature-card pos-section-card">
            <div className="pos-warning-box is-warning">
              <strong>Preparación de CFDI pendiente</strong>
              <p>El timbrado CFDI aún está pendiente. Esta vista solo prepara las solicitudes.</p>
            </div>
            {canOpenBillingQueue ? (
              <div className="pos-action-row">
                <button className="ghost-button" onClick={() => navigate("/facturacion-pendiente")} type="button">
                  Ver en bandeja fiscal
                </button>
              </div>
            ) : null}
          </section>

          <section className="feature-card pos-section-card">
            <form className="pos-report-filters pos-invoice-filters" onSubmit={handleInvoiceRequestSearch}>
              <label>
                <span>Estado</span>
                <select
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestFilters((current) => ({ ...current, estado: event.target.value }))}
                  value={invoiceRequestFilters.estado}
                >
                  <option value="">Todos los estados</option>
                  <option value="pendiente_datos">Pendiente de datos</option>
                  <option value="lista_para_facturar">Lista para facturar</option>
                  <option value="solicitada">Solicitada</option>
                  <option value="en_revision">En revision</option>
                  <option value="observada">Observada</option>
                  <option value="preparada">Preparada</option>
                  <option value="descartada">Descartada</option>
                </select>
              </label>

              <label>
                <span>Fecha desde</span>
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestFilters((current) => ({ ...current, fecha_desde: event.target.value }))}
                  type="date"
                  value={invoiceRequestFilters.fecha_desde}
                />
              </label>

              <label>
                <span>Fecha hasta</span>
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestFilters((current) => ({ ...current, fecha_hasta: event.target.value }))}
                  type="date"
                  value={invoiceRequestFilters.fecha_hasta}
                />
              </label>

              <label>
                <span>RFC</span>
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestFilters((current) => ({ ...current, rfc: event.target.value }))}
                  placeholder="RFC"
                  type="text"
                  value={invoiceRequestFilters.rfc}
                />
              </label>

              <label>
                <span>Folio</span>
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestFilters((current) => ({ ...current, folio: event.target.value }))}
                  placeholder="Folio"
                  type="text"
                  value={invoiceRequestFilters.folio}
                />
              </label>

              <div className="pos-action-row">
                <button className="ghost-button" type="submit">
                  Aplicar
                </button>
                <button className="ghost-button" onClick={handleInvoiceRequestReset} type="button">
                  Limpiar
                </button>
              </div>
            </form>
          </section>

          <section className="feature-card pos-section-card">
            {invoiceRequests.length === 0 ? (
              <EmptyState
                icon={<ReceiptText size={18} />}
                note="Las ventas con datos fiscales preparados aparecerán aquí."
                title="No hay solicitudes de factura."
              />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table pos-report-table">
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Fecha</th>
                      <th>Cliente</th>
                      <th>RFC</th>
                      <th>Total</th>
                      <th>Estado</th>
                      <th>Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoiceRequests.map((item) => (
                      <tr key={item.venta_id}>
                        <td>{item.folio}</td>
                        <td>{formatDateTime(item.fecha_solicitud || item.fecha)}</td>
                        <td>{item.cliente_nombre || "Mostrador"}</td>
                        <td>{item.rfc || "Sin RFC"}</td>
                        <td>{formatMoney(item.total)}</td>
                        <td>
                          <StatusBadge
                            label={getInvoiceStatusLabel(item.factura_estado)}
                            tone={getInvoiceStatusTone(item.factura_estado)}
                          />
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openInvoiceRequestModal(item.venta_id)} type="button">
                            Ver / Editar datos
                          </button>
                          {canOpenBillingQueue ? (
                            <button
                              className="link-button"
                              onClick={() => navigate(`/facturacion-pendiente?sale_id=${item.venta_id}`)}
                              type="button"
                            >
                              Ver en bandeja fiscal
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
              meta={invoiceRequestMeta}
              onNext={() => handleInvoiceRequestPageChange(invoiceRequestMeta.offset + invoiceRequestMeta.limit)}
              onPrevious={() => handleInvoiceRequestPageChange(Math.max(0, invoiceRequestMeta.offset - invoiceRequestMeta.limit))}
            />
          </section>
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

            <section className="feature-card pos-note-card">
              <div className="feature-header">
                <p className="eyebrow">Facturación</p>
                <h3>Solicitud de factura</h3>
              </div>
              <div className="pos-ticket-meta-grid">
                <article className="mini-card">
                  <span className="eyebrow">Estado fiscal</span>
                  <strong>{getInvoiceStatusLabel(selectedSale.factura_estado)}</strong>
                  <p>{selectedSale.factura_solicitada_at ? formatDateTime(selectedSale.factura_solicitada_at) : "Sin solicitud registrada"}</p>
                </article>
                <article className="mini-card">
                  <span className="eyebrow">RFC</span>
                  <strong>{selectedSale.factura_rfc || "Sin RFC"}</strong>
                  <p>{selectedSale.factura_razon_social || "Sin razón social"}</p>
                </article>
                <article className="mini-card">
                  <span className="eyebrow">Email fiscal</span>
                  <strong>{selectedSale.factura_email || "Sin email"}</strong>
                  <p>{selectedSale.factura_uso_cfdi || "Sin uso CFDI"}</p>
                </article>
              </div>
              <div className="pos-action-row">
                {selectedSale.estatus === "pagada" ? (
                  <>
                    <button className="ghost-button" onClick={() => openInvoiceRequestModal(selectedSale.id)} type="button">
                      {hasPreparedInvoiceRequest(selectedSale) ? "Editar datos fiscales" : "Solicitar factura"}
                    </button>
                    {hasPreparedInvoiceRequest(selectedSale) ? (
                      <>
                        <button className="ghost-button" onClick={() => openInvoiceRequestModal(selectedSale.id)} type="button">
                          Ver solicitud
                        </button>
                        {canOpenBillingQueue ? (
                          <button
                            className="ghost-button"
                            onClick={() => navigate(`/facturacion-pendiente?sale_id=${selectedSale.id}`)}
                            type="button"
                          >
                            Ver en bandeja fiscal
                          </button>
                        ) : null}
                      </>
                    ) : null}
                  </>
                ) : selectedSale.estatus === "cancelada" ? (
                  <p className="table-note">Venta cancelada. La solicitud de factura no está disponible.</p>
                ) : (
                  <p className="table-note">Solo las ventas pagadas pueden preparar solicitud de factura.</p>
                )}
              </div>
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
        onClose={() => setInvoiceRequestModalOpen(false)}
        open={invoiceRequestModalOpen}
        subtitle="Captura los datos fiscales del cliente. Esta solicitud quedará pendiente; aún no se timbra CFDI."
        title="Solicitar factura"
      >
        {selectedInvoiceRequest ? (
          <form className="pos-modal-stack" onSubmit={handleSaveInvoiceRequest}>
            <div className="pos-warning-box is-warning">
              <strong>Solicitud de factura</strong>
              <p>El timbrado CFDI aún está pendiente. Esta vista solo prepara la solicitud.</p>
            </div>

            <div className="pos-ticket-meta-grid">
              <article className="mini-card">
                <span className="eyebrow">Venta</span>
                <strong>{selectedInvoiceRequest.folio}</strong>
                <p>{formatMoney(selectedInvoiceRequest.total)}</p>
              </article>
              <article className="mini-card">
                <span className="eyebrow">Estado fiscal</span>
                <strong>{getInvoiceStatusLabel(selectedInvoiceRequest.factura_estado)}</strong>
                <p>{selectedInvoiceRequest.fecha_solicitud ? formatDateTime(selectedInvoiceRequest.fecha_solicitud) : "Sin solicitud registrada"}</p>
              </article>
            </div>

            <div className="pos-form-grid">
              <label>
                Nombre del cliente
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, cliente_nombre: event.target.value }))}
                  type="text"
                  value={invoiceRequestForm.cliente_nombre}
                />
              </label>

              <label>
                RFC
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, rfc: event.target.value.toUpperCase() }))}
                  placeholder="XAXX010101000"
                  type="text"
                  value={invoiceRequestForm.rfc}
                />
              </label>

              <label className="inventory-form-span-2">
                Razón social
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, razon_social: event.target.value }))}
                  type="text"
                  value={invoiceRequestForm.razon_social}
                />
              </label>

              <label>
                Email
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, email: event.target.value }))}
                  type="email"
                  value={invoiceRequestForm.email}
                />
              </label>

              <label>
                Uso CFDI
                <select
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, uso_cfdi: event.target.value }))}
                  value={invoiceRequestForm.uso_cfdi}
                >
                  {invoiceUsageOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Régimen fiscal
                <select
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, regimen_fiscal: event.target.value }))}
                  value={invoiceRequestForm.regimen_fiscal}
                >
                  {invoiceFiscalRegimeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Código postal
                <input
                  className="pos-input"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, codigo_postal: event.target.value }))}
                  type="text"
                  value={invoiceRequestForm.codigo_postal}
                />
              </label>

              <label className="inventory-form-span-2">
                Notas
                <textarea
                  className="pos-textarea"
                  onChange={(event) => setInvoiceRequestForm((current) => ({ ...current, notas: event.target.value }))}
                  rows={4}
                  value={invoiceRequestForm.notas}
                />
              </label>
            </div>

            <div className="pos-action-row">
              <button className="ghost-button" onClick={() => setInvoiceRequestModalOpen(false)} type="button">
                Cerrar
              </button>
              <button className="primary-button" disabled={invoiceSubmitting} type="submit">
                {invoiceSubmitting ? "Guardando..." : "Guardar solicitud"}
              </button>
            </div>
          </form>
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
                <Printer size={16} />
                <span>Imprimir</span>
              </button>
            </div>
          ) : null
        }
        onClose={() => setTicketModalOpen(false)}
        open={ticketModalOpen}
        size="wide"
        subtitle="Comprobante de venta. No es comprobante fiscal."
        title="Ticket"
      >
        {!selectedTicket ? (
          <EmptyState note="Selecciona una venta para ver su ticket." title="Sin ticket activo" />
        ) : (
          <div className="pos-modal-stack">
            <article className="pos-ticket-print pos-ticket-printable">
              <div className="pos-ticket-receipt">
                <header className="pos-ticket-receipt-head">
                  <div>
                    <p className="eyebrow">Comprobante de venta</p>
                    <h3>{selectedTicket.empresa}</h3>
                    <p>{selectedTicket.almacen}</p>
                  </div>
                  <div className="pos-ticket-status-block">
                    <StatusBadge
                      label={selectedTicket.estatus === "cancelada" ? "Cancelada" : "Pagada"}
                      tone={selectedTicket.estatus === "cancelada" ? "danger" : "success"}
                    />
                    <strong>{selectedTicket.folio}</strong>
                    <span>{formatDateTime(selectedTicket.fecha)}</span>
                  </div>
                </header>

                {selectedTicket.estatus === "cancelada" ? (
                  <div className="pos-ticket-cancelled-stamp">VENTA CANCELADA</div>
                ) : null}

                <div className="pos-ticket-facts">
                  <div>
                    <span>Cajero</span>
                    <strong>{selectedTicket.vendedor}</strong>
                  </div>
                  <div>
                    <span>Cliente</span>
                    <strong>{selectedTicket.cliente_nombre || "Mostrador"}</strong>
                  </div>
                  <div>
                    <span>Email</span>
                    <strong>{selectedTicket.cliente_email || "-"}</strong>
                  </div>
                  <div>
                    <span>Turno</span>
                    <strong>{selectedTicket.turno_folio || "Sin turno"}</strong>
                  </div>
                </div>

                <div className="table-wrap pos-ticket-table-wrap">
                  <table className="inventory-table pos-ticket-table">
                    <thead>
                      <tr>
                        <th>Cant.</th>
                        <th>Producto</th>
                        <th>Precio</th>
                        <th>Desc.</th>
                        <th>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedTicket.productos.map((item, index) => (
                        <tr key={`${item.sku}-${index}`}>
                          <td>{formatNumber(item.cantidad)}</td>
                          <td>
                            <div className="pos-ticket-product-cell">
                              <strong>{item.nombre}</strong>
                              <span>{item.sku}</span>
                            </div>
                          </td>
                          <td>{formatMoney(item.precio_unitario)}</td>
                          <td>{formatMoney(item.descuento_unitario)}</td>
                          <td>{formatMoney(item.total_linea)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="pos-ticket-totals">
                  <div><span>Subtotal bruto</span><strong>{formatMoney(selectedTicket.subtotal)}</strong></div>
                  <div><span>Descuentos de línea</span><strong>-{formatMoney(selectedTicket.descuento_lineas_total)}</strong></div>
                  <div><span>Descuento global</span><strong>-{formatMoney(selectedTicket.descuento_global)}</strong></div>
                  <div><span>Total</span><strong>{formatMoney(selectedTicket.total)}</strong></div>
                  <div><span>Pagado</span><strong>{formatMoney(selectedTicket.monto_pagado)}</strong></div>
                  <div><span>Cambio</span><strong>{formatMoney(selectedTicket.cambio)}</strong></div>
                </div>

                <section className="pos-ticket-section">
                  <div className="feature-header">
                    <p className="eyebrow">Pagos</p>
                    <h3>{selectedTicket.metodo_pago === "mixto" ? "Pago mixto" : "Pago registrado"}</h3>
                  </div>
                  <div className="pos-payment-breakdown pos-ticket-payment-list">
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
                  <section className="pos-ticket-section">
                    <div className="feature-header">
                      <p className="eyebrow">Nota</p>
                      <h3>Nota de venta</h3>
                    </div>
                    <p>{selectedTicket.notas}</p>
                  </section>
                ) : null}

                {selectedTicket.cancel_reason ? (
                  <section className="pos-ticket-section">
                    <div className="feature-header">
                      <p className="eyebrow">Cancelación</p>
                      <h3>Motivo de cancelación</h3>
                    </div>
                    <p>{selectedTicket.cancel_reason}</p>
                  </section>
                ) : null}

                <footer className="pos-ticket-footer">
                  <strong>Gracias por su compra</strong>
                  <p>No es comprobante fiscal.</p>
                </footer>
              </div>
            </article>

          </div>
        )}
      </PosModal>

      <PosModal
        footer={
          selectedShiftReport ? (
            <div className="inventory-actions">
              <button className="ghost-button" onClick={() => setShiftReportModalOpen(false)} type="button">
                Cerrar
              </button>
              <button className="primary-button" onClick={printShiftReport} type="button">
                <Printer size={16} />
                <span>Imprimir corte</span>
              </button>
            </div>
          ) : null
        }
        onClose={() => setShiftReportModalOpen(false)}
        open={shiftReportModalOpen}
        size="wide"
        subtitle="Resumen operativo del turno, movimientos manuales, ventas y cancelaciones."
        title="Corte de caja"
      >
        {!selectedShiftReport ? (
          <EmptyState note="Selecciona un turno para consultar su corte de caja." title="Sin corte activo" />
        ) : (
          <div className="pos-modal-stack">
            <article className="pos-shift-report-print">
              <div className="pos-shift-report-sheet">
                <header className="pos-shift-report-head">
                  <div>
                    <p className="eyebrow">Corte de caja</p>
                    <h3>{selectedShiftReport.shift.almacen_nombre}</h3>
                    <p>Turno {selectedShiftReport.shift.folio}</p>
                  </div>
                  <div className="pos-ticket-status-block">
                    <StatusBadge
                      label={selectedShiftReport.shift.estatus === "cerrada" ? "Cerrada" : "Abierta"}
                      tone={selectedShiftReport.shift.estatus === "cerrada" ? "success" : "warning"}
                    />
                    <strong>{formatDateTime(selectedShiftReport.shift.opened_at)}</strong>
                    <span>Impreso {formatDateTime(selectedShiftReport.generated_at)}</span>
                  </div>
                </header>

                <div className="pos-shift-report-meta">
                  <div>
                    <span>Apertura</span>
                    <strong>{formatDateTime(selectedShiftReport.shift.opened_at)}</strong>
                  </div>
                  <div>
                    <span>Cierre</span>
                    <strong>{selectedShiftReport.shift.closed_at ? formatDateTime(selectedShiftReport.shift.closed_at) : "Sin cierre contado"}</strong>
                  </div>
                  <div>
                    <span>Usuario apertura</span>
                    <strong>{selectedShiftReport.shift.usuario_apertura_nombre}</strong>
                  </div>
                  <div>
                    <span>Usuario cierre</span>
                    <strong>{selectedShiftReport.shift.usuario_cierre_nombre || "No registrado"}</strong>
                  </div>
                  <div>
                    <span>Duración</span>
                    <strong>{formatDurationLabel(selectedShiftReport.duracion_segundos)}</strong>
                  </div>
                  <div>
                    <span>Estatus</span>
                    <strong>{selectedShiftReport.shift.estatus === "cerrada" ? "Cerrada" : "Abierta"}</strong>
                  </div>
                </div>

                <div className="pos-shift-report-grid">
                  <section className="pos-ticket-totals">
                    <div><span>Fondo inicial</span><strong>{formatMoney(selectedShiftReport.shift.fondo_inicial)}</strong></div>
                    <div><span>Total bruto</span><strong>{formatMoney(selectedShiftReport.shift.total_bruto)}</strong></div>
                    <div><span>Cancelaciones</span><strong>{formatMoney(selectedShiftReport.shift.ventas_canceladas_total)}</strong></div>
                    <div><span>Total neto</span><strong>{formatMoney(selectedShiftReport.shift.total_neto)}</strong></div>
                    <div><span>Descuentos de línea</span><strong>{formatMoney(selectedShiftReport.descuento_lineas_total)}</strong></div>
                    <div><span>Descuento global</span><strong>{formatMoney(selectedShiftReport.descuento_global_total)}</strong></div>
                    <div><span>Descuentos totales</span><strong>{formatMoney(selectedShiftReport.descuentos_totales)}</strong></div>
                    <div><span>Ingresos manuales</span><strong>{formatMoney(selectedShiftReport.shift.ingresos_manuales)}</strong></div>
                    <div><span>Retiros manuales</span><strong>{formatMoney(selectedShiftReport.shift.retiros_manuales)}</strong></div>
                    <div><span>Efectivo esperado</span><strong>{formatMoney(selectedShiftReport.shift.efectivo_esperado)}</strong></div>
                    <div><span>Efectivo contado</span><strong>{selectedShiftReport.shift.efectivo_contado != null ? formatMoney(selectedShiftReport.shift.efectivo_contado) : "Sin cierre contado"}</strong></div>
                    <div>
                      <span>Diferencia</span>
                      <strong className={selectedShiftReport.shift.diferencia == null ? "" : getShiftDifferenceClass(selectedShiftReport.shift.diferencia)}>
                        {selectedShiftReport.shift.diferencia != null ? formatMoney(selectedShiftReport.shift.diferencia) : "No registrada"}
                      </strong>
                    </div>
                  </section>

                  <section className="pos-ticket-section">
                    <div className="feature-header">
                      <p className="eyebrow">Métodos de pago</p>
                      <h3>Desglose del turno</h3>
                    </div>
                    <div className="pos-shift-payment-grid">
                      <article className="mini-card">
                        <span className="eyebrow">Efectivo</span>
                        <strong>{formatMoney(selectedShiftReport.shift.total_efectivo)}</strong>
                      </article>
                      <article className="mini-card">
                        <span className="eyebrow">Tarjeta</span>
                        <strong>{formatMoney(selectedShiftReport.shift.total_tarjeta)}</strong>
                      </article>
                      <article className="mini-card">
                        <span className="eyebrow">Transferencia</span>
                        <strong>{formatMoney(selectedShiftReport.shift.total_transferencia)}</strong>
                      </article>
                      <article className="mini-card">
                        <span className="eyebrow">Otro</span>
                        <strong>{formatMoney(selectedShiftReport.shift.total_otro)}</strong>
                      </article>
                    </div>
                  </section>
                </div>

                <section className="pos-ticket-section">
                  <div className="feature-header">
                    <p className="eyebrow">Movimientos manuales</p>
                    <h3>Ingresos y retiros</h3>
                  </div>
                  {selectedShiftReport.movimientos_manuales.length === 0 ? (
                    <p className="table-note">No hay movimientos manuales registrados en este turno.</p>
                  ) : (
                    <div className="table-wrap">
                      <table className="inventory-table pos-report-table">
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
                          {selectedShiftReport.movimientos_manuales.map((movement) => (
                            <tr key={movement.id}>
                              <td>{movement.tipo === "ingreso" ? "Ingreso manual" : "Retiro manual"}</td>
                              <td>{formatMoney(movement.monto)}</td>
                              <td>{movement.motivo}</td>
                              <td>{movement.usuario_nombre}</td>
                              <td>{formatDateTime(movement.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                <section className="pos-ticket-section">
                  <div className="feature-header">
                    <p className="eyebrow">Ventas del turno</p>
                    <h3>Listado de operaciones</h3>
                  </div>
                  {selectedShiftReport.ventas.length === 0 ? (
                    <p className="table-note">No hay ventas registradas en este turno.</p>
                  ) : (
                    <div className="table-wrap">
                      <table className="inventory-table pos-report-table">
                        <thead>
                          <tr>
                            <th>Folio</th>
                            <th>Fecha</th>
                            <th>Estatus</th>
                            <th>Método</th>
                            <th>Cliente</th>
                            <th>Cajero</th>
                            <th>Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedShiftReport.ventas.map((sale) => (
                            <tr key={sale.id}>
                              <td>{sale.folio}</td>
                              <td>{formatDateTime(sale.fecha)}</td>
                              <td>{getSaleStatusLabel(sale.estatus)}</td>
                              <td>{getPaymentMethodLabel(sale.metodo_pago)}</td>
                              <td>{sale.cliente_nombre || "Mostrador"}</td>
                              <td>{sale.vendedor_nombre}</td>
                              <td>{formatMoney(sale.total)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>

                {selectedShiftReport.cancelaciones.length > 0 ? (
                  <section className="pos-ticket-section">
                    <div className="feature-header">
                      <p className="eyebrow">Cancelaciones</p>
                      <h3>Ventas reversadas</h3>
                    </div>
                    <div className="table-wrap">
                      <table className="inventory-table pos-report-table">
                        <thead>
                          <tr>
                            <th>Folio</th>
                            <th>Fecha</th>
                            <th>Total</th>
                            <th>Método</th>
                            <th>Motivo</th>
                            <th>Usuario</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedShiftReport.cancelaciones.map((sale) => (
                            <tr key={sale.id}>
                              <td>{sale.folio}</td>
                              <td>{formatDateTime(sale.fecha)}</td>
                              <td>{formatMoney(sale.total)}</td>
                              <td>{getPaymentMethodLabel(sale.metodo_pago)}</td>
                              <td>{sale.motivo || "Sin motivo"}</td>
                              <td>{sale.usuario_nombre || "No registrado"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                ) : null}
              </div>
            </article>
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
              <span>Fondo inicial</span>
              <strong>{formatMoney(activeShift?.fondo_inicial)}</strong>
            </div>
            <div>
              <span>Efectivo de ventas</span>
              <strong>{formatMoney(activeShift?.total_efectivo)}</strong>
            </div>
            <div>
              <span>Ingresos manuales</span>
              <strong>{formatMoney(activeShift?.ingresos_manuales)}</strong>
            </div>
            <div>
              <span>Retiros manuales</span>
              <strong>{formatMoney(activeShift?.retiros_manuales)}</strong>
            </div>
            <div>
              <span>Efectivo esperado</span>
              <strong>{formatMoney(expectedCash)}</strong>
            </div>
            <div>
              <span>Efectivo contado</span>
              <strong>{formatMoney(countedCash)}</strong>
            </div>
            <div className={getShiftDifferenceClass(closeShiftDifference)}>
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



