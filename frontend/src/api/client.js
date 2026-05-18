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


async function parseResponse(response) {
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : null;

  if (!response.ok) {
    const detail = data?.detail;
    const detailMessage = Array.isArray(detail) ? detail.join(", ") : detail;
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


export function getWarehouses({ token, empresaId, includeInactive = true }) {
  const query = new URLSearchParams({ include_inactive: String(includeInactive) });
  return apiRequest(`/inventory/warehouses?${query.toString()}`, { token, empresaId });
}


export function getInventoryOnboardingStatus({ token, empresaId }) {
  return apiRequest("/inventory/onboarding-status", { token, empresaId });
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


export function getMaterials({ token, empresaId, includeInactive = true }) {
  const query = new URLSearchParams({ include_inactive: String(includeInactive) });
  return apiRequest(`/inventory/materials?${query.toString()}`, { token, empresaId });
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


export function getStock({ token, empresaId, almacenId, materialId }) {
  const query = new URLSearchParams();
  if (almacenId) {
    query.set("almacen_id", almacenId);
  }
  if (materialId) {
    query.set("material_id", materialId);
  }
  const suffix = query.toString();
  return apiRequest(`/inventory/stock${suffix ? `?${suffix}` : ""}`, { token, empresaId });
}


export function getInventoryMovements({ token, empresaId, limit = 25 }) {
  const query = new URLSearchParams({ limit: String(limit) });
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
