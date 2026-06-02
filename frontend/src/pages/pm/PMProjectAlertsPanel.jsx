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

export default function PMProjectAlertsPanel({
  alerts = [],
  onDismiss,
  onResolve,
  actionLoading = {},
  compact = false,
}) {
  return (
    <DataCard
      className={compact ? "pm-alerts-panel pm-alerts-panel-compact" : "pm-alerts-panel"}
      subtitle="Señales operativas del proyecto deduplicadas por tipo y tarea."
      title="Alertas activas"
    >
      {alerts.length === 0 ? (
        <EmptyState compact note="Sin alertas activas." title="Sin alertas activas" />
      ) : (
        <div className="pm-alert-list">
          {alerts.map((alert) => {
            const resolving = isPending(actionLoading, alert.id, "resolve");
            const dismissing = isPending(actionLoading, alert.id, "dismiss");
            const busy = resolving || dismissing;

            return (
              <div className={`pm-alert-card pm-alert-card-${getAlertSeverityTone(alert.severidad)}`} key={alert.id}>
                <div className="pm-alert-card-head">
                  <div className="pm-alert-card-copy">
                    <div className="pm-inline-metadata">
                      <StatusBadge tone={getAlertSeverityTone(alert.severidad)}>
                        <BellRing size={12} strokeWidth={1.9} />
                        {normalizePmCopy(safeDisplayText(alert.titulo))}
                      </StatusBadge>
                      <StatusBadge tone="neutral">{getAlertTypeLabel(alert.tipo)}</StatusBadge>
                    </div>
                    <strong>{normalizePmCopy(safeDisplayText(alert.tarea_titulo, "Proyecto"))}</strong>
                    <p className="table-note">{normalizePmCopy(safeDisplayText(alert.descripcion, "Sin detalle adicional."))}</p>
                  </div>
                  <div className="pm-alert-card-meta">
                    <span>{safeDisplayText(formatDate(alert.updated_at), "—")}</span>
                  </div>
                </div>

                <div className="pm-alert-card-actions">
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
      )}
    </DataCard>
  );
}
