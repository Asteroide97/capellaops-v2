const filterKeys = {
  clients: ["q", "tipo", "estatus"], contacts: ["q", "activo"],
  opportunities: ["q", "etapa", "activa"],
  activities: ["q", "tipo", "completada", "activo", "vencidas"],
  quotes: ["search", "estatus", "cliente_id", "oportunidad_id"],
};

export function activeCrmFilters(kind, filters = {}) {
  const labels = { q: "Busqueda", search: "Busqueda", tipo: "Tipo", estatus: "Estatus", etapa: "Etapa" };
  return (filterKeys[kind] || []).flatMap(key => {
    const value = filters[key];
    if (value === undefined || value === null || String(value).trim() === "") return [];
    if (key === "vencidas") return value === true || value === "true" ? ["Solo vencidas"] : [];
    if (key === "completada") return [value === true || value === "true" ? "Completadas" : "Pendientes"];
    if (key === "activo" || key === "activa") return [value === true || value === "true" ? "Activos" : "Inactivos"];
    if (key === "cliente_id") return ["Cliente seleccionado"];
    if (key === "oportunidad_id") return ["Oportunidad seleccionada"];
    const text = key === "q" || key === "search" ? String(value) : String(value).replace(/_/g, " ");
    return [`${labels[key]}: ${text}`];
  });
}

export function clearCrmFilters(kind, filters) {
  const cleared = { ...filters, offset: 0 };
  for (const key of filterKeys[kind] || []) cleared[key] = key === "vencidas" ? "false" : "";
  return cleared;
}

export function classifyCrmEmptyState(kind, page) {
  const filters = activeCrmFilters(kind, page.applied.filters);
  const hasActiveFilters = filters.length > 0;
  const hasReadError = page.status === "error" || Boolean(page.error);
  let mode;
  if (hasReadError) mode = "error";
  else if (kind === "contacts" && !page.applied.clientId) mode = "selection";
  else if (page.status !== "ready") mode = "loading";
  else if (page.items.length) mode = "data";
  else if (hasActiveFilters || page.meta.offset > 0 || page.meta.total > 0) mode = "filtered-empty";
  else if (page.meta.total === 0) mode = "truly-empty";
  else mode = "error";
  return { mode, filters, hasActiveFilters, hasReadError,
    isTrulyEmpty: mode === "truly-empty", isFilteredEmpty: mode === "filtered-empty" };
}
