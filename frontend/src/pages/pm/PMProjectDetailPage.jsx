import { useEffect, useMemo, useState } from "react";
import {
  Calendar,
  CheckSquare,
  Folder,
  FolderKanban,
  Gauge,
  MessageSquare,
  Plus,
  Users,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import {
  addPmProjectMember,
  createPmProjectComment,
  deactivatePmProjectMember,
  getPmProject,
  listPmProjectMembers,
  listPmTasks,
} from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FormGrid,
  MetricCard,
  ModalShell,
  PageHeader,
  ResultMeta,
  StatusBadge,
  formatDate,
  formatMoney,
  safeDisplayText,
} from "../inventory/shared";
import PMTaskDetailModal from "./PMTaskDetailModal";
import PMProjectMaterialsTab from "./PMProjectMaterialsTab";
import {
  formatPercent,
  getPriorityLabel,
  getPriorityTone,
  getProjectStatusLabel,
  getProjectStatusTone,
  getTaskStatusLabel,
  getTaskStatusTone,
  isTaskOverdue,
  projectMemberRoleOptions,
} from "./shared";


const projectTabs = [
  { key: "resumen", label: "Resumen", icon: Folder },
  { key: "tareas", label: "Tareas", icon: CheckSquare },
  { key: "miembros", label: "Miembros", icon: Users },
  { key: "comentarios", label: "Comentarios", icon: MessageSquare },
  { key: "materiales", label: "Materiales", icon: FolderKanban },
  { key: "compras", label: "Compras", icon: FolderKanban },
  { key: "costos", label: "Costos", icon: Gauge },
  { key: "documentos", label: "Documentos", icon: FolderKanban },
];

const defaultMemberForm = {
  email: "",
  nombre_snapshot: "",
  rol_en_proyecto: "colaborador",
};


function PlaceholderTab({ title, note }) {
  return (
    <DataCard title={title}>
      <EmptyState note={note} title="Disponible en fase posterior" />
    </DataCard>
  );
}


export default function PMProjectDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { empresaId, token } = useAuth();
  const [activeTab, setActiveTab] = useState("resumen");
  const [loading, setLoading] = useState(true);
  const [taskLoading, setTaskLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [project, setProject] = useState(null);
  const [members, setMembers] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [memberForm, setMemberForm] = useState(defaultMemberForm);
  const [commentBody, setCommentBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function loadProjectBundle() {
    if (!token || !empresaId || !id) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const [projectResponse, membersResponse, tasksResponse] = await Promise.all([
        getPmProject({ projectId: id, token, empresaId }),
        listPmProjectMembers({ projectId: id, token, empresaId }),
        listPmTasks({
          projectId: id,
          token,
          empresaId,
          filters: { limit: 100, offset: 0, activo: true },
        }),
      ]);
      setProject(projectResponse);
      setMembers(membersResponse.items ?? []);
      setTasks(tasksResponse.items ?? []);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el proyecto.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProjectBundle();
  }, [token, empresaId, id]);

  const activeMembers = useMemo(() => members.filter((item) => item.activo), [members]);
  const tasksByStatus = useMemo(() => {
    const groups = {
      pendiente: [],
      en_progreso: [],
      en_revision: [],
      completada: [],
      cancelada: [],
    };
    tasks.forEach((task) => {
      const key = groups[task.estatus] ? task.estatus : "pendiente";
      groups[key].push(task);
    });
    return groups;
  }, [tasks]);

  function openNewTaskModal() {
    setSelectedTaskId(null);
    setTaskModalOpen(true);
  }

  function openExistingTaskModal(taskId) {
    setSelectedTaskId(taskId);
    setTaskModalOpen(true);
  }

  function closeTaskModal() {
    setTaskModalOpen(false);
    setSelectedTaskId(null);
  }

  function closeMemberModal() {
    if (submitting) {
      return;
    }
    setMemberModalOpen(false);
    setMemberForm(defaultMemberForm);
  }

  async function refreshTasksAndProject() {
    if (!id) {
      return;
    }
    setTaskLoading(true);
    try {
      const [projectResponse, tasksResponse] = await Promise.all([
        getPmProject({ projectId: id, token, empresaId }),
        listPmTasks({ projectId: id, token, empresaId, filters: { limit: 100, offset: 0, activo: true } }),
      ]);
      setProject(projectResponse);
      setTasks(tasksResponse.items ?? []);
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el proyecto.");
    } finally {
      setTaskLoading(false);
    }
  }

  async function handleTaskSaved() {
    await refreshTasksAndProject();
  }

  async function handleAddMember(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await addPmProjectMember({
        projectId: id,
        token,
        empresaId,
        payload: {
          email: memberForm.email.trim() || null,
          nombre_snapshot: memberForm.nombre_snapshot.trim() || null,
          rol_en_proyecto: memberForm.rol_en_proyecto,
        },
      });
      setSuccess("Miembro agregado al proyecto.");
      closeMemberModal();
      const response = await listPmProjectMembers({ projectId: id, token, empresaId });
      setMembers(response.items ?? []);
    } catch (requestError) {
      setError(requestError.message || "No se pudo agregar el miembro.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeactivateMember(memberId) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmProjectMember({ projectId: id, memberId, token, empresaId });
      setSuccess("Miembro desactivado.");
      const response = await listPmProjectMembers({ projectId: id, token, empresaId });
      setMembers(response.items ?? []);
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el miembro.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateProjectComment(event) {
    event.preventDefault();
    if (!commentBody.trim()) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await createPmProjectComment({
        projectId: id,
        token,
        empresaId,
        payload: { body: commentBody.trim() },
      });
      setCommentBody("");
      setSuccess("Comentario agregado.");
      const projectResponse = await getPmProject({ projectId: id, token, empresaId });
      setProject(projectResponse);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el comentario.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando proyecto PM...</div>;
  }

  if (!project) {
    return (
      <EmptyState
        action={
          <ActionButton onClick={() => navigate("/pm/projects")} tone="primary" type="button">
            Volver a proyectos
          </ActionButton>
        }
        note="No fue posible cargar el detalle del proyecto."
        title="Proyecto no disponible"
      />
    );
  }

  return (
    <div className="inventory-shell inventory-screen pm-screen">
      <PageHeader
        eyebrow="PM Core"
        title={project.nombre}
        subtitle="Detalle operativo de proyecto, tareas, miembros y comentarios."
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={() => navigate("/pm/projects")} type="button">
              Volver a proyectos
            </ActionButton>
            <ActionButton onClick={openNewTaskModal} tone="primary" type="button">
              Nueva tarea
            </ActionButton>
          </div>
        }
        meta={
          <div className="inventory-inline-meta">
            <StatusBadge tone={getProjectStatusTone(project.estatus)}>{getProjectStatusLabel(project.estatus)}</StatusBadge>
            <StatusBadge tone={getPriorityTone(project.prioridad)}>{getPriorityLabel(project.prioridad)}</StatusBadge>
            <span className="table-note">{safeDisplayText(project.codigo, "Sin codigo")}</span>
          </div>
        }
      />

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operacion" : "Operacion completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard
          icon={<Gauge size={18} strokeWidth={1.9} />}
          label="Avance"
          meta="Calculado desde tareas activas"
          tone="info"
          value={formatPercent(project.porcentaje_avance)}
        />
        <MetricCard
          icon={<CheckSquare size={18} strokeWidth={1.9} />}
          label="Tareas"
          meta="Activas en el proyecto"
          tone="success"
          value={project.task_stats?.total ?? 0}
        />
        <MetricCard
          icon={<Users size={18} strokeWidth={1.9} />}
          label="Miembros"
          meta="Asignados al proyecto"
          tone="neutral"
          value={project.miembros_activos ?? activeMembers.length}
        />
        <MetricCard
          icon={<Calendar size={18} strokeWidth={1.9} />}
          label="Vencidas"
          meta="Tareas fuera de fecha"
          tone="warning"
          value={project.task_stats?.vencidas ?? 0}
        />
      </section>

      <div className="inventory-subnav pm-subnav">
        {projectTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              className={`inventory-tab-button ${activeTab === tab.key ? "active" : ""}`}
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              type="button"
            >
              <span className="inventory-button-glyph"><Icon size={15} strokeWidth={1.9} /></span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {activeTab === "resumen" ? (
        <div className="inventory-content-grid inventory-content-grid-2">
          <DataCard subtitle="Contexto general y datos base." title="Resumen del proyecto">
            <div className="pm-meta-list">
              <div>
                <strong>Responsable</strong>
                <span>{safeDisplayText(project.responsable_nombre_snapshot, "Sin responsable")}</span>
              </div>
              <div>
                <strong>Cliente</strong>
                <span>{safeDisplayText(project.cliente_nombre_snapshot, "Sin cliente")}</span>
              </div>
              <div>
                <strong>Inicio</strong>
                <span>{safeDisplayText(formatDate(project.fecha_inicio), "-")}</span>
              </div>
              <div>
                <strong>Fin planificada</strong>
                <span>{safeDisplayText(formatDate(project.fecha_fin_planificada), "-")}</span>
              </div>
              <div>
                <strong>Fin real</strong>
                <span>{safeDisplayText(formatDate(project.fecha_fin_real), "-")}</span>
              </div>
              <div>
                <strong>Presupuesto</strong>
                <span>{formatMoney(project.presupuesto_estimado ?? 0)}</span>
              </div>
            </div>
            <div className="inventory-form-note">
              <strong>Descripcion</strong>
              <p className="table-note">{safeDisplayText(project.descripcion, "Sin descripcion operativa.")}</p>
            </div>
          </DataCard>

          <DataCard subtitle="Conteo simple de ejecucion." title="KPIs de tareas">
            <div className="inventory-metric-grid inventory-metric-grid-4">
              <MetricCard label="Pendientes" meta="Backlog" tone="neutral" value={project.task_stats?.pendientes ?? 0} />
              <MetricCard label="En progreso" meta="Ejecucion" tone="info" value={project.task_stats?.en_progreso ?? 0} />
              <MetricCard label="En revision" meta="Validacion" tone="warning" value={project.task_stats?.en_revision ?? 0} />
              <MetricCard label="Completadas" meta="Cierre" tone="success" value={project.task_stats?.completadas ?? 0} />
            </div>
          </DataCard>
        </div>
      ) : null}

      {activeTab === "tareas" ? (
        <div className="inventory-content-grid">
          <DataCard
            actions={
              <ActionButton disabled={taskLoading} onClick={openNewTaskModal} tone="primary" type="button">
                Nueva tarea
              </ActionButton>
            }
            subtitle="Kanban simple por estatus y listado editable."
            title="Tareas del proyecto"
          >
            <div className="pm-kanban-grid">
              {["pendiente", "en_progreso", "en_revision", "completada"].map((statusKey) => (
                <div className="pm-kanban-column" key={statusKey}>
                  <div className="pm-kanban-column-head">
                    <StatusBadge tone={getTaskStatusTone(statusKey)}>{getTaskStatusLabel(statusKey)}</StatusBadge>
                    <strong>{tasksByStatus[statusKey]?.length ?? 0}</strong>
                  </div>
                  {(tasksByStatus[statusKey]?.length ?? 0) === 0 ? (
                    <EmptyState compact note="Sin tareas en esta columna." title="Vacio" />
                  ) : (
                    <div className="pm-kanban-card-stack">
                      {tasksByStatus[statusKey].map((task) => (
                        <button
                          className="pm-task-card"
                          key={task.id}
                          onClick={() => openExistingTaskModal(task.id)}
                          type="button"
                        >
                          <div className="pm-task-card-head">
                            <strong>{safeDisplayText(task.titulo)}</strong>
                            <StatusBadge tone={getPriorityTone(task.prioridad)}>{getPriorityLabel(task.prioridad)}</StatusBadge>
                          </div>
                          <div className="inventory-cell-sub">{safeDisplayText(task.asignado_nombre_snapshot, "Sin asignacion")}</div>
                          <div className="pm-inline-metadata">
                            <span className="table-note">{safeDisplayText(formatDate(task.fecha_vencimiento), "-")}</span>
                            {isTaskOverdue(task) ? <StatusBadge tone="danger">Vencida</StatusBadge> : null}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <DataTable columns={["Tarea", "Prioridad", "Asignado", "Vence", "Avance", "Acciones"]}>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(task.titulo)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(task.descripcion, "Sin descripcion")}</div>
                    </td>
                    <td>
                      <StatusBadge tone={getPriorityTone(task.prioridad)}>{getPriorityLabel(task.prioridad)}</StatusBadge>
                    </td>
                    <td>{safeDisplayText(task.asignado_nombre_snapshot, "Sin asignacion")}</td>
                    <td>
                      {safeDisplayText(formatDate(task.fecha_vencimiento), "-")}
                      {isTaskOverdue(task) ? <div className="inventory-cell-sub">Vencida</div> : null}
                    </td>
                    <td>{formatPercent(task.porcentaje_avance)}</td>
                    <td>
                      <ActionButton onClick={() => openExistingTaskModal(task.id)} size="sm" type="button">
                        Abrir
                      </ActionButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </DataCard>
        </div>
      ) : null}

      {activeTab === "miembros" ? (
        <DataCard
          actions={
            <ActionButton onClick={() => setMemberModalOpen(true)} tone="primary" type="button">
              Agregar miembro
            </ActionButton>
          }
          subtitle="Miembros internos o snapshots manuales por email/nombre."
          title="Miembros del proyecto"
        >
          <ResultMeta label="miembros" loaded={members.length} total={members.length} />
          {members.length === 0 ? (
            <EmptyState compact note="Aun no se han asignado miembros." title="Sin miembros" />
          ) : (
            <DataTable columns={["Miembro", "Rol", "Estado", "Fecha", "Acciones"]}>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(member.nombre_snapshot, "Sin nombre")}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(member.email, "Sin correo")}</div>
                    </td>
                    <td><StatusBadge tone="info">{safeDisplayText(member.rol_en_proyecto)}</StatusBadge></td>
                    <td><StatusBadge tone={member.activo ? "success" : "neutral"}>{member.activo ? "Activo" : "Inactivo"}</StatusBadge></td>
                    <td>{safeDisplayText(formatDate(member.created_at), "-")}</td>
                    <td>
                      {member.activo ? (
                        <ActionButton onClick={() => handleDeactivateMember(member.id)} size="sm" tone="danger" type="button">
                          Desactivar
                        </ActionButton>
                      ) : (
                        <span className="table-note">Sin acciones</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      ) : null}

      {activeTab === "comentarios" ? (
        <DataCard subtitle="Conversacion del proyecto a nivel general." title="Comentarios">
          <form className="inventory-modal-form" onSubmit={handleCreateProjectComment}>
            <Field label="Nuevo comentario">
              <textarea
                onChange={(event) => setCommentBody(event.target.value)}
                rows={4}
                value={commentBody}
              />
            </Field>
            <div className="inventory-actions">
              <ActionButton disabled={submitting || !commentBody.trim()} tone="primary" type="submit">
                Comentar
              </ActionButton>
            </div>
          </form>
          {(project.comments?.length ?? 0) === 0 ? (
            <EmptyState compact note="Aun no hay comentarios de proyecto." title="Sin comentarios" />
          ) : (
            <div className="pm-comment-list">
              {project.comments.map((comment) => (
                <article className="pm-comment-card" key={comment.id}>
                  <div className="pm-comment-head">
                    <strong>{safeDisplayText(comment.created_by_nombre_snapshot, "Usuario")}</strong>
                    <span className="inventory-cell-sub">{safeDisplayText(formatDate(comment.created_at), "-")}</span>
                  </div>
                  <p>{safeDisplayText(comment.body, "")}</p>
                </article>
              ))}
            </div>
          )}
        </DataCard>
      ) : null}

      {activeTab === "materiales" ? (
        <PMProjectMaterialsTab empresaId={empresaId} project={project} projectId={id} token={token} />
      ) : null}
      {activeTab === "compras" ? (
        <PlaceholderTab note="Se conectara en PM <-> Compras Fase 4." title="Compras del proyecto" />
      ) : null}
      {activeTab === "costos" ? (
        <PlaceholderTab note="Se conectara en PM Tiempo/Costos Fase 3." title="Costos y tiempo" />
      ) : null}
      {activeTab === "documentos" ? (
        <PlaceholderTab note="Se conectara en Portal/Documentos Fase 5." title="Documentos" />
      ) : null}

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeMemberModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="pm-member-form" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Agregar miembro"}
            </ActionButton>
          </div>
        }
        onClose={closeMemberModal}
        open={memberModalOpen}
        size="medium"
        subtitle="Se puede vincular por correo y nombre sin crear usuarios fuera de la empresa."
        title="Agregar miembro al proyecto"
      >
        <form className="inventory-modal-form" id="pm-member-form" onSubmit={handleAddMember}>
          <FormGrid>
            <Field label="Correo">
              <input
                onChange={(event) => setMemberForm((current) => ({ ...current, email: event.target.value }))}
                required
                type="email"
                value={memberForm.email}
              />
            </Field>
            <Field label="Nombre">
              <input
                onChange={(event) => setMemberForm((current) => ({ ...current, nombre_snapshot: event.target.value }))}
                type="text"
                value={memberForm.nombre_snapshot}
              />
            </Field>
            <Field label="Rol" span={2}>
              <select
                onChange={(event) => setMemberForm((current) => ({ ...current, rol_en_proyecto: event.target.value }))}
                value={memberForm.rol_en_proyecto}
              >
                {projectMemberRoleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </FormGrid>
          <div className="inventory-form-note">
            <strong>Vinculacion controlada</strong>
            <p className="table-note">Si el correo ya pertenece a un usuario activo de la empresa, el backend lo vincula automaticamente.</p>
          </div>
        </form>
      </ModalShell>

      <PMTaskDetailModal
        empresaId={empresaId}
        memberOptions={activeMembers}
        onClose={closeTaskModal}
        onSaved={handleTaskSaved}
        open={taskModalOpen}
        projectId={id}
        taskId={selectedTaskId}
        token={token}
      />
    </div>
  );
}
