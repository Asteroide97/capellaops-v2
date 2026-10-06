export function isDuplicateMaterialSkuError(error) {
  return error?.status === 409 && typeof error.message === 'string'
    && error.message.includes('El SKU ya existe en esta empresa');
}

export function getRegisteredMaterialTotal(response) {
  return Number.isSafeInteger(response?.registered_total) && response.registered_total >= 0
    ? response.registered_total : null;
}

export function formatRegisteredMaterialTotal(snapshot, empresaId) {
  const total = snapshot && empresaId && snapshot.empresaId === empresaId ? snapshot.total : null;
  return Number.isSafeInteger(total) && total >= 0
    ? `SKUs registrados: ${total}` : 'SKUs registrados: No disponible';
}
