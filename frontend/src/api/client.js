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


export { ApiError };
