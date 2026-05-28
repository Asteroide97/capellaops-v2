import { useEffect, useMemo, useState } from "react";


export const DEFAULT_PAGE_SIZE = 25;


export function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


export function formatDate(value) {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "medium",
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


export function formatPlanLabel(planCode) {
  const map = {
    basico: "Plan Básico",
    pro: "Plan Pro",
    total: "Plan Total",
  };
  return map[planCode] ?? "Plan";
}


export function toDisplayText(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  if (typeof value === "object") {
    if ("label" in value && value.label) {
      return String(value.label);
    }
    if ("name" in value && value.name) {
      return String(value.name);
    }
    if ("nombre" in value && value.nombre) {
      return String(value.nombre);
    }
    if ("sku" in value && value.sku) {
      return String(value.sku);
    }
    return fallback;
  }

  return String(value);
}


export function safeDisplayText(value, fallback = "â€”") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => safeDisplayText(item, "")).filter(Boolean).join(", ") || fallback;
  }

  if (typeof value === "object") {
    return (
      value.nombre ||
      value.name ||
      value.label ||
      value.titulo ||
      value.title ||
      value.sku ||
      value.codigo ||
      value.email ||
      value.id ||
      fallback
    );
  }

  return fallback;
}


export function getStatusTone(value) {
  const normalized = String(value ?? "").toLowerCase();

  if (["activo", "activa", "confirmado", "confirmada", "aprobada", "aplicado", "recibida", "entrada", "sano"].includes(normalized)) {
    return "success";
  }

  if (["agotado", "cancelada", "cancelado", "rechazada", "inactivo", "salida"].includes(normalized)) {
    return "danger";
  }

  if (["bajo mínimo", "bajo minimo", "ajuste", "emitida", "recibida_parcial", "enviada"].includes(normalized)) {
    return "warning";
  }

  if (["borrador", "pendiente"].includes(normalized)) {
    return "neutral";
  }

  if (["info"].includes(normalized)) {
    return "info";
  }

  return "neutral";
}


export function buttonClassName({ tone = "ghost", size = "md", active = false, iconOnly = false, className = "" } = {}) {
  return [
    tone === "primary" ? "primary-button" : "ghost-button",
    "inventory-button",
    `inventory-button-${tone}`,
    `inventory-button-${size}`,
    active ? "is-active" : "",
    iconOnly ? "inventory-button-icon" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
}


export function ActionButton({
  tone = "ghost",
  size = "md",
  active = false,
  icon = null,
  className = "",
  children,
  ...props
}) {
  return (
    <button className={buttonClassName({ tone, size, active, className })} {...props}>
      {icon ? <span className="inventory-button-glyph">{icon}</span> : null}
      <span>{children}</span>
    </button>
  );
}


export function IconButton({ title, tone = "ghost", size = "sm", className = "", children, ...props }) {
  return (
    <button
      aria-label={title}
      className={buttonClassName({ tone, size, iconOnly: true, className })}
      title={title}
      {...props}
    >
      <span className="inventory-button-glyph">{children}</span>
    </button>
  );
}


export function EmptyState({ title, note, action, compact = false }) {
  return (
    <div className={`empty-state ${compact ? "empty-state-compact" : ""}`}>
      <strong>{safeDisplayText(title)}</strong>
      <p>{safeDisplayText(note)}</p>
      {action}
    </div>
  );
}


export function ResultMeta({ loaded, total, label }) {
  return (
    <p className="table-note">
      Mostrando {safeDisplayText(loaded)} de {safeDisplayText(total)} {safeDisplayText(label)}.
    </p>
  );
}


export function StatusBadge({ children, tone }) {
  return <span className={`status-badge ${tone ?? getStatusTone(children)}`}>{safeDisplayText(children)}</span>;
}


export function StockBadge({ stock, minimo, zeroLabel = "Agotado", lowLabel = "Bajo mínimo", okLabel = "Stock sano" }) {
  const numericStock = Number(stock ?? 0);
  const numericMin = Number(minimo ?? 0);

  if (numericStock <= 0) {
    return <StatusBadge tone="danger">{zeroLabel}</StatusBadge>;
  }

  if (numericMin > 0 && numericStock <= numericMin) {
    return <StatusBadge tone="warning">{lowLabel}</StatusBadge>;
  }

  return <StatusBadge tone="success">{okLabel}</StatusBadge>;
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
        <ActionButton disabled={!canGoPrevious} onClick={onPrevious} size="sm" type="button">
          Anterior
        </ActionButton>
        <ActionButton disabled={!canGoNext} onClick={onNext} size="sm" type="button">
          Siguiente
        </ActionButton>
      </div>
    </div>
  );
}


export function SectionTitle({ eyebrow, title, subtitle, actions }) {
  return (
    <div className="inventory-section-title">
      <div>
        {eyebrow ? <p className="eyebrow">{safeDisplayText(eyebrow)}</p> : null}
        <h2>{safeDisplayText(title)}</h2>
        {subtitle ? <p className="table-note">{safeDisplayText(subtitle)}</p> : null}
      </div>
      {actions ? <div className="inventory-actions inventory-actions-wrap">{actions}</div> : null}
    </div>
  );
}


export function PageHeader({ eyebrow, title, subtitle, actions, meta, children }) {
  return (
    <section className="feature-card inventory-page-header">
      <SectionTitle actions={actions} eyebrow={eyebrow} subtitle={subtitle} title={title} />
      {meta ? <div className="inventory-inline-meta">{meta}</div> : null}
      {children}
    </section>
  );
}


export function Toolbar({ children }) {
  return <section className="feature-card inventory-toolbar-card">{children}</section>;
}


export function FilterCard({ title, subtitle, actions, children }) {
  return (
    <section className="feature-card inventory-filter-card">
      {title ? <SectionTitle actions={actions} subtitle={subtitle} title={title} /> : actions ? <div className="inventory-actions inventory-actions-wrap">{actions}</div> : null}
      {children}
    </section>
  );
}


export function SearchInput({
  label = "Buscar",
  placeholder,
  value,
  onChange,
  onKeyDown,
  hint,
  action = null,
}) {
  return (
    <label className="inventory-search-field">
      <span className="inventory-field-label">{safeDisplayText(label)}</span>
      <div className="inventory-search-control">
        <input
          onChange={onChange}
          onKeyDown={onKeyDown}
          placeholder={safeDisplayText(placeholder, "")}
          type="text"
          value={safeDisplayText(value, "")}
        />
        {action ? <div className="inventory-search-action">{action}</div> : null}
      </div>
      {hint ? <span className="inventory-field-hint">{safeDisplayText(hint)}</span> : null}
    </label>
  );
}


export function MetricCard({ label, value, meta, tone = "neutral", icon = null }) {
  return (
    <article className={`inventory-metric-card ${tone}`}>
      <div className="inventory-metric-head">
        {icon ? <span className={`inventory-metric-icon ${tone}`}>{icon}</span> : null}
        <div className="inventory-metric-copy">
          <span className="inventory-metric-label">{safeDisplayText(label)}</span>
          <strong className="inventory-metric-value">{safeDisplayText(value)}</strong>
        </div>
      </div>
      {meta ? <p className="table-note">{safeDisplayText(meta)}</p> : null}
    </article>
  );
}


export function DataCard({ title, subtitle, children, actions, className = "" }) {
  return (
    <section className={`feature-card inventory-card ${className}`.trim()}>
      {title ? <SectionTitle actions={actions} subtitle={subtitle} title={title} /> : actions ? <div className="inventory-actions inventory-actions-wrap">{actions}</div> : null}
      {children}
    </section>
  );
}


export function DataTable({ columns, children, dense = true, className = "" }) {
  return (
    <div className="table-wrap inventory-table-shell">
      <table className={`inventory-table ${dense ? "inventory-table-dense" : ""} ${className}`.trim()}>
        {columns ? (
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={typeof column === "string" ? column : column.key}>
                  {safeDisplayText(typeof column === "string" ? column : column.label)}
                </th>
              ))}
            </tr>
          </thead>
        ) : null}
        {children}
      </table>
    </div>
  );
}


export function FormGrid({ children, columns = 2, className = "" }) {
  return (
    <div
      className={`inventory-form-grid ${columns === 1 ? "inventory-form-grid-single" : "inventory-form-grid-double"} ${className}`.trim()}
    >
      {children}
    </div>
  );
}


export function Field({ label, hint, span = 1, children, className = "" }) {
  const spanClass = span === 2 ? "inventory-form-span-2" : "";
  return (
    <label className={`inventory-field ${spanClass} ${className}`.trim()}>
      {label ? <span className="inventory-field-label">{safeDisplayText(label)}</span> : null}
      {children}
      {hint ? <span className="inventory-field-hint">{safeDisplayText(hint)}</span> : null}
    </label>
  );
}


export function ModalShell({ title, subtitle, open, onClose, children, size = "wide", footer = null }) {
  if (!open) {
    return null;
  }

  return (
    <div className="inventory-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className={`inventory-modal-shell inventory-modal-${size}`}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="inventory-modal-header">
          <div>
            <h3>{safeDisplayText(title)}</h3>
            {subtitle ? <p className="table-note">{safeDisplayText(subtitle)}</p> : null}
          </div>
          <ActionButton onClick={onClose} size="sm" type="button">
            Cerrar
          </ActionButton>
        </div>
        <div className="inventory-modal-body">{children}</div>
        {footer ? <div className="inventory-modal-footer">{footer}</div> : null}
      </div>
    </div>
  );
}


export function ImageThumb({ src, alt, size = "md" }) {
  const [hasError, setHasError] = useState(!src);

  useEffect(() => {
    setHasError(!src);
  }, [src]);

  if (!src || hasError) {
    return (
      <div className={`inventory-thumbnail inventory-thumbnail-${size} inventory-thumbnail-placeholder`}>
        Sin imagen
      </div>
    );
  }

  return (
    <img
      alt={alt}
      className={`inventory-thumbnail inventory-thumbnail-${size}`}
      onError={() => setHasError(true)}
      src={src}
    />
  );
}


export function MaterialImage(props) {
  return <ImageThumb {...props} />;
}
