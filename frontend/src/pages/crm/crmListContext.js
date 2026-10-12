export function emptyCrmListPage(applied, status = "idle", error = "") {
  return { applied, status, error, items: [],
    meta: { total: 0, limit: applied.filters.limit, offset: applied.filters.offset } };
}

export async function readLatestCrmPage({ requestRef, scopeRef, scope, applied, load, setPage, validateRows, errorMessage }) {
  const sameScope = () => scopeRef.current.token === scope.token && scopeRef.current.empresaId === scope.empresaId;
  if (!sameScope()) return null;
  const requestId = ++requestRef.current;
  const current = () => sameScope() && requestRef.current === requestId;
  setPage(emptyCrmListPage(applied, "loading"));
  try {
    const response = await load();
    if (!current()) return null;
    if (!response || !Array.isArray(response.items) || !Number.isInteger(response.total) || response.total < 0 ||
        !Number.isInteger(response.limit) || response.limit <= 0 || !Number.isInteger(response.offset) || response.offset < 0 ||
        !validateRows(response.items)) throw new Error("Invalid CRM page");
    setPage({ applied, status: "ready", error: "", items: response.items,
      meta: { total: response.total, limit: response.limit, offset: response.offset } });
    return response;
  } catch {
    if (current()) setPage(emptyCrmListPage(applied, "error", errorMessage));
    return null;
  }
}

export function hasOpportunityFilters(filters) {
  return Boolean(String(filters.q || "").trim() || filters.etapa || ["true", "false"].includes(String(filters.activa)));
}

export function describeOpportunityFilters(filters) {
  const parts = [];
  if (String(filters.q || "").trim()) parts.push(`Busqueda: ${filters.q}`);
  if (filters.etapa) parts.push(`Etapa: ${filters.etapa.replace(/_/g, " ")}`);
  if (["true", "false"].includes(String(filters.activa))) parts.push(String(filters.activa) === "true" ? "Activas" : "Cerradas");
  return parts.length ? parts.join(" · ") : "Sin filtros";
}

export function describeContactFilters(filters) {
  return `${filters.q ? `Busqueda: ${filters.q} · ` : ""}${filters.activo === "true" ? "Activos" : filters.activo === "false" ? "Inactivos" : "Todos los estados"}`;
}

export function parseOpportunityAmount(value) {
  const text = String(value ?? "").trim().replace(",", ".");
  if (!text) return { value: 0, error: "" };
  const amount = Number(text);
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text) || !Number.isFinite(amount)) {
    return { value: null, error: "Captura un monto estimado valido." };
  }
  if (amount < 0) return { value: null, error: "El monto estimado debe ser mayor o igual a cero." };
  return { value: amount, error: "" };
}
