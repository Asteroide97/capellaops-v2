import { formatNumber } from "../inventory/shared";


export const projectStatusOptions = [
  { value: "borrador", label: "Borrador" },
  { value: "activo", label: "Activo" },
  { value: "en_pausa", label: "En pausa" },
  { value: "completado", label: "Completado" },
  { value: "cancelado", label: "Cancelado" },
];

export const taskStatusOptions = [
  { value: "pendiente", label: "Pendiente" },
  { value: "en_progreso", label: "En progreso" },
  { value: "en_revision", label: "En revisión" },
  { value: "completada", label: "Completada" },
  { value: "cancelada", label: "Cancelada" },
];

export const priorityOptions = [
  { value: "baja", label: "Baja" },
  { value: "media", label: "Media" },
  { value: "alta", label: "Alta" },
  { value: "critica", label: "Crítica" },
];

export const projectMemberRoleOptions = [
  { value: "lider", label: "Líder" },
  { value: "colaborador", label: "Colaborador" },
  { value: "observador", label: "Observador" },
];

export const pmRateRoleOptions = [
  { value: "owner", label: "Owner" },
  { value: "admin", label: "Admin" },
  { value: "user", label: "Usuario" },
  { value: "almacenista", label: "Almacenista" },
  { value: "lider", label: "Líder" },
  { value: "colaborador", label: "Colaborador" },
  { value: "observador", label: "Observador" },
];

export const pmDocumentTypeOptions = [
  { value: "contrato", label: "Contrato" },
  { value: "alcance", label: "Alcance" },
  { value: "minuta", label: "Minuta" },
  { value: "cambio_alcance", label: "Cambio de alcance" },
  { value: "entrega", label: "Entrega" },
  { value: "evidencia", label: "Evidencia" },
  { value: "cierre", label: "Cierre" },
  { value: "otro", label: "Otro" },
];

export const pmApprovalTypeOptions = [
  { value: "aprobar_presupuesto", label: "Aprobar presupuesto" },
  { value: "aprobar_cambio_alcance", label: "Aprobar cambio de alcance" },
  { value: "aprobar_entrega", label: "Aprobar entrega" },
  { value: "aprobar_cierre_etapa", label: "Aprobar cierre de etapa" },
  { value: "aprobar_cierre_proyecto", label: "Aprobar cierre de proyecto" },
  { value: "otro", label: "Otro" },
];

export const pmExternalAccessModeOptions = [
  { value: "solo_lectura", label: "Solo lectura" },
  { value: "comentario", label: "Puede comentar" },
];

const pmVisualCopyFixups = [
  [/Construccion/g, "Construcción"],
  [/construccion/g, "construcción"],
  [/Operacion/g, "Operación"],
  [/operacion/g, "operación"],
  [/Ejecucion/g, "Ejecución"],
  [/ejecucion/g, "ejecución"],
  [/Prerequisito/g, "Prerrequisito"],
  [/Prerequisitos/g, "Prerrequisitos"],
];


export function normalizePmCopy(value) {
  const text = String(value ?? "");
  return pmVisualCopyFixups.reduce((current, [pattern, replacement]) => current.replace(pattern, replacement), text);
}


export function getProjectStatusLabel(value) {
  return projectStatusOptions.find((item) => item.value === value)?.label ?? value ?? "Borrador";
}


export function getTaskStatusLabel(value) {
  return taskStatusOptions.find((item) => item.value === value)?.label ?? value ?? "Pendiente";
}


export function getPriorityLabel(value) {
  return priorityOptions.find((item) => item.value === value)?.label ?? value ?? "Media";
}


export function getDocumentTypeLabel(value) {
  return pmDocumentTypeOptions.find((item) => item.value === value)?.label ?? value ?? "Documento";
}


export function getApprovalTypeLabel(value) {
  return pmApprovalTypeOptions.find((item) => item.value === value)?.label ?? value ?? "Otro";
}


export function getExternalAccessModeLabel(value) {
  return pmExternalAccessModeOptions.find((item) => item.value === value)?.label ?? value ?? "Solo lectura";
}


export function getProjectStatusTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "activo") {
    return "success";
  }
  if (normalized === "en_pausa") {
    return "warning";
  }
  if (normalized === "completado") {
    return "info";
  }
  if (normalized === "cancelado") {
    return "danger";
  }
  return "neutral";
}


export function getTaskStatusTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "en_progreso") {
    return "info";
  }
  if (normalized === "en_revision") {
    return "warning";
  }
  if (normalized === "completada") {
    return "success";
  }
  if (normalized === "cancelada") {
    return "danger";
  }
  return "neutral";
}


export function getApprovalStatusTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "aprobada") {
    return "success";
  }
  if (normalized === "rechazada") {
    return "danger";
  }
  if (normalized === "cancelada") {
    return "warning";
  }
  return "neutral";
}


export function getPriorityTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "alta") {
    return "warning";
  }
  if (normalized === "critica") {
    return "danger";
  }
  if (normalized === "media") {
    return "info";
  }
  return "neutral";
}


export function formatPercent(value) {
  const numericValue = Number(value ?? 0);
  return `${formatNumber(Number.isNaN(numericValue) ? 0 : numericValue)}%`;
}


export function isTaskOverdue(task) {
  if (!task?.fecha_vencimiento) {
    return false;
  }
  if (["completada", "cancelada"].includes(String(task?.estatus ?? "").toLowerCase())) {
    return false;
  }
  const due = new Date(task.fecha_vencimiento);
  const today = new Date();
  due.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  return due < today;
}


export function getRateSourceLabel(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "usuario") {
    return "Usuario";
  }
  if (normalized === "rol") {
    return "Rol";
  }
  if (normalized === "manual") {
    return "Manual";
  }
  return "Sin tarifa";
}


export function getRateSourceTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "usuario") {
    return "success";
  }
  if (normalized === "rol") {
    return "info";
  }
  if (normalized === "manual") {
    return "warning";
  }
  return "danger";
}
