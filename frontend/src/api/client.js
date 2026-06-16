function normalizeBaseUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function resolveApiUrl() {
  return normalizeBaseUrl(import.meta.env.VITE_API_URL) || "/api";
}

function resolvePublicAppUrl() {
  const configured = normalizeBaseUrl(import.meta.env.VITE_PUBLIC_APP_URL);
  if (configured) {
    return configured;
  }
  if (typeof window !== "undefined" && window.location?.origin) {
    return normalizeBaseUrl(window.location.origin);
  }
  return "";
}

const API_URL = resolveApiUrl();
const DEV = import.meta.env.DEV;


class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}


function buildSafeDebugBody(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return body;
  }

  const safeBody = {};
  for (const [key, value] of Object.entries(body)) {
    if (key === "password") {
      safeBody.password_present = Boolean(value);
      continue;
    }

    if (key === "recaptcha_token") {
      safeBody.recaptcha_token_present = Boolean(value);
      continue;
    }

    if (key === "phone_number") {
      safeBody.phone_number_present = Boolean(value);
      continue;
    }

    if (key === "phone_e164") {
      safeBody.phone_e164_present = Boolean(value);
      continue;
    }

    if (key.toLowerCase().includes("token")) {
      safeBody[`${key}_present`] = Boolean(value);
      continue;
    }

    safeBody[key] = value;
  }

  return safeBody;
}


function logApiDebug(label, payload) {
  if (!DEV) {
    return;
  }

  console.info(`[api] ${label}`, payload);
}


function normalizeApiMessage(value, fallback = "Error inesperado") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => normalizeApiMessage(item, "")).filter(Boolean).join(", ") || fallback;
  }

  if (typeof value === "object") {
    if (value.detail !== undefined) {
      return normalizeApiMessage(value.detail, fallback);
    }
    if (value.message !== undefined) {
      return normalizeApiMessage(value.message, fallback);
    }
    if (value.msg !== undefined) {
      return normalizeApiMessage(value.msg, fallback);
    }
    if (value.error !== undefined) {
      return normalizeApiMessage(value.error, fallback);
    }
    if (value.nombre !== undefined) {
      return normalizeApiMessage(value.nombre, fallback);
    }
    if (value.name !== undefined) {
      return normalizeApiMessage(value.name, fallback);
    }
    if (value.label !== undefined) {
      return normalizeApiMessage(value.label, fallback);
    }
    if (value.title !== undefined) {
      return normalizeApiMessage(value.title, fallback);
    }
    if (value.id !== undefined) {
      return normalizeApiMessage(value.id, fallback);
    }
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }

  return fallback;
}


function clampLimit(limit, fallback = 50, max = 100) {
  const parsed = Number(limit || fallback);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }

  return Math.min(parsed, max);
}


async function parseResponse(response) {
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : null;
  const text = isJson ? "" : (await response.text()).trim();

  if (!response.ok) {
    const detail = data?.detail;
    const detailMessage = normalizeApiMessage(detail, "");
    const message =
      detailMessage ||
      text ||
      (response.status >= 500 ? "Error interno de servidor" : "No se pudo completar la solicitud.");
    logApiDebug("response", {
      url: response.url,
      status: response.status,
      message,
    });
    throw new ApiError(message, response.status);
  }

  logApiDebug("response", {
    url: response.url,
    status: response.status,
    message: "ok",
  });

  return data;
}


export async function apiRequest(path, { method = "GET", body, token, empresaId } = {}) {
  const url = `${API_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  if (empresaId) {
    headers["X-Empresa-Id"] = empresaId;
  }

  logApiDebug("request", {
    url,
    method,
    body: buildSafeDebugBody(body),
    has_auth: Boolean(token),
    has_empresa_id: Boolean(empresaId),
  });

  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    logApiDebug("network_error", {
      url,
      method,
      message: "No se pudo conectar con el backend",
    });
    throw new ApiError("No se pudo conectar con el backend");
  }

  return parseResponse(response);
}


export async function uploadFormDataRequest(path, { formData, token, empresaId } = {}) {
  const url = `${API_URL}${path}`;
  const headers = {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  if (empresaId) {
    headers["X-Empresa-Id"] = empresaId;
  }

  logApiDebug("request", {
    url,
    method: "POST",
    body: {
      has_file: Boolean(formData?.get("file")),
    },
    has_auth: Boolean(token),
    has_empresa_id: Boolean(empresaId),
  });

  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });
  } catch {
    logApiDebug("network_error", {
      url,
      method: "POST",
      message: "No se pudo conectar con el backend",
    });
    throw new ApiError("No se pudo conectar con el backend");
  }

  return parseResponse(response);
}


export function startPasswordReset(payload) {
  return apiRequest("/auth/password-reset/start", {
    method: "POST",
    body: {
      email: payload.email,
      phone: payload.phone,
    },
  });
}


export function verifyPasswordReset(payload) {
  return apiRequest("/auth/password-reset/verify", {
    method: "POST",
    body: {
      email: payload.email,
      phone: payload.phone,
      code: payload.code,
    },
  });
}


export function completePasswordReset(payload) {
  return apiRequest("/auth/password-reset/complete", {
    method: "POST",
    body: {
      reset_token: payload.reset_token,
      new_password: payload.new_password,
    },
  });
}


function extractFilenameFromDisposition(value, fallback = "documento.pdf") {
  const disposition = String(value || "");
  const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) {
    try {
      return decodeURIComponent(utfMatch[1]);
    } catch {
      return utfMatch[1];
    }
  }
  const basicMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
  if (basicMatch?.[1]) {
    return basicMatch[1];
  }
  return fallback;
}


export async function downloadFileRequest(path, { token, empresaId, filenameFallback = "documento.pdf" } = {}) {
  const url = `${API_URL}${path}`;
  const headers = {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  if (empresaId) {
    headers["X-Empresa-Id"] = empresaId;
  }

  logApiDebug("request", {
    url,
    method: "GET",
    body: null,
    has_auth: Boolean(token),
    has_empresa_id: Boolean(empresaId),
  });

  let response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers,
    });
  } catch {
    throw new ApiError("No se pudo conectar con el backend");
  }

  if (!response.ok) {
    const isJson = response.headers.get("content-type")?.includes("application/json");
    const data = isJson ? await response.json() : null;
    const text = isJson ? "" : (await response.text()).trim();
    const detailMessage = normalizeApiMessage(data?.detail, "");
    throw new ApiError(
      detailMessage || text || (response.status >= 500 ? "Error interno de servidor" : "No se pudo completar la solicitud."),
      response.status,
    );
  }

  const blob = await response.blob();
  const filename = extractFilenameFromDisposition(response.headers.get("content-disposition"), filenameFallback);
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
  return { filename };
}


function appendQueryValue(query, key, value) {
  if (value !== undefined && value !== null && value !== "") {
    query.set(key, key === "limit" ? String(clampLimit(value)) : String(value));
  }
}


export function getWarehouses({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  return apiRequest(`/inventory/warehouses?${query.toString()}`, { token, empresaId });
}


export function getWarehouseDetail({ warehouseId, token, empresaId }) {
  return apiRequest(`/inventory/warehouses/${warehouseId}`, { token, empresaId });
}


export function getInventoryOnboardingStatus({ token, empresaId }) {
  return apiRequest("/inventory/onboarding-status", { token, empresaId });
}


export function getInventorySummary({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "almacen_id", filters.almacen_id);
  appendQueryValue(query, "periodo_dias", filters.periodo_dias);
  appendQueryValue(query, "categoria", filters.categoria);
  const suffix = query.toString();
  return apiRequest(`/inventory/summary${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createFirstWarehouse({ token, empresaId, payload }) {
  return apiRequest("/inventory/first-warehouse", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function createWarehouse({ token, empresaId, payload }) {
  return apiRequest("/inventory/warehouses", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateWarehouse({ warehouseId, token, empresaId, payload }) {
  return apiRequest(`/inventory/warehouses/${warehouseId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function getMaterials({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "categoria", filters.categoria);
  appendQueryValue(query, "proveedor_principal_id", filters.proveedor_principal_id);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "stock_bajo", filters.stock_bajo);
  appendQueryValue(query, "sin_stock", filters.sin_stock);
  appendQueryValue(query, "sin_precio_venta", filters.sin_precio_venta);
  appendQueryValue(query, "sin_costo", filters.sin_costo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  return apiRequest(`/inventory/materials?${query.toString()}`, { token, empresaId });
}


export function getMaterialDetail({ materialId, token, empresaId }) {
  return apiRequest(`/inventory/materials/${materialId}`, { token, empresaId });
}


export function inventoryLookupMaterial({ code, token, empresaId }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "code", code);
  return apiRequest(`/inventory/materials/lookup?${query.toString()}`, { token, empresaId });
}


export function uploadMaterialImage({ file, token, empresaId }) {
  const formData = new FormData();
  formData.append("file", file);
  return uploadFormDataRequest("/inventory/materials/image-upload", {
    formData,
    token,
    empresaId,
  });
}


export function createMaterialRequisition({ materialId, token, empresaId }) {
  return apiRequest(`/inventory/materials/${materialId}/create-requisition`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function createMaterial({ token, empresaId, payload }) {
  return apiRequest("/inventory/materials", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateMaterial({ materialId, token, empresaId, payload }) {
  return apiRequest(`/inventory/materials/${materialId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function getStock({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "almacen_id", filters.almacen_id);
  appendQueryValue(query, "material_id", filters.material_id);
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "stock_bajo", filters.stock_bajo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/stock${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getInventoryMovements({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "almacen_id", filters.almacen_id);
  appendQueryValue(query, "material_id", filters.material_id);
  appendQueryValue(query, "tipo", filters.tipo);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  return apiRequest(`/inventory/movements?${query.toString()}`, { token, empresaId });
}


export function getInventoryProjects({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/projects${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getInventoryProjectMaterials({ projectId, token, empresaId }) {
  return apiRequest(`/inventory/projects/${projectId}/materials`, { token, empresaId });
}


export function getInventoryProjectMovements({ projectId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/projects/${projectId}/movements${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function createInventoryMovement({ token, empresaId, payload }) {
  return apiRequest("/inventory/movements", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function createInventoryMovementBulk({ token, empresaId, payload }) {
  return apiRequest("/inventory/movements/bulk", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getMaterialKardex({ materialId, token, empresaId, almacenId }) {
  const query = new URLSearchParams();
  if (almacenId) {
    query.set("almacen_id", almacenId);
  }
  const suffix = query.toString();
  return apiRequest(`/inventory/materials/${materialId}/kardex${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function getTransfers({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "almacen_origen_id", filters.almacen_origen_id);
  appendQueryValue(query, "almacen_destino_id", filters.almacen_destino_id);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/transfers${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getTransferDetail({ transferId, token, empresaId }) {
  return apiRequest(`/inventory/transfers/${transferId}`, { token, empresaId });
}


export function createTransfer({ token, empresaId, payload }) {
  return apiRequest("/inventory/transfers", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateTransfer({ transferId, token, empresaId, payload }) {
  return apiRequest(`/inventory/transfers/${transferId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function addTransferDetail({ transferId, token, empresaId, payload }) {
  return apiRequest(`/inventory/transfers/${transferId}/details`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateTransferDetail({ transferId, detailId, token, empresaId, payload }) {
  return apiRequest(`/inventory/transfers/${transferId}/details/${detailId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deleteTransferDetail({ transferId, detailId, token, empresaId }) {
  return apiRequest(`/inventory/transfers/${transferId}/details/${detailId}`, {
    method: "DELETE",
    token,
    empresaId,
  });
}


export function confirmTransfer({ transferId, token, empresaId }) {
  return apiRequest(`/inventory/transfers/${transferId}/confirm`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function cancelTransfer({ transferId, token, empresaId }) {
  return apiRequest(`/inventory/transfers/${transferId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getCounts({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "almacen_id", filters.almacen_id);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/counts${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getCountDetail({ countId, token, empresaId }) {
  return apiRequest(`/inventory/counts/${countId}`, { token, empresaId });
}


export function createCount({ token, empresaId, payload }) {
  return apiRequest("/inventory/counts", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateCount({ countId, token, empresaId, payload }) {
  return apiRequest(`/inventory/counts/${countId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function addCountDetail({ countId, token, empresaId, payload }) {
  return apiRequest(`/inventory/counts/${countId}/details`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateCountDetail({ countId, detailId, token, empresaId, payload }) {
  return apiRequest(`/inventory/counts/${countId}/details/${detailId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deleteCountDetail({ countId, detailId, token, empresaId }) {
  return apiRequest(`/inventory/counts/${countId}/details/${detailId}`, {
    method: "DELETE",
    token,
    empresaId,
  });
}


export function applyCount({ countId, token, empresaId }) {
  return apiRequest(`/inventory/counts/${countId}/apply`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function cancelCount({ countId, token, empresaId }) {
  return apiRequest(`/inventory/counts/${countId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getPosCatalog({ token, empresaId, almacenId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "almacen_id", almacenId);
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pos/catalog${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getPosReportSummary({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "almacen_id", filters.almacen_id);
  appendQueryValue(query, "usuario_id", filters.usuario_id);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "agrupacion", filters.agrupacion);
  const suffix = query.toString();
  return apiRequest(`/pos/reports/summary${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getPosActiveShift({ token, empresaId, warehouseId }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "warehouse_id", warehouseId);
  return apiRequest(`/pos/shift/active?${query.toString()}`, { token, empresaId });
}


export function openPosShift({ token, empresaId, payload }) {
  return apiRequest("/pos/shift/open", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function closePosShift({ token, empresaId, payload }) {
  return apiRequest("/pos/shift/close", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function createPosShiftManualIncome({ token, empresaId, payload }) {
  return apiRequest("/pos/shift/manual-income", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function createPosShiftManualWithdrawal({ token, empresaId, payload }) {
  return apiRequest("/pos/shift/manual-withdrawal", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPosShifts({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "almacen_id", filters.almacen_id);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "usuario_id", filters.usuario_id);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pos/shifts${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getPosShiftDetail({ shiftId, token, empresaId }) {
  return apiRequest(`/pos/shifts/${shiftId}`, { token, empresaId });
}


export function getPosShiftReport({ shiftId, token, empresaId }) {
  return apiRequest(`/pos/shifts/${shiftId}/report`, { token, empresaId });
}


export function getPosSales({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "almacen_id", filters.almacen_id);
  appendQueryValue(query, "metodo_pago", filters.metodo_pago);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pos/sales${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getPosSaleDetail({ saleId, token, empresaId }) {
  return apiRequest(`/pos/sales/${saleId}`, { token, empresaId });
}


export function linkPosSaleToCrm({ saleId, token, empresaId, payload }) {
  return apiRequest(`/pos/sales/${saleId}/crm-link`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function unlinkPosSaleFromCrm({ saleId, token, empresaId }) {
  return apiRequest(`/pos/sales/${saleId}/crm-link`, {
    method: "DELETE",
    token,
    empresaId,
  });
}


export function createPosSale({ token, empresaId, payload }) {
  return apiRequest("/pos/sales", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function suspendPosSale({ token, empresaId, payload }) {
  return apiRequest("/pos/sales/suspend", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function resumePosSale({ saleId, token, empresaId }) {
  return apiRequest(`/pos/sales/${saleId}/resume`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function paySuspendedPosSale({ saleId, token, empresaId, payload }) {
  return apiRequest(`/pos/sales/${saleId}/pay`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function cancelPosSale({ saleId, token, empresaId, payload }) {
  return apiRequest(`/pos/sales/${saleId}/cancel`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPosTicket({ saleId, token, empresaId }) {
  return apiRequest(`/pos/ticket/${saleId}`, { token, empresaId });
}


export function requestPosSaleInvoice({ saleId, token, empresaId, payload }) {
  return apiRequest(`/pos/sales/${saleId}/request-invoice`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPosSaleInvoiceRequest({ saleId, token, empresaId }) {
  return apiRequest(`/pos/sales/${saleId}/invoice-request`, { token, empresaId });
}


export function updatePosSaleInvoiceRequest({ saleId, token, empresaId, payload }) {
  return apiRequest(`/pos/sales/${saleId}/invoice-request`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function getPosInvoiceRequests({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "estado", filters.estado);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "rfc", filters.rfc);
  appendQueryValue(query, "folio", filters.folio);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pos/invoice-requests${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getBillingPosInvoiceRequests({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "estado", filters.estado);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "rfc", filters.rfc);
  appendQueryValue(query, "folio", filters.folio);
  appendQueryValue(query, "cliente", filters.cliente);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/billing/pos/invoice-requests${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getBillingPosInvoiceRequestDetail({ saleId, token, empresaId }) {
  return apiRequest(`/billing/pos/invoice-requests/${saleId}`, { token, empresaId });
}


export function reviewBillingPosInvoiceRequest({ saleId, token, empresaId, payload }) {
  return apiRequest(`/billing/pos/invoice-requests/${saleId}/review`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function observeBillingPosInvoiceRequest({ saleId, token, empresaId, payload }) {
  return apiRequest(`/billing/pos/invoice-requests/${saleId}/observe`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function prepareBillingPosInvoiceRequest({ saleId, token, empresaId }) {
  return apiRequest(`/billing/pos/invoice-requests/${saleId}/prepare`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function discardBillingPosInvoiceRequest({ saleId, token, empresaId, payload }) {
  return apiRequest(`/billing/pos/invoice-requests/${saleId}/discard`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getCompanyUsers({ token, empresaId }) {
  return apiRequest("/company/users", { token, empresaId });
}


export function listCompanyUsers({ token, empresaId }) {
  return getCompanyUsers({ token, empresaId });
}


export function inviteCompanyUser({ token, empresaId, payload }) {
  return apiRequest("/company/users/invite", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateCompanyUser({ membershipId, token, empresaId, payload }) {
  return apiRequest(`/company/users/${membershipId}`, {
    method: "PATCH",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivateCompanyUser({ membershipId, token, empresaId }) {
  return apiRequest(`/company/users/${membershipId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getCompanyProfile({ token, empresaId }) {
  return apiRequest("/company/profile", { token, empresaId });
}


export function updateCompanyProfile({ token, empresaId, payload }) {
  return apiRequest("/company/profile", {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function uploadCompanyLogo({ token, empresaId, file }) {
  const formData = new FormData();
  formData.append("file", file);
  return uploadFormDataRequest("/company/logo-upload", {
    formData,
    token,
    empresaId,
  });
}


export function deleteCompanyLogo({ token, empresaId }) {
  return apiRequest("/company/logo", {
    method: "DELETE",
    token,
    empresaId,
  });
}


export function getPmConfig({ token, empresaId }) {
  return apiRequest("/pm/config", { token, empresaId });
}


export function getPmDashboard({ token, empresaId }) {
  return apiRequest("/pm/dashboard", { token, empresaId });
}


export function getPmExecutiveReport({ token, empresaId, params = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "estatus", params?.estatus);
  appendQueryValue(query, "prioridad", params?.prioridad);
  appendQueryValue(query, "responsable_id", params?.responsable_id);
  appendQueryValue(query, "fecha_desde", params?.fecha_desde);
  appendQueryValue(query, "fecha_hasta", params?.fecha_hasta);
  appendQueryValue(query, "salud", params?.salud);
  appendQueryValue(query, "con_alertas", params?.con_alertas);
  appendQueryValue(query, "con_pendiente_cobro", params?.con_pendiente_cobro);
  appendQueryValue(query, "limit", params?.limit ?? 50);
  appendQueryValue(query, "offset", params?.offset ?? 0);
  const suffix = query.toString();
  return apiRequest(`/pm/reports/executive${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function listPmProjects({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "prioridad", filters.prioridad);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pm/projects${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createPmProject({ token, empresaId, payload }) {
  return apiRequest("/pm/projects", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmProject({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}`, { token, empresaId });
}


export function linkPmProjectToCrm({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/crm-link`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function unlinkPmProjectFromCrm({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/crm-link`, {
    method: "DELETE",
    token,
    empresaId,
  });
}


export function getPmProjectMaterials({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/materials`, { token, empresaId });
}


export function addPmProjectMaterialPlan({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/materials/plan`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmProjectMaterialPlan({ projectId, planId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/materials/plan/${planId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmProjectMaterialPlan({ projectId, planId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/materials/plan/${planId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function createPmProjectMaterialRequisition({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/requisitions`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function listPmProjectRequisitions({ projectId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pm/projects/${projectId}/requisitions${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getPmProjectRequisition({ requisitionId, token, empresaId }) {
  return apiRequest(`/pm/requisitions/${requisitionId}`, { token, empresaId });
}


export function submitPmProjectRequisition({ requisitionId, token, empresaId }) {
  return apiRequest(`/pm/requisitions/${requisitionId}/submit`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function cancelPmProjectRequisition({ requisitionId, token, empresaId }) {
  return apiRequest(`/pm/requisitions/${requisitionId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function consumePmProjectMaterial({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/materials/consume`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function returnPmProjectMaterial({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/materials/return`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmProjectCosts({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/costs`, { token, empresaId });
}


export function refreshPmProjectCosts({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/costs/refresh`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getPmProjectBudget({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/budget`, { token, empresaId });
}


export function createPmProjectBudget({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/budget`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmBudget({ budgetId, token, empresaId, payload }) {
  return apiRequest(`/pm/budgets/${budgetId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function approvePmBudget({ budgetId, token, empresaId }) {
  return apiRequest(`/pm/budgets/${budgetId}/approve`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function cancelPmBudget({ budgetId, token, empresaId }) {
  return apiRequest(`/pm/budgets/${budgetId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function refreshPmProjectBudget({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/budget/refresh`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getPmProjectBudgetVsActual({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/budget-vs-actual`, { token, empresaId });
}


export function createPmBudgetItem({ budgetId, token, empresaId, payload }) {
  return apiRequest(`/pm/budgets/${budgetId}/items`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmBudgetItem({ itemId, token, empresaId, payload }) {
  return apiRequest(`/pm/budget-items/${itemId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmBudgetItem({ itemId, token, empresaId }) {
  return apiRequest(`/pm/budget-items/${itemId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function createPmBudgetItemMaterial({ itemId, token, empresaId, payload }) {
  return apiRequest(`/pm/budget-items/${itemId}/materials`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmBudgetItemMaterial({ componentId, token, empresaId, payload }) {
  return apiRequest(`/pm/budget-item-materials/${componentId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmBudgetItemMaterial({ componentId, token, empresaId }) {
  return apiRequest(`/pm/budget-item-materials/${componentId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function createPmBudgetItemLabor({ itemId, token, empresaId, payload }) {
  return apiRequest(`/pm/budget-items/${itemId}/labor`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmBudgetItemLabor({ componentId, token, empresaId, payload }) {
  return apiRequest(`/pm/budget-item-labor/${componentId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmBudgetItemLabor({ componentId, token, empresaId }) {
  return apiRequest(`/pm/budget-item-labor/${componentId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function createPmBudgetIndirect({ budgetId, token, empresaId, payload }) {
  return apiRequest(`/pm/budgets/${budgetId}/indirects`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmBudgetIndirect({ indirectId, token, empresaId, payload }) {
  return apiRequest(`/pm/budget-indirects/${indirectId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmBudgetIndirect({ indirectId, token, empresaId }) {
  return apiRequest(`/pm/budget-indirects/${indirectId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listPmProjectTimeEntries({ projectId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "user_id", filters.user_id);
  appendQueryValue(query, "task_id", filters.task_id);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pm/projects/${projectId}/time-entries${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createPmProjectTimeEntry({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/time-entries`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmTimeEntry({ timeEntryId, token, empresaId, payload }) {
  return apiRequest(`/pm/time-entries/${timeEntryId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmTimeEntry({ timeEntryId, token, empresaId }) {
  return apiRequest(`/pm/time-entries/${timeEntryId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listPmUserRates({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "activa", filters.activa);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pm/rates/users${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createPmUserRate({ token, empresaId, payload }) {
  return apiRequest("/pm/rates/users", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmUserRate({ rateId, token, empresaId, payload }) {
  return apiRequest(`/pm/rates/users/${rateId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmUserRate({ rateId, token, empresaId }) {
  return apiRequest(`/pm/rates/users/${rateId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listPmRoleRates({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "activa", filters.activa);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pm/rates/roles${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createPmRoleRate({ token, empresaId, payload }) {
  return apiRequest("/pm/rates/roles", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmRoleRate({ rateId, token, empresaId, payload }) {
  return apiRequest(`/pm/rates/roles/${rateId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmRoleRate({ rateId, token, empresaId }) {
  return apiRequest(`/pm/rates/roles/${rateId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function updatePmProject({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmProject({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listPmProjectMembers({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/members`, { token, empresaId });
}


export function addPmProjectMember({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/members`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmProjectMember({ projectId, memberId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/members/${memberId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listPmTasks({ projectId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "prioridad", filters.prioridad);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/pm/projects/${projectId}/tasks${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createPmTask({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/tasks`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmTask({ taskId, token, empresaId }) {
  return apiRequest(`/pm/tasks/${taskId}`, { token, empresaId });
}


export function getPmTaskDependencies({ taskId, token, empresaId }) {
  return apiRequest(`/pm/tasks/${taskId}/dependencies`, { token, empresaId });
}


export function listPmProjectDependencies({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/dependencies`, { token, empresaId });
}


export function getPmProjectPlanning({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/planning`, { token, empresaId });
}


export function refreshPmProjectPlanning({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/refresh-planning`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getPmProjectWorkCalendar({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/work-calendar`, { token, empresaId });
}


export function updatePmProjectWorkCalendar({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/work-calendar`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmProjectCriticalPath({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/critical-path`, { token, empresaId });
}


export function getPmTaskRescheduleImpact({ projectId, taskId, token, empresaId, params }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "fecha_inicio", params?.fecha_inicio);
  appendQueryValue(query, "fecha_fin", params?.fecha_fin);
  const suffix = query.toString();
  return apiRequest(`/pm/projects/${projectId}/tasks/${taskId}/reschedule-impact${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function applyPmTaskSuggestedDates({ projectId, taskId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/projects/${projectId}/tasks/${taskId}/apply-suggested-dates`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmTaskDates({ projectId, taskId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/tasks/${taskId}/update-dates`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function listPmProjectAlerts({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/alerts`, { token, empresaId });
}


export function listPmProjectBaselines({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/baselines`, { token, empresaId });
}


export function createPmProjectBaseline({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/baselines`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmBaseline({ baselineId, token, empresaId }) {
  return apiRequest(`/pm/baselines/${baselineId}`, { token, empresaId });
}


export function setPmBaselineAsMain({ baselineId, token, empresaId }) {
  return apiRequest(`/pm/baselines/${baselineId}/set-main`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function archivePmBaseline({ baselineId, token, empresaId }) {
  return apiRequest(`/pm/baselines/${baselineId}/archive`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getPmProjectBaselineVsActual({ projectId, token, empresaId, params = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "baseline_id", params?.baseline_id);
  const suffix = query.toString();
  return apiRequest(`/pm/projects/${projectId}/baseline-vs-actual${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function listPmProjectChanges({ projectId, token, empresaId, params = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "estatus", params?.estatus);
  appendQueryValue(query, "tipo_cambio", params?.tipo_cambio);
  const suffix = query.toString();
  return apiRequest(`/pm/projects/${projectId}/changes${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function listPmProjectEstimations({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/estimations`, { token, empresaId });
}


export function createPmProjectEstimation({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/estimations`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmEstimation({ estimationId, token, empresaId }) {
  return apiRequest(`/pm/estimations/${estimationId}`, { token, empresaId });
}


export function downloadPmEstimationPdf({ estimationId, token, empresaId }) {
  return downloadFileRequest(`/pm/estimations/${estimationId}/pdf`, {
    token,
    empresaId,
    filenameFallback: "estimacion.pdf",
  });
}


export function updatePmEstimation({ estimationId, token, empresaId, payload }) {
  return apiRequest(`/pm/estimations/${estimationId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function cancelPmEstimation({ estimationId, token, empresaId }) {
  return apiRequest(`/pm/estimations/${estimationId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function addPmEstimationDetail({ estimationId, token, empresaId, payload }) {
  return apiRequest(`/pm/estimations/${estimationId}/details`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmEstimationDetail({ detailId, token, empresaId, payload }) {
  return apiRequest(`/pm/estimation-details/${detailId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmEstimationDetail({ detailId, token, empresaId }) {
  return apiRequest(`/pm/estimation-details/${detailId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function submitPmEstimation({ estimationId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/estimations/${estimationId}/submit`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function approvePmEstimation({ estimationId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/estimations/${estimationId}/approve`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function rejectPmEstimation({ estimationId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/estimations/${estimationId}/reject`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}

export function returnPmEstimationToDraft({ estimationId, token, empresaId }) {
  return apiRequest(`/pm/estimations/${estimationId}/return-to-draft`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function markPmEstimationSent({ estimationId, token, empresaId }) {
  return apiRequest(`/pm/estimations/${estimationId}/mark-sent`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function markPmEstimationCollected({ estimationId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/estimations/${estimationId}/mark-collected`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmProjectEstimationsSummary({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/estimations-summary`, { token, empresaId });
}


export function listPmProjectEstimationCandidates({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/estimation-candidates`, { token, empresaId });
}


export function createPmProjectChange({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/changes`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPmProjectChange({ changeId, token, empresaId }) {
  return apiRequest(`/pm/changes/${changeId}`, { token, empresaId });
}


export function updatePmProjectChange({ changeId, token, empresaId, payload }) {
  return apiRequest(`/pm/changes/${changeId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function submitPmProjectChange({ changeId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/changes/${changeId}/submit`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function approvePmProjectChange({ changeId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/changes/${changeId}/approve`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function rejectPmProjectChange({ changeId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/changes/${changeId}/reject`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function cancelPmProjectChange({ changeId, token, empresaId }) {
  return apiRequest(`/pm/changes/${changeId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function applyPmProjectChange({ changeId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/changes/${changeId}/apply`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function resolvePmAlert({ alertId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/alerts/${alertId}/resolve`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function dismissPmAlert({ alertId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/alerts/${alertId}/dismiss`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function createPmTaskDependency({ taskId, token, empresaId, payload }) {
  return apiRequest(`/pm/tasks/${taskId}/dependencies`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmTaskDependency({ dependencyId, token, empresaId }) {
  return apiRequest(`/pm/task-dependencies/${dependencyId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function updatePmTask({ taskId, token, empresaId, payload }) {
  return apiRequest(`/pm/tasks/${taskId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmTask({ taskId, token, empresaId }) {
  return apiRequest(`/pm/tasks/${taskId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function createPmSubtask({ taskId, token, empresaId, payload }) {
  return apiRequest(`/pm/tasks/${taskId}/subtasks`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmSubtask({ subtaskId, token, empresaId, payload }) {
  return apiRequest(`/pm/subtasks/${subtaskId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function createPmChecklistItem({ taskId, token, empresaId, payload }) {
  return apiRequest(`/pm/tasks/${taskId}/checklist`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePmChecklistItem({ itemId, token, empresaId, payload }) {
  return apiRequest(`/pm/checklist/${itemId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function createPmProjectComment({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/comments`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function createPmTaskComment({ taskId, token, empresaId, payload }) {
  return apiRequest(`/pm/tasks/${taskId}/comments`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function listPmProjectDocuments({ projectId, token, empresaId, includeInactive = false }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "include_inactive", includeInactive ? "true" : undefined);
  const suffix = query.toString();
  return apiRequest(`/pm/projects/${projectId}/documents${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function uploadPmProjectDocument({ projectId, token, empresaId, formData }) {
  return uploadFormDataRequest(`/pm/projects/${projectId}/documents`, {
    formData,
    token,
    empresaId,
  });
}


export function updatePmProjectDocument({ documentId, token, empresaId, payload }) {
  return apiRequest(`/pm/documents/${documentId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivatePmProjectDocument({ documentId, token, empresaId }) {
  return apiRequest(`/pm/documents/${documentId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listPmProjectApprovals({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/approvals`, { token, empresaId });
}


export function createPmProjectApproval({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/approvals`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function approvePmApproval({ approvalId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/approvals/${approvalId}/approve`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function rejectPmApproval({ approvalId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/approvals/${approvalId}/reject`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function cancelPmApproval({ approvalId, token, empresaId, payload = {} }) {
  return apiRequest(`/pm/approvals/${approvalId}/cancel`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function listPmProjectExternalInvites({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/external-invites`, { token, empresaId });
}


export function listPmProjectPortalAccessLogs({ projectId, token, empresaId }) {
  return apiRequest(`/pm/projects/${projectId}/portal-access-logs`, { token, empresaId });
}


export function createPmProjectExternalInvite({ projectId, token, empresaId, payload }) {
  return apiRequest(`/pm/projects/${projectId}/external-invites`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function revokePmProjectExternalInvite({ inviteId, token, empresaId }) {
  return apiRequest(`/pm/external-invites/${inviteId}/revoke`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function regeneratePmProjectExternalInvite({ inviteId, token, empresaId }) {
  return apiRequest(`/pm/external-invites/${inviteId}/regenerate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getPmPortalProject({ token }) {
  return apiRequest(`/pm/portal/${token}`);
}


export function createPmPortalComment({ token, payload }) {
  return apiRequest(`/pm/portal/${token}/comments`, {
    method: "POST",
    body: payload,
  });
}


export function getPublicAppUrl() {
  return resolvePublicAppUrl();
}


export function getSuppliers({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/suppliers${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getSupplierDetail({ supplierId, token, empresaId }) {
  return apiRequest(`/inventory/suppliers/${supplierId}`, { token, empresaId });
}


export function getSupplierSummary({ supplierId, token, empresaId }) {
  return apiRequest(`/inventory/suppliers/${supplierId}/summary`, { token, empresaId });
}


export function getSupplierPurchaseOrders({ supplierId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/suppliers/${supplierId}/purchase-orders${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function getSupplierReceipts({ supplierId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/suppliers/${supplierId}/receipts${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function getSupplierMaterials({ supplierId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/suppliers/${supplierId}/materials${suffix ? `?${suffix}` : ""}`, {
    token,
    empresaId,
  });
}


export function createSupplier({ token, empresaId, payload }) {
  return apiRequest("/inventory/suppliers", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateSupplier({ supplierId, token, empresaId, payload }) {
  return apiRequest(`/inventory/suppliers/${supplierId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function getRequisitions({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "proveedor_sugerido_id", filters.proveedor_sugerido_id);
  appendQueryValue(query, "proyecto", filters.proyecto);
  appendQueryValue(query, "proyecto_id", filters.proyecto_id);
  appendQueryValue(query, "material_id", filters.material_id);
  appendQueryValue(query, "es_proyecto", filters.es_proyecto);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/requisitions${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function listRequisitions({ token, empresaId, filters = {} }) {
  return getRequisitions({ token, empresaId, filters });
}


export function getRequisitionDetail({ requisitionId, token, empresaId }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}`, { token, empresaId });
}


export function createRequisition({ token, empresaId, payload }) {
  return apiRequest("/inventory/requisitions", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateRequisition({ requisitionId, token, empresaId, payload }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function addRequisitionDetail({ requisitionId, token, empresaId, payload }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/details`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateRequisitionDetail({ requisitionId, detailId, token, empresaId, payload }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/details/${detailId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deleteRequisitionDetail({ requisitionId, detailId, token, empresaId }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/details/${detailId}`, {
    method: "DELETE",
    token,
    empresaId,
  });
}


export function submitRequisition({ requisitionId, token, empresaId }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/submit`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function approveRequisition({ requisitionId, token, empresaId, payload = { items: [] } }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/approve`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function rejectRequisition({ requisitionId, token, empresaId, payload }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/reject`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function cancelRequisition({ requisitionId, token, empresaId }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function fulfillRequisition({ requisitionId, token, empresaId, payload }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/fulfill`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function createPurchaseOrderFromRequisition({ requisitionId, token, empresaId, payload }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/create-purchase-order`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPurchaseOrders({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "proveedor_id", filters.proveedor_id);
  appendQueryValue(query, "almacen_destino_id", filters.almacen_destino_id);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/purchase-orders${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function listPurchaseOrders({ token, empresaId, filters = {} }) {
  return getPurchaseOrders({ token, empresaId, filters });
}


export function getPurchaseOrderDetail({ orderId, token, empresaId }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}`, { token, empresaId });
}


export function getPurchaseOrderReceipts({ orderId, token, empresaId }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/receipts`, { token, empresaId });
}


export function downloadPurchaseOrderPdf({ orderId, token, empresaId }) {
  return downloadFileRequest(`/inventory/purchase-orders/${orderId}/pdf`, {
    token,
    empresaId,
    filenameFallback: "orden-compra.pdf",
  });
}


export function createPurchaseOrder({ token, empresaId, payload }) {
  return apiRequest("/inventory/purchase-orders", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePurchaseOrder({ orderId, token, empresaId, payload }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function addPurchaseOrderDetail({ orderId, token, empresaId, payload }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/details`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updatePurchaseOrderDetail({ orderId, detailId, token, empresaId, payload }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/details/${detailId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deletePurchaseOrderDetail({ orderId, detailId, token, empresaId }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/details/${detailId}`, {
    method: "DELETE",
    token,
    empresaId,
  });
}


export function issuePurchaseOrder({ orderId, token, empresaId }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/issue`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function cancelPurchaseOrder({ orderId, token, empresaId }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/cancel`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function receivePurchaseOrder({ orderId, token, empresaId, payload }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/receive`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getPendingPurchaseOrderReport({ token, empresaId }) {
  return apiRequest("/inventory/purchase-reports/pending", { token, empresaId });
}


export function getCrmSummary({ token, empresaId }) {
  return apiRequest("/crm/summary", { token, empresaId });
}


export function listCrmClients({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "tipo", filters.tipo);
  appendQueryValue(query, "estatus", filters.estatus);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/crm/clients${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createCrmClient({ token, empresaId, payload }) {
  return apiRequest("/crm/clients", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getCrmClient({ clientId, token, empresaId }) {
  return apiRequest(`/crm/clients/${clientId}`, { token, empresaId });
}


export function getCrmClientTimeline({ clientId, token, empresaId }) {
  return apiRequest(`/crm/clients/${clientId}/timeline`, { token, empresaId });
}


export function getCrmClientCommercialSummary({ clientId, token, empresaId }) {
  return apiRequest(`/crm/clients/${clientId}/commercial-summary`, { token, empresaId });
}


export function updateCrmClient({ clientId, token, empresaId, payload }) {
  return apiRequest(`/crm/clients/${clientId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivateCrmClient({ clientId, token, empresaId }) {
  return apiRequest(`/crm/clients/${clientId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function reactivateCrmClient({ clientId, token, empresaId }) {
  return apiRequest(`/crm/clients/${clientId}/reactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listCrmClientContacts({ clientId, token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/crm/clients/${clientId}/contacts${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createCrmContact({ clientId, token, empresaId, payload }) {
  return apiRequest(`/crm/clients/${clientId}/contacts`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateCrmContact({ contactId, token, empresaId, payload }) {
  return apiRequest(`/crm/contacts/${contactId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function deactivateCrmContact({ contactId, token, empresaId }) {
  return apiRequest(`/crm/contacts/${contactId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function listCrmOpportunities({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "etapa", filters.etapa);
  appendQueryValue(query, "activa", filters.activa);
  appendQueryValue(query, "client_id", filters.client_id);
  appendQueryValue(query, "responsable_user_id", filters.responsable_user_id);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/crm/opportunities${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createCrmOpportunity({ token, empresaId, payload }) {
  return apiRequest("/crm/opportunities", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function getCrmOpportunity({ opportunityId, token, empresaId }) {
  return apiRequest(`/crm/opportunities/${opportunityId}`, { token, empresaId });
}


export function updateCrmOpportunity({ opportunityId, token, empresaId, payload }) {
  return apiRequest(`/crm/opportunities/${opportunityId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function closeCrmOpportunityWon({ opportunityId, token, empresaId, payload }) {
  return apiRequest(`/crm/opportunities/${opportunityId}/close-won`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function closeCrmOpportunityLost({ opportunityId, token, empresaId, payload }) {
  return apiRequest(`/crm/opportunities/${opportunityId}/close-lost`, {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function listCrmActivities({ token, empresaId, filters = {} }) {
  const query = new URLSearchParams();
  appendQueryValue(query, "q", filters.q);
  appendQueryValue(query, "tipo", filters.tipo);
  appendQueryValue(query, "completada", filters.completada);
  appendQueryValue(query, "activo", filters.activo);
  appendQueryValue(query, "cliente_id", filters.cliente_id ?? filters.client_id);
  appendQueryValue(query, "oportunidad_id", filters.oportunidad_id ?? filters.opportunity_id);
  appendQueryValue(query, "fecha_desde", filters.fecha_desde);
  appendQueryValue(query, "fecha_hasta", filters.fecha_hasta);
  appendQueryValue(query, "vencidas", filters.vencidas);
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/crm/activities${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function createCrmActivity({ token, empresaId, payload }) {
  return apiRequest("/crm/activities", {
    method: "POST",
    body: payload,
    token,
    empresaId,
  });
}


export function updateCrmActivity({ activityId, token, empresaId, payload }) {
  return apiRequest(`/crm/activities/${activityId}`, {
    method: "PUT",
    body: payload,
    token,
    empresaId,
  });
}


export function completeCrmActivity({ activityId, token, empresaId }) {
  return apiRequest(`/crm/activities/${activityId}/complete`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function deactivateCrmActivity({ activityId, token, empresaId }) {
  return apiRequest(`/crm/activities/${activityId}/deactivate`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function getSuperadminOverview({ token }) {
  return apiRequest("/superadmin/overview", { token });
}


export function getSuperadminCompanies({ token, filters = {} }) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const suffix = query.toString();
  return apiRequest(`/superadmin/companies${suffix ? `?${suffix}` : ""}`, { token });
}


export function getSuperadminCompanyDetail({ empresaId, token }) {
  return apiRequest(`/superadmin/companies/${empresaId}`, { token });
}


export function getSuperadminUsers({ token, filters = {} }) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const suffix = query.toString();
  return apiRequest(`/superadmin/users${suffix ? `?${suffix}` : ""}`, { token });
}


export function getSuperadminUserDetail({ usuarioId, token }) {
  return apiRequest(`/superadmin/users/${usuarioId}`, { token });
}


export function updateCompanyAccess({ empresaId, token, payload }) {
  return apiRequest(`/superadmin/companies/${empresaId}/access`, {
    method: "PATCH",
    body: payload,
    token,
  });
}


export function impersonateUser({ token, payload }) {
  return apiRequest("/superadmin/impersonate", {
    method: "POST",
    body: payload,
    token,
  });
}


export function getSuperadminAuditLogs({ token, filters = {} }) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const suffix = query.toString();
  return apiRequest(`/superadmin/audit-logs${suffix ? `?${suffix}` : ""}`, { token });
}


export { ApiError };
