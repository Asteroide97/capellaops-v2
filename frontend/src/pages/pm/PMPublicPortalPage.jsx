import { useEffect, useState } from "react";
import { Calendar, FileText, MessageSquare, RefreshCw } from "lucide-react";
import { useParams } from "react-router-dom";

import { createPmPortalComment, getPmPortalProject } from "../../api/client";
import {
  ActionButton,
  DataCard,
  EmptyState,
  Field,
  MetricCard,
  StatusBadge,
  formatDate,
  safeDisplayText,
} from "../inventory/shared";
import { formatPercent, getTaskStatusLabel, getTaskStatusTone } from "./shared";


function getErrorMessage(error, fallback) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}


export default function PMPublicPortalPage() {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [portalProject, setPortalProject] = useState(null);
  const [commentAuthor, setCommentAuthor] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function loadPortal({ background = false } = {}) {
    if (!token) {
      return;
    }
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const response = await getPmPortalProject({ token });
      setPortalProject(response);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Este enlace no está disponible."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadPortal();
  }, [token]);

  async function handleSubmitComment(event) {
    event.preventDefault();
    if (!token) {
      return;
    }
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await createPmPortalComment({
        token,
        payload: {
          autor_nombre: commentAuthor.trim() || null,
          body: commentBody.trim(),
        },
      });
      setSuccess("Comentario enviado.");
      setCommentBody("");
      await loadPortal({ background: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo enviar el comentario."));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="pm-public-portal-shell"><p className="table-note">Cargando portal...</p></div>;
  }

  if (error && !portalProject) {
    return (
      <div className="pm-public-portal-shell">
        <DataCard subtitle="Verifica con tu administrador interno del proyecto." title="Portal del proyecto">
          <EmptyState compact note={error} title="Este enlace no está disponible." />
        </DataCard>
      </div>
    );
  }

  return (
    <div className="pm-public-portal-shell">
      <section className="pm-public-portal-hero">
        <div>
          <p className="eyebrow">Capella Ops</p>
          <h1>{safeDisplayText(portalProject?.nombre, "Proyecto")}</h1>
          <p className="table-note">
            {safeDisplayText(portalProject?.codigo, "Sin código")} · {safeDisplayText(portalProject?.estatus, "Activo")}
          </p>
        </div>
        <div className="inventory-actions">
          <ActionButton
            icon={<RefreshCw size={16} strokeWidth={1.9} />}
            onClick={() => loadPortal({ background: true })}
            type="button"
          >
            {refreshing ? "Actualizando..." : "Actualizar"}
          </ActionButton>
        </div>
      </section>

      {error ? <div className="inventory-inline-feedback inventory-inline-feedback-danger">{error}</div> : null}
      {success ? <div className="inventory-inline-feedback inventory-inline-feedback-success">{success}</div> : null}

      <div className="inventory-metrics-grid pm-public-portal-metrics">
        <MetricCard label="Avance" value={formatPercent(portalProject?.porcentaje_avance ?? 0)} />
        <MetricCard label="Pendientes" value={String(portalProject?.tasks_summary?.pendientes ?? 0)} />
        <MetricCard label="En progreso" value={String(portalProject?.tasks_summary?.en_progreso ?? 0)} />
        <MetricCard label="Completadas" value={String(portalProject?.tasks_summary?.completadas ?? 0)} />
      </div>

      <div className="pm-public-portal-grid">
        <DataCard
          subtitle="Vista limitada del proyecto compartida por la empresa."
          title="Resumen del proyecto"
        >
          <div className="pm-public-portal-summary">
            <div>
              <strong>Estatus</strong>
              <StatusBadge tone="info">{safeDisplayText(portalProject?.estatus, "Activo")}</StatusBadge>
            </div>
            <div>
              <strong>Inicio</strong>
              <span>{formatDate(portalProject?.fecha_inicio)}</span>
            </div>
            <div>
              <strong>Fin planificado</strong>
              <span>{formatDate(portalProject?.fecha_fin_planificada)}</span>
            </div>
            <div>
              <strong>Acceso</strong>
              <span>{portalProject?.can_comment ? "Puede comentar" : "Solo lectura"}</span>
            </div>
          </div>
        </DataCard>

        <DataCard subtitle="Tareas visibles para seguimiento general." title="Resumen de tareas">
          {portalProject?.tasks?.length ? (
            <div className="pm-public-task-list">
              {portalProject.tasks.map((task, index) => (
                <article className="pm-public-task-card" key={`${task.titulo}-${index}`}>
                  <div className="pm-public-task-head">
                    <strong>{safeDisplayText(task.titulo, "Tarea")}</strong>
                    <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                  </div>
                  <div className="pm-public-task-meta">
                    <span><Calendar size={14} strokeWidth={1.9} /> {formatDate(task.fecha_vencimiento)}</span>
                    <span>{formatPercent(task.porcentaje_avance)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState compact note="Todavía no hay tareas visibles en este proyecto." title="Sin tareas" />
          )}
        </DataCard>
      </div>

      <DataCard subtitle="Solo se muestran archivos marcados como visibles para cliente." title="Documentos visibles">
        {portalProject?.documents?.length ? (
          <div className="pm-public-document-list">
            {portalProject.documents.map((document, index) => (
              <a className="pm-public-document-card" href={document.url_archivo} key={`${document.url_archivo}-${index}`} rel="noreferrer" target="_blank">
                <div className="pm-public-document-head">
                  <FileText size={18} strokeWidth={1.9} />
                  <strong>{safeDisplayText(document.nombre, "Documento")}</strong>
                </div>
                <span>{safeDisplayText(document.tipo_documento, "Documento")}</span>
                <small>{formatDate(document.created_at)}</small>
              </a>
            ))}
          </div>
        ) : (
          <EmptyState compact note="No hay documentos visibles para cliente." title="Sin documentos visibles" />
        )}
      </DataCard>

      <DataCard subtitle="Comentarios enviados desde este portal." title="Comentarios externos">
        {portalProject?.comments?.length ? (
          <div className="pm-comment-list">
            {portalProject.comments.map((comment, index) => (
              <article className="pm-comment-card" key={`${comment.created_at}-${index}`}>
                <div className="pm-comment-head">
                  <strong>{safeDisplayText(comment.autor_nombre, "Invitado")}</strong>
                  <span className="inventory-cell-sub">{formatDate(comment.created_at)}</span>
                </div>
                <p>{safeDisplayText(comment.body, "")}</p>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState compact note="Todavía no hay comentarios externos." title="Sin comentarios" />
        )}

        {portalProject?.can_comment ? (
          <form className="inventory-modal-form pm-public-comment-form" onSubmit={handleSubmitComment}>
            <Field label="Nombre">
              <input
                onChange={(event) => setCommentAuthor(event.target.value)}
                placeholder={safeDisplayText(portalProject?.invite_name, "Opcional")}
                type="text"
                value={commentAuthor}
              />
            </Field>
            <Field label="Comentario">
              <textarea
                maxLength={1000}
                onChange={(event) => setCommentBody(event.target.value)}
                required
                rows={4}
                value={commentBody}
              />
            </Field>
            <div className="inventory-actions">
              <ActionButton
                disabled={submitting || !commentBody.trim()}
                icon={<MessageSquare size={14} strokeWidth={1.9} />}
                tone="primary"
                type="submit"
              >
                {submitting ? "Enviando..." : "Enviar comentario"}
              </ActionButton>
            </div>
          </form>
        ) : (
          <div className="pm-public-readonly-note">Este acceso es solo de lectura.</div>
        )}
      </DataCard>
    </div>
  );
}
