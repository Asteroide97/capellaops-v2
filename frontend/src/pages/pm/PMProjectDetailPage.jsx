import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  BadgeDollarSign,
  Calendar,
  CheckCheck,
  CheckSquare,
  Clock3,
  Eye,
  FileText,
  FolderKanban,
  Gauge,
  Link2,
  Lock,
  MessageSquare,
  PackageOpen,
  Pencil,
  Plus,
  RefreshCw,
  Users,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import {
  addPmProjectMember,
  createPmProjectComment,
  deactivatePmProjectMember,
  deactivatePmTask,
  getPmProject,
  getPmProjectCosts,
  getPmProjectMaterials,
  listPmProjectMembers,
  listPmProjectDependencies,
  listPmProjectTimeEntries,
  listPmTasks,
  updatePmTask,
} from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  ActionButton,
  DataCard,
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
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";
import PMProjectMaterialsTab from "./PMProjectMaterialsTab";
import PMProjectBudgetTab from "./PMProjectBudgetTab";
import PMProjectTimeCostsTab from "./PMProjectTimeCostsTab";
import PMProjectWorkPlanView from "./PMProjectWorkPlanView";
import PMTaskDetailModal from "./PMTaskDetailModal";
import {
  formatPercent,
  getPriorityLabel,
  getPriorityTone,
  getProjectStatusLabel,
  getProjectStatusTone,
  getTaskStatusLabel,
  getTaskStatusTone,
  isTaskOverdue,
  normalizePmCopy,
  projectMemberRoleOptions,
} from "./shared";


const projectViews = [
  { key: "general", label: "Vista general", icon: Gauge },
  { key: "plan", label: "Plan de trabajo", icon: CheckSquare },
  { key: "kanban", label: "Kanban", icon: FolderKanban },
  { key: "presupuesto", label: "Presupuesto", icon: BadgeDollarSign },
  { key: "materiales", label: "Materiales", icon: PackageOpen },
  { key: "costos", label: "Tiempo y costos", icon: Clock3 },
  { key: "comentarios", label: "Comentarios", icon: MessageSquare },
  { key: "documentos", label: "Documentos", icon: FileText },
];

const defaultMemberForm = {
  email: "",
  nombre_snapshot: "",
  rol_en_proyecto: "colaborador",
};


function PlaceholderView({ title, note }) {
  return (
    <DataCard subtitle="Bloque operativo pendiente en una fase posterior." title={title}>
      <EmptyState compact note={note} title="Disponible más adelante" />
    </DataCard>
  );
}


function sortByDateDesc(items, field) {
  return [...(items ?? [])].sort((left, right) => new Date(right?.[field] ?? 0) - new Date(left?.[field] ?? 0));
}


function getTaskBlockerTitles(task) {
  return (task?.blockers ?? [])
    .map((blocker) => safeDisplayText(blocker?.titulo, "").trim())
    .filter(Boolean);
}


function getTaskBlockerSummary(task) {
  const titles = getTaskBlockerTitles(task);
  if (titles.length === 0) {
    return "";
  }
  if (titles.length === 1) {
    return titles[0];
  }
  if (titles.length === 2) {
    return `${titles[0]} y ${titles[1]}`;
  }
  return `${titles[0]}, ${titles[1]} y ${titles.length - 2} más`;
}


function formatTaskTitleList(items) {
  const titles = [...new Set((items ?? []).filter(Boolean))];
  if (titles.length === 0) {
    return "";
  }
  if (titles.length === 1) {
    return titles[0];
  }
  if (titles.length === 2) {
    return `${titles[0]} y ${titles[1]}`;
  }
  return `${titles[0]}, ${titles[1]} y ${titles.length - 2} más`;
}


function getTaskDependencyState(task, dependencies = []) {
  const blocked = Boolean(task?.is_blocked || Number(task?.blockers_count ?? 0) > 0);
  const blockerSummary = formatTaskTitleList(getTaskBlockerTitles(task));
  const dependencyTitles = formatTaskTitleList(
    (dependencies ?? [])
      .map((dependency) => safeDisplayText(dependency?.depende_de_tarea_titulo, "").trim())
      .filter(Boolean),
  );

  if (blocked) {
    return {
      blocked: true,
      badgeLabel: "Bloqueada",
      badgeTone: "warning",
      title: "Bloqueada",
      detail: blockerSummary ? `Depende de: ${blockerSummary}` : "Tiene prerrequisitos pendientes.",
    };
  }

  if (dependencyTitles) {
    return {
      blocked: false,
      badgeLabel: null,
      badgeTone: "success",
      title: "Prerrequisitos completados",
      detail: dependencyTitles,
    };
  }

  return {
    blocked: false,
    badgeLabel: null,
    badgeTone: "success",
    title: "",
    detail: "",
  };
}


export default function PMProjectDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { empresaId, token } = useAuth();

  const [activeView, setActiveView] = useState("plan");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [project, setProject] = useState(null);
  const [projectCosts, setProjectCosts] = useState(null);
  const [projectMaterials, setProjectMaterials] = useState(null);
  const [projectDependencies, setProjectDependencies] = useState([]);
  const [members, setMembers] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [projectTimeEntries, setProjectTimeEntries] = useState([]);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [selectedTaskModalId, setSelectedTaskModalId] = useState(null);
  const [memberForm, setMemberForm] = useState(defaultMemberForm);
  const [commentBody, setCommentBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function loadProjectBundle({ background = false } = {}) {
    if (!token || !empresaId || !id) {
      return;
    }

    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");

    try {
      const [projectResponse, costsResponse, materialsResponse, dependenciesResponse, membersResponse, tasksResponse, timeEntriesResponse] = await Promise.all([
        getPmProject({ projectId: id, token, empresaId }),
        getPmProjectCosts({ projectId: id, token, empresaId }),
        getPmProjectMaterials({ projectId: id, token, empresaId }),
        listPmProjectDependencies({ projectId: id, token, empresaId }),
        listPmProjectMembers({ projectId: id, token, empresaId }),
        listPmTasks({ projectId: id, token, empresaId, filters: { limit: 100, offset: 0, activo: true } }),
        listPmProjectTimeEntries({ projectId: id, token, empresaId, filters: { limit: 200, offset: 0, activo: true } }),
      ]);

      const nextTasks = tasksResponse.items ?? [];
      setProject(projectResponse);
      setProjectCosts(costsResponse);
      setProjectMaterials(materialsResponse);
      setProjectDependencies(dependenciesResponse ?? []);
      setMembers(membersResponse.items ?? []);
      setTasks(nextTasks);
      setProjectTimeEntries(timeEntriesResponse.items ?? []);
      setSelectedTaskId((current) => {
        if (current && nextTasks.some((task) => task.id === current)) {
          return current;
        }
        return nextTasks[0]?.id ?? null;
      });
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el proyecto.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadProjectBundle();
  }, [token, empresaId, id]);

  const activeMembers = useMemo(() => members.filter((item) => item.activo), [members]);
  const activeTasks = useMemo(
    () => tasks.filter((task) => task.activo && !["completada", "cancelada"].includes(String(task.estatus || "").toLowerCase())),
    [tasks],
  );
  const overdueTasks = useMemo(() => tasks.filter((task) => isTaskOverdue(task)), [tasks]);
  const tasksByStatus = useMemo(() => {
    const groups = {
      pendiente: [],
      en_progreso: [],
      en_revision: [],
      completada: [],
    };
    tasks.forEach((task) => {
      const key = groups[task.estatus] ? task.estatus : "pendiente";
      groups[key].push(task);
    });
    return groups;
  }, [tasks]);
  const taskDependenciesMap = useMemo(
    () =>
      (projectDependencies ?? []).reduce((accumulator, dependency) => {
        if (!dependency?.tarea_id || dependency.activo === false) {
          return accumulator;
        }
        const bucket = accumulator[dependency.tarea_id] ?? [];
        bucket.push(dependency);
        accumulator[dependency.tarea_id] = bucket;
        return accumulator;
      }, {}),
    [projectDependencies],
  );

  const upcomingTasks = useMemo(
    () =>
      [...tasks]
        .filter((task) => task.activo && !["completada", "cancelada"].includes(task.estatus) && task.fecha_vencimiento)
        .sort((left, right) => new Date(left.fecha_vencimiento) - new Date(right.fecha_vencimiento))
        .slice(0, 5),
    [tasks],
  );

  const recentTasks = useMemo(() => sortByDateDesc(tasks, "updated_at").slice(0, 5), [tasks]);
  const recentTimeEntries = useMemo(() => sortByDateDesc(projectTimeEntries, "created_at").slice(0, 5), [projectTimeEntries]);
  const recentMaterialConsumptions = useMemo(
    () => sortByDateDesc(projectMaterials?.consumptions ?? [], "created_at").slice(0, 5),
    [projectMaterials],
  );

  const alertItems = useMemo(() => {
    const items = [];
    const detailedBudget = Number(projectCosts?.presupuesto_detallado_costo ?? 0);
    const effectiveBudget = detailedBudget > 0 ? detailedBudget : Number(projectCosts?.presupuesto_estimado ?? 0);
    if (overdueTasks.length > 0) {
      items.push({
        key: "overdue",
        tone: "danger",
        title: "Tareas vencidas",
        note: `${formatNumber(overdueTasks.length)} tareas requieren atención inmediata.`,
      });
    }
    if (Number(projectCosts?.horas_sin_tarifa ?? 0) > 0) {
      items.push({
        key: "no-rate",
        tone: "warning",
        title: "Horas sin tarifa",
        note: `Hay ${formatNumber(projectCosts?.horas_sin_tarifa ?? 0)} horas sin costo resuelto.`,
      });
    }
    if (effectiveBudget > 0 && Number(projectCosts?.costo_total_real ?? 0) > effectiveBudget) {
      items.push({
        key: "budget",
        tone: "danger",
        title: detailedBudget > 0 ? "Presupuesto detallado superado" : "Presupuesto superado",
        note: detailedBudget > 0
          ? "El costo real ya rebasa el presupuesto detallado cargado para este proyecto."
          : "El costo real ya rebasa el presupuesto estimado.",
      });
    }
    if (Number(projectMaterials?.summary?.materiales_pendientes ?? 0) > 0) {
      items.push({
        key: "materials",
        tone: "info",
        title: "Material pendiente",
        note: `${formatNumber(projectMaterials?.summary?.materiales_pendientes ?? 0)} materiales siguen pendientes de surtir o solicitar.`,
      });
    }
    return items;
  }, [overdueTasks, projectCosts, projectMaterials]);

  function openNewTaskModal() {
    setSelectedTaskModalId(null);
    setTaskModalOpen(true);
  }

  function openExistingTaskModal(taskId) {
    setSelectedTaskId(taskId);
    setSelectedTaskModalId(taskId);
    setTaskModalOpen(true);
  }

  function closeTaskModal() {
    setTaskModalOpen(false);
    setSelectedTaskModalId(null);
  }

  function closeMemberModal() {
    if (submitting) {
      return;
    }
    setMemberModalOpen(false);
    setMemberForm(defaultMemberForm);
  }

  function openTaskInPlan(taskId) {
    if (!taskId) {
      return;
    }
    setSelectedTaskId(taskId);
    setSelectedTaskModalId(null);
    setActiveView("plan");
  }

  async function handleTaskSaved(savedTask) {
    if (savedTask?.id) {
      setSelectedTaskId(savedTask.id);
      setSelectedTaskModalId(savedTask.id);
    }
    await loadProjectBundle({ background: true });
  }

  function handleBlockedTaskAttempt(task) {
    const blockerSummary = getTaskBlockerSummary(task);
    setSuccess("");
    setError(
      blockerSummary
        ? `No puedes avanzar esta tarea. Completa primero: ${blockerSummary}.`
        : "No puedes avanzar esta tarea porque tiene prerrequisitos pendientes.",
    );
  }

  async function handleTaskStatusChange(task, nextStatus) {
    if (!task?.id) {
      return;
    }

    setError("");
    setSuccess("");
    try {
      await updatePmTask({
        taskId: task.id,
        token,
        empresaId,
        payload: {
          estatus: nextStatus,
          porcentaje_avance: nextStatus === "completada"
            ? 100
            : Math.max(Number(task.porcentaje_avance || 0), 15),
        },
      });
      setSuccess(`Tarea "${safeDisplayText(task.titulo)}" actualizada.`);
      await loadProjectBundle({ background: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el estatus de la tarea.");
    }
  }

  async function handleDeactivateTask(task) {
    if (!task?.id) {
      return;
    }
    setError("");
    setSuccess("");
    try {
      await deactivatePmTask({ taskId: task.id, token, empresaId });
      setSuccess(`Tarea "${safeDisplayText(task.titulo)}" desactivada.`);
      await loadProjectBundle({ background: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar la tarea.");
    }
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
      await loadProjectBundle({ background: true });
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
      await loadProjectBundle({ background: true });
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
      await loadProjectBundle({ background: true });
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
        eyebrow="Gestión de proyectos"
        title={normalizePmCopy(safeDisplayText(project.nombre, "Proyecto PM"))}
        subtitle="Workspace operativo del proyecto con tareas, fechas, materiales, horas y costos en una sola vista."
        actions={
          <div className="inventory-actions">
            <ActionButton icon={<ArrowLeft size={16} strokeWidth={1.9} />} onClick={() => navigate("/pm/projects")} type="button">
              Volver a proyectos
            </ActionButton>
            <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openNewTaskModal} tone="primary" type="button">
              Nueva tarea
            </ActionButton>
            <ActionButton icon={<RefreshCw size={16} strokeWidth={1.9} />} onClick={() => loadProjectBundle({ background: true })} type="button">
              {refreshing ? "Actualizando..." : "Actualizar"}
            </ActionButton>
          </div>
        }
        meta={
          <>
            <StatusBadge tone={getProjectStatusTone(project.estatus)}>{getProjectStatusLabel(project.estatus)}</StatusBadge>
            <StatusBadge tone={getPriorityTone(project.prioridad)}>{getPriorityLabel(project.prioridad)}</StatusBadge>
            <span className="table-note">{safeDisplayText(project.codigo, "Sin código")}</span>
          </>
        }
      >
        <div className="pm-project-header-grid">
          <div className="pm-project-header-item">
            <span>Cliente</span>
            <strong>{safeDisplayText(project.cliente_nombre_snapshot, "Sin cliente")}</strong>
          </div>
          <div className="pm-project-header-item">
            <span>Inicio</span>
            <strong>{safeDisplayText(formatDate(project.fecha_inicio), "—")}</strong>
          </div>
          <div className="pm-project-header-item">
            <span>Fin planificada</span>
            <strong>{safeDisplayText(formatDate(project.fecha_fin_planificada), "—")}</strong>
          </div>
          <div className="pm-project-header-item">
            <span>Presupuesto</span>
            <strong>{formatMoney(projectCosts?.presupuesto_estimado ?? project.presupuesto_estimado ?? 0)}</strong>
          </div>
        </div>
      </PageHeader>

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-5">
        <MetricCard icon={<Gauge size={18} strokeWidth={1.9} />} label="Avance" meta="Calculado desde tareas activas" tone="info" value={formatPercent(project.porcentaje_avance)} />
        <MetricCard icon={<CheckSquare size={18} strokeWidth={1.9} />} label="Tareas activas" meta="Pendientes y en ejecución" tone="success" value={formatNumber(activeTasks.length)} />
        <MetricCard icon={<Users size={18} strokeWidth={1.9} />} label="Miembros" meta="Equipo asignado" tone="neutral" value={formatNumber(activeMembers.length)} />
        <MetricCard icon={<Calendar size={18} strokeWidth={1.9} />} label="Vencidas" meta="Requieren atención" tone={overdueTasks.length > 0 ? "danger" : "neutral"} value={formatNumber(overdueTasks.length)} />
        <MetricCard icon={<PackageOpen size={18} strokeWidth={1.9} />} label="Costo materiales real" meta="Consumo acumulado" tone="warning" value={formatMoney(projectCosts?.costo_materiales_real ?? 0)} />
        <MetricCard icon={<Clock3 size={18} strokeWidth={1.9} />} label="Costo horas real" meta="Labor acumulada" tone="info" value={formatMoney(projectCosts?.costo_horas_real ?? 0)} />
        <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Costo total real" meta="Materiales + horas" tone="danger" value={formatMoney(projectCosts?.costo_total_real ?? 0)} />
        <MetricCard
          icon={<BadgeDollarSign size={18} strokeWidth={1.9} />}
          label="Presupuesto"
          meta={Number(projectCosts?.presupuesto_detallado_costo ?? 0) > 0 ? "Detalle aprobado" : "Base del proyecto"}
          tone="neutral"
          value={formatMoney((Number(projectCosts?.presupuesto_detallado_costo ?? 0) > 0 ? projectCosts?.presupuesto_detallado_costo : projectCosts?.presupuesto_estimado) ?? 0)}
        />
        <MetricCard
          icon={<Gauge size={18} strokeWidth={1.9} />}
          label="Variación"
          meta={Number(projectCosts?.presupuesto_detallado_costo ?? 0) > 0 ? "Presupuesto detallado - costo real" : "Presupuesto - costo real"}
          tone={Number((Number(projectCosts?.presupuesto_detallado_costo ?? 0) > 0 ? projectCosts?.variacion_vs_presupuesto_detallado : projectCosts?.variacion_presupuesto) ?? 0) < 0 ? "danger" : "success"}
          value={formatMoney((Number(projectCosts?.presupuesto_detallado_costo ?? 0) > 0 ? projectCosts?.variacion_vs_presupuesto_detallado : projectCosts?.variacion_presupuesto) ?? 0)}
        />
      </section>

      <div className="pm-view-switcher">
        {projectViews.map((view) => {
          const Icon = view.icon;
          return (
            <ActionButton
              active={activeView === view.key}
              className="pm-view-switcher-button"
              icon={<Icon size={16} strokeWidth={1.9} />}
              key={view.key}
              onClick={() => setActiveView(view.key)}
              type="button"
            >
              {view.label}
            </ActionButton>
          );
        })}
      </div>

      {activeView === "general" ? (
        <div className="inventory-content-grid inventory-content-grid-2">
          <DataCard subtitle="Contexto y objetivos del proyecto." title="Resumen del proyecto">
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
                <span>{safeDisplayText(formatDate(project.fecha_inicio), "—")}</span>
              </div>
              <div>
                <strong>Fin planificada</strong>
                <span>{safeDisplayText(formatDate(project.fecha_fin_planificada), "—")}</span>
              </div>
              <div>
                <strong>Fin real</strong>
                <span>{safeDisplayText(formatDate(project.fecha_fin_real), "—")}</span>
              </div>
              <div>
                <strong>Presupuesto</strong>
                <span>{formatMoney((Number(projectCosts?.presupuesto_detallado_costo ?? 0) > 0 ? projectCosts?.presupuesto_detallado_costo : projectCosts?.presupuesto_estimado) ?? 0)}</span>
              </div>
            </div>
            <div className="inventory-form-note">
              <strong>Descripción</strong>
              <p className="table-note">{safeDisplayText(project.descripcion, "Sin descripción operativa.")}</p>
            </div>
          </DataCard>

          <DataCard subtitle="Señales tempranas del proyecto." title="Alertas">
            {alertItems.length === 0 ? (
              <EmptyState compact note="No hay alertas críticas para este proyecto." title="Proyecto estable" />
            ) : (
              <div className="inventory-alert-stack">
                {alertItems.map((item) => (
                  <div className={`inventory-form-note inventory-form-note-${item.tone === "info" ? "success" : item.tone === "danger" ? "danger" : "warning"}`} key={item.key}>
                    <strong>{item.title}</strong>
                    <p className="table-note">{item.note}</p>
                  </div>
                ))}
              </div>
            )}
          </DataCard>

          <DataCard subtitle="Siguiente carga operativa por fecha compromiso." title="Próximos vencimientos">
            {upcomingTasks.length === 0 ? (
              <EmptyState compact note="Las tareas con fecha aparecerán aquí." title="Sin vencimientos" />
            ) : (
              <div className="pm-detail-list">
                {upcomingTasks.map((task) => (
                  <button className="pm-detail-list-item pm-detail-list-item-button" key={task.id} onClick={() => setSelectedTaskId(task.id)} type="button">
                    <div>
                      <strong>{safeDisplayText(task.titulo)}</strong>
                      <span>{safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")} · {safeDisplayText(formatDate(task.fecha_vencimiento), "—")}</span>
                    </div>
                    <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                  </button>
                ))}
              </div>
            )}
          </DataCard>

          <DataCard subtitle="Actividad reciente del plan de trabajo." title="Tareas recientes">
            {recentTasks.length === 0 ? (
              <EmptyState compact note="No hay actividad reciente todavía." title="Sin actividad" />
            ) : (
              <div className="pm-detail-list">
                {recentTasks.map((task) => (
                  <button className="pm-detail-list-item pm-detail-list-item-button" key={task.id} onClick={() => openExistingTaskModal(task.id)} type="button">
                    <div>
                      <strong>{safeDisplayText(task.titulo)}</strong>
                      <span>{safeDisplayText(formatDate(task.updated_at), "—")} · {safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")}</span>
                    </div>
                    <StatusBadge tone={getPriorityTone(task.prioridad)}>{getPriorityLabel(task.prioridad)}</StatusBadge>
                  </button>
                ))}
              </div>
            )}
          </DataCard>

          <DataCard
            actions={
              <ActionButton onClick={() => setMemberModalOpen(true)} tone="primary" type="button">
                Agregar miembro
              </ActionButton>
            }
            subtitle="Usuarios vinculados al proyecto activo."
            title="Equipo del proyecto"
          >
            <ResultMeta label="miembros" loaded={members.length} total={members.length} />
            {members.length === 0 ? (
              <EmptyState compact note="Aún no se han asignado miembros." title="Sin miembros" />
            ) : (
              <div className="pm-detail-list">
                {members.map((member) => (
                  <div className="pm-detail-list-item" key={member.id}>
                    <div>
                      <strong>{safeDisplayText(member.nombre_snapshot, "Sin nombre")}</strong>
                      <span>{safeDisplayText(member.email, "Sin correo")} · {safeDisplayText(member.rol_en_proyecto, "colaborador")}</span>
                    </div>
                    {member.activo ? (
                      <ActionButton onClick={() => handleDeactivateMember(member.id)} size="sm" tone="danger" type="button">
                        Desactivar
                      </ActionButton>
                    ) : (
                      <StatusBadge tone="neutral">Inactivo</StatusBadge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </DataCard>

          <DataCard subtitle="Lectura rápida de presupuesto y costos." title="Costos principales">
            <div className="inventory-metric-grid inventory-metric-grid-3">
              <MetricCard label="Materiales reales" meta="Consumo" tone="success" value={formatMoney(projectCosts?.costo_materiales_real ?? 0)} />
              <MetricCard label="Horas reales" meta="Labor" tone="info" value={formatMoney(projectCosts?.costo_horas_real ?? 0)} />
              <MetricCard label="Total real" meta="Proyecto" tone="warning" value={formatMoney(projectCosts?.costo_total_real ?? 0)} />
              <MetricCard label="Presupuesto detallado" meta={projectCosts?.presupuesto_origen === "detallado" ? "Activo" : "Sin detalle"} tone="neutral" value={formatMoney(projectCosts?.presupuesto_detallado_costo ?? 0)} />
              <MetricCard label="Venta esperada" meta="Presupuesto detallado" tone="success" value={formatMoney(projectCosts?.presupuesto_detallado_venta ?? 0)} />
              <MetricCard label="Margen esperado" meta="Venta - costo" tone={Number(projectCosts?.margen_estimado ?? 0) < 0 ? "danger" : "info"} value={formatMoney(projectCosts?.margen_estimado ?? 0)} />
              <MetricCard label="Variación" meta={projectCosts?.presupuesto_origen === "detallado" ? "Detalle - costo real" : "Presupuesto - costo real"} tone={Number((projectCosts?.presupuesto_origen === "detallado" ? projectCosts?.variacion_vs_presupuesto_detallado : projectCosts?.variacion_presupuesto) ?? 0) < 0 ? "danger" : "success"} value={formatMoney((projectCosts?.presupuesto_origen === "detallado" ? projectCosts?.variacion_vs_presupuesto_detallado : projectCosts?.variacion_presupuesto) ?? 0)} />
              <MetricCard label="Horas sin tarifa" meta="Pendiente por resolver" tone={Number(projectCosts?.horas_sin_tarifa ?? 0) > 0 ? "warning" : "neutral"} value={formatNumber(projectCosts?.horas_sin_tarifa ?? 0)} />
            </div>
          </DataCard>

          <DataCard subtitle="Últimos consumos ligados al proyecto." title="Materiales recientes">
            {recentMaterialConsumptions.length === 0 ? (
              <EmptyState compact note="Los consumos aparecerán cuando se surtan requisiciones o salidas vinculadas." title="Sin consumos" />
            ) : (
              <div className="pm-detail-list">
                {recentMaterialConsumptions.map((consumption) => (
                  <div className="pm-detail-list-item" key={consumption.id}>
                    <div>
                      <strong>{safeDisplayText(consumption.material_nombre_snapshot)}</strong>
                      <span>{safeDisplayText(formatDate(consumption.created_at), "—")} · {formatNumber(consumption.cantidad_consumida)} · {safeDisplayText(consumption.origen)}</span>
                    </div>
                    <strong>{formatMoney(consumption.costo_total_snapshot)}</strong>
                  </div>
                ))}
              </div>
            )}
          </DataCard>

          <DataCard subtitle="Últimos registros de tiempo del proyecto." title="Horas recientes">
            {recentTimeEntries.length === 0 ? (
              <EmptyState compact note="Los registros aparecerán cuando el equipo capture horas." title="Sin horas" />
            ) : (
              <div className="pm-detail-list">
                {recentTimeEntries.map((entry) => (
                  <div className="pm-detail-list-item" key={entry.id}>
                    <div>
                      <strong>{safeDisplayText(entry.usuario_nombre_snapshot, "Registro manual")}</strong>
                      <span>{safeDisplayText(formatDate(entry.fecha), "—")} · {safeDisplayText(entry.tarea_titulo, "Proyecto general")}</span>
                    </div>
                    <strong>{formatMoney(entry.costo_total_snapshot)}</strong>
                  </div>
                ))}
              </div>
            )}
          </DataCard>
        </div>
      ) : null}

      {activeView === "plan" ? (
        <PMProjectWorkPlanView
          empresaId={empresaId}
          materialConsumptions={projectMaterials?.consumptions ?? []}
          materialPlans={projectMaterials?.plans ?? []}
          onCreateTask={openNewTaskModal}
          onDeactivateTask={handleDeactivateTask}
          onDependenciesChanged={() => loadProjectBundle({ background: true })}
          onEditTask={openExistingTaskModal}
          onRefresh={() => loadProjectBundle({ background: true })}
          onSelectTask={setSelectedTaskId}
          onSetTaskStatus={handleTaskStatusChange}
          projectId={id}
          refreshing={refreshing}
          selectedTaskId={selectedTaskId}
          tasks={tasks}
          timeEntries={projectTimeEntries}
          token={token}
        />
      ) : null}

      {activeView === "kanban" ? (
        <DataCard
          actions={
            <ActionButton onClick={openNewTaskModal} tone="primary" type="button">
              Nueva tarea
            </ActionButton>
          }
          subtitle="Vista rápida de ejecución por estados, con bloqueo visible por prerrequisitos."
          title="Kanban"
        >
          {(tasks ?? []).length === 0 ? (
            <EmptyState compact note="Crea tareas para ver el flujo del proyecto." title="Sin tareas" />
          ) : (
            <div className="pm-kanban-grid">
              {["pendiente", "en_progreso", "en_revision", "completada"].map((statusKey) => (
                <div className="pm-kanban-column" key={statusKey}>
                  <div className="pm-kanban-column-head">
                    <StatusBadge tone={getTaskStatusTone(statusKey)}>{getTaskStatusLabel(statusKey)}</StatusBadge>
                    <strong>{tasksByStatus[statusKey]?.length ?? 0}</strong>
                  </div>
                  {(tasksByStatus[statusKey]?.length ?? 0) === 0 ? (
                    <EmptyState compact note="Sin tareas" title="Sin tareas" />
                  ) : (
                    <div className="pm-kanban-card-stack">
                      {tasksByStatus[statusKey].map((task) => {
                        const dependencyState = getTaskDependencyState(task, taskDependenciesMap[task.id] ?? []);
                        const blocked = dependencyState.blocked;
                        const blockerSummary = getTaskBlockerSummary(task);
                        const normalizedStatus = String(task.estatus ?? "").toLowerCase();
                        const isCompleted = normalizedStatus === "completada";
                        const isPending = normalizedStatus === "pendiente";
                        const isInProgress = normalizedStatus === "en_progreso";
                        const isInReview = normalizedStatus === "en_revision";
                        const hasDependencies = Boolean((taskDependenciesMap[task.id] ?? []).length);

                        return (
                          <article className={`pm-task-card ${blocked ? "is-blocked" : ""}`} key={task.id}>
                            <div className="pm-task-card-head">
                              <div className="pm-task-card-title-block">
                                <strong>{normalizePmCopy(safeDisplayText(task.titulo))}</strong>
                                <span className="inventory-cell-sub">{safeDisplayText(task.asignado_nombre_snapshot, "Sin responsable")}</span>
                              </div>
                              <div className="pm-task-card-badges">
                                <StatusBadge tone={getPriorityTone(task.prioridad)}>{getPriorityLabel(task.prioridad)}</StatusBadge>
                                <StatusBadge tone={getTaskStatusTone(task.estatus)}>{getTaskStatusLabel(task.estatus)}</StatusBadge>
                              </div>
                            </div>

                            <div className="pm-task-card-meta-grid">
                              <div>
                                <span>Vence</span>
                                <strong>{safeDisplayText(formatDate(task.fecha_vencimiento), "Sin fecha")}</strong>
                              </div>
                              <div>
                                <span>Avance</span>
                                <strong>{formatPercent(task.porcentaje_avance)}</strong>
                              </div>
                            </div>

                            <div className="pm-task-card-status-row">
                              {blocked && dependencyState.badgeLabel ? (
                                <StatusBadge tone={dependencyState.badgeTone}>
                                  <Lock size={12} strokeWidth={1.9} />
                                  {dependencyState.badgeLabel}
                                </StatusBadge>
                              ) : null}
                              {!blocked && dependencyState.title ? (
                                <StatusBadge tone="success">
                                  <CheckCheck size={12} strokeWidth={1.9} />
                                  {dependencyState.title}
                                </StatusBadge>
                              ) : null}
                              {isTaskOverdue(task) ? <StatusBadge tone="danger">Vencida</StatusBadge> : null}
                            </div>

                            {dependencyState.detail ? (
                              <div className={`pm-task-card-alert ${blocked ? "is-blocked" : ""}`}>
                                <strong>{dependencyState.title}</strong>
                                <span>{dependencyState.detail}</span>
                              </div>
                            ) : null}

                            <div className="pm-task-card-actions">
                              <ActionButton
                                icon={<Eye size={14} strokeWidth={1.9} />}
                                onClick={() => openTaskInPlan(task.id)}
                                size="sm"
                                type="button"
                              >
                                Ver detalle
                              </ActionButton>
                              <ActionButton
                                icon={<Pencil size={14} strokeWidth={1.9} />}
                                onClick={() => openExistingTaskModal(task.id)}
                                size="sm"
                                type="button"
                              >
                                Editar
                              </ActionButton>
                              {isPending ? (
                                <ActionButton
                                  icon={<CheckSquare size={14} strokeWidth={1.9} />}
                                  className={blocked ? "is-soft-disabled" : ""}
                                  onClick={() => {
                                    if (blocked) {
                                      handleBlockedTaskAttempt(task);
                                      return;
                                    }
                                    handleTaskStatusChange(task, "en_progreso");
                                  }}
                                  size="sm"
                                  title={blocked ? "Completa primero los prerrequisitos" : undefined}
                                  type="button"
                                >
                                  Marcar en progreso
                                </ActionButton>
                              ) : null}
                              {isPending || isInProgress || isInReview ? (
                                <ActionButton
                                  icon={<CheckCheck size={14} strokeWidth={1.9} />}
                                  className={blocked ? "is-soft-disabled" : ""}
                                  onClick={() => {
                                    if (blocked) {
                                      handleBlockedTaskAttempt(task);
                                      return;
                                    }
                                    handleTaskStatusChange(task, "completada");
                                  }}
                                  size="sm"
                                  title={blocked ? "Completa primero los prerrequisitos" : undefined}
                                  tone={blocked ? "warning" : "primary"}
                                  type="button"
                                >
                                  Completar
                                </ActionButton>
                              ) : null}
                              {hasDependencies && !isCompleted ? (
                                <ActionButton
                                  icon={<Link2 size={14} strokeWidth={1.9} />}
                                  onClick={() => openTaskInPlan(task.id)}
                                  size="sm"
                                  type="button"
                                >
                                  Ver prerrequisitos
                                </ActionButton>
                              ) : null}
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </DataCard>
      ) : null}

      {activeView === "materiales" ? (
        <PMProjectMaterialsTab empresaId={empresaId} project={project} projectId={id} token={token} />
      ) : null}

      {activeView === "presupuesto" ? (
        <PMProjectBudgetTab
          empresaId={empresaId}
          onChanged={() => loadProjectBundle({ background: true })}
          project={project}
          projectId={id}
          token={token}
        />
      ) : null}

      {activeView === "costos" ? (
        <PMProjectTimeCostsTab
          empresaId={empresaId}
          members={members}
          onChanged={() => loadProjectBundle({ background: true })}
          project={project}
          projectId={id}
          tasks={tasks}
          token={token}
        />
      ) : null}

      {activeView === "comentarios" ? (
        <DataCard subtitle="Conversación general del proyecto." title="Comentarios">
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
            <EmptyState compact note="Aún no hay comentarios de proyecto." title="Sin comentarios" />
          ) : (
            <div className="pm-comment-list">
              {project.comments.map((comment) => (
                <article className="pm-comment-card" key={comment.id}>
                  <div className="pm-comment-head">
                    <strong>{safeDisplayText(comment.created_by_nombre_snapshot, "Usuario")}</strong>
                    <span className="inventory-cell-sub">{safeDisplayText(formatDate(comment.created_at), "—")}</span>
                  </div>
                  <p>{safeDisplayText(comment.body, "")}</p>
                </article>
              ))}
            </div>
          )}
        </DataCard>
      ) : null}

      {activeView === "documentos" ? (
        <PlaceholderView
          note="La vista de documentos se conectará en una fase posterior. Todavía no hay drag & drop, dependencias ni ruta crítica."
          title="Documentos del proyecto"
        />
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
            <strong>Vinculación controlada</strong>
            <p className="table-note">Si el correo ya pertenece a un usuario activo de la empresa, el backend lo vincula automáticamente.</p>
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
        taskId={selectedTaskModalId}
        tasks={tasks}
        token={token}
      />
    </div>
  );
}
