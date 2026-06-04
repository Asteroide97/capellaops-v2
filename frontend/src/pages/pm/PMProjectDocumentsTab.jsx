import { useEffect, useMemo, useState } from "react";
import { Eye, EyeOff, FileUp, Pencil, RefreshCw, Trash2 } from "lucide-react";

import {
  deactivatePmProjectDocument,
  listPmProjectDocuments,
  updatePmProjectDocument,
  uploadPmProjectDocument,
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
import { getDocumentTypeLabel, pmDocumentTypeOptions } from "./shared";

const defaultUploadForm = {
  file: null,
  nombre: "",
  tipo_documento: "otro",
  descripcion: "",
  visible_externo: false,
};

const defaultEditForm = {
  id: "",
  nombre: "",
  tipo_documento: "otro",
  descripcion: "",
  visible_externo: false,
};

function formatBytes(sizeBytes) {
  const value = Number(sizeBytes ?? 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "—";
  }
  if (value >= 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(2)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value} B`;
}

function getErrorMessage(error, fallback) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}

export default function PMProjectDocumentsTab({ empresaId, projectId, token }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [documents, setDocuments] = useState([]);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [uploadForm, setUploadForm] = useState(defaultUploadForm);
  const [editForm, setEditForm] = useState(defaultEditForm);
  const [submitting, setSubmitting] = useState(false);

  const documentsCount = useMemo(() => documents.length, [documents]);
  const storageNotConfigured = error.includes("almacenamiento de documentos no está configurado");

  async function loadDocuments({ background = false } = {}) {
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
      const response = await listPmProjectDocuments({ projectId, token, empresaId });
      setDocuments(response ?? []);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudieron cargar los documentos del proyecto."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, [token, empresaId, projectId]);

  function resetUploadForm() {
    setUploadForm(defaultUploadForm);
  }

  function closeUploadModal(force = false) {
    if (submitting && !force) {
      return;
    }
    setUploadModalOpen(false);
    resetUploadForm();
  }

  function closeEditModal(force = false) {
    if (submitting && !force) {
      return;
    }
    setEditModalOpen(false);
    setEditForm(defaultEditForm);
  }

  async function handleUploadDocument(event) {
    event.preventDefault();
    if (!uploadForm.file) {
      setError("Debes seleccionar un archivo.");
      return;
    }
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const formData = new FormData();
      formData.append("file", uploadForm.file);
      formData.append("nombre", uploadForm.nombre.trim());
      formData.append("tipo_documento", uploadForm.tipo_documento);
      formData.append("descripcion", uploadForm.descripcion.trim());
      formData.append("visible_externo", String(uploadForm.visible_externo));
      await uploadPmProjectDocument({ projectId, token, empresaId, formData });
      setSuccess("Documento cargado.");
      await loadDocuments({ background: true });
      closeUploadModal(true);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo subir el documento."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUpdateDocument(event) {
    event.preventDefault();
    if (!editForm.id) {
      return;
    }
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await updatePmProjectDocument({
        documentId: editForm.id,
        token,
        empresaId,
        payload: {
          nombre: editForm.nombre.trim(),
          tipo_documento: editForm.tipo_documento,
          descripcion: editForm.descripcion.trim(),
          visible_externo: editForm.visible_externo,
        },
      });
      setSuccess("Documento actualizado.");
      await loadDocuments({ background: true });
      closeEditModal(true);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo actualizar el documento."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleExternal(document) {
    setError("");
    setSuccess("");
    try {
      await updatePmProjectDocument({
        documentId: document.id,
        token,
        empresaId,
        payload: {
          visible_externo: !document.visible_externo,
        },
      });
      setSuccess(document.visible_externo ? "Documento marcado como solo interno." : "Documento visible para cliente.");
      await loadDocuments({ background: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo actualizar la visibilidad del documento."));
    }
  }

  async function handleDeactivateDocument(documentId) {
    setError("");
    setSuccess("");
    try {
      await deactivatePmProjectDocument({ documentId, token, empresaId });
      setSuccess("Documento desactivado.");
      await loadDocuments({ background: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo desactivar el documento."));
    }
  }

  return (
    <DataCard
      actions={(
        <div className="inventory-actions inventory-actions-wrap">
          <ActionButton
            icon={<RefreshCw size={16} strokeWidth={1.9} />}
            onClick={() => loadDocuments({ background: true })}
            type="button"
          >
            {refreshing ? "Actualizando..." : "Actualizar"}
          </ActionButton>
          <ActionButton
            icon={<FileUp size={16} strokeWidth={1.9} />}
            onClick={() => {
              setError("");
              setSuccess("");
              setUploadModalOpen(true);
            }}
            tone="primary"
            type="button"
          >
            Subir documento
          </ActionButton>
        </div>
      )}
      subtitle="Contratos, minutas, alcances, evidencias y entregables del proyecto."
      title="Documentos del proyecto"
    >
      {error ? <div className="inventory-inline-feedback inventory-inline-feedback-danger">{error}</div> : null}
      {success ? <div className="inventory-inline-feedback inventory-inline-feedback-success">{success}</div> : null}
      {storageNotConfigured ? (
        <div className="inventory-inline-feedback inventory-inline-feedback-warning">
          Para subir documentos reales, configura Azure Blob Storage en `backend/.env`.
        </div>
      ) : null}

      {loading ? (
        <p className="table-note">Cargando documentos...</p>
      ) : documentsCount === 0 ? (
        <EmptyState
          compact
          note="Sube contratos, minutas, evidencias u otros archivos del proyecto."
          title="No hay documentos todavía."
        />
      ) : (
        <DataTable columns={["Documento", "Tipo", "Visibilidad", "Tamaño", "Fecha", "Acciones"]}>
          <tbody>
            {documents.map((document) => (
              <tr key={document.id}>
                <td>
                  <div className="inventory-cell-main">{safeDisplayText(document.nombre, "Documento")}</div>
                  <div className="inventory-cell-sub">{safeDisplayText(document.nombre_archivo, "—")}</div>
                </td>
                <td>{getDocumentTypeLabel(document.tipo_documento)}</td>
                <td>
                  <StatusBadge tone={document.visible_externo ? "success" : "neutral"}>
                    {document.visible_externo ? "Visible para cliente" : "Solo interno"}
                  </StatusBadge>
                </td>
                <td>{formatBytes(document.size_bytes)}</td>
                <td>{formatDateTime(document.created_at)}</td>
                <td>
                  <div className="inventory-actions inventory-actions-wrap">
                    <a
                      className="inventory-button ghost-button inventory-button inventory-button-sm"
                      href={document.url_archivo}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <span>Ver</span>
                    </a>
                    <ActionButton
                      icon={<Pencil size={14} strokeWidth={1.9} />}
                      onClick={() => {
                        setEditForm({
                          id: document.id,
                          nombre: document.nombre ?? "",
                          tipo_documento: document.tipo_documento ?? "otro",
                          descripcion: document.descripcion ?? "",
                          visible_externo: Boolean(document.visible_externo),
                        });
                        setError("");
                        setSuccess("");
                        setEditModalOpen(true);
                      }}
                      size="sm"
                      type="button"
                    >
                      Editar
                    </ActionButton>
                    <ActionButton
                      icon={document.visible_externo ? <EyeOff size={14} strokeWidth={1.9} /> : <Eye size={14} strokeWidth={1.9} />}
                      onClick={() => handleToggleExternal(document)}
                      size="sm"
                      type="button"
                    >
                      {document.visible_externo ? "Ocultar del portal" : "Mostrar en portal"}
                    </ActionButton>
                    <ActionButton
                      icon={<Trash2 size={14} strokeWidth={1.9} />}
                      onClick={() => handleDeactivateDocument(document.id)}
                      size="sm"
                      tone="danger"
                      type="button"
                    >
                      Desactivar
                    </ActionButton>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeUploadModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="pm-document-upload-form" tone="primary" type="submit">
              {submitting ? "Subiendo..." : "Subir documento"}
            </ActionButton>
          </div>
        )}
        onClose={closeUploadModal}
        open={uploadModalOpen}
        size="medium"
        subtitle="Visible para cliente mostrará el archivo en el portal externo."
        title="Subir documento"
      >
        {error ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo subir el documento</strong>
            <p className="table-note">{error}</p>
          </div>
        ) : null}
        <form className="inventory-modal-form" id="pm-document-upload-form" onSubmit={handleUploadDocument}>
          <FormGrid>
            <Field label="Archivo" span={2}>
              <input
                accept=".pdf,.jpg,.jpeg,.png,.webp,.docx,.xlsx,.txt"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setUploadForm((current) => ({
                    ...current,
                    file,
                    nombre: current.nombre || file?.name || "",
                  }));
                }}
                required
                type="file"
              />
            </Field>
            <Field label="Nombre" span={2}>
              <input
                onChange={(event) => setUploadForm((current) => ({ ...current, nombre: event.target.value }))}
                required
                type="text"
                value={uploadForm.nombre}
              />
            </Field>
            <Field label="Tipo">
              <select
                onChange={(event) => setUploadForm((current) => ({ ...current, tipo_documento: event.target.value }))}
                value={uploadForm.tipo_documento}
              >
                {pmDocumentTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Visible para cliente">
              <label className="pm-inline-checkbox">
                <input
                  checked={uploadForm.visible_externo}
                  onChange={(event) => setUploadForm((current) => ({ ...current, visible_externo: event.target.checked }))}
                  type="checkbox"
                />
                <span>Mostrar en el portal externo</span>
              </label>
            </Field>
            <Field label="Descripción" span={2}>
              <textarea
                onChange={(event) => setUploadForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={4}
                value={uploadForm.descripcion}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeEditModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="pm-document-edit-form" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Guardar cambios"}
            </ActionButton>
          </div>
        )}
        onClose={closeEditModal}
        open={editModalOpen}
        size="medium"
        subtitle="Actualiza la clasificación y visibilidad del documento."
        title="Editar documento"
      >
        {error ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo actualizar el documento</strong>
            <p className="table-note">{error}</p>
          </div>
        ) : null}
        <form className="inventory-modal-form" id="pm-document-edit-form" onSubmit={handleUpdateDocument}>
          <FormGrid>
            <Field label="Nombre" span={2}>
              <input
                onChange={(event) => setEditForm((current) => ({ ...current, nombre: event.target.value }))}
                required
                type="text"
                value={editForm.nombre}
              />
            </Field>
            <Field label="Tipo">
              <select
                onChange={(event) => setEditForm((current) => ({ ...current, tipo_documento: event.target.value }))}
                value={editForm.tipo_documento}
              >
                {pmDocumentTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Visible para cliente">
              <label className="pm-inline-checkbox">
                <input
                  checked={editForm.visible_externo}
                  onChange={(event) => setEditForm((current) => ({ ...current, visible_externo: event.target.checked }))}
                  type="checkbox"
                />
                <span>Mostrar en el portal externo</span>
              </label>
            </Field>
            <Field label="Descripción" span={2}>
              <textarea
                onChange={(event) => setEditForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={4}
                value={editForm.descripcion}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>
    </DataCard>
  );
}
