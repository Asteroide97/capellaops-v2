export function getKardexScopeMetrics(kardex, warehouseId = '') {
  if (!kardex) return null;
  const quantity = Number(kardex.existencia_total ?? 0);
  // Keep the exact cost expression already displayed by Kardex; no cost policy change.
  const cost = Number(kardex.material.costo_promedio_actual ?? kardex.material.costo_unitario ?? 0);
  const costScopeAmbiguous = kardex.material.costo_promedio_actual != null
    && cost === 0 && Number(kardex.material.costo_unitario) > 0
    && Number(kardex.material.valor_inventario) > 0;
  const localValue = Boolean(warehouseId) && (quantity === 0 || !costScopeAmbiguous);
  return {
    quantity,
    cost,
    value: localValue ? quantity * cost : Number(kardex.material.valor_inventario ?? 0),
    valueScope: localValue ? 'local' : 'global',
  };
}

export async function readWarehouseStock(fetchPage, warehouseId) {
  const items = [];
  const seen = new Set();
  const limit = 100;
  let offset = 0;
  while (true) {
    const response = await fetchPage({limit, offset});
    if (!Array.isArray(response?.items) || !Number.isInteger(response.total) || response.total < 0 || response.offset !== offset
        || response.items.some((item) => item.almacen_id !== warehouseId
          || !item.material_id || item.cantidad == null
          || !Number.isFinite(Number(item.cantidad)) || Number(item.cantidad) < 0)) {
      throw new Error('No se pudo consultar la disponibilidad local.');
    }
    for (const item of response.items) {
      if (seen.has(item.material_id)) throw new Error('La disponibilidad cambió durante la consulta. Intenta actualizarla.');
      seen.add(item.material_id);
    }
    items.push(...response.items);
    if (items.length >= response.total) return items;
    if (response.items.length === 0) throw new Error('No se pudo completar la consulta de disponibilidad local.');
    offset += response.items.length;
  }
}

export function getWarehouseAvailability(snapshot, empresaId, warehouseId, materialId) {
  if (!warehouseId) return {status: 'select_warehouse', quantity: null};
  if (!materialId) return {status: 'select_material', quantity: null};
  if (!snapshot || snapshot.empresaId !== empresaId || snapshot.warehouseId !== warehouseId) {
    return {status: 'loading', quantity: null};
  }
  if (snapshot.status === 'error') return {status: 'error', quantity: null};
  if (snapshot.status !== 'ready') return {status: 'loading', quantity: null};
  const row = snapshot.items.find((item) => item.material_id === materialId);
  return {status: 'ready', quantity: row ? Number(row.cantidad) : 0};
}
