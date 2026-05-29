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
  { value: "en_revision", label: "En revision" },
  { value: "completada", label: "Completada" },
  { value: "cancelada", label: "Cancelada" },
];

export const priorityOptions = [
  { value: "baja", label: "Baja" },
  { value: "media", label: "Media" },
  { value: "alta", label: "Alta" },
  { value: "critica", label: "Critica" },
];

export const projectMemberRoleOptions = [
  { value: "lider", label: "Lider" },
  { value: "colaborador", label: "Colaborador" },
  { value: "observador", label: "Observador" },
];

export function getProjectStatusLabel(value) {
  return projectStatusOptions.find((item) => item.value === value)?.label ?? value ?? "Borrador";
}

export function getTaskStatusLabel(value) {
  return taskStatusOptions.find((item) => item.value === value)?.label ?? value ?? "Pendiente";
}

export function getPriorityLabel(value) {
  return priorityOptions.find((item) => item.value === value)?.label ?? value ?? "Media";
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
