export const DEFAULT_PAGE_SIZE = 25;


export function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


export function formatNumber(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    minimumFractionDigits: Number.isInteger(numericValue) ? 0 : 2,
    maximumFractionDigits: 4,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


export function formatMoney(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


export function normalizeDecimalInput(value) {
  return value.replace(",", ".").replace(/[^\d.]/g, "");
}


export function parseBooleanFilter(value) {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return undefined;
}


export function EmptyState({ title, note }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{note}</p>
    </div>
  );
}


export function ResultMeta({ loaded, total, label }) {
  return <p className="table-note">Mostrando {loaded} de {total} {label}.</p>;
}


export function PaginationControls({ meta, onPrevious, onNext }) {
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
