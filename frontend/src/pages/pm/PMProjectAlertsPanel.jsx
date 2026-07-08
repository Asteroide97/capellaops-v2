import { BellRing, CheckCheck, CircleOff } from "lucide-react";

import {
  ActionButton,
  DataCard,
  EmptyState,
  StatusBadge,
  formatDate,
  safeDisplayText,
} from "../inventory/shared";
import { getAlertSeverityTone, getAlertTypeLabel, normalizePmCopy } from "./shared";

function isPending(actionLoading = {}, alertId, action) {
  return Boolean(actionLoading?.[`${alertId}:${action}`]);
}

function AlertsPanelBody({
  actionLoading = {},
  alerts = [],
  compact = false,
  onDismiss,
  onResolve,
}) {
  if (alerts.length === 0) {
    return <EmptyState compact={compact} note="Sin alertas activas." title="Sin alertas activas" />;
  }

  return (
    <div className="pm-alert-list">
      {alerts.map((alert) => {
        const resolving = isPending(actionLoading, alert.id, "resolve");
        const dismissing = isPending(actionLoading, alert.id, "dismiss");
        const busy = resolving || dismissing;
        const tone = getAlertSeverityTone(alert.severidad);
        const alertType = getAlertTypeLabel(alert.tipo);
        const title = normalizePmCopy(safeDisplayText(alert.tarea_titulo, "Proyecto"));
        const description = normalizePmCopy(safeDisplayText(alert.descripcion, "Sin detalle adicional."));

        return (
          <div className={`pm-alert-row pm-alert-row-${tone}`} key={alert.id}>
            <div className="pm-alert-row-main">
              <div className="pm-alert-row-badges">
                <StatusBadge tone={tone}>
                  <BellRing size={12} strokeWidth={1.9} />
                  {normalizePmCopy(safeDisplayText(alert.titulo, "Alerta"))}
                </StatusBadge>
              </div>
              <div className="pm-alert-row-copy" title={`${alertType} · ${title} · ${description}`}>
                <strong>{alertType}</strong>
                <span className="pm-alert-row-bullet">·</span>
                <span className="pm-alert-row-title">{title}</span>
                <span className="pm-alert-row-bullet">·</span>
                <span className="pm-alert-row-description">{description}</span>
              </div>
            </div>

            <div className="pm-alert-row-meta">
              <span>{safeDisplayText(formatDate(alert.updated_at), "-")}</span>
            </div>

            <div className="pm-alert-row-actions">
              <ActionButton
                className={resolving ? "pm-button-loading" : ""}
                disabled={busy}
                icon={<CheckCheck size={14} strokeWidth={1.9} />}
                onClick={() => onResolve?.(alert)}
                size="sm"
                tone="primary"
                type="button"
              >
                {resolving ? "Resolviendo..." : "Resolver"}
              </ActionButton>
              <ActionButton
                className={dismissing ? "pm-button-loading" : ""}
                disabled={busy}
                icon={<CircleOff size={14} strokeWidth={1.9} />}
                onClick={() => onDismiss?.(alert)}
                size="sm"
                tone="danger"
                type="button"
              >
                {dismissing ? "Descartando..." : "Descartar"}
              </ActionButton>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function PMProjectAlertsPanel(props) {
  const { compact = false, embedded = false } = props;

  if (embedded) {
    return <AlertsPanelBody {...props} />;
  }

  return (
    <DataCard
      className={compact ? "pm-alerts-panel pm-alerts-panel-compact" : "pm-alerts-panel"}
      subtitle="Senales operativas del proyecto deduplicadas por tipo y tarea."
      title="Alertas activas"
    >
      <AlertsPanelBody {...props} />
    </DataCard>
  );
}
