import { useEffect, useState } from "react";
import { CheckCheck, RefreshCw, ShieldCheck, Slash, XCircle } from "lucide-react";

import {
  approvePmApproval,
  cancelPmApproval,
  createPmProjectApproval,
  listPmProjectApprovals,
  rejectPmApproval,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FormGrid,
  ModalShell,
  StatusBadge,
  formatDateTime,
  safeDisplayText,
} from "../inventory/shared";
import { getApprovalStatusTone, getApprovalTypeLabel, pmApprovalTypeOptions } from "./shared";

const defaultApprovalForm = {
  tipo_aprobacion: "aprobar_presupuesto",
  titulo: "",
  descripcion: "",
  entidad_tipo: "",
  entidad_id: "",
};

const defaultResolveForm = {
  comentario_resolucion: "",
};

const relatedEntityOptions = [
  { value: "", label: "Sin relación directa" },
  { value: "presupuesto", label: "Presupuesto" },
  { value: "documento", label: "Documento" },
  { value: "tarea", label: "Tarea" },
  { value: "otro", label: "Otro" },
];

const approvalStatusLabels = {
  pendiente: "Pendiente",
  aprobada: "Aprobada",
  rechazada: "Rechazada",
  cancelada: "Cancelada",
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

export default function PMProjectApprovalsTab({ empresaId, projectId, token }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [approvals, setApprovals] = useState([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [approvalForm, setApprovalForm] = useState(defaultApprovalForm);
  const [resolveForm, setResolveForm] = useState(defaultResolveForm);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [resolveAction, setResolveAction] = useState("approve");
  const [submitting, setSubmitting] = useState(false);

  const requiresRelatedEntity = Boolean(approvalForm.entidad_tipo);

  async function loadApprovals({ background = false } = {}) {
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
      const response = await listPmProjectApprovals({ projectId, token, empresaId });
      setApprovals(response ?? []);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudieron cargar las aprobaciones."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadApprovals();
  }, [token, empresaId, projectId]);

  function closeCreateModal(force = false) {
    if (submitting && !force) {
      return;
    }
    setCreateModalOpen(false);
    setApprovalForm(defaultApprovalForm);
  }

  function closeResolveModal(force = false) {
    if (submitting && !force) {
      return;
    }
    setResolveModalOpen(false);
    setSelectedApproval(null);
    setResolveForm(defaultResolveForm);
  }

  async function handleCreateApproval(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await createPmProjectApproval({
        projectId,
        token,
        empresaId,
        payload: {
          tipo_aprobacion: approvalForm.tipo_aprobacion,
          titulo: approvalForm.titulo.trim(),
          descripcion: approvalForm.descripcion.trim() || null,
          entidad_tipo: requiresRelatedEntity ? approvalForm.entidad_tipo : null,
          entidad_id: requiresRelatedEntity ? approvalForm.entidad_id.trim() || null : null,
        },
      });
      setSuccess("Aprobación solicitada.");
      await loadApprovals({ background: true });
      closeCreateModal(true);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo crear la aprobación."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResolveApproval(event) {
    event.preventDefault();
    if (!selectedApproval) {
      return;
    }
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = { comentario_resolucion: resolveForm.comentario_resolucion.trim() || null };
      if (resolveAction === "approve") {
        await approvePmApproval({ approvalId: selectedApproval.id, token, empresaId, payload });
      } else if (resolveAction === "reject") {
        await rejectPmApproval({ approvalId: selectedApproval.id, token, empresaId, payload });
      } else {
        await cancelPmApproval({ approvalId: selectedApproval.id, token, empresaId, payload });
      }
      setSuccess(
        resolveAction === "approve"
          ? "Aprobación aprobada."
          : resolveAction === "reject"
            ? "Aprobación rechazada."
            : "Solicitud cancelada.",
      );
      await loadApprovals({ background: true });
      closeResolveModal(true);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo resolver la aprobación."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DataCard
      actions={(
        <div className="inventory-actions inventory-actions-wrap">
          <ActionButton
            icon={<RefreshCw size={16} strokeWidth={1.9} />}
            onClick={() => loadApprovals({ background: true })}
            type="button"
          >
            {refreshing ? "Actualizando..." : "Actualizar"}
          </ActionButton>
          <ActionButton
            icon={<ShieldCheck size={16} strokeWidth={1.9} />}
            onClick={() => {
              setError("");
              setSuccess("");
              setCreateModalOpen(true);
            }}
            tone="primary"
            type="button"
          >
            Solicitar aprobación
          </ActionButton>
        </div>
      )}
      subtitle="Controla aprobaciones de presupuesto, cambios, entregas y cierres."
      title="Aprobaciones"
    >
      {error ? <div className="inventory-inline-feedback inventory-inline-feedback-danger">{error}</div> : null}
      {success ? <div className="inventory-inline-feedback inventory-inline-feedback-success">{success}</div> : null}

      {loading ? (
        <p className="table-note">Cargando aprobaciones...</p>
      ) : approvals.length === 0 ? (
        <EmptyState compact note="Crea la primera solicitud de aprobación del proyecto." title="No hay aprobaciones todavía." />
      ) : (
        <DataTable
          columns={[
            "Título",
            "Tipo",
            "Estatus",
            "Solicitado por",
            "Solicitud",
            "Resuelto por",
            "Resolución",
            "Acciones",
          ]}
        >
          <tbody>
            {approvals.map((approval) => {
              const pending = approval.estatus === "pendiente";
              return (
                <tr key={approval.id}>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(approval.titulo, "Solicitud")}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(approval.descripcion, "—")}</div>
                  </td>
                  <td>{getApprovalTypeLabel(approval.tipo_aprobacion)}</td>
                  <td>
                    <StatusBadge tone={getApprovalStatusTone(approval.estatus)}>
                      {approvalStatusLabels[approval.estatus] ?? approval.estatus}
                    </StatusBadge>
                  </td>
                  <td>{safeDisplayText(approval.solicitado_por_nombre ?? approval.solicitado_por, "—")}</td>
                  <td>{formatDateTime(approval.solicitado_en)}</td>
                  <td>{safeDisplayText(approval.resuelto_por_nombre ?? approval.resuelto_por, "—")}</td>
                  <td>{formatDateTime(approval.resuelto_en)}</td>
                  <td>
                    {pending ? (
                      <div className="inventory-actions inventory-actions-wrap">
                        <ActionButton
                          icon={<CheckCheck size={14} strokeWidth={1.9} />}
                          onClick={() => {
                            setResolveAction("approve");
                            setSelectedApproval(approval);
                            setResolveForm(defaultResolveForm);
                            setResolveModalOpen(true);
                          }}
                          size="sm"
                          tone="primary"
                          type="button"
                        >
                          Aprobar
                        </ActionButton>
                        <ActionButton
                          icon={<XCircle size={14} strokeWidth={1.9} />}
                          onClick={() => {
                            setResolveAction("reject");
                            setSelectedApproval(approval);
                            setResolveForm(defaultResolveForm);
                            setResolveModalOpen(true);
                          }}
                          size="sm"
                          tone="danger"
                          type="button"
                        >
                          Rechazar
                        </ActionButton>
                        <ActionButton
                          icon={<Slash size={14} strokeWidth={1.9} />}
                          onClick={() => {
                            setResolveAction("cancel");
                            setSelectedApproval(approval);
                            setResolveForm(defaultResolveForm);
                            setResolveModalOpen(true);
                          }}
                          size="sm"
                          type="button"
                        >
                          Cancelar
                        </ActionButton>
                      </div>
                    ) : (
                      <span className="inventory-cell-sub">Sin acciones pendientes</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      )}

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeCreateModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="pm-approval-create-form" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Solicitar aprobación"}
            </ActionButton>
          </div>
        )}
        onClose={closeCreateModal}
        open={createModalOpen}
        size="medium"
        subtitle="Relaciona la aprobación con presupuesto, documento o tarea si aplica."
        title="Solicitar aprobación"
      >
        {error ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo solicitar la aprobación</strong>
            <p className="table-note">{error}</p>
          </div>
        ) : null}
        <form className="inventory-modal-form" id="pm-approval-create-form" onSubmit={handleCreateApproval}>
          <FormGrid>
            <Field label="Tipo">
              <select
                onChange={(event) => setApprovalForm((current) => ({ ...current, tipo_aprobacion: event.target.value }))}
                value={approvalForm.tipo_aprobacion}
              >
                {pmApprovalTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Relacionar con">
              <select
                onChange={(event) =>
                  setApprovalForm((current) => ({
                    ...current,
                    entidad_tipo: event.target.value,
                    entidad_id: event.target.value ? current.entidad_id : "",
                  }))
                }
                value={approvalForm.entidad_tipo}
              >
                {relatedEntityOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Título" span={2}>
              <input
                onChange={(event) => setApprovalForm((current) => ({ ...current, titulo: event.target.value }))}
                required
                type="text"
                value={approvalForm.titulo}
              />
            </Field>
            <Field label="ID relacionado" span={2}>
              <input
                disabled={!requiresRelatedEntity}
                onChange={(event) => setApprovalForm((current) => ({ ...current, entidad_id: event.target.value }))}
                placeholder={requiresRelatedEntity ? "Requerido si hay relación directa" : "No aplica para aprobación general"}
                type="text"
                value={approvalForm.entidad_id}
              />
            </Field>
            <Field label="Descripción" span={2}>
              <textarea
                onChange={(event) => setApprovalForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={4}
                value={approvalForm.descripcion}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeResolveModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              disabled={submitting}
              form="pm-approval-resolve-form"
              tone={resolveAction === "approve" ? "primary" : resolveAction === "reject" ? "danger" : "ghost"}
              type="submit"
            >
              {submitting
                ? "Guardando..."
                : resolveAction === "approve"
                  ? "Aprobar"
                  : resolveAction === "reject"
                    ? "Rechazar"
                    : "Cancelar solicitud"}
            </ActionButton>
          </div>
        )}
        onClose={closeResolveModal}
        open={resolveModalOpen}
        size="medium"
        subtitle={safeDisplayText(selectedApproval?.titulo, "Resolución de aprobación")}
        title={
          resolveAction === "approve"
            ? "Aprobar solicitud"
            : resolveAction === "reject"
              ? "Rechazar solicitud"
              : "Cancelar solicitud"
        }
      >
        {error ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo completar la acción</strong>
            <p className="table-note">{error}</p>
          </div>
        ) : null}
        <form className="inventory-modal-form" id="pm-approval-resolve-form" onSubmit={handleResolveApproval}>
          <Field label="Comentario">
            <textarea
              onChange={(event) => setResolveForm({ comentario_resolucion: event.target.value })}
              rows={4}
              value={resolveForm.comentario_resolucion}
            />
          </Field>
        </form>
      </ModalShell>
    </DataCard>
  );
}
