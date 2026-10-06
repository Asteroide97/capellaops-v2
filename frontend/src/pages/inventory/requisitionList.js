export async function readRequisitionList(fetchList) {
  const response = await fetchList();
  if (!response || !Array.isArray(response.items) || !Number.isInteger(response.total)
      || response.total < 0 || !Number.isInteger(response.limit) || response.limit < 1
      || !Number.isInteger(response.offset) || response.offset < 0) {
    throw new Error('No se pudo cargar el listado de requisiciones. Intenta actualizarlo.');
  }
  return response;
}

export function countRequisitionStates(items) {
  const counts = Object.fromEntries(['borrador', 'enviada', 'aprobada', 'parcial', 'surtida',
    'convertida_a_oc', 'cancelada', 'rechazada'].map((state) => [state, 0]));
  for (const item of items) if (Object.hasOwn(counts, item.estatus)) counts[item.estatus]++;
  return counts;
}

export async function refreshCommittedRequisitionList(refresh, reportError, message = 'La operación quedó registrada, pero no se pudo actualizar el listado. Intenta actualizarlo.') {
  try {
    await refresh();
    return true;
  } catch {
    reportError(message);
    return false;
  }
}
