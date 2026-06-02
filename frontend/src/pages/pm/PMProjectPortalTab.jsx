import { useEffect, useMemo, useState } from "react";
import { Copy, ExternalLink, KeyRound, RefreshCw, RotateCcw, ShieldOff } from "lucide-react";

import {
  createPmProjectExternalInvite,
  listPmProjectExternalInvites,
  listPmProjectPortalAccessLogs,
  regeneratePmProjectExternalInvite,
  revokePmProjectExternalInvite,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FormGrid,
  MetricCard,
  ModalShell,
  StatusBadge,
  formatDateTime,
  safeDisplayText,
} from "../inventory/shared";
import { getExternalAccessModeLabel, pmExternalAccessModeOptions } from "./shared";

const defaultInviteForm = {
  nombre: "",
  email: "",
  modo_acceso: "solo_lectura",
  expira_at: "",
};

function getErrorMessage(error, fallback) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}

function getInviteStatus(invite) {
  if (invite.revocado_at || invite.activo === false) {
    return { label: "Revocado", tone: "danger" };
  }
  if (invite.expira_at && new Date(invite.expira_at) <= new Date()) {
    return { label: "Expirado", tone: "warning" };
  }
  return { label: "Activo", tone: "success" };
}

function toPortalExpiryIso(value) {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString();
}

export default function PMProjectPortalTab({ empresaId, project, projectId, token }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [invites, setInvites] = useState([]);
  const [logs, setLogs] = useState([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [inviteForm, setInviteForm] = useState(defaultInviteForm);
  const [submitting, setSubmitting] = useState(false);
  const [generatedLink, setGeneratedLink] = useState("");

  const externalComments = useMemo(
    () => (project?.comments ?? []).filter((comment) => comment?.externo),
    [project],
  );

  async function loadPortalData({ background = false } = {}) {
    if (!token || !empresaId || !projectId) {
      return;
    }
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const [invitesResponse, logsResponse] = await Promise.all([
        listPmProjectExternalInvites({ projectId, token, empresaId }),
        listPmProjectPortalAccessLogs({ projectId, token, empresaId }),
      ]);
      setInvites(invitesResponse ?? []);
      setLogs(logsResponse ?? []);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo cargar la configuración del portal externo."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadPortalData();
  }, [token, empresaId, projectId]);

  function closeCreateModal() {
    if (submitting) {
      return;
    }
    setCreateModalOpen(false);
    setInviteForm(defaultInviteForm);
  }

  async function copyLink(link) {
    if (!link) {
      return;
    }
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(link);
      }
      setSuccess("Link copiado.");
    } catch {
      setSuccess("Copia manualmente el link generado.");
    }
  }

  async function handleCreateInvite(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const expiraAt = inviteForm.expira_at ? toPortalExpiryIso(inviteForm.expira_at) : null;
      if (inviteForm.expira_at && !expiraAt) {
        setError("Fecha de expiración inválida.");
        return;
      }
      const response = await createPmProjectExternalInvite({
        projectId,
        token,
        empresaId,
        payload: {
          nombre: inviteForm.nombre.trim(),
          email: inviteForm.email.trim() || null,
          modo_acceso: inviteForm.modo_acceso,
          expira_at: expiraAt,
        },
      });
      const link = response.portal_url || `${window.location.origin}${response.portal_path}`;
      setGeneratedLink(link);
      setSuccess("Acceso externo creado.");
      closeCreateModal();
      await loadPortalData({ background: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo crear el acceso externo."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevokeInvite(inviteId) {
    setError("");
    setSuccess("");
    try {
      await revokePmProjectExternalInvite({ inviteId, token, empresaId });
      setSuccess("Acceso revocado.");
      await loadPortalData({ background: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo revocar el acceso externo."));
    }
  }

  async function handleRegenerateInvite(inviteId) {
    setError("");
    setSuccess("");
    try {
      const response = await regeneratePmProjectExternalInvite({ inviteId, token, empresaId });
      const link = response.portal_url || `${window.location.origin}${response.portal_path}`;
      setGeneratedLink(link);
      setSuccess("Link regenerado.");
      await loadPortalData({ background: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo regenerar el link."));
    }
  }

  return (
    <div className="pm-portal-tab">
      <DataCard
        actions={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton
              icon={<RefreshCw size={16} strokeWidth={1.9} />}
              onClick={() => loadPortalData({ background: true })}
              type="button"
            >
              {refreshing ? "Actualizando..." : "Actualizar"}
            </ActionButton>
            <ActionButton
              icon={<KeyRound size={16} strokeWidth={1.9} />}
              onClick={() => {
                setError("");
                setSuccess("");
                setCreateModalOpen(true);
              }}
              tone="primary"
              type="button"
            >
              Crear acceso externo
            </ActionButton>
          </div>
        )}
        subtitle="Comparte una vista limitada del proyecto con clientes o invitados."
        title="Portal externo"
      >
        {error ? <div className="inventory-inline-feedback inventory-inline-feedback-danger">{error}</div> : null}
        {success ? <div className="inventory-inline-feedback inventory-inline-feedback-success">{success}</div> : null}

        {generatedLink ? (
          <div className="pm-portal-link-card">
            <div>
              <strong>Link público del portal</strong>
              <p className="table-note">Guarda este link. Por seguridad, el token completo solo se muestra una vez.</p>
              <code>{generatedLink}</code>
            </div>
            <div className="inventory-actions inventory-actions-wrap">
              <ActionButton icon={<Copy size={14} strokeWidth={1.9} />} onClick={() => copyLink(generatedLink)} size="sm" type="button">
                Copiar link
              </ActionButton>
              <a className="inventory-button ghost-button inventory-button inventory-button-sm" href={generatedLink} rel="noreferrer" target="_blank">
                <span className="inventory-button-glyph">
                  <ExternalLink size={14} strokeWidth={1.9} />
                </span>
                <span>Abrir portal</span>
              </a>
            </div>
          </div>
        ) : null}

        <div className="inventory-metrics-grid pm-portal-info-grid">
          <MetricCard label="Invitados externos" value={String(invites.length)} />
          <MetricCard label="Accesos registrados" value={String(logs.length)} />
          <MetricCard label="Comentarios externos" value={String(externalComments.length)} />
        </div>
      </DataCard>

      <DataCard
        subtitle="El cliente verá avance, fechas, resumen de tareas y documentos marcados como visibles. No verá costos, tarifas, compras, inventario ni márgenes."
        title="Qué verá el cliente"
      >
        <div className="pm-portal-what-client-sees">
          <StatusBadge tone="success">Visible en portal</StatusBadge>
          <ul>
            <li>Nombre y estatus del proyecto.</li>
            <li>Porcentaje de avance y fechas principales.</li>
            <li>Resumen de tareas por estatus.</li>
            <li>Documentos marcados como visibles para cliente.</li>
            <li>Comentarios externos cuando el acceso lo permita.</li>
          </ul>
          <StatusBadge tone="warning">Nunca visible</StatusBadge>
          <ul>
            <li>Costos, presupuestos, márgenes y tarifas.</li>
            <li>Compras, inventario y datos internos operativos.</li>
            <li>Usuarios internos, responsables y notas privadas.</li>
          </ul>
        </div>
      </DataCard>

      <DataCard subtitle="Links vigentes y revocados del proyecto." title="Invitados existentes">
        {loading ? (
          <p className="table-note">Cargando accesos externos...</p>
        ) : invites.length === 0 ? (
          <EmptyState compact note="Todavía no hay accesos externos creados." title="Sin invitados externos" />
        ) : (
          <DataTable columns={["Invitado", "Modo", "Estado", "Token", "Accesos", "Último acceso", "Acciones"]}>
            <tbody>
              {invites.map((invite) => {
                const statusMeta = getInviteStatus(invite);
                return (
                  <tr key={invite.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(invite.nombre, "Invitado")}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(invite.email, "Sin correo")}</div>
                    </td>
                    <td>{getExternalAccessModeLabel(invite.modo_acceso)}</td>
                    <td>
                      <StatusBadge tone={statusMeta.tone}>{statusMeta.label}</StatusBadge>
                    </td>
                    <td>{safeDisplayText(invite.token_preview, "—")}</td>
                    <td>{safeDisplayText(invite.total_accesos, "0")}</td>
                    <td>{formatDateTime(invite.ultimo_acceso_at)}</td>
                    <td>
                      <div className="inventory-actions inventory-actions-wrap">
                        <ActionButton
                          icon={<RotateCcw size={14} strokeWidth={1.9} />}
                          onClick={() => handleRegenerateInvite(invite.id)}
                          size="sm"
                          type="button"
                        >
                          Regenerar link
                        </ActionButton>
                        <ActionButton
                          icon={<ShieldOff size={14} strokeWidth={1.9} />}
                          onClick={() => handleRevokeInvite(invite.id)}
                          size="sm"
                          tone="danger"
                          type="button"
                        >
                          Revocar acceso
                        </ActionButton>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <DataCard subtitle="Historial básico de accesos y eventos del portal." title="Bitácora de acceso">
        {logs.length === 0 ? (
          <EmptyState compact note="Aún no hay accesos registrados en el portal." title="Sin bitácora" />
        ) : (
          <div className="pm-portal-log-list">
            {logs.map((logEntry) => (
              <article className="pm-portal-log-item" key={logEntry.id}>
                <div className="pm-portal-log-head">
                  <strong>{safeDisplayText(logEntry.accion, "Acción")}</strong>
                  <StatusBadge tone={logEntry.resultado === "ok" ? "success" : "warning"}>
                    {safeDisplayText(logEntry.resultado, "ok")}
                  </StatusBadge>
                </div>
                <p>{safeDisplayText(logEntry.detalle, "Sin detalle")}</p>
                <span className="inventory-cell-sub">{formatDateTime(logEntry.created_at)}</span>
              </article>
            ))}
          </div>
        )}
      </DataCard>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeCreateModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="pm-portal-invite-form" tone="primary" type="submit">
              {submitting ? "Creando..." : "Crear acceso externo"}
            </ActionButton>
          </div>
        )}
        onClose={closeCreateModal}
        open={createModalOpen}
        size="medium"
        subtitle="Comparte una vista pública limitada del proyecto."
        title="Crear acceso externo"
      >
        <form className="inventory-modal-form" id="pm-portal-invite-form" onSubmit={handleCreateInvite}>
          <FormGrid>
            <Field label="Nombre">
              <input
                onChange={(event) => setInviteForm((current) => ({ ...current, nombre: event.target.value }))}
                required
                type="text"
                value={inviteForm.nombre}
              />
            </Field>
            <Field label="Email">
              <input
                onChange={(event) => setInviteForm((current) => ({ ...current, email: event.target.value }))}
                placeholder="Opcional"
                type="email"
                value={inviteForm.email}
              />
            </Field>
            <Field label="Modo de acceso">
              <select
                onChange={(event) => setInviteForm((current) => ({ ...current, modo_acceso: event.target.value }))}
                value={inviteForm.modo_acceso}
              >
                {pmExternalAccessModeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Fecha de expiración">
              <input
                onChange={(event) => setInviteForm((current) => ({ ...current, expira_at: event.target.value }))}
                type="datetime-local"
                value={inviteForm.expira_at}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>
    </div>
  );
}
