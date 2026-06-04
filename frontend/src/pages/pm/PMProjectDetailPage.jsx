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
  Flag,
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
  applyPmTaskSuggestedDates,
  applyPmProjectChange,
  createPmProjectChange,
  createPmProjectComment,
  deactivatePmProjectMember,
  deactivatePmTask,
  dismissPmAlert,
  getPmProject,
  getPmProjectCosts,
  getPmProjectMaterials,
  getPmProjectPlanning,
  getPmProjectWorkCalendar,
  listPmProjectBaselines,
  listPmProjectMembers,
  listPmProjectAlerts,
  listPmProjectTimeEntries,
  refreshPmProjectPlanning,
  resolvePmAlert,
  submitPmProjectChange,
  updatePmProjectWorkCalendar,
  updatePmTaskDates,
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
import PMProjectDocumentsTab from "./PMProjectDocumentsTab";
import PMProjectApprovalsTab from "./PMProjectApprovalsTab";
import PMProjectBaselineTab from "./PMProjectBaselineTab";
import PMProjectPortalTab from "./PMProjectPortalTab";
import PMRescheduleImpactModal from "./PMRescheduleImpactModal";
import PMTaskDetailModal from "./PMTaskDetailModal";
import PMWorkCalendarModal from "./PMWorkCalendarModal";
import {
  formatPercent,
  formatWorkCalendarSummary,
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
  { key: "baseline", label: "Línea base", icon: Flag },
  { key: "presupuesto", label: "Presupuesto", icon: BadgeDollarSign },
  { key: "materiales", label: "Materiales", icon: PackageOpen },
  { key: "costos", label: "Tiempo y costos", icon: Clock3 },
  { key: "comentarios", label: "Comentarios", icon: MessageSquare },
  { key: "aprobaciones", label: "Aprobaciones", icon: CheckCheck },
  { key: "documentos", label: "Documentos", icon: FileText },
  { key: "portal", label: "Portal externo", icon: Lock },
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


function getResolvedDependencyItems(dependencies = [], taskMap = {}) {
  return (dependencies ?? [])
    .filter((dependency) => dependency?.activo !== false)
    .map((dependency) => {
      const prerequisiteTask = taskMap[dependency.depende_de_tarea_id];
      const title = normalizePmCopy(
        safeDisplayText(prerequisiteTask?.titulo ?? dependency?.depende_de_tarea_titulo, "").trim(),
      );
      const status = String(prerequisiteTask?.estatus ?? dependency?.depende_de_tarea_estatus ?? "").toLowerCase();
      return {
        ...dependency,
        resolved_title: title,
        resolved_status: status,
      };
    })
    .filter((dependency) => dependency.resolved_title);
}


function getTaskDependencyState(task, dependencies = [], taskMap = {}) {
  const resolvedDependencies = getResolvedDependencyItems(dependencies, taskMap);
  const pendingDependencies = resolvedDependencies.filter(
    (dependency) => dependency.bloqueante !== false && dependency.resolved_status !== "completada",
  );
  const blocked = pendingDependencies.length > 0;
  const blockerSummary = formatTaskTitleList(pendingDependencies.map((dependency) => dependency.resolved_title));
  const dependencyTitles = formatTaskTitleList(resolvedDependencies.map((dependency) => dependency.resolved_title));

  if (blocked) {
    return {
      blocked: true,
      badgeLabel: "Bloqueada",
      badgeTone: "warning",
      title: "Bloqueada",
      detail: blockerSummary ? `Depende de: ${blockerSummary}` : "Tiene prerrequisitos pendientes.",
      dependencies: resolvedDependencies,
      blockers: pendingDependencies.map((dependency) => ({
        tarea_id: dependency.depende_de_tarea_id,
        titulo: dependency.resolved_title,
        estatus: dependency.resolved_status,
      })),
    };
  }

  if (dependencyTitles) {
    return {
      blocked: false,
      badgeLabel: null,
      badgeTone: "success",
      title: "Prerrequisitos completados",
      detail: dependencyTitles,
      dependencies: resolvedDependencies,
      blockers: [],
    };
  }

  return {
    blocked: false,
    badgeLabel: null,
    badgeTone: "success",
    title: "",
    detail: "",
    dependencies: [],
    blockers: [],
  };
}


function getTaskActionKey(taskId, action) {
  return `${taskId}:${action}`;
}

function buildDateChangePayload(task, nextStart, nextEnd, requiresApproval) {
  const taskTitle = normalizePmCopy(safeDisplayText(task?.titulo, "Tarea"));
  const currentStart = task?.fecha_inicio ?? null;
  const currentEnd = task?.fecha_vencimiento ?? null;
  const currentEndDate = currentEnd ? new Date(currentEnd) : currentStart ? new Date(currentStart) : null;
  const nextEndDate = nextEnd ? new Date(nextEnd) : nextStart ? new Date(nextStart) : null;
  let impactDays = 0;

  if (currentEndDate && nextEndDate) {
    currentEndDate.setHours(0, 0, 0, 0);
    nextEndDate.setHours(0, 0, 0, 0);
    impactDays = Math.round((nextEndDate - currentEndDate) / (1000 * 60 * 60 * 24));
  }

  return {
    tipo_cambio: "fecha",
    titulo: `Cambio de fechas — ${taskTitle}`,
    descripcion: `La tarea ${taskTitle} cambió sus fechas dentro del Gantt del proyecto.`,
    motivo: null,
    requiere_aprobacion: requiresApproval,
    entidad_tipo: "tarea",
    entidad_id: task?.id ?? null,
    impacto_dias: impactDays,
    impacto_costo: 0,
    impacto_venta: 0,
    antes_json: {
      origen: "gantt_drag_drop",
      tarea_id: task?.id ?? null,
      tarea_titulo: taskTitle,
      fecha_inicio_actual: currentStart,
      fecha_fin_actual: currentEnd,
      fecha_inicio: currentStart,
      fecha_fin: currentEnd,
    },
    despues_json: {
      tarea_id: task?.id ?? null,
      tarea_titulo: taskTitle,
      fecha_inicio_actual: nextStart ?? null,
      fecha_fin_actual: nextEnd ?? null,
      fecha_inicio: nextStart ?? null,
      fecha_fin: nextEnd ?? null,
    },
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
  const [projectPlanning, setProjectPlanning] = useState(null);
  const [projectAlerts, setProjectAlerts] = useState([]);
  const [baselineComparison, setBaselineComparison] = useState(null);
  const [baselineInfo, setBaselineInfo] = useState(null);
  const [baselineInfoLoading, setBaselineInfoLoading] = useState(false);
  const [projectDependencies, setProjectDependencies] = useState([]);
  const [members, setMembers] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [projectTimeEntries, setProjectTimeEntries] = useState([]);
  const [taskActionLoading, setTaskActionLoading] = useState({});
  const [alertActionLoading, setAlertActionLoading] = useState({});
  const [planningRefreshing, setPlanningRefreshing] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [selectedTaskModalId, setSelectedTaskModalId] = useState(null);
  const [workCalendarModalOpen, setWorkCalendarModalOpen] = useState(false);
  const [calendarSaving, setCalendarSaving] = useState(false);
  const [rescheduleModalState, setRescheduleModalState] = useState({
    open: false,
    taskId: null,
    mode: "edit",
    proposedStart: null,
    proposedEnd: null,
    source: "edit",
  });
  const [memberForm, setMemberForm] = useState(defaultMemberForm);
  const [commentBody, setCommentBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [baselineReloadToken, setBaselineReloadToken] = useState(0);

  function setTaskLoading(taskId, action, isLoading) {
    const key = getTaskActionKey(taskId, action);
    setTaskActionLoading((current) => {
      if (isLoading) {
        return { ...current, [key]: true };
      }
      if (!current[key]) {
        return current;
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function isTaskActionPending(taskId, action) {
    return Boolean(taskActionLoading[getTaskActionKey(taskId, action)]);
  }

  function syncSelectedTask(nextTasks) {
    setSelectedTaskId((current) => {
      if (current && nextTasks.some((task) => task.id === current)) {
        return current;
      }
      return nextTasks[0]?.id ?? null;
    });
  }

  function setAlertLoading(alertId, action, isLoading) {
    const key = `${alertId}:${action}`;
    setAlertActionLoading((current) => {
      if (isLoading) {
        return { ...current, [key]: true };
      }
      if (!current[key]) {
        return current;
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function isAlertActionPending(alertId, action) {
    return Boolean(alertActionLoading[`${alertId}:${action}`]);
  }

  function applyWorkPlanSnapshot(projectResponse, planningResponse, alertsResponse = []) {
    const nextTasks = planningResponse?.tasks ?? [];
    setProject(projectResponse);
    setProjectPlanning(planningResponse ?? null);
    setProjectDependencies(planningResponse?.dependencies ?? []);
    setProjectAlerts(alertsResponse ?? []);
    setTasks(nextTasks);
    syncSelectedTask(nextTasks);
    return nextTasks;
  }

  function applyPlanningOnlySnapshot(planningResponse, alertsResponse = []) {
    const nextTasks = planningResponse?.tasks ?? [];
    setProjectPlanning(planningResponse ?? null);
    setProjectDependencies(planningResponse?.dependencies ?? []);
    setProjectAlerts(alertsResponse ?? []);
    setTasks(nextTasks);
    syncSelectedTask(nextTasks);
    return nextTasks;
  }

  function upsertLocalTask(nextTask) {
    if (!nextTask?.id) {
      return;
    }
    setTasks((current) => {
      const existingIndex = current.findIndex((task) => task.id === nextTask.id);
      if (existingIndex === -1) {
        return [...current, nextTask];
      }
      return current.map((task) => (task.id === nextTask.id ? { ...task, ...nextTask } : task));
    });
  }

  function patchLocalTask(taskId, updater) {
    if (!taskId || typeof updater !== "function") {
      return;
    }
    setTasks((current) => current.map((task) => (task.id === taskId ? updater(task) : task)));
  }

  async function refreshPmWorkPlanLight({ background = false } = {}) {
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
      const [projectResponse, planningResponse, alertsResponse] = await Promise.all([
        getPmProject({ projectId: id, token, empresaId }),
        getPmProjectPlanning({ projectId: id, token, empresaId }),
        listPmProjectAlerts({ projectId: id, token, empresaId }),
      ]);
      applyWorkPlanSnapshot(projectResponse, planningResponse, alertsResponse);
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el plan de trabajo.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  function getOptimisticTaskPatch(task, nextStatus) {
    return {
      ...task,
      estatus: nextStatus,
      porcentaje_avance: nextStatus === "completada"
        ? 100
        : Math.max(Number(task?.porcentaje_avance || 0), 15),
    };
  }

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
      const [projectResponse, costsResponse, materialsResponse, planningResponse, alertsResponse, membersResponse, timeEntriesResponse] = await Promise.all([
        getPmProject({ projectId: id, token, empresaId }),
        getPmProjectCosts({ projectId: id, token, empresaId }),
        getPmProjectMaterials({ projectId: id, token, empresaId }),
        getPmProjectPlanning({ projectId: id, token, empresaId }),
        listPmProjectAlerts({ projectId: id, token, empresaId }),
        listPmProjectMembers({ projectId: id, token, empresaId }),
        listPmProjectTimeEntries({ projectId: id, token, empresaId, filters: { limit: 200, offset: 0, activo: true } }),
      ]);

      setProjectCosts(costsResponse);
      setProjectMaterials(materialsResponse);
      setMembers(membersResponse.items ?? []);
      setProjectTimeEntries(timeEntriesResponse.items ?? []);
      applyWorkPlanSnapshot(projectResponse, planningResponse, alertsResponse);
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

  useEffect(() => {
    if (baselineComparison?.baseline?.id) {
      setBaselineInfo({
        id: baselineComparison.baseline.id,
        nombre: baselineComparison.baseline.nombre ?? "Línea base principal",
      });
      return;
    }
    if (baselineComparison === null) {
      setBaselineInfo(null);
    }
  }, [baselineComparison]);

  async function ensureBaselineInfo({ force = false, silent = true } = {}) {
    if (!token || !empresaId || !id) {
      return null;
    }
    if (!force && baselineComparison?.baseline?.id) {
      return {
        id: baselineComparison.baseline.id,
        nombre: baselineComparison.baseline.nombre ?? "Línea base principal",
      };
    }
    if (!force && baselineInfo) {
      return baselineInfo;
    }

    setBaselineInfoLoading(true);
    try {
      const baselineList = await listPmProjectBaselines({ projectId: id, token, empresaId });
      const mainBaseline =
        (baselineList ?? []).find((item) => item.es_principal && item.estatus === "activa")
        ?? (baselineList ?? []).find((item) => item.estatus === "activa")
        ?? null;
      const nextInfo = mainBaseline
        ? {
          id: mainBaseline.id,
          nombre: mainBaseline.nombre ?? "Línea base principal",
        }
        : null;
      setBaselineInfo(nextInfo);
      return nextInfo;
    } catch (requestError) {
      if (!silent) {
        setError(requestError.message || "No se pudo verificar la línea base activa.");
      }
      return baselineInfo ?? null;
    } finally {
      setBaselineInfoLoading(false);
    }
  }

  const taskMap = useMemo(
    () =>
      tasks.reduce((accumulator, task) => {
        accumulator[task.id] = task;
        return accumulator;
      }, {}),
    [tasks],
  );
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
  const taskSuccessorsMap = useMemo(
    () =>
      (projectDependencies ?? []).reduce((accumulator, dependency) => {
        if (!dependency?.depende_de_tarea_id || dependency.activo === false) {
          return accumulator;
        }
        const bucket = accumulator[dependency.depende_de_tarea_id] ?? [];
        bucket.push(dependency);
        accumulator[dependency.depende_de_tarea_id] = bucket;
        return accumulator;
      }, {}),
    [projectDependencies],
  );
  const planningDependencyStateMap = projectPlanning?.dependency_state_by_task_id ?? {};
  const planningScheduleMap = projectPlanning?.schedule_suggestions_by_task_id ?? {};
  const planningSummary = projectPlanning?.alerts_summary ?? null;
  const planningCriticalPath = projectPlanning?.critical_path ?? null;
  const workCalendar = projectPlanning?.work_calendar ?? null;
  const taskDependencyContextMap = useMemo(
    () =>
      tasks.reduce((accumulator, task) => {
        const liveDependencyState = getTaskDependencyState(task, taskDependenciesMap[task.id] ?? [], taskMap);
        const planningDependencyState = planningDependencyStateMap[task.id];
        const successors = (planningDependencyState?.successors?.length ? planningDependencyState.successors : taskSuccessorsMap[task.id] ?? [])
          .map((dependency) => {
            const successorTask = taskMap[dependency.tarea_id];
            const title = normalizePmCopy(
              safeDisplayText(successorTask?.titulo ?? dependency?.tarea_titulo, "").trim(),
            );
            if (!title) {
              return null;
            }
            return {
              tarea_id: dependency.tarea_id,
              titulo: title,
              estatus: String(successorTask?.estatus ?? dependency?.tarea_estatus ?? "").toLowerCase(),
            };
          })
          .filter(Boolean);
        const mergedDependencyState = {
          ...planningDependencyState,
          ...liveDependencyState,
          blocked: liveDependencyState.blocked,
          is_blocked: liveDependencyState.blocked,
          title: liveDependencyState.title || planningDependencyState?.title || "",
          detail: liveDependencyState.detail || planningDependencyState?.detail || "",
          dependencies: liveDependencyState.dependencies,
          blockers: liveDependencyState.blockers,
          successors,
        };
        accumulator[task.id] = {
          ...mergedDependencyState,
          dependencies_count: mergedDependencyState.dependencies.length,
          blockers_count: mergedDependencyState.blockers.length,
          successors,
          successors_count: successors.length,
        };
        return accumulator;
      }, {}),
    [tasks, taskDependenciesMap, taskSuccessorsMap, taskMap, planningDependencyStateMap],
  );
  const resolvedTasks = useMemo(
    () =>
      tasks.map((task) => {
        const dependencyContext = taskDependencyContextMap[task.id] ?? getTaskDependencyState(task, [], taskMap);
        return {
          ...task,
          schedule_suggestion: task.schedule_suggestion ?? planningScheduleMap[task.id] ?? null,
          is_blocked: dependencyContext.blocked,
          blockers_count: dependencyContext.blockers.length,
          dependencies_count: dependencyContext.dependencies.length,
          successors_count: dependencyContext.successors_count ?? 0,
          blockers: dependencyContext.blockers,
          dependencies: dependencyContext.dependencies,
          successors: dependencyContext.successors ?? [],
          dependency_state: dependencyContext,
        };
      }),
    [tasks, taskDependencyContextMap, taskMap, planningScheduleMap],
  );
  const outOfSequenceTasks = useMemo(
    () => resolvedTasks.filter((task) => task?.schedule_suggestion?.fuera_de_secuencia),
    [resolvedTasks],
  );
  const selectedRescheduleTask = useMemo(
    () => resolvedTasks.find((task) => task.id === rescheduleModalState.taskId) ?? null,
    [resolvedTasks, rescheduleModalState.taskId],
  );
  const activeBaselineInfo = useMemo(
    () =>
      baselineComparison?.baseline?.id
        ? {
          id: baselineComparison.baseline.id,
          nombre: baselineComparison.baseline.nombre ?? "Línea base principal",
        }
        : baselineInfo,
    [baselineComparison, baselineInfo],
  );
  const hasActiveBaseline = Boolean(activeBaselineInfo?.id);
  const activeMembers = useMemo(() => members.filter((item) => item.activo), [members]);
  const activeTasks = useMemo(
    () => resolvedTasks.filter((task) => task.activo && !["completada", "cancelada"].includes(String(task.estatus || "").toLowerCase())),
    [resolvedTasks],
  );
  const overdueTasks = useMemo(() => resolvedTasks.filter((task) => isTaskOverdue(task)), [resolvedTasks]);
  const tasksByStatus = useMemo(() => {
    const groups = {
      pendiente: [],
      en_progreso: [],
      en_revision: [],
      completada: [],
    };
    resolvedTasks.forEach((task) => {
      const key = groups[task.estatus] ? task.estatus : "pendiente";
      groups[key].push(task);
    });
    return groups;
  }, [resolvedTasks]);

  const upcomingTasks = useMemo(
    () =>
      [...resolvedTasks]
        .filter((task) => task.activo && !["completada", "cancelada"].includes(task.estatus) && task.fecha_vencimiento)
        .sort((left, right) => new Date(left.fecha_vencimiento) - new Date(right.fecha_vencimiento))
        .slice(0, 5),
    [resolvedTasks],
  );

  const recentTasks = useMemo(() => sortByDateDesc(resolvedTasks, "updated_at").slice(0, 5), [resolvedTasks]);
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

  function openWorkCalendarModal() {
    setWorkCalendarModalOpen(true);
  }

  function closeWorkCalendarModal() {
    if (calendarSaving) {
      return;
    }
    setWorkCalendarModalOpen(false);
  }

  function openTaskDatesModal(taskId, mode = "edit", options = {}) {
    if (!taskId) {
      return;
    }
    setSelectedTaskId(taskId);
    setRescheduleModalState({
      open: true,
      taskId,
      mode,
      proposedStart: options.proposedStart ?? null,
      proposedEnd: options.proposedEnd ?? null,
      source: options.source ?? mode,
    });
    ensureBaselineInfo().catch(() => {});
  }

  function closeRescheduleModal() {
    setRescheduleModalState({
      open: false,
      taskId: null,
      mode: "edit",
      proposedStart: null,
      proposedEnd: null,
      source: "edit",
    });
  }

  function handleGanttInteractionNotice(message) {
    if (!message) {
      return;
    }
    setSuccess("");
    setError(message);
  }

  async function handleTaskSaved(savedTask, successMessage = "") {
    if (savedTask?.id) {
      setSelectedTaskId(savedTask.id);
      setSelectedTaskModalId(savedTask.id);
      upsertLocalTask(savedTask);
    }
    if (successMessage) {
      setSuccess(successMessage);
    }
    await refreshPmWorkPlanLight({ background: true });
  }

  async function syncPlanningStateFromResponse(planningResponse, successMessage = "") {
    const alertsResponse = await listPmProjectAlerts({ projectId: id, token, empresaId });
    applyPlanningOnlySnapshot(planningResponse, alertsResponse);
    if (successMessage) {
      setSuccess(successMessage);
    }
  }

  async function handleSaveWorkCalendar(payload) {
    setCalendarSaving(true);
    setError("");
    setSuccess("");
    try {
      await updatePmProjectWorkCalendar({
        projectId: id,
        token,
        empresaId,
        payload,
      });
      const planningResponse = await refreshPmProjectPlanning({ projectId: id, token, empresaId });
      await syncPlanningStateFromResponse(planningResponse, "Calendario laboral actualizado.");
      closeWorkCalendarModal();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el calendario laboral.");
    } finally {
      setCalendarSaving(false);
    }
  }

  async function handleTaskSchedulingSubmit({ taskId, fecha_inicio, fecha_fin, applyDependents, mode, strategy }) {
    if (!taskId) {
      return;
    }
    const action = mode === "suggestion" ? "apply-suggestion" : "dates";
    if (isTaskActionPending(taskId, action)) {
      return;
    }
    const task = resolvedTasks.find((item) => item.id === taskId);
    if (!task) {
      return;
    }
    setTaskLoading(taskId, action, true);
    setError("");
    setSuccess("");
    try {
      const activeBaseline = await ensureBaselineInfo();
      const hasBaseline = Boolean(activeBaseline?.id);
      let successMessage = "Fechas actualizadas.";

      if (strategy === "register-and-submit") {
        const changePayload = buildDateChangePayload(task, fecha_inicio, fecha_fin, true);
        const createdChange = await createPmProjectChange({
          projectId: id,
          token,
          empresaId,
          payload: changePayload,
        });
        await submitPmProjectChange({
          changeId: createdChange.id,
          token,
          empresaId,
          payload: {},
        });
        successMessage = "Cambio enviado a aprobación. Las fechas se aplicarán cuando sea aprobado.";
        await refreshPmWorkPlanLight({ background: true });
      } else if (strategy === "apply-and-register") {
        const changePayload = buildDateChangePayload(task, fecha_inicio, fecha_fin, false);
        const createdChange = await createPmProjectChange({
          projectId: id,
          token,
          empresaId,
          payload: changePayload,
        });
        const response = await applyPmProjectChange({
          changeId: createdChange.id,
          token,
          empresaId,
          payload: {
            apply_dependents: applyDependents,
            comentario: null,
          },
        });
        await syncPlanningStateFromResponse(response.planning, response.message || "Cambio aplicado y registrado.");
        successMessage = response.message || "Cambio aplicado y registrado.";
      } else {
        if (hasBaseline && strategy !== "apply-and-register") {
          throw new Error("Este proyecto tiene línea base. Registra el cambio o envíalo a aprobación antes de aplicarlo.");
        }
        const response = await updatePmTaskDates({
          projectId: id,
          taskId,
          token,
          empresaId,
          payload: {
            fecha_inicio,
            fecha_fin,
            apply_dependents: applyDependents,
          },
        });
        await syncPlanningStateFromResponse(response.planning, response.message || "Fechas actualizadas.");
        successMessage = response.message || "Fechas actualizadas.";
      }

      if (hasBaseline || strategy === "register-and-submit" || strategy === "apply-and-register") {
        setBaselineReloadToken((current) => current + 1);
      }
      setSuccess(successMessage);
      closeRescheduleModal();
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar la planeación de la tarea.");
    } finally {
      setTaskLoading(taskId, action, false);
    }
  }

  async function handleApplyAllSuggestions() {
    if (!outOfSequenceTasks.length || planningRefreshing) {
      return;
    }
    const confirmed = window.confirm(`Se aplicarán las fechas sugeridas a ${outOfSequenceTasks.length} tareas fuera de secuencia. ¿Deseas continuar?`);
    if (!confirmed) {
      return;
    }
    setPlanningRefreshing(true);
    setError("");
    setSuccess("");
    try {
      let lastPlanning = null;
      for (const task of outOfSequenceTasks) {
        try {
          const response = await applyPmTaskSuggestedDates({
            projectId: id,
            taskId: task.id,
            token,
            empresaId,
            payload: { apply_dependents: true },
          });
          lastPlanning = response.planning ?? lastPlanning;
        } catch {
          // Si una sugerencia deja de aplicar por reprogramación previa, el refresh final corrige el estado.
        }
      }
      if (lastPlanning) {
        await syncPlanningStateFromResponse(lastPlanning, "Sugerencias aplicadas.");
      } else {
        const planningResponse = await refreshPmProjectPlanning({ projectId: id, token, empresaId });
        await syncPlanningStateFromResponse(planningResponse, "Planeación actualizada.");
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar las fechas sugeridas.");
    } finally {
      setPlanningRefreshing(false);
    }
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

    const currentTask = resolvedTasks.find((item) => item.id === task.id) ?? task;
    const action = nextStatus === "completada" ? "complete" : nextStatus === "en_progreso" ? "start" : "update";
    if (currentTask.is_blocked) {
      handleBlockedTaskAttempt(currentTask);
      return;
    }
    if (isTaskActionPending(task.id, action)) {
      return;
    }

    const rollbackTask = {
      estatus: currentTask.estatus,
      porcentaje_avance: currentTask.porcentaje_avance,
    };
    const optimisticTask = getOptimisticTaskPatch(currentTask, nextStatus);

    setError("");
    setSuccess("");
    setTaskLoading(task.id, action, true);
    patchLocalTask(task.id, () => optimisticTask);
    try {
      await updatePmTask({
        taskId: task.id,
        token,
        empresaId,
        payload: {
          estatus: nextStatus,
          porcentaje_avance: optimisticTask.porcentaje_avance,
        },
      });
      setSuccess(`Tarea "${safeDisplayText(task.titulo)}" actualizada.`);
      await refreshPmWorkPlanLight({ background: true });
    } catch (requestError) {
      patchLocalTask(task.id, (current) => ({
        ...current,
        estatus: rollbackTask.estatus,
        porcentaje_avance: rollbackTask.porcentaje_avance,
      }));
      setError(requestError.message || "No se pudo actualizar el estatus de la tarea.");
    } finally {
      setTaskLoading(task.id, action, false);
    }
  }

  async function handleDeactivateTask(task) {
    if (!task?.id) {
      return;
    }
    if (isTaskActionPending(task.id, "deactivate")) {
      return;
    }
    setError("");
    setSuccess("");
    setTaskLoading(task.id, "deactivate", true);
    try {
      await deactivatePmTask({ taskId: task.id, token, empresaId });
      setSuccess(`Tarea "${safeDisplayText(task.titulo)}" desactivada.`);
      await refreshPmWorkPlanLight({ background: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar la tarea.");
    } finally {
      setTaskLoading(task.id, "deactivate", false);
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

  function handleRefreshCurrentView() {
    if (activeView === "plan" || activeView === "kanban") {
      refreshPmWorkPlanLight({ background: true });
      return;
    }
    if (activeView === "baseline") {
      setBaselineReloadToken((current) => current + 1);
      return;
    }
    loadProjectBundle({ background: true });
  }

  async function handleRecalculatePlanning() {
    if (!id || planningRefreshing) {
      return;
    }
    setPlanningRefreshing(true);
    setError("");
    setSuccess("");
    try {
      const planningResponse = await refreshPmProjectPlanning({ projectId: id, token, empresaId });
      const alertsResponse = await listPmProjectAlerts({ projectId: id, token, empresaId });
      applyWorkPlanSnapshot(project, planningResponse, alertsResponse);
      setSuccess("Planeación recalculada.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo recalcular la planeación.");
    } finally {
      setPlanningRefreshing(false);
    }
  }

  async function handleResolveAlert(alert) {
    if (!alert?.id || isAlertActionPending(alert.id, "resolve")) {
      return;
    }
    setAlertLoading(alert.id, "resolve", true);
    setError("");
    setSuccess("");
    try {
      await resolvePmAlert({ alertId: alert.id, token, empresaId, payload: {} });
      setSuccess(`Alerta "${safeDisplayText(alert.titulo, "PM")}" resuelta.`);
      await refreshPmWorkPlanLight({ background: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo resolver la alerta.");
    } finally {
      setAlertLoading(alert.id, "resolve", false);
    }
  }

  async function handleDismissAlert(alert) {
    if (!alert?.id || isAlertActionPending(alert.id, "dismiss")) {
      return;
    }
    setAlertLoading(alert.id, "dismiss", true);
    setError("");
    setSuccess("");
    try {
      await dismissPmAlert({ alertId: alert.id, token, empresaId, payload: {} });
      setSuccess(`Alerta "${safeDisplayText(alert.titulo, "PM")}" descartada.`);
      await refreshPmWorkPlanLight({ background: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo descartar la alerta.");
    } finally {
      setAlertLoading(alert.id, "dismiss", false);
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
            <ActionButton icon={<RefreshCw size={16} strokeWidth={1.9} />} onClick={handleRefreshCurrentView} type="button">
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
          alertActionLoading={alertActionLoading}
          alerts={projectAlerts}
          baselineComparison={baselineComparison}
          empresaId={empresaId}
          materialConsumptions={projectMaterials?.consumptions ?? []}
          materialPlans={projectMaterials?.plans ?? []}
          onApplyAllSuggestions={handleApplyAllSuggestions}
          onApplySuggestedDates={(taskId) => openTaskDatesModal(taskId, "suggestion")}
          onConfigureCalendar={openWorkCalendarModal}
          onCreateTask={openNewTaskModal}
          onDeactivateTask={handleDeactivateTask}
          onDependenciesChanged={() => refreshPmWorkPlanLight({ background: true })}
          onDismissAlert={handleDismissAlert}
          onEditTaskDates={(taskId) => openTaskDatesModal(taskId, "edit")}
          onEditTask={openExistingTaskModal}
          onGanttNotice={handleGanttInteractionNotice}
          onPreviewReschedule={(taskId, draft) =>
            openTaskDatesModal(taskId, "drag", {
              proposedStart: draft?.proposedStart ?? null,
              proposedEnd: draft?.proposedEnd ?? null,
              source: draft?.source ?? "drag",
            })}
          onRefresh={handleRefreshCurrentView}
          onRecalculatePlanning={handleRecalculatePlanning}
          onResolveAlert={handleResolveAlert}
          onSelectTask={setSelectedTaskId}
          onSetTaskStatus={handleTaskStatusChange}
          planningCriticalPath={planningCriticalPath}
          planningRefreshing={planningRefreshing}
          planningSummary={planningSummary}
          projectId={id}
          refreshing={refreshing}
          selectedTaskId={selectedTaskId}
          taskActionLoading={taskActionLoading}
          taskDependencyContextMap={taskDependencyContextMap}
          tasks={resolvedTasks}
          timeEntries={projectTimeEntries}
          token={token}
          workCalendar={workCalendar}
        />
      ) : null}

      {activeView === "baseline" ? (
        <PMProjectBaselineTab
          empresaId={empresaId}
          onComparisonLoaded={setBaselineComparison}
          onOpenApprovals={() => setActiveView("aprobaciones")}
          onPlanningChanged={() => refreshPmWorkPlanLight({ background: true })}
          projectId={id}
          reloadToken={baselineReloadToken}
          tasks={resolvedTasks}
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
                        const dependencyState = task.dependency_state ?? getTaskDependencyState(task, taskDependenciesMap[task.id] ?? [], taskMap);
                        const blocked = dependencyState.blocked;
                        const blockerSummary = getTaskBlockerSummary(task);
                        const normalizedStatus = String(task.estatus ?? "").toLowerCase();
                        const isCompleted = normalizedStatus === "completada";
                        const isPending = normalizedStatus === "pendiente";
                        const isInProgress = normalizedStatus === "en_progreso";
                        const isInReview = normalizedStatus === "en_revision";
                        const hasDependencies = Boolean((taskDependenciesMap[task.id] ?? []).length);
                        const completing = isTaskActionPending(task.id, "complete");
                        const starting = isTaskActionPending(task.id, "start");
                        const deactivating = isTaskActionPending(task.id, "deactivate");

                        return (
                          <article className={`pm-task-card ${blocked ? "is-blocked" : ""} ${completing || starting || deactivating ? "pm-card-updating" : ""}`} key={task.id}>
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
                                  className={`${blocked ? "is-soft-disabled" : ""} ${starting ? "pm-button-loading" : ""}`.trim()}
                                  disabled={starting || completing || deactivating}
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
                                  {starting ? "Actualizando..." : "Marcar en progreso"}
                                </ActionButton>
                              ) : null}
                              {isPending || isInProgress || isInReview ? (
                                <ActionButton
                                  icon={<CheckCheck size={14} strokeWidth={1.9} />}
                                  className={`${blocked ? "is-soft-disabled" : ""} ${completing ? "pm-button-loading" : ""}`.trim()}
                                  disabled={starting || completing || deactivating}
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
                                  {completing ? "Completando..." : "Completar"}
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
          tasks={resolvedTasks}
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
                    <div className="inventory-actions inventory-actions-wrap">
                      <strong>
                        {safeDisplayText(
                          comment.externo ? comment.autor_nombre_snapshot : comment.created_by_nombre_snapshot,
                          comment.externo ? "Invitado externo" : "Usuario",
                        )}
                      </strong>
                      {comment.externo ? <StatusBadge tone="info">Comentario externo</StatusBadge> : null}
                    </div>
                    <span className="inventory-cell-sub">{safeDisplayText(formatDate(comment.created_at), "—")}</span>
                  </div>
                  <p>{safeDisplayText(comment.body, "")}</p>
                </article>
              ))}
            </div>
          )}
        </DataCard>
      ) : null}

      {activeView === "aprobaciones" ? (
        <PMProjectApprovalsTab empresaId={empresaId} projectId={id} token={token} />
      ) : null}

      {activeView === "documentos" ? (
        <PMProjectDocumentsTab empresaId={empresaId} projectId={id} token={token} />
      ) : null}

      {activeView === "portal" ? (
        <PMProjectPortalTab empresaId={empresaId} project={project} projectId={id} token={token} />
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
        tasks={resolvedTasks}
        token={token}
      />

      <PMWorkCalendarModal
        calendar={workCalendar}
        onClose={closeWorkCalendarModal}
        onSave={handleSaveWorkCalendar}
        open={workCalendarModalOpen}
        saving={calendarSaving}
      />

      <PMRescheduleImpactModal
        allowDirectApply={!hasActiveBaseline}
        baselineChecking={baselineInfoLoading && !hasActiveBaseline}
        baselineInfo={activeBaselineInfo}
        empresaId={empresaId}
        initialEnd={selectedRescheduleTask?.fecha_vencimiento ?? null}
        initialStart={selectedRescheduleTask?.fecha_inicio ?? null}
        mode={rescheduleModalState.mode}
        onClose={closeRescheduleModal}
        onSubmit={handleTaskSchedulingSubmit}
        open={rescheduleModalState.open}
        projectId={id}
        proposedEnd={rescheduleModalState.proposedEnd}
        proposedStart={rescheduleModalState.proposedStart}
        saving={
          selectedRescheduleTask
            ? isTaskActionPending(
              selectedRescheduleTask.id,
              rescheduleModalState.mode === "suggestion" ? "apply-suggestion" : "dates",
            )
            : false
        }
        suggestionEnd={selectedRescheduleTask?.schedule_suggestion?.fecha_fin_sugerida ?? null}
        suggestionStart={selectedRescheduleTask?.schedule_suggestion?.fecha_inicio_sugerida ?? null}
        task={selectedRescheduleTask}
        token={token}
      />
    </div>
  );
}



