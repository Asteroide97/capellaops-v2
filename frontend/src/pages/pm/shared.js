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

export const pmBaselineStatusOptions = [
  { value: "activa", label: "Activa" },
  { value: "archivada", label: "Archivada" },
  { value: "sustituida", label: "Sustituida" },
  { value: "cancelada", label: "Cancelada" },
];

export const pmChangeTypeOptions = [
  { value: "fecha", label: "Fecha" },
  { value: "alcance", label: "Alcance" },
  { value: "presupuesto", label: "Presupuesto" },
  { value: "partida", label: "Partida" },
  { value: "tarea_critica", label: "Tarea crítica" },
  { value: "documento", label: "Documento" },
  { value: "otro", label: "Otro" },
];

export const pmChangeStatusOptions = [
  { value: "borrador", label: "Borrador" },
  { value: "pendiente_aprobacion", label: "Pendiente de aprobación" },
  { value: "aprobado", label: "Aprobado" },
  { value: "rechazado", label: "Rechazado" },
  { value: "aplicado", label: "Aplicado" },
  { value: "cancelado", label: "Cancelado" },
];

export const weekdayOptions = [
  { key: "lunes", label: "Lunes" },
  { key: "martes", label: "Martes" },
  { key: "miercoles", label: "Miércoles" },
  { key: "jueves", label: "Jueves" },
  { key: "viernes", label: "Viernes" },
  { key: "sabado", label: "Sábado" },
  { key: "domingo", label: "Domingo" },
];

const mojibakeFixups = [
  ["\u00c3\u00a1", "á"],
  ["\u00c3\u00a9", "é"],
  ["\u00c3\u00ad", "í"],
  ["\u00c3\u00b3", "ó"],
  ["\u00c3\u00ba", "ú"],
  ["\u00c3\u0081", "Á"],
  ["\u00c3\u0089", "É"],
  ["\u00c3\u008d", "Í"],
  ["\u00c3\u0093", "Ó"],
  ["\u00c3\u009a", "Ú"],
  ["\u00c3\u00b1", "ñ"],
  ["\u00c3\u0091", "Ñ"],
  ["\u00c2\u00b7", "·"],
  ["\u00c2", ""],
  ["\u00e2\u20ac\u201d", "—"],
  ["\u00e2\u20ac\u201c", "–"],
  ["\u00e2\u2020\u2019", "→"],
  ["\u00e2\u20ac\u00a6", "…"],
];

const pmVisualCopyFixups = [
  [/Construccion/g, "Construcción"],
  [/construccion/g, "construcción"],
  [/Operacion/g, "Operación"],
  [/operacion/g, "operación"],
  [/Ejecucion/g, "Ejecución"],
  [/ejecucion/g, "ejecución"],
  [/Gestion/g, "Gestión"],
  [/gestion/g, "gestión"],
  [/Variacion/g, "Variación"],
  [/variacion/g, "variación"],
  [/Atencion/g, "Atención"],
  [/atencion/g, "atención"],
  [/Proximos/g, "Próximos"],
  [/proximos/g, "próximos"],
];

export function normalizePmCopy(value) {
  const source = String(value ?? "");
  const withoutMojibake = mojibakeFixups.reduce(
    (current, [pattern, replacement]) => current.split(pattern).join(replacement),
    source,
  );
  return pmVisualCopyFixups.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    withoutMojibake,
  );
}

function getOptionLabel(options, value, fallback) {
  return options.find((item) => item.value === value)?.label ?? normalizePmCopy(value ?? fallback);
}

export function getProjectStatusLabel(value) {
  return getOptionLabel(projectStatusOptions, value, "Borrador");
}

export function getTaskStatusLabel(value) {
  return getOptionLabel(taskStatusOptions, value, "Pendiente");
}

export function getPriorityLabel(value) {
  return getOptionLabel(priorityOptions, value, "Media");
}

export function getDocumentTypeLabel(value) {
  return getOptionLabel(pmDocumentTypeOptions, value, "Documento");
}

export function getApprovalTypeLabel(value) {
  return getOptionLabel(pmApprovalTypeOptions, value, "Otro");
}

export function getExternalAccessModeLabel(value) {
  return getOptionLabel(pmExternalAccessModeOptions, value, "Solo lectura");
}

export function getBaselineStatusLabel(value) {
  return getOptionLabel(pmBaselineStatusOptions, value, "Activa");
}

export function getChangeTypeLabel(value) {
  return getOptionLabel(pmChangeTypeOptions, value, "Otro");
}

export function getChangeStatusLabel(value) {
  return getOptionLabel(pmChangeStatusOptions, value, "Borrador");
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

export function getBaselineStatusTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "activa") {
    return "success";
  }
  if (normalized === "sustituida") {
    return "warning";
  }
  if (normalized === "archivada") {
    return "neutral";
  }
  if (normalized === "cancelada") {
    return "danger";
  }
  return "neutral";
}

export function getChangeStatusTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "aprobado" || normalized === "aplicado") {
    return "success";
  }
  if (normalized === "pendiente_aprobacion") {
    return "warning";
  }
  if (normalized === "rechazado" || normalized === "cancelado") {
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

export function getAlertSeverityTone(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "critical") {
    return "danger";
  }
  if (normalized === "warning") {
    return "warning";
  }
  return "info";
}

export function getAlertTypeLabel(value) {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "tarea_vencida") {
    return "Tarea vencida";
  }
  if (normalized === "proyecto_atrasado") {
    return "Proyecto atrasado";
  }
  if (normalized === "tarea_bloqueada") {
    return "Tarea bloqueada";
  }
  if (normalized === "tarea_critica_atrasada") {
    return "Tarea en ruta crítica atrasada";
  }
  if (normalized === "tarea_fuera_de_secuencia") {
    return "Fuera de secuencia";
  }
  if (normalized === "presupuesto_sobrepasado") {
    return "Presupuesto sobrepasado";
  }
  if (normalized === "proyecto_desviado_fecha") {
    return "Proyecto desviado en fecha";
  }
  if (normalized === "proyecto_desviado_costo") {
    return "Proyecto desviado en costo";
  }
  if (normalized === "cambio_pendiente_aprobacion") {
    return "Cambio pendiente de aprobación";
  }
  if (normalized === "tarea_critica_desviada") {
    return "Tarea crítica desviada";
  }
  if (normalized === "sin_tarifa") {
    return "Sin tarifa";
  }
  return normalizePmCopy(value ?? "Alerta");
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

export function formatWorkCalendarSummary(calendar) {
  if (!calendar) {
    return "Este proyecto usa calendario lunes a viernes.";
  }
  const activeDays = weekdayOptions
    .filter((item) => Boolean(calendar?.[item.key]))
    .map((item) => item.label.toLowerCase());

  if (activeDays.length === 0) {
    return "Este proyecto no tiene días laborales configurados.";
  }
  if (activeDays.length === 7) {
    return "Este proyecto usa calendario de lunes a domingo.";
  }
  if (
    activeDays.length === 5 &&
    activeDays[0] === "lunes" &&
    activeDays[1] === "martes" &&
    activeDays[2] === "miércoles" &&
    activeDays[3] === "jueves" &&
    activeDays[4] === "viernes"
  ) {
    return "Este proyecto usa calendario lunes a viernes.";
  }
  return `Días laborales: ${activeDays.join(", ")}.`;
}
