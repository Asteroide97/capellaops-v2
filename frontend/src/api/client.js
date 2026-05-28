const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
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
    return (
      value.detail ||
      value.message ||
      value.msg ||
      value.error ||
      value.nombre ||
      value.name ||
      value.label ||
      value.title ||
      value.id ||
      fallback
    );
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

  if (!response.ok) {
    const detail = data?.detail;
    const detailMessage = normalizeApiMessage(detail, "");
    const message =
      detailMessage ||
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


export function getInventorySummary({ token, empresaId }) {
  return apiRequest("/inventory/summary", { token, empresaId });
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


export function createPosSale({ token, empresaId, payload }) {
  return apiRequest("/pos/sales", {
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
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/requisitions${suffix ? `?${suffix}` : ""}`, { token, empresaId });
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


export function approveRequisition({ requisitionId, token, empresaId }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/approve`, {
    method: "POST",
    token,
    empresaId,
  });
}


export function rejectRequisition({ requisitionId, token, empresaId }) {
  return apiRequest(`/inventory/requisitions/${requisitionId}/reject`, {
    method: "POST",
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
  appendQueryValue(query, "limit", filters.limit);
  appendQueryValue(query, "offset", filters.offset);
  const suffix = query.toString();
  return apiRequest(`/inventory/purchase-orders${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getPurchaseOrderDetail({ orderId, token, empresaId }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}`, { token, empresaId });
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


export function receivePurchaseOrder({ orderId, token, empresaId, payload }) {
  return apiRequest(`/inventory/purchase-orders/${orderId}/receive`, {
    method: "POST",
    body: payload,
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
