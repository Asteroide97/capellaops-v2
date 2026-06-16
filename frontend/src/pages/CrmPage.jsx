import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  BriefcaseBusiness,
  Building2,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Eye,
  Filter,
  HandCoins,
  KanbanSquare,
  Plus,
  RefreshCw,
  Target,
  TrendingUp,
  UserCircle2,
  Users,
  XCircle,
} from "lucide-react";

import { useAuth } from "../auth/AuthContext";
import {
  closeCrmOpportunityLost,
  closeCrmOpportunityWon,
  completeCrmActivity,
  createCrmActivity,
  createCrmClient,
  createCrmContact,
  createCrmOpportunity,
  deactivateCrmActivity,
  deactivateCrmClient,
  deactivateCrmContact,
  getCrmClient,
  getCrmClientCommercialSummary,
  getCrmClientTimeline,
  getCrmOpportunity,
  getCrmSummary,
  listCrmActivities,
  listCrmClientContacts,
  listCrmClients,
  listCrmOpportunities,
  reactivateCrmClient,
  updateCrmActivity,
  updateCrmClient,
  updateCrmContact,
  updateCrmOpportunity,
} from "../api/client";
import {
  ActionButton,
  DEFAULT_PAGE_SIZE,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  MetricCard,
  ModalShell,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  formatDate,
  formatDateTime,
  formatMoney,
  formatNumber,
  normalizeDecimalInput,
  parseBooleanFilter,
  safeDisplayText,
} from "./inventory/shared";


const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const RFC_REGEX = /^([A-Z&N]{3,4}\d{6}[A-Z0-9]{3}|XAXX010101000)$/i;
const POSTAL_CODE_REGEX = /^\d{5}$/;
const EMPTY_META = { total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 };
const CRM_VIEWS = ["summary", "clients", "contacts", "opportunities", "activities", "pipeline"];
const CLIENT_TYPE_OPTIONS = [
  { value: "prospecto", label: "Prospecto" },
  { value: "cliente", label: "Cliente" },
  { value: "otro", label: "Otro" },
];
const CLIENT_STATUS_OPTIONS = [
  { value: "activo", label: "Activo" },
  { value: "inactivo", label: "Inactivo" },
];
const OPPORTUNITY_STAGE_OPTIONS = [
  { value: "nueva", label: "Nueva" },
  { value: "contactado", label: "Contactado" },
  { value: "propuesta", label: "Propuesta" },
  { value: "negociacion", label: "Negociacion" },
  { value: "ganada", label: "Ganada" },
  { value: "perdida", label: "Perdida" },
];
const ACTIVITY_TYPE_OPTIONS = [
  { value: "llamada", label: "Llamada" },
  { value: "email", label: "Email" },
  { value: "reunion", label: "Reunion" },
  { value: "tarea", label: "Tarea" },
  { value: "nota", label: "Nota" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "otro", label: "Otro" },
];
const PIPELINE_STAGE_ORDER = ["nueva", "contactado", "propuesta", "negociacion", "ganada", "perdida"];

const defaultSummary = {
  kpis: {
    clientes_activos: 0,
    prospectos: 0,
    oportunidades_abiertas: 0,
    oportunidades_ganadas: 0,
    oportunidades_perdidas: 0,
    monto_pipeline: 0,
    monto_ganado: 0,
    actividades_pendientes: 0,
    actividades_vencidas: 0,
  },
  pipeline_por_etapa: [],
  oportunidades_recientes: [],
  actividades_pendientes: [],
  clientes_recientes: [],
};

const defaultClientFilters = {
  q: "",
  tipo: "",
  estatus: "activo",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultClientCommercialSummary = {
  client_id: "",
  total_ventas_pos: 0,
  ventas_count: 0,
  proyectos_count: 0,
  proyectos_activos: 0,
  oportunidades_abiertas: 0,
  monto_pipeline: 0,
  facturas_solicitadas: 0,
  actividades_pendientes: 0,
  ultima_actividad_at: null,
};

const defaultContactFilters = {
  q: "",
  activo: "true",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultOpportunityFilters = {
  q: "",
  etapa: "",
  activa: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultActivityFilters = {
  q: "",
  tipo: "",
  completada: "false",
  activo: "true",
  vencidas: "false",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultClientForm = {
  id: "",
  nombre_comercial: "",
  razon_social: "",
  rfc: "",
  tipo: "prospecto",
  email: "",
  telefono: "",
  sitio_web: "",
  direccion: "",
  ciudad: "",
  estado: "",
  pais: "",
  codigo_postal: "",
  origen: "",
  industria: "",
  notas: "",
  estatus: "activo",
};

const defaultContactForm = {
  id: "",
  client_id: "",
  nombre: "",
  puesto: "",
  email: "",
  telefono: "",
  whatsapp: "",
  principal: false,
  notas: "",
  activo: true,
};

const defaultOpportunityForm = {
  id: "",
  cliente_id: "",
  contacto_id: "",
  titulo: "",
  descripcion: "",
  etapa: "nueva",
  monto_estimado: "0",
  probabilidad: "0",
  fecha_estimada_cierre: "",
  origen: "",
  notas: "",
  activa: true,
};

const defaultOpportunityCloseForm = {
  opportunity_id: "",
  mode: "won",
  titulo: "",
  notas: "",
  motivo_perdida: "",
};

function getNowDateTimeLocalValue() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

const defaultActivityForm = {
  id: "",
  cliente_id: "",
  oportunidad_id: "",
  contacto_id: "",
  tipo: "tarea",
  titulo: "",
  descripcion: "",
  fecha_actividad: getNowDateTimeLocalValue(),
  fecha_vencimiento: "",
  completada: false,
  activo: true,
};


function normalizeOptionalText(value) {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed : null;
}


function normalizeIntegerInput(value) {
  return String(value ?? "").replace(/[^\d]/g, "");
}


function toDateInputValue(value) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return parsed.toISOString().slice(0, 10);
}


function toDateTimeLocalValue(value) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}


function toIsoDateTime(value) {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString();
}


function resolveCrmView(value) {
  return CRM_VIEWS.includes(value) ? value : "summary";
}


function clientDisplayName(client) {
  return client?.nombre_comercial || client?.razon_social || "Sin cliente";
}


function contactDisplayName(contact) {
  return contact?.nombre || "Sin contacto";
}


function opportunityStageLabel(value) {
  return OPPORTUNITY_STAGE_OPTIONS.find((option) => option.value === value)?.label || safeDisplayText(value, "Sin etapa");
}


function clientTypeLabel(value) {
  return CLIENT_TYPE_OPTIONS.find((option) => option.value === value)?.label || safeDisplayText(value, "Sin tipo");
}


function activityTypeLabel(value) {
  return ACTIVITY_TYPE_OPTIONS.find((option) => option.value === value)?.label || safeDisplayText(value, "Sin tipo");
}


function humanizeStatus(value) {
  if (!value) {
    return "Sin estatus";
  }
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}


function timelineTypeLabel(value) {
  switch (value) {
    case "venta_pos":
      return "Venta POS";
    case "proyecto_pm":
      return "Proyecto PM";
    case "oportunidad":
      return "Oportunidad";
    case "actividad":
      return "Actividad";
    case "solicitud_factura_pos":
      return "Solicitud de factura";
    default:
      return safeDisplayText(value, "Sin tipo");
  }
}


function timelineTypeTone(value) {
  switch (value) {
    case "venta_pos":
      return "success";
    case "proyecto_pm":
      return "info";
    case "oportunidad":
      return "warning";
    case "actividad":
      return "neutral";
    case "solicitud_factura_pos":
      return "info";
    default:
      return "neutral";
  }
}


function timelineStatusLabel(item) {
  if (!item?.estatus) {
    return "Sin estatus";
  }
  if (item.tipo === "oportunidad") {
    return opportunityStageLabel(item.estatus);
  }
  return humanizeStatus(item.estatus);
}


function timelineStatusTone(item) {
  if (!item?.estatus) {
    return "neutral";
  }
  if (item.tipo === "oportunidad") {
    return opportunityStageTone(item.estatus);
  }
  switch (item.estatus) {
    case "pagada":
    case "completada":
    case "activo":
    case "lista_para_facturar":
    case "preparada":
      return "success";
    case "cancelada":
    case "perdida":
    case "descartada":
      return "danger";
    case "pendiente":
    case "pendiente_datos":
    case "suspendida":
    case "solicitada":
    case "en_revision":
      return "warning";
    default:
      return "neutral";
  }
}


function opportunityStageTone(value) {
  switch (value) {
    case "ganada":
      return "success";
    case "perdida":
      return "danger";
    case "negociacion":
    case "propuesta":
      return "warning";
    case "contactado":
      return "info";
    case "nueva":
    default:
      return "neutral";
  }
}


function clientTypeTone(value) {
  switch (value) {
    case "cliente":
      return "success";
    case "otro":
      return "info";
    case "prospecto":
    default:
      return "warning";
  }
}


function isOverdue(activity) {
  if (!activity?.fecha_vencimiento || activity?.completada) {
    return false;
  }
  return new Date(activity.fecha_vencimiento).getTime() < Date.now();
}


function buildClientPayload(form) {
  return {
    nombre_comercial: String(form.nombre_comercial ?? "").trim(),
    razon_social: normalizeOptionalText(form.razon_social),
    rfc: normalizeOptionalText(form.rfc)?.toUpperCase() || null,
    tipo: form.tipo || "prospecto",
    email: normalizeOptionalText(form.email)?.toLowerCase() || null,
    telefono: normalizeOptionalText(form.telefono),
    sitio_web: normalizeOptionalText(form.sitio_web),
    direccion: normalizeOptionalText(form.direccion),
    ciudad: normalizeOptionalText(form.ciudad),
    estado: normalizeOptionalText(form.estado),
    pais: normalizeOptionalText(form.pais),
    codigo_postal: normalizeOptionalText(form.codigo_postal),
    origen: normalizeOptionalText(form.origen),
    industria: normalizeOptionalText(form.industria),
    notas: normalizeOptionalText(form.notas),
    estatus: form.estatus || "activo",
  };
}


function validateClientForm(form) {
  if (!String(form.nombre_comercial ?? "").trim()) {
    return "Captura el nombre comercial del cliente.";
  }
  if (normalizeOptionalText(form.email) && !EMAIL_REGEX.test(String(form.email).trim())) {
    return "Ingresa un email valido.";
  }
  if (normalizeOptionalText(form.rfc) && !RFC_REGEX.test(String(form.rfc).trim().toUpperCase())) {
    return "Ingresa un RFC valido.";
  }
  if (normalizeOptionalText(form.codigo_postal) && !POSTAL_CODE_REGEX.test(String(form.codigo_postal).trim())) {
    return "Ingresa un codigo postal valido.";
  }
  return "";
}


function buildContactPayload(form) {
  return {
    nombre: String(form.nombre ?? "").trim(),
    puesto: normalizeOptionalText(form.puesto),
    email: normalizeOptionalText(form.email)?.toLowerCase() || null,
    telefono: normalizeOptionalText(form.telefono),
    whatsapp: normalizeOptionalText(form.whatsapp),
    principal: Boolean(form.principal),
    notas: normalizeOptionalText(form.notas),
    activo: Boolean(form.activo),
  };
}


function validateContactForm(form) {
  if (!form.client_id) {
    return "Selecciona un cliente para el contacto.";
  }
  if (!String(form.nombre ?? "").trim()) {
    return "Captura el nombre del contacto.";
  }
  if (normalizeOptionalText(form.email) && !EMAIL_REGEX.test(String(form.email).trim())) {
    return "Ingresa un email valido.";
  }
  return "";
}


function buildOpportunityPayload(form) {
  return {
    cliente_id: form.cliente_id,
    contacto_id: form.contacto_id || null,
    titulo: String(form.titulo ?? "").trim(),
    descripcion: normalizeOptionalText(form.descripcion),
    etapa: form.etapa || "nueva",
    monto_estimado: Number(form.monto_estimado || 0),
    probabilidad: Number(form.probabilidad || 0),
    fecha_estimada_cierre: form.fecha_estimada_cierre || null,
    origen: normalizeOptionalText(form.origen),
    notas: normalizeOptionalText(form.notas),
    activa: Boolean(form.activa),
  };
}


function validateOpportunityForm(form) {
  if (!form.cliente_id) {
    return "Selecciona un cliente para la oportunidad.";
  }
  if (!String(form.titulo ?? "").trim()) {
    return "Captura el titulo de la oportunidad.";
  }
  const amount = Number(form.monto_estimado || 0);
  if (Number.isNaN(amount) || amount < 0) {
    return "El monto estimado debe ser mayor o igual a cero.";
  }
  const probability = Number(form.probabilidad || 0);
  if (!Number.isFinite(probability) || probability < 0 || probability > 100) {
    return "La probabilidad debe estar entre 0 y 100.";
  }
  if (form.etapa === "perdida" && !String(form.notas ?? "").trim()) {
    return "Usa cerrar perdida para registrar un motivo.";
  }
  return "";
}


function buildActivityPayload(form) {
  return {
    cliente_id: form.cliente_id || null,
    oportunidad_id: form.oportunidad_id || null,
    contacto_id: form.contacto_id || null,
    tipo: form.tipo || "nota",
    titulo: String(form.titulo ?? "").trim(),
    descripcion: normalizeOptionalText(form.descripcion),
    fecha_actividad: toIsoDateTime(form.fecha_actividad),
    fecha_vencimiento: toIsoDateTime(form.fecha_vencimiento),
    completada: Boolean(form.completada),
    activo: Boolean(form.activo),
  };
}


function validateActivityForm(form) {
  if (!String(form.titulo ?? "").trim()) {
    return "Captura el titulo de la actividad.";
  }
  if (!toIsoDateTime(form.fecha_actividad)) {
    return "Captura la fecha de actividad.";
  }
  return "";
}


function formatOpportunityProbability(value) {
  return `${formatNumber(Number(value || 0))}%`;
}


function CrmTabButton({ active, icon, label, onClick }) {
  return (
    <button
      className={`crm-tab-button ${active ? "active" : ""}`}
      onClick={onClick}
      type="button"
    >
      <span className="crm-tab-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
}


export default function CrmPage() {
  const { token, empresaId } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeView = resolveCrmView(searchParams.get("view"));

  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [summary, setSummary] = useState(defaultSummary);
  const [clients, setClients] = useState([]);
  const [clientMeta, setClientMeta] = useState(EMPTY_META);
  const [clientFilters, setClientFilters] = useState(defaultClientFilters);
  const [clientOptions, setClientOptions] = useState([]);

  const [contactClientId, setContactClientId] = useState("");
  const [contacts, setContacts] = useState([]);
  const [contactMeta, setContactMeta] = useState(EMPTY_META);
  const [contactFilters, setContactFilters] = useState(defaultContactFilters);
  const [contactOptionsByClient, setContactOptionsByClient] = useState({});

  const [opportunities, setOpportunities] = useState([]);
  const [opportunityMeta, setOpportunityMeta] = useState(EMPTY_META);
  const [opportunityFilters, setOpportunityFilters] = useState(defaultOpportunityFilters);
  const [opportunityOptions, setOpportunityOptions] = useState([]);

  const [activities, setActivities] = useState([]);
  const [activityMeta, setActivityMeta] = useState(EMPTY_META);
  const [activityFilters, setActivityFilters] = useState(defaultActivityFilters);

  const [clientFormOpen, setClientFormOpen] = useState(false);
  const [clientForm, setClientForm] = useState(defaultClientForm);
  const [clientDetailOpen, setClientDetailOpen] = useState(false);
  const [clientDetail, setClientDetail] = useState(null);
  const [clientDetailCommercialSummary, setClientDetailCommercialSummary] = useState(defaultClientCommercialSummary);
  const [clientDetailTimeline, setClientDetailTimeline] = useState([]);
  const [clientDetailContacts, setClientDetailContacts] = useState([]);
  const [clientDetailOpportunities, setClientDetailOpportunities] = useState([]);
  const [clientDetailActivities, setClientDetailActivities] = useState([]);

  const [contactFormOpen, setContactFormOpen] = useState(false);
  const [contactForm, setContactForm] = useState(defaultContactForm);

  const [opportunityFormOpen, setOpportunityFormOpen] = useState(false);
  const [opportunityForm, setOpportunityForm] = useState(defaultOpportunityForm);
  const [opportunityCloseOpen, setOpportunityCloseOpen] = useState(false);
  const [opportunityCloseForm, setOpportunityCloseForm] = useState(defaultOpportunityCloseForm);

  const [activityFormOpen, setActivityFormOpen] = useState(false);
  const [activityForm, setActivityForm] = useState(defaultActivityForm);

  const selectedContactClient = useMemo(
    () => clientOptions.find((item) => item.id === contactClientId) || null,
    [clientOptions, contactClientId],
  );

  const currentOpportunityContacts = useMemo(
    () => contactOptionsByClient[opportunityForm.cliente_id] || [],
    [contactOptionsByClient, opportunityForm.cliente_id],
  );

  const currentActivityContacts = useMemo(
    () => contactOptionsByClient[activityForm.cliente_id] || [],
    [contactOptionsByClient, activityForm.cliente_id],
  );

  const currentActivityOpportunities = useMemo(() => {
    if (!activityForm.cliente_id) {
      return opportunityOptions;
    }
    return opportunityOptions.filter((item) => item.cliente_id === activityForm.cliente_id);
  }, [activityForm.cliente_id, opportunityOptions]);

  const pipelineColumns = useMemo(() => {
    return PIPELINE_STAGE_ORDER.map((stage) => ({
      stage,
      label: opportunityStageLabel(stage),
      tone: opportunityStageTone(stage),
      summary: summary.pipeline_por_etapa.find((item) => item.etapa === stage) || {
        etapa: stage,
        oportunidades_count: 0,
        monto_total: 0,
      },
      items: opportunities.filter((item) => item.etapa === stage),
    }));
  }, [opportunities, summary.pipeline_por_etapa]);

  const clientCommercialMetrics = useMemo(() => ([
    {
      key: "total_ventas_pos",
      label: "Total ventas POS",
      meta: "Ventas pagadas relacionadas",
      value: formatMoney(clientDetailCommercialSummary.total_ventas_pos),
      tone: "success",
    },
    {
      key: "ventas_count",
      label: "Numero de ventas",
      meta: "Ventas POS ligadas al cliente",
      value: formatNumber(clientDetailCommercialSummary.ventas_count),
      tone: "info",
    },
    {
      key: "proyectos_count",
      label: "Proyectos",
      meta: "Total de proyectos vinculados",
      value: formatNumber(clientDetailCommercialSummary.proyectos_count),
      tone: "info",
    },
    {
      key: "proyectos_activos",
      label: "Proyectos activos",
      meta: "Proyectos en curso",
      value: formatNumber(clientDetailCommercialSummary.proyectos_activos),
      tone: "warning",
    },
    {
      key: "oportunidades_abiertas",
      label: "Oportunidades abiertas",
      meta: "Pipeline actual",
      value: formatNumber(clientDetailCommercialSummary.oportunidades_abiertas),
      tone: "warning",
    },
    {
      key: "monto_pipeline",
      label: "Monto pipeline",
      meta: "Valor estimado abierto",
      value: formatMoney(clientDetailCommercialSummary.monto_pipeline),
      tone: "warning",
    },
    {
      key: "facturas_solicitadas",
      label: "Facturas solicitadas",
      meta: "Solicitudes POS relacionadas",
      value: formatNumber(clientDetailCommercialSummary.facturas_solicitadas),
      tone: "info",
    },
    {
      key: "actividades_pendientes",
      label: "Actividades pendientes",
      meta: "Seguimiento por hacer",
      value: formatNumber(clientDetailCommercialSummary.actividades_pendientes),
      tone: clientDetailCommercialSummary.actividades_pendientes > 0 ? "warning" : "success",
    },
    {
      key: "ultima_actividad_at",
      label: "Ultima actividad",
      meta: "Actividad comercial mas reciente",
      value: clientDetailCommercialSummary.ultima_actividad_at ? formatDateTime(clientDetailCommercialSummary.ultima_actividad_at) : "Sin actividad",
      tone: "neutral",
    },
  ]), [clientDetailCommercialSummary]);

  async function loadSummaryData() {
    setSummaryLoading(true);
    try {
      const response = await getCrmSummary({ token, empresaId });
      setSummary(response);
      return response;
    } finally {
      setSummaryLoading(false);
    }
  }

  async function loadClientOptions() {
    const response = await listCrmClients({
      token,
      empresaId,
      filters: {
        limit: 100,
        offset: 0,
      },
    });
    setClientOptions(response.items || []);
    return response.items || [];
  }

  async function loadOpportunityOptions() {
    const response = await listCrmOpportunities({
      token,
      empresaId,
      filters: {
        limit: 100,
        offset: 0,
      },
    });
    setOpportunityOptions(response.items || []);
    return response.items || [];
  }

  async function loadClientContactOptions(clientId, { force = false } = {}) {
    if (!clientId) {
      return [];
    }
    if (!force && contactOptionsByClient[clientId]) {
      return contactOptionsByClient[clientId];
    }
    const response = await listCrmClientContacts({
      clientId,
      token,
      empresaId,
      filters: {
        limit: 100,
        offset: 0,
      },
    });
    const items = response.items || [];
    setContactOptionsByClient((current) => ({
      ...current,
      [clientId]: items,
    }));
    return items;
  }

  async function loadClientsPage(nextFilters = clientFilters) {
    const response = await listCrmClients({
      token,
      empresaId,
      filters: nextFilters,
    });
    setClients(response.items || []);
    setClientMeta({
      total: response.total || 0,
      limit: response.limit || nextFilters.limit,
      offset: response.offset || nextFilters.offset,
    });
    return response;
  }

  async function loadContactsPage(selectedClientId = contactClientId, nextFilters = contactFilters) {
    if (!selectedClientId) {
      setContacts([]);
      setContactMeta(EMPTY_META);
      return { items: [], total: 0, limit: nextFilters.limit, offset: nextFilters.offset };
    }
    const response = await listCrmClientContacts({
      clientId: selectedClientId,
      token,
      empresaId,
      filters: {
        ...nextFilters,
        activo: parseBooleanFilter(nextFilters.activo),
      },
    });
    setContacts(response.items || []);
    setContactMeta({
      total: response.total || 0,
      limit: response.limit || nextFilters.limit,
      offset: response.offset || nextFilters.offset,
    });
    return response;
  }

  async function loadOpportunitiesPage(nextFilters = opportunityFilters) {
    const response = await listCrmOpportunities({
      token,
      empresaId,
      filters: {
        ...nextFilters,
        activa: parseBooleanFilter(nextFilters.activa),
      },
    });
    setOpportunities(response.items || []);
    setOpportunityMeta({
      total: response.total || 0,
      limit: response.limit || nextFilters.limit,
      offset: response.offset || nextFilters.offset,
    });
    return response;
  }

  async function loadActivitiesPage(nextFilters = activityFilters) {
    const response = await listCrmActivities({
      token,
      empresaId,
      filters: {
        ...nextFilters,
        completada: parseBooleanFilter(nextFilters.completada),
        activo: parseBooleanFilter(nextFilters.activo),
        vencidas: nextFilters.vencidas === "true",
      },
    });
    setActivities(response.items || []);
    setActivityMeta({
      total: response.total || 0,
      limit: response.limit || nextFilters.limit,
      offset: response.offset || nextFilters.offset,
    });
    return response;
  }

  async function loadClientDetailBundle(clientId) {
    const [clientResponse, commercialSummaryResponse, timelineResponse, contactsResponse, opportunitiesResponse, activitiesResponse] = await Promise.all([
      getCrmClient({ clientId, token, empresaId }),
      getCrmClientCommercialSummary({ clientId, token, empresaId }),
      getCrmClientTimeline({ clientId, token, empresaId }),
      listCrmClientContacts({
        clientId,
        token,
        empresaId,
        filters: { limit: 5, offset: 0 },
      }),
      listCrmOpportunities({
        token,
        empresaId,
        filters: { client_id: clientId, limit: 5, offset: 0 },
      }),
      listCrmActivities({
        token,
        empresaId,
        filters: { client_id: clientId, limit: 5, offset: 0 },
      }),
    ]);
    setClientDetail(clientResponse);
    setClientDetailCommercialSummary(commercialSummaryResponse || defaultClientCommercialSummary);
    setClientDetailTimeline(timelineResponse.items || []);
    setClientDetailContacts(contactsResponse.items || []);
    setClientDetailOpportunities(opportunitiesResponse.items || []);
    setClientDetailActivities(activitiesResponse.items || []);
    return clientResponse;
  }

  function closeClientDetailModal() {
    setClientDetailOpen(false);
    setClientDetail(null);
    setClientDetailCommercialSummary(defaultClientCommercialSummary);
    setClientDetailTimeline([]);
    setClientDetailContacts([]);
    setClientDetailOpportunities([]);
    setClientDetailActivities([]);
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const [summaryResponse, optionClients, optionOpportunities, clientResponse, opportunityResponse, activityResponse] = await Promise.all([
          getCrmSummary({ token, empresaId }),
          listCrmClients({ token, empresaId, filters: { limit: 100, offset: 0 } }),
          listCrmOpportunities({ token, empresaId, filters: { limit: 100, offset: 0 } }),
          listCrmClients({ token, empresaId, filters: defaultClientFilters }),
          listCrmOpportunities({ token, empresaId, filters: defaultOpportunityFilters }),
          listCrmActivities({
            token,
            empresaId,
            filters: {
              ...defaultActivityFilters,
              completada: false,
              activo: true,
              vencidas: false,
            },
          }),
        ]);

        setSummary(summaryResponse);
        setClientOptions(optionClients.items || []);
        setOpportunityOptions(optionOpportunities.items || []);
        setClients(clientResponse.items || []);
        setClientMeta({
          total: clientResponse.total || 0,
          limit: clientResponse.limit || defaultClientFilters.limit,
          offset: clientResponse.offset || defaultClientFilters.offset,
        });
        setOpportunities(opportunityResponse.items || []);
        setOpportunityMeta({
          total: opportunityResponse.total || 0,
          limit: opportunityResponse.limit || defaultOpportunityFilters.limit,
          offset: opportunityResponse.offset || defaultOpportunityFilters.offset,
        });
        setActivities(activityResponse.items || []);
        setActivityMeta({
          total: activityResponse.total || 0,
          limit: activityResponse.limit || defaultActivityFilters.limit,
          offset: activityResponse.offset || defaultActivityFilters.offset,
        });

        const initialClientId = optionClients.items?.[0]?.id || "";
        setContactClientId(initialClientId);
        if (initialClientId) {
          await loadContactsPage(initialClientId, defaultContactFilters);
          await loadClientContactOptions(initialClientId, { force: true });
        } else {
          setContacts([]);
          setContactMeta(EMPTY_META);
        }
      } catch (requestError) {
        setError(requestError.message || "No se pudo cargar el CRM.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  function setCrmView(nextView) {
    const resolved = resolveCrmView(nextView);
    const nextParams = new URLSearchParams(searchParams);
    if (resolved === "summary") {
      nextParams.delete("view");
    } else {
      nextParams.set("view", resolved);
    }
    setSearchParams(nextParams, { replace: true });
  }

  function resetClientForm() {
    setClientForm(defaultClientForm);
  }

  function resetContactForm(nextClientId = contactClientId) {
    setContactForm({
      ...defaultContactForm,
      client_id: nextClientId || "",
    });
  }

  function resetOpportunityForm(nextClientId = "") {
    setOpportunityForm({
      ...defaultOpportunityForm,
      cliente_id: nextClientId || "",
    });
  }

  function resetActivityForm(nextClientId = "", nextOpportunityId = "") {
    setActivityForm({
      ...defaultActivityForm,
      cliente_id: nextClientId || "",
      oportunidad_id: nextOpportunityId || "",
      fecha_actividad: getNowDateTimeLocalValue(),
    });
  }

  function openClientCreateModal() {
    resetClientForm();
    setClientFormOpen(true);
    setError("");
    setSuccess("");
  }

  async function openClientEditModal(clientId) {
    setSubmitting(true);
    setError("");
    try {
      const response = await getCrmClient({ clientId, token, empresaId });
      setClientForm({
        id: response.id,
        nombre_comercial: response.nombre_comercial || "",
        razon_social: response.razon_social || "",
        rfc: response.rfc || "",
        tipo: response.tipo || "prospecto",
        email: response.email || "",
        telefono: response.telefono || "",
        sitio_web: response.sitio_web || "",
        direccion: response.direccion || "",
        ciudad: response.ciudad || "",
        estado: response.estado || "",
        pais: response.pais || "",
        codigo_postal: response.codigo_postal || "",
        origen: response.origen || "",
        industria: response.industria || "",
        notas: response.notas || "",
        estatus: response.estatus || "activo",
      });
      setClientFormOpen(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el cliente.");
    } finally {
      setSubmitting(false);
    }
  }

  async function openClientDetailModal(clientId) {
    setClientDetailOpen(true);
    setDetailLoading(true);
    setClientDetail(null);
    setClientDetailCommercialSummary(defaultClientCommercialSummary);
    setClientDetailTimeline([]);
    setError("");
    try {
      await loadClientDetailBundle(clientId);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle del cliente.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function openContactCreateModal(nextClientId = contactClientId) {
    if (!nextClientId) {
      setError("Agrega al menos un cliente antes de crear contactos.");
      return;
    }
    await loadClientContactOptions(nextClientId);
    resetContactForm(nextClientId);
    setContactFormOpen(true);
    setError("");
    setSuccess("");
  }

  async function openContactEditModal(contact) {
    await loadClientContactOptions(contact.cliente_id);
    setContactForm({
      id: contact.id,
      client_id: contact.cliente_id,
      nombre: contact.nombre || "",
      puesto: contact.puesto || "",
      email: contact.email || "",
      telefono: contact.telefono || "",
      whatsapp: contact.whatsapp || "",
      principal: Boolean(contact.principal),
      notas: contact.notas || "",
      activo: Boolean(contact.activo),
    });
    setContactFormOpen(true);
    setError("");
    setSuccess("");
  }

  async function openOpportunityCreateModal(nextClientId = "") {
    if (nextClientId) {
      await loadClientContactOptions(nextClientId);
    }
    resetOpportunityForm(nextClientId);
    setOpportunityFormOpen(true);
    setError("");
    setSuccess("");
  }

  async function openOpportunityEditModal(opportunityId) {
    setSubmitting(true);
    setError("");
    try {
      const response = await getCrmOpportunity({ opportunityId, token, empresaId });
      if (response.cliente_id) {
        await loadClientContactOptions(response.cliente_id);
      }
      setOpportunityForm({
        id: response.id,
        cliente_id: response.cliente_id || "",
        contacto_id: response.contacto_id || "",
        titulo: response.titulo || "",
        descripcion: response.descripcion || "",
        etapa: response.etapa || "nueva",
        monto_estimado: String(response.monto_estimado ?? 0),
        probabilidad: String(response.probabilidad ?? 0),
        fecha_estimada_cierre: toDateInputValue(response.fecha_estimada_cierre),
        origen: response.origen || "",
        notas: response.notas || "",
        activa: Boolean(response.activa),
      });
      setOpportunityFormOpen(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar la oportunidad.");
    } finally {
      setSubmitting(false);
    }
  }

  function openOpportunityCloseModal(opportunity, mode) {
    setOpportunityCloseForm({
      opportunity_id: opportunity.id,
      mode,
      titulo: opportunity.titulo || "",
      notas: opportunity.notas || "",
      motivo_perdida: "",
    });
    setOpportunityCloseOpen(true);
    setError("");
    setSuccess("");
  }

  async function openActivityCreateModal(nextClientId = "", nextOpportunityId = "") {
    if (nextClientId) {
      await loadClientContactOptions(nextClientId);
    }
    resetActivityForm(nextClientId, nextOpportunityId);
    setActivityFormOpen(true);
    setError("");
    setSuccess("");
  }

  async function openActivityEditModal(activity) {
    if (activity.cliente_id) {
      await loadClientContactOptions(activity.cliente_id);
    }
    setActivityForm({
      id: activity.id,
      cliente_id: activity.cliente_id || "",
      oportunidad_id: activity.oportunidad_id || "",
      contacto_id: activity.contacto_id || "",
      tipo: activity.tipo || "nota",
      titulo: activity.titulo || "",
      descripcion: activity.descripcion || "",
      fecha_actividad: toDateTimeLocalValue(activity.fecha_actividad),
      fecha_vencimiento: toDateTimeLocalValue(activity.fecha_vencimiento),
      completada: Boolean(activity.completada),
      activo: Boolean(activity.activo),
    });
    setActivityFormOpen(true);
    setError("");
    setSuccess("");
  }

  async function handleClientSubmit(event) {
    event.preventDefault();
    const validationMessage = validateClientForm(clientForm);
    if (validationMessage) {
      setError(validationMessage);
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildClientPayload(clientForm);
      const response = clientForm.id
        ? await updateCrmClient({ clientId: clientForm.id, token, empresaId, payload })
        : await createCrmClient({ token, empresaId, payload });

      setClientFormOpen(false);
      resetClientForm();
      await Promise.all([
        loadSummaryData(),
        loadClientsPage(clientFilters),
        loadClientOptions(),
      ]);

      if (!contactClientId) {
        setContactClientId(response.id);
        await loadContactsPage(response.id, defaultContactFilters);
      }
      if (clientDetailOpen && clientDetail?.id === response.id) {
        await loadClientDetailBundle(response.id);
      }
      setSuccess(clientForm.id ? "Cliente actualizado correctamente." : "Cliente creado correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el cliente.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleClientStatusToggle(client) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      if (client.estatus === "activo") {
        await deactivateCrmClient({ clientId: client.id, token, empresaId });
      } else {
        await reactivateCrmClient({ clientId: client.id, token, empresaId });
      }
      await Promise.all([
        loadSummaryData(),
        loadClientsPage(clientFilters),
        loadClientOptions(),
      ]);
      if (clientDetailOpen && clientDetail?.id === client.id) {
        await loadClientDetailBundle(client.id);
      }
      setSuccess(client.estatus === "activo" ? "Cliente desactivado." : "Cliente reactivado.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el cliente.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleContactSubmit(event) {
    event.preventDefault();
    const validationMessage = validateContactForm(contactForm);
    if (validationMessage) {
      setError(validationMessage);
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildContactPayload(contactForm);
      if (contactForm.id) {
        await updateCrmContact({
          contactId: contactForm.id,
          token,
          empresaId,
          payload,
        });
      } else {
        await createCrmContact({
          clientId: contactForm.client_id,
          token,
          empresaId,
          payload,
        });
      }

      setContactFormOpen(false);
      resetContactForm(contactForm.client_id);
      await Promise.all([
        loadContactsPage(contactForm.client_id, contactFilters),
        loadClientContactOptions(contactForm.client_id, { force: true }),
      ]);
      if (clientDetailOpen && clientDetail?.id === contactForm.client_id) {
        await loadClientDetailBundle(contactForm.client_id);
      }
      setSuccess(contactForm.id ? "Contacto actualizado correctamente." : "Contacto creado correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el contacto.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleContactStatusToggle(contact) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      if (contact.activo) {
        await deactivateCrmContact({ contactId: contact.id, token, empresaId });
      } else {
        await updateCrmContact({
          contactId: contact.id,
          token,
          empresaId,
          payload: { activo: true },
        });
      }
      await Promise.all([
        loadContactsPage(contact.cliente_id, contactFilters),
        loadClientContactOptions(contact.cliente_id, { force: true }),
      ]);
      if (clientDetailOpen && clientDetail?.id === contact.cliente_id) {
        await loadClientDetailBundle(contact.cliente_id);
      }
      setSuccess(contact.activo ? "Contacto desactivado." : "Contacto reactivado.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el contacto.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOpportunitySubmit(event) {
    event.preventDefault();
    const validationMessage = validateOpportunityForm(opportunityForm);
    if (validationMessage) {
      setError(validationMessage);
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildOpportunityPayload(opportunityForm);
      if (opportunityForm.id) {
        await updateCrmOpportunity({
          opportunityId: opportunityForm.id,
          token,
          empresaId,
          payload,
        });
      } else {
        await createCrmOpportunity({ token, empresaId, payload });
      }

      const relatedClientId = opportunityForm.cliente_id;
      setOpportunityFormOpen(false);
      resetOpportunityForm();
      await Promise.all([
        loadSummaryData(),
        loadOpportunitiesPage(opportunityFilters),
        loadOpportunityOptions(),
      ]);
      if (clientDetailOpen && clientDetail?.id === relatedClientId) {
        await loadClientDetailBundle(relatedClientId);
      }
      setSuccess(opportunityForm.id ? "Oportunidad actualizada correctamente." : "Oportunidad creada correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la oportunidad.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOpportunityCloseSubmit(event) {
    event.preventDefault();
    if (opportunityCloseForm.mode === "lost" && !String(opportunityCloseForm.motivo_perdida ?? "").trim()) {
      setError("Captura el motivo de perdida.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      if (opportunityCloseForm.mode === "won") {
        await closeCrmOpportunityWon({
          opportunityId: opportunityCloseForm.opportunity_id,
          token,
          empresaId,
          payload: normalizeOptionalText(opportunityCloseForm.notas) ? { notas: opportunityCloseForm.notas } : undefined,
        });
      } else {
        await closeCrmOpportunityLost({
          opportunityId: opportunityCloseForm.opportunity_id,
          token,
          empresaId,
          payload: {
            motivo_perdida: String(opportunityCloseForm.motivo_perdida ?? "").trim(),
            notas: normalizeOptionalText(opportunityCloseForm.notas),
          },
        });
      }

      setOpportunityCloseOpen(false);
      setOpportunityCloseForm(defaultOpportunityCloseForm);
      await Promise.all([
        loadSummaryData(),
        loadOpportunitiesPage(opportunityFilters),
        loadOpportunityOptions(),
      ]);
      setSuccess(opportunityCloseForm.mode === "won" ? "Oportunidad cerrada como ganada." : "Oportunidad cerrada como perdida.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo cerrar la oportunidad.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleActivitySubmit(event) {
    event.preventDefault();
    const validationMessage = validateActivityForm(activityForm);
    if (validationMessage) {
      setError(validationMessage);
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = buildActivityPayload(activityForm);
      if (activityForm.id) {
        await updateCrmActivity({
          activityId: activityForm.id,
          token,
          empresaId,
          payload,
        });
      } else {
        await createCrmActivity({ token, empresaId, payload });
      }

      const relatedClientId = activityForm.cliente_id;
      setActivityFormOpen(false);
      resetActivityForm();
      await Promise.all([
        loadSummaryData(),
        loadActivitiesPage(activityFilters),
      ]);
      if (clientDetailOpen && clientDetail?.id === relatedClientId) {
        await loadClientDetailBundle(relatedClientId);
      }
      setSuccess(activityForm.id ? "Actividad actualizada correctamente." : "Actividad creada correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la actividad.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleActivityComplete(activity) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await completeCrmActivity({ activityId: activity.id, token, empresaId });
      await Promise.all([
        loadSummaryData(),
        loadActivitiesPage(activityFilters),
      ]);
      if (clientDetailOpen && clientDetail?.id === activity.cliente_id) {
        await loadClientDetailBundle(activity.cliente_id);
      }
      setSuccess("Actividad marcada como completada.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo completar la actividad.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleActivityDeactivate(activity) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await deactivateCrmActivity({ activityId: activity.id, token, empresaId });
      await Promise.all([
        loadSummaryData(),
        loadActivitiesPage(activityFilters),
      ]);
      if (clientDetailOpen && clientDetail?.id === activity.cliente_id) {
        await loadClientDetailBundle(activity.cliente_id);
      }
      setSuccess("Actividad desactivada.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar la actividad.");
    } finally {
      setSubmitting(false);
    }
  }

  async function applyClientFilters(nextFilters) {
    setClientFilters(nextFilters);
    setError("");
    try {
      await loadClientsPage(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar los filtros de clientes.");
    }
  }

  async function applyContactFilters(nextFilters, nextClientId = contactClientId) {
    setContactFilters(nextFilters);
    setError("");
    try {
      await loadContactsPage(nextClientId, nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar los filtros de contactos.");
    }
  }

  async function applyOpportunityFilters(nextFilters) {
    setOpportunityFilters(nextFilters);
    setError("");
    try {
      await loadOpportunitiesPage(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar los filtros de oportunidades.");
    }
  }

  async function applyActivityFilters(nextFilters) {
    setActivityFilters(nextFilters);
    setError("");
    try {
      await loadActivitiesPage(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar los filtros de actividades.");
    }
  }

  async function handleRefreshAll() {
    setError("");
    try {
      await Promise.all([
        loadSummaryData(),
        loadClientOptions(),
        loadClientsPage(clientFilters),
        loadOpportunityOptions(),
        loadOpportunitiesPage(opportunityFilters),
        loadActivitiesPage(activityFilters),
      ]);
      if (contactClientId) {
        await loadContactsPage(contactClientId, contactFilters);
      }
      setSuccess("CRM actualizado.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el CRM.");
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando CRM...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen crm-screen">
      <PageHeader
        actions={(
          <div className="inventory-actions">
            <ActionButton icon={<Plus size={16} />} onClick={openClientCreateModal} size="sm" tone="primary" type="button">
              Nuevo cliente
            </ActionButton>
            <ActionButton icon={<RefreshCw size={16} />} onClick={handleRefreshAll} size="sm" type="button">
              Actualizar
            </ActionButton>
          </div>
        )}
        eyebrow="CRM"
        subtitle="Resumen comercial, clientes, contactos, oportunidades, actividades y pipeline operativo."
        title="CRM"
      >
        <div className="crm-tab-bar">
          <CrmTabButton active={activeView === "summary"} icon={<TrendingUp size={16} />} label="Resumen" onClick={() => setCrmView("summary")} />
          <CrmTabButton active={activeView === "clients"} icon={<Building2 size={16} />} label="Clientes" onClick={() => setCrmView("clients")} />
          <CrmTabButton active={activeView === "contacts"} icon={<Users size={16} />} label="Contactos" onClick={() => setCrmView("contacts")} />
          <CrmTabButton active={activeView === "opportunities"} icon={<Target size={16} />} label="Oportunidades" onClick={() => setCrmView("opportunities")} />
          <CrmTabButton active={activeView === "activities"} icon={<CalendarClock size={16} />} label="Actividades" onClick={() => setCrmView("activities")} />
          <CrmTabButton active={activeView === "pipeline"} icon={<KanbanSquare size={16} />} label="Pipeline" onClick={() => setCrmView("pipeline")} />
        </div>
      </PageHeader>

      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>Error operativo</strong>
          <p>{error}</p>
        </div>
      ) : null}

      {success ? (
        <div className="inventory-form-note inventory-form-note-success">
          <strong>Operacion completada</strong>
          <p>{success}</p>
        </div>
      ) : null}

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard icon={<Building2 size={16} />} label="Clientes activos" meta="Base activa" tone="success" value={formatNumber(summary.kpis.clientes_activos)} />
        <MetricCard icon={<UserCircle2 size={16} />} label="Prospectos" meta="Listos para seguimiento" tone="warning" value={formatNumber(summary.kpis.prospectos)} />
        <MetricCard icon={<BriefcaseBusiness size={16} />} label="Oportunidades abiertas" meta="Pipeline vivo" tone="info" value={formatNumber(summary.kpis.oportunidades_abiertas)} />
        <MetricCard icon={<HandCoins size={16} />} label="Monto pipeline" meta={summaryLoading ? "Actualizando..." : "Valor estimado"} tone="info" value={formatMoney(summary.kpis.monto_pipeline)} />
        <MetricCard icon={<CheckCircle2 size={16} />} label="Ganadas" meta="Cerradas a favor" tone="success" value={formatNumber(summary.kpis.oportunidades_ganadas)} />
        <MetricCard icon={<XCircle size={16} />} label="Perdidas" meta="Cerradas en contra" tone="danger" value={formatNumber(summary.kpis.oportunidades_perdidas)} />
        <MetricCard icon={<Clock3 size={16} />} label="Actividades pendientes" meta="Sin completar" tone="warning" value={formatNumber(summary.kpis.actividades_pendientes)} />
        <MetricCard icon={<AlertTriangle size={16} />} label="Actividades vencidas" meta="Requieren accion" tone="danger" value={formatNumber(summary.kpis.actividades_vencidas)} />
      </section>

      {activeView === "summary" ? (
        <div className="crm-view-stack">
          <section className="crm-summary-grid">
            <DataCard
              actions={<ActionButton icon={<Target size={16} />} onClick={() => setCrmView("pipeline")} size="sm" type="button">Ver pipeline</ActionButton>}
              subtitle="Conteo y monto por etapa con base en las solicitudes del backend."
              title="Pipeline por etapa"
            >
              {summary.pipeline_por_etapa.length === 0 ? (
                <EmptyState compact note="Agrega la primera oportunidad para activar el embudo comercial." title="Sin pipeline registrado" />
              ) : (
                <div className="crm-stage-summary-grid">
                  {pipelineColumns.map((column) => (
                    <article className={`crm-stage-summary-card tone-${column.tone}`} key={column.stage}>
                      <div>
                        <strong>{column.label}</strong>
                        <span>{formatNumber(column.summary.oportunidades_count)} oportunidades</span>
                      </div>
                      <b>{formatMoney(column.summary.monto_total)}</b>
                    </article>
                  ))}
                </div>
              )}
            </DataCard>

            <DataCard
              actions={<ActionButton icon={<Plus size={16} />} onClick={() => openOpportunityCreateModal()} size="sm" tone="primary" type="button">Nueva oportunidad</ActionButton>}
              subtitle="Ultimas oportunidades creadas o actualizadas."
              title="Oportunidades recientes"
            >
              {summary.oportunidades_recientes.length === 0 ? (
                <EmptyState compact note="Todavia no hay oportunidades en CRM." title="Sin oportunidades recientes" />
              ) : (
                <DataTable
                  columns={[
                    { key: "titulo", label: "Oportunidad" },
                    { key: "cliente", label: "Cliente" },
                    { key: "etapa", label: "Etapa" },
                    { key: "monto", label: "Monto" },
                    { key: "acciones", label: "Acciones" },
                  ]}
                >
                  <tbody>
                    {summary.oportunidades_recientes.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.titulo)}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.descripcion, "Sin descripcion")}</div>
                        </td>
                        <td>{safeDisplayText(item.cliente_nombre_comercial, "Sin cliente")}</td>
                        <td>
                          <StatusBadge tone={opportunityStageTone(item.etapa)}>
                            {opportunityStageLabel(item.etapa)}
                          </StatusBadge>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{formatMoney(item.monto_estimado)}</div>
                          <div className="inventory-cell-sub">{formatOpportunityProbability(item.probabilidad)}</div>
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openOpportunityEditModal(item.id)} type="button">
                            Editar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </DataCard>
          </section>

          <section className="crm-summary-grid">
            <DataCard
              actions={<ActionButton icon={<Plus size={16} />} onClick={() => openActivityCreateModal()} size="sm" tone="primary" type="button">Nueva actividad</ActionButton>}
              subtitle="Actividades activas y sin completar."
              title="Actividades pendientes"
            >
              {summary.actividades_pendientes.length === 0 ? (
                <EmptyState compact note="No hay actividades pendientes por ahora." title="Todo al corriente" />
              ) : (
                <DataTable
                  columns={[
                    { key: "actividad", label: "Actividad" },
                    { key: "vinculo", label: "Cliente / oportunidad" },
                    { key: "fecha", label: "Fecha" },
                    { key: "estado", label: "Estado" },
                    { key: "acciones", label: "Acciones" },
                  ]}
                >
                  <tbody>
                    {summary.actividades_pendientes.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.titulo)}</div>
                          <div className="inventory-cell-sub">{activityTypeLabel(item.tipo)}</div>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.cliente_nombre_comercial, "Sin cliente")}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.oportunidad_titulo, "Sin oportunidad")}</div>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{formatDateTime(item.fecha_actividad)}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.fecha_vencimiento ? formatDateTime(item.fecha_vencimiento) : "Sin vencimiento")}</div>
                        </td>
                        <td>
                          <StatusBadge tone={isOverdue(item) ? "danger" : "warning"}>
                            {isOverdue(item) ? "Vencida" : "Pendiente"}
                          </StatusBadge>
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openActivityEditModal(item)} type="button">
                            Editar
                          </button>
                          <button className="link-button" onClick={() => handleActivityComplete(item)} type="button">
                            Completar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </DataCard>

            <DataCard
              actions={<ActionButton icon={<Eye size={16} />} onClick={() => setCrmView("clients")} size="sm" type="button">Ver clientes</ActionButton>}
              subtitle="Altas recientes en el directorio comercial."
              title="Clientes recientes"
            >
              {summary.clientes_recientes.length === 0 ? (
                <EmptyState compact note="Aun no hay clientes creados en CRM." title="Sin clientes recientes" />
              ) : (
                <DataTable
                  columns={[
                    { key: "cliente", label: "Cliente" },
                    { key: "tipo", label: "Tipo" },
                    { key: "contacto", label: "Contacto" },
                    { key: "estatus", label: "Estatus" },
                    { key: "acciones", label: "Acciones" },
                  ]}
                >
                  <tbody>
                    {summary.clientes_recientes.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className="inventory-cell-main">{clientDisplayName(item)}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.razon_social, "Sin razon social")}</div>
                        </td>
                        <td>
                          <StatusBadge tone={clientTypeTone(item.tipo)}>{clientTypeLabel(item.tipo)}</StatusBadge>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.email, "Sin email")}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.telefono, "Sin telefono")}</div>
                        </td>
                        <td>
                          <StatusBadge tone={item.estatus === "activo" ? "success" : "neutral"}>
                            {safeDisplayText(item.estatus)}
                          </StatusBadge>
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openClientDetailModal(item.id)} type="button">
                            Ver detalle
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </DataCard>
          </section>
        </div>
      ) : null}

      {activeView === "clients" ? (
        <div className="crm-view-stack">
          <FilterCard
            actions={(
              <div className="inventory-actions">
                <ActionButton icon={<Filter size={16} />} onClick={() => applyClientFilters({ ...clientFilters, offset: 0 })} size="sm" tone="primary" type="button">
                  Aplicar
                </ActionButton>
                <ActionButton onClick={() => applyClientFilters(defaultClientFilters)} size="sm" type="button">
                  Limpiar
                </ActionButton>
              </div>
            )}
            title="Filtros de clientes"
          >
            <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
              <SearchInput
                hint="Busca por nombre comercial, razon social, RFC, email o industria."
                label="Buscar cliente"
                onChange={(event) => setClientFilters((current) => ({ ...current, q: event.target.value }))}
                onKeyDown={async (event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    await applyClientFilters({ ...clientFilters, offset: 0 });
                  }
                }}
                placeholder="Cliente, RFC o industria"
                value={clientFilters.q}
              />

              <FormGrid>
                <Field label="Tipo">
                  <select onChange={(event) => setClientFilters((current) => ({ ...current, tipo: event.target.value }))} value={clientFilters.tipo}>
                    <option value="">Todos</option>
                    {CLIENT_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Estatus">
                  <select onChange={(event) => setClientFilters((current) => ({ ...current, estatus: event.target.value }))} value={clientFilters.estatus}>
                    <option value="">Todos</option>
                    {CLIENT_STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </Field>
              </FormGrid>
            </div>
          </FilterCard>

          <DataCard
            actions={<ResultMeta label="clientes" loaded={clients.length} total={clientMeta.total} />}
            subtitle="Base multiempresa para prospectos y clientes activos."
            title="Directorio de clientes"
          >
            {clients.length === 0 ? (
              <EmptyState note="Crea el primer cliente para empezar a trabajar el pipeline." title="No hay clientes registrados" />
            ) : (
              <>
                <DataTable
                  columns={[
                    { key: "cliente", label: "Cliente" },
                    { key: "tipo", label: "Tipo" },
                    { key: "contacto", label: "Contacto" },
                    { key: "origen", label: "Origen / industria" },
                    { key: "estatus", label: "Estatus" },
                    { key: "acciones", label: "Acciones" },
                  ]}
                >
                  <tbody>
                    {clients.map((client) => (
                      <tr key={client.id}>
                        <td>
                          <div className="inventory-cell-main">{clientDisplayName(client)}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(client.razon_social, "Sin razon social")}</div>
                        </td>
                        <td>
                          <StatusBadge tone={clientTypeTone(client.tipo)}>{clientTypeLabel(client.tipo)}</StatusBadge>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(client.email, "Sin email")}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(client.telefono, "Sin telefono")}</div>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(client.origen, "Sin origen")}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(client.industria, "Sin industria")}</div>
                        </td>
                        <td>
                          <StatusBadge tone={client.estatus === "activo" ? "success" : "neutral"}>{safeDisplayText(client.estatus)}</StatusBadge>
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openClientDetailModal(client.id)} type="button">
                            Ver detalle
                          </button>
                          <button className="link-button" onClick={() => openClientEditModal(client.id)} type="button">
                            Editar
                          </button>
                          <button
                            className="link-button"
                            onClick={async () => {
                              setContactClientId(client.id);
                              await applyContactFilters({ ...defaultContactFilters, offset: 0 }, client.id);
                              setCrmView("contacts");
                            }}
                            type="button"
                          >
                            Contactos
                          </button>
                          <button className="link-button" onClick={() => handleClientStatusToggle(client)} type="button">
                            {client.estatus === "activo" ? "Desactivar" : "Reactivar"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>

                <PaginationControls
                  meta={clientMeta}
                  onNext={() => applyClientFilters({ ...clientFilters, offset: clientMeta.offset + clientMeta.limit })}
                  onPrevious={() => applyClientFilters({ ...clientFilters, offset: Math.max(0, clientMeta.offset - clientMeta.limit) })}
                />
              </>
            )}
          </DataCard>
        </div>
      ) : null}

      {activeView === "contacts" ? (
        <div className="crm-view-stack">
          <FilterCard
            actions={(
              <div className="inventory-actions">
                <ActionButton icon={<Plus size={16} />} onClick={() => openContactCreateModal(contactClientId)} size="sm" tone="primary" type="button">
                  Nuevo contacto
                </ActionButton>
                <ActionButton onClick={() => applyContactFilters({ ...contactFilters, offset: 0 }, contactClientId)} size="sm" tone="primary" type="button">
                  Aplicar
                </ActionButton>
              </div>
            )}
            subtitle="Gestiona contactos por cliente sin perder el contexto comercial."
            title="Contactos"
          >
            <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
              <FormGrid>
                <Field label="Cliente">
                  <select
                    onChange={async (event) => {
                      const nextClientId = event.target.value;
                      setContactClientId(nextClientId);
                      await loadClientContactOptions(nextClientId);
                      await applyContactFilters({ ...defaultContactFilters, offset: 0 }, nextClientId);
                    }}
                    value={contactClientId}
                  >
                    <option value="">Selecciona un cliente</option>
                    {clientOptions.map((client) => (
                      <option key={client.id} value={client.id}>
                        {clientDisplayName(client)}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Activo">
                  <select onChange={(event) => setContactFilters((current) => ({ ...current, activo: event.target.value }))} value={contactFilters.activo}>
                    <option value="true">Activos</option>
                    <option value="false">Inactivos</option>
                    <option value="">Todos</option>
                  </select>
                </Field>
              </FormGrid>

              <SearchInput
                hint="Busca por nombre, puesto, email o telefono."
                label="Buscar contacto"
                onChange={(event) => setContactFilters((current) => ({ ...current, q: event.target.value }))}
                onKeyDown={async (event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    await applyContactFilters({ ...contactFilters, offset: 0 }, contactClientId);
                  }
                }}
                placeholder="Nombre, email o telefono"
                value={contactFilters.q}
              />
            </div>
          </FilterCard>

          <DataCard
            actions={<ResultMeta label="contactos" loaded={contacts.length} total={contactMeta.total} />}
            subtitle={selectedContactClient ? `Cliente seleccionado: ${clientDisplayName(selectedContactClient)}` : "Selecciona un cliente para ver sus contactos."}
            title="Agenda comercial"
          >
            {!contactClientId ? (
              <EmptyState note="Selecciona un cliente y luego carga o crea contactos." title="Sin cliente seleccionado" />
            ) : contacts.length === 0 ? (
              <EmptyState note="Agrega el primer contacto para este cliente." title="No hay contactos registrados" />
            ) : (
              <>
                <DataTable
                  columns={[
                    { key: "contacto", label: "Contacto" },
                    { key: "cliente", label: "Cliente" },
                    { key: "canales", label: "Canales" },
                    { key: "rol", label: "Puesto" },
                    { key: "estatus", label: "Estatus" },
                    { key: "acciones", label: "Acciones" },
                  ]}
                >
                  <tbody>
                    {contacts.map((contact) => (
                      <tr key={contact.id}>
                        <td>
                          <div className="inventory-cell-main">{contactDisplayName(contact)}</div>
                          <div className="inventory-cell-sub">{contact.principal ? "Contacto principal" : "Contacto secundario"}</div>
                        </td>
                        <td>{safeDisplayText(contact.cliente_nombre_comercial, "Sin cliente")}</td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(contact.email, "Sin email")}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(contact.telefono || contact.whatsapp, "Sin telefono")}</div>
                        </td>
                        <td>{safeDisplayText(contact.puesto, "Sin puesto")}</td>
                        <td>
                          <StatusBadge tone={contact.activo ? "success" : "neutral"}>
                            {contact.activo ? "Activo" : "Inactivo"}
                          </StatusBadge>
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openContactEditModal(contact)} type="button">
                            Editar
                          </button>
                          <button className="link-button" onClick={() => handleContactStatusToggle(contact)} type="button">
                            {contact.activo ? "Desactivar" : "Reactivar"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>

                <PaginationControls
                  meta={contactMeta}
                  onNext={() => applyContactFilters({ ...contactFilters, offset: contactMeta.offset + contactMeta.limit }, contactClientId)}
                  onPrevious={() => applyContactFilters({ ...contactFilters, offset: Math.max(0, contactMeta.offset - contactMeta.limit) }, contactClientId)}
                />
              </>
            )}
          </DataCard>
        </div>
      ) : null}

      {activeView === "opportunities" ? (
        <div className="crm-view-stack">
          <FilterCard
            actions={(
              <div className="inventory-actions">
                <ActionButton icon={<Plus size={16} />} onClick={() => openOpportunityCreateModal()} size="sm" tone="primary" type="button">
                  Nueva oportunidad
                </ActionButton>
                <ActionButton onClick={() => applyOpportunityFilters({ ...opportunityFilters, offset: 0 })} size="sm" tone="primary" type="button">
                  Aplicar
                </ActionButton>
                <ActionButton onClick={() => applyOpportunityFilters(defaultOpportunityFilters)} size="sm" type="button">
                  Limpiar
                </ActionButton>
              </div>
            )}
            title="Filtros de oportunidades"
          >
            <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
              <SearchInput
                hint="Busca por titulo, descripcion o cliente."
                label="Buscar oportunidad"
                onChange={(event) => setOpportunityFilters((current) => ({ ...current, q: event.target.value }))}
                onKeyDown={async (event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    await applyOpportunityFilters({ ...opportunityFilters, offset: 0 });
                  }
                }}
                placeholder="Titulo o cliente"
                value={opportunityFilters.q}
              />

              <FormGrid>
                <Field label="Etapa">
                  <select onChange={(event) => setOpportunityFilters((current) => ({ ...current, etapa: event.target.value }))} value={opportunityFilters.etapa}>
                    <option value="">Todas</option>
                    {OPPORTUNITY_STAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Activa">
                  <select onChange={(event) => setOpportunityFilters((current) => ({ ...current, activa: event.target.value }))} value={opportunityFilters.activa}>
                    <option value="">Todas</option>
                    <option value="true">Activas</option>
                    <option value="false">Cerradas</option>
                  </select>
                </Field>
              </FormGrid>
            </div>
          </FilterCard>

          <DataCard
            actions={<ResultMeta label="oportunidades" loaded={opportunities.length} total={opportunityMeta.total} />}
            subtitle="Embudo comercial con monto estimado y probabilidad de cierre."
            title="Oportunidades"
          >
            {opportunities.length === 0 ? (
              <EmptyState note="Crea la primera oportunidad y conecta cliente, monto y etapa." title="No hay oportunidades registradas" />
            ) : (
              <>
                <DataTable
                  columns={[
                    { key: "oportunidad", label: "Oportunidad" },
                    { key: "cliente", label: "Cliente" },
                    { key: "etapa", label: "Etapa" },
                    { key: "monto", label: "Monto" },
                    { key: "cierre", label: "Cierre" },
                    { key: "acciones", label: "Acciones" },
                  ]}
                >
                  <tbody>
                    {opportunities.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.titulo)}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.descripcion, "Sin descripcion")}</div>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.cliente_nombre_comercial, "Sin cliente")}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.contacto_nombre, "Sin contacto")}</div>
                        </td>
                        <td>
                          <StatusBadge tone={opportunityStageTone(item.etapa)}>
                            {opportunityStageLabel(item.etapa)}
                          </StatusBadge>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{formatMoney(item.monto_estimado)}</div>
                          <div className="inventory-cell-sub">{formatOpportunityProbability(item.probabilidad)}</div>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.fecha_estimada_cierre ? formatDate(item.fecha_estimada_cierre) : "Sin fecha")}</div>
                          <div className="inventory-cell-sub">{item.activa ? "Activa" : safeDisplayText(item.cerrada_at ? formatDateTime(item.cerrada_at) : "Cerrada")}</div>
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openOpportunityEditModal(item.id)} type="button">
                            Editar
                          </button>
                          {item.etapa !== "ganada" ? (
                            <button className="link-button" onClick={() => openOpportunityCloseModal(item, "won")} type="button">
                              Ganada
                            </button>
                          ) : null}
                          {item.etapa !== "perdida" ? (
                            <button className="link-button" onClick={() => openOpportunityCloseModal(item, "lost")} type="button">
                              Perdida
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>

                <PaginationControls
                  meta={opportunityMeta}
                  onNext={() => applyOpportunityFilters({ ...opportunityFilters, offset: opportunityMeta.offset + opportunityMeta.limit })}
                  onPrevious={() => applyOpportunityFilters({ ...opportunityFilters, offset: Math.max(0, opportunityMeta.offset - opportunityMeta.limit) })}
                />
              </>
            )}
          </DataCard>
        </div>
      ) : null}

      {activeView === "activities" ? (
        <div className="crm-view-stack">
          <FilterCard
            actions={(
              <div className="inventory-actions">
                <ActionButton icon={<Plus size={16} />} onClick={() => openActivityCreateModal()} size="sm" tone="primary" type="button">
                  Nueva actividad
                </ActionButton>
                <ActionButton onClick={() => applyActivityFilters({ ...activityFilters, offset: 0 })} size="sm" tone="primary" type="button">
                  Aplicar
                </ActionButton>
                <ActionButton onClick={() => applyActivityFilters(defaultActivityFilters)} size="sm" type="button">
                  Limpiar
                </ActionButton>
              </div>
            )}
            title="Filtros de actividades"
          >
            <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
              <SearchInput
                hint="Busca por titulo o descripcion."
                label="Buscar actividad"
                onChange={(event) => setActivityFilters((current) => ({ ...current, q: event.target.value }))}
                onKeyDown={async (event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    await applyActivityFilters({ ...activityFilters, offset: 0 });
                  }
                }}
                placeholder="Actividad, cliente u oportunidad"
                value={activityFilters.q}
              />

              <FormGrid>
                <Field label="Tipo">
                  <select onChange={(event) => setActivityFilters((current) => ({ ...current, tipo: event.target.value }))} value={activityFilters.tipo}>
                    <option value="">Todos</option>
                    {ACTIVITY_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Completada">
                  <select onChange={(event) => setActivityFilters((current) => ({ ...current, completada: event.target.value }))} value={activityFilters.completada}>
                    <option value="false">Pendientes</option>
                    <option value="true">Completadas</option>
                    <option value="">Todas</option>
                  </select>
                </Field>
                <Field label="Activa">
                  <select onChange={(event) => setActivityFilters((current) => ({ ...current, activo: event.target.value }))} value={activityFilters.activo}>
                    <option value="true">Activas</option>
                    <option value="false">Inactivas</option>
                    <option value="">Todas</option>
                  </select>
                </Field>
                <Field label="Vencidas">
                  <select onChange={(event) => setActivityFilters((current) => ({ ...current, vencidas: event.target.value }))} value={activityFilters.vencidas}>
                    <option value="false">Todas</option>
                    <option value="true">Solo vencidas</option>
                  </select>
                </Field>
              </FormGrid>
            </div>
          </FilterCard>

          <DataCard
            actions={<ResultMeta label="actividades" loaded={activities.length} total={activityMeta.total} />}
            subtitle="Seguimiento comercial por cliente, oportunidad y fecha de vencimiento."
            title="Actividades"
          >
            {activities.length === 0 ? (
              <EmptyState note="Programa la primera actividad para empezar el seguimiento." title="No hay actividades registradas" />
            ) : (
              <>
                <DataTable
                  columns={[
                    { key: "actividad", label: "Actividad" },
                    { key: "vinculo", label: "Cliente / oportunidad" },
                    { key: "fecha", label: "Fecha" },
                    { key: "vencimiento", label: "Vencimiento" },
                    { key: "estado", label: "Estado" },
                    { key: "acciones", label: "Acciones" },
                  ]}
                >
                  <tbody>
                    {activities.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.titulo)}</div>
                          <div className="inventory-cell-sub">{activityTypeLabel(item.tipo)}</div>
                        </td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(item.cliente_nombre_comercial, "Sin cliente")}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(item.oportunidad_titulo, "Sin oportunidad")}</div>
                        </td>
                        <td>{formatDateTime(item.fecha_actividad)}</td>
                        <td>{safeDisplayText(item.fecha_vencimiento ? formatDateTime(item.fecha_vencimiento) : "Sin vencimiento")}</td>
                        <td>
                          {item.completada ? (
                            <StatusBadge tone="success">Completada</StatusBadge>
                          ) : isOverdue(item) ? (
                            <StatusBadge tone="danger">Vencida</StatusBadge>
                          ) : (
                            <StatusBadge tone={item.activo ? "warning" : "neutral"}>
                              {item.activo ? "Pendiente" : "Inactiva"}
                            </StatusBadge>
                          )}
                        </td>
                        <td className="inventory-row-actions">
                          <button className="link-button" onClick={() => openActivityEditModal(item)} type="button">
                            Editar
                          </button>
                          {!item.completada ? (
                            <button className="link-button" onClick={() => handleActivityComplete(item)} type="button">
                              Completar
                            </button>
                          ) : null}
                          {item.activo ? (
                            <button className="link-button" onClick={() => handleActivityDeactivate(item)} type="button">
                              Desactivar
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>

                <PaginationControls
                  meta={activityMeta}
                  onNext={() => applyActivityFilters({ ...activityFilters, offset: activityMeta.offset + activityMeta.limit })}
                  onPrevious={() => applyActivityFilters({ ...activityFilters, offset: Math.max(0, activityMeta.offset - activityMeta.limit) })}
                />
              </>
            )}
          </DataCard>
        </div>
      ) : null}

      {activeView === "pipeline" ? (
        <div className="crm-view-stack">
          <DataCard
            actions={<ActionButton icon={<Plus size={16} />} onClick={() => openOpportunityCreateModal()} size="sm" tone="primary" type="button">Nueva oportunidad</ActionButton>}
            subtitle="Vista compacta del pipeline con base en la lista actual de oportunidades."
            title="Pipeline comercial"
          >
            {opportunities.length === 0 ? (
              <EmptyState note="Crea oportunidades para empezar a poblar el pipeline." title="Sin oportunidades para mostrar" />
            ) : (
              <div className="crm-pipeline-grid">
                {pipelineColumns.map((column) => (
                  <section className={`crm-pipeline-column tone-${column.tone}`} key={column.stage}>
                    <header className="crm-pipeline-column-header">
                      <div>
                        <strong>{column.label}</strong>
                        <span>{formatNumber(column.summary.oportunidades_count)} oportunidades</span>
                      </div>
                      <b>{formatMoney(column.summary.monto_total)}</b>
                    </header>

                    <div className="crm-pipeline-cards">
                      {column.items.length === 0 ? (
                        <div className="crm-pipeline-empty">Sin oportunidades</div>
                      ) : (
                        column.items.map((item) => (
                          <article className="crm-pipeline-card" key={item.id}>
                            <div className="crm-pipeline-card-top">
                              <strong>{safeDisplayText(item.titulo)}</strong>
                              <StatusBadge tone={opportunityStageTone(item.etapa)}>
                                {opportunityStageLabel(item.etapa)}
                              </StatusBadge>
                            </div>
                            <p>{safeDisplayText(item.cliente_nombre_comercial, "Sin cliente")}</p>
                            <div className="crm-pipeline-card-meta">
                              <span>{formatMoney(item.monto_estimado)}</span>
                              <span>{formatOpportunityProbability(item.probabilidad)}</span>
                            </div>
                            <div className="crm-pipeline-card-actions">
                              <button className="link-button" onClick={() => openOpportunityEditModal(item.id)} type="button">
                                Editar
                              </button>
                              {item.etapa !== "ganada" ? (
                                <button className="link-button" onClick={() => openOpportunityCloseModal(item, "won")} type="button">
                                  Ganada
                                </button>
                              ) : null}
                              {item.etapa !== "perdida" ? (
                                <button className="link-button" onClick={() => openOpportunityCloseModal(item, "lost")} type="button">
                                  Perdida
                                </button>
                              ) : null}
                            </div>
                          </article>
                        ))
                      )}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </DataCard>
        </div>
      ) : null}

      <ModalShell
        footer={(
          <div className="inventory-actions">
            <ActionButton onClick={() => setClientFormOpen(false)} size="sm" type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} size="sm" tone="primary" type="submit" form="crm-client-form">
              {submitting ? "Guardando..." : "Guardar cliente"}
            </ActionButton>
          </div>
        )}
        onClose={() => setClientFormOpen(false)}
        open={clientFormOpen}
        size="xl"
        subtitle="Datos base del cliente para oportunidades y seguimiento comercial."
        title={clientForm.id ? "Editar cliente" : "Nuevo cliente"}
      >
        <form className="inventory-modal-form" id="crm-client-form" onSubmit={handleClientSubmit}>
          <section className="inventory-form-section">
            <SectionTitle title="Datos generales" />
            <FormGrid>
              <Field label="Nombre comercial">
                <input onChange={(event) => setClientForm((current) => ({ ...current, nombre_comercial: event.target.value }))} required type="text" value={clientForm.nombre_comercial} />
              </Field>
              <Field label="Razon social">
                <input onChange={(event) => setClientForm((current) => ({ ...current, razon_social: event.target.value }))} type="text" value={clientForm.razon_social} />
              </Field>
              <Field label="RFC">
                <input onChange={(event) => setClientForm((current) => ({ ...current, rfc: event.target.value.toUpperCase() }))} type="text" value={clientForm.rfc} />
              </Field>
              <Field label="Tipo">
                <select onChange={(event) => setClientForm((current) => ({ ...current, tipo: event.target.value }))} value={clientForm.tipo}>
                  {CLIENT_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Estatus">
                <select onChange={(event) => setClientForm((current) => ({ ...current, estatus: event.target.value }))} value={clientForm.estatus}>
                  {CLIENT_STATUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Origen">
                <input onChange={(event) => setClientForm((current) => ({ ...current, origen: event.target.value }))} type="text" value={clientForm.origen} />
              </Field>
              <Field label="Industria">
                <input onChange={(event) => setClientForm((current) => ({ ...current, industria: event.target.value }))} type="text" value={clientForm.industria} />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle title="Contacto" />
            <FormGrid>
              <Field label="Email">
                <input onChange={(event) => setClientForm((current) => ({ ...current, email: event.target.value }))} type="email" value={clientForm.email} />
              </Field>
              <Field label="Telefono">
                <input onChange={(event) => setClientForm((current) => ({ ...current, telefono: event.target.value }))} type="text" value={clientForm.telefono} />
              </Field>
              <Field label="Sitio web" span={2}>
                <input onChange={(event) => setClientForm((current) => ({ ...current, sitio_web: event.target.value }))} type="text" value={clientForm.sitio_web} />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle title="Direccion" />
            <FormGrid>
              <Field label="Direccion" span={2}>
                <textarea onChange={(event) => setClientForm((current) => ({ ...current, direccion: event.target.value }))} rows={3} value={clientForm.direccion} />
              </Field>
              <Field label="Ciudad">
                <input onChange={(event) => setClientForm((current) => ({ ...current, ciudad: event.target.value }))} type="text" value={clientForm.ciudad} />
              </Field>
              <Field label="Estado">
                <input onChange={(event) => setClientForm((current) => ({ ...current, estado: event.target.value }))} type="text" value={clientForm.estado} />
              </Field>
              <Field label="Pais">
                <input onChange={(event) => setClientForm((current) => ({ ...current, pais: event.target.value }))} type="text" value={clientForm.pais} />
              </Field>
              <Field label="Codigo postal">
                <input onChange={(event) => setClientForm((current) => ({ ...current, codigo_postal: normalizeIntegerInput(event.target.value).slice(0, 5) }))} type="text" value={clientForm.codigo_postal} />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle title="Notas" />
            <FormGrid columns={1}>
              <Field label="Notas">
                <textarea onChange={(event) => setClientForm((current) => ({ ...current, notas: event.target.value }))} rows={4} value={clientForm.notas} />
              </Field>
            </FormGrid>
          </section>
        </form>
      </ModalShell>

      <ModalShell
        onClose={closeClientDetailModal}
        open={clientDetailOpen}
        size="xl"
        subtitle="Resumen comercial del cliente con contactos, oportunidades y actividades recientes."
        title="Detalle de cliente"
      >
        {detailLoading ? (
          <div className="screen-center">Cargando detalle...</div>
        ) : clientDetail ? (
          <div className="inventory-modal-form">
            <section className="inventory-form-section">
              <SectionTitle
                actions={(
                  <div className="inventory-actions">
                    <ActionButton onClick={() => openContactCreateModal(clientDetail.id)} size="sm" type="button">
                      Nuevo contacto
                    </ActionButton>
                    <ActionButton onClick={() => openOpportunityCreateModal(clientDetail.id)} size="sm" tone="primary" type="button">
                      Nueva oportunidad
                    </ActionButton>
                  </div>
                )}
                title={clientDisplayName(clientDetail)}
              />
              <div className="inventory-detail-grid">
                <p><strong>Razon social:</strong> {safeDisplayText(clientDetail.razon_social, "Sin razon social")}</p>
                <p><strong>RFC:</strong> {safeDisplayText(clientDetail.rfc, "Sin RFC")}</p>
                <p><strong>Tipo:</strong> {clientTypeLabel(clientDetail.tipo)}</p>
                <p><strong>Estatus:</strong> {safeDisplayText(clientDetail.estatus, "Sin estatus")}</p>
                <p><strong>Email:</strong> {safeDisplayText(clientDetail.email, "Sin email")}</p>
                <p><strong>Telefono:</strong> {safeDisplayText(clientDetail.telefono, "Sin telefono")}</p>
                <p><strong>Industria:</strong> {safeDisplayText(clientDetail.industria, "Sin industria")}</p>
                <p><strong>Origen:</strong> {safeDisplayText(clientDetail.origen, "Sin origen")}</p>
                <p className="inventory-form-span-2"><strong>Direccion:</strong> {safeDisplayText(clientDetail.direccion, "Sin direccion")}</p>
                <p className="inventory-form-span-2"><strong>Notas:</strong> {safeDisplayText(clientDetail.notas, "Sin notas")}</p>
              </div>
            </section>

            <DataCard
              subtitle="Ventas POS, proyectos, pipeline, facturacion pendiente y ultima actividad."
              title="Resumen comercial"
            >
              <div className="crm-stage-summary-grid">
                {clientCommercialMetrics.map((metric) => (
                  <article className={`crm-stage-summary-card tone-${metric.tone}`} key={metric.key}>
                    <div>
                      <strong>{metric.label}</strong>
                      <span>{metric.meta}</span>
                    </div>
                    <b>{metric.value}</b>
                  </article>
                ))}
              </div>
            </DataCard>

            <section className="crm-summary-grid">
              <DataCard subtitle="Hasta 5 contactos para este cliente." title="Contactos">
                {clientDetailContacts.length === 0 ? (
                  <EmptyState compact note="Crea un contacto comercial para empezar." title="Sin contactos" />
                ) : (
                  <DataTable
                    columns={[
                      { key: "nombre", label: "Nombre" },
                      { key: "puesto", label: "Puesto" },
                      { key: "email", label: "Email" },
                      { key: "telefono", label: "Telefono" },
                    ]}
                  >
                    <tbody>
                      {clientDetailContacts.map((contact) => (
                        <tr key={contact.id}>
                          <td>{safeDisplayText(contact.nombre)}</td>
                          <td>{safeDisplayText(contact.puesto, "Sin puesto")}</td>
                          <td>{safeDisplayText(contact.email, "Sin email")}</td>
                          <td>{safeDisplayText(contact.telefono || contact.whatsapp, "Sin telefono")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </DataTable>
                )}
              </DataCard>

              <DataCard subtitle="Hasta 5 oportunidades ligadas al cliente." title="Oportunidades">
                {clientDetailOpportunities.length === 0 ? (
                  <EmptyState compact note="Aun no hay oportunidades para este cliente." title="Sin oportunidades" />
                ) : (
                  <DataTable
                    columns={[
                      { key: "titulo", label: "Titulo" },
                      { key: "etapa", label: "Etapa" },
                      { key: "monto", label: "Monto" },
                      { key: "cierre", label: "Cierre" },
                    ]}
                  >
                    <tbody>
                      {clientDetailOpportunities.map((opportunity) => (
                        <tr key={opportunity.id}>
                          <td>{safeDisplayText(opportunity.titulo)}</td>
                          <td>
                            <StatusBadge tone={opportunityStageTone(opportunity.etapa)}>
                              {opportunityStageLabel(opportunity.etapa)}
                            </StatusBadge>
                          </td>
                          <td>{formatMoney(opportunity.monto_estimado)}</td>
                          <td>{safeDisplayText(opportunity.fecha_estimada_cierre ? formatDate(opportunity.fecha_estimada_cierre) : "Sin fecha")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </DataTable>
                )}
              </DataCard>
            </section>

            <DataCard
              subtitle="Eventos operativos relacionados con ventas POS, proyectos, oportunidades, actividades y solicitudes de factura."
              title="Timeline comercial"
            >
              {clientDetailTimeline.length === 0 ? (
                <EmptyState compact note="No hay actividad comercial registrada." title="Sin timeline comercial" />
              ) : (
                <div className="crm-timeline-list">
                  {clientDetailTimeline.map((item) => (
                    <article className="crm-timeline-item" key={`${item.tipo}-${item.referencia_id}-${item.fecha}`}>
                      <div className="crm-timeline-item-top">
                        <div className="crm-timeline-item-headings">
                          <div className="crm-timeline-badges">
                            <StatusBadge tone={timelineTypeTone(item.tipo)}>{timelineTypeLabel(item.tipo)}</StatusBadge>
                            <StatusBadge tone={timelineStatusTone(item)}>{timelineStatusLabel(item)}</StatusBadge>
                          </div>
                          <strong>{safeDisplayText(item.titulo, "Sin titulo")}</strong>
                        </div>
                        <div className="crm-timeline-item-meta">
                          <span>{formatDateTime(item.fecha)}</span>
                          {item.monto !== null && item.monto !== undefined ? <b>{formatMoney(item.monto)}</b> : null}
                        </div>
                      </div>
                      <p>{safeDisplayText(item.descripcion, "Sin descripcion adicional")}</p>
                    </article>
                  ))}
                </div>
              )}
            </DataCard>

            <DataCard subtitle="Hasta 5 actividades recientes del cliente." title="Actividades">
              {clientDetailActivities.length === 0 ? (
                <EmptyState compact note="No hay actividades relacionadas todavia." title="Sin actividades" />
              ) : (
                <DataTable
                  columns={[
                    { key: "titulo", label: "Actividad" },
                    { key: "tipo", label: "Tipo" },
                    { key: "fecha", label: "Fecha" },
                    { key: "estado", label: "Estado" },
                  ]}
                >
                  <tbody>
                    {clientDetailActivities.map((activity) => (
                      <tr key={activity.id}>
                        <td>{safeDisplayText(activity.titulo)}</td>
                        <td>{activityTypeLabel(activity.tipo)}</td>
                        <td>{formatDateTime(activity.fecha_actividad)}</td>
                        <td>
                          {activity.completada ? (
                            <StatusBadge tone="success">Completada</StatusBadge>
                          ) : isOverdue(activity) ? (
                            <StatusBadge tone="danger">Vencida</StatusBadge>
                          ) : (
                            <StatusBadge tone="warning">Pendiente</StatusBadge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </DataCard>
          </div>
        ) : (
          <EmptyState note="No se encontro informacion del cliente." title="Sin detalle disponible" />
        )}
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions">
            <ActionButton onClick={() => setContactFormOpen(false)} size="sm" type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="crm-contact-form" size="sm" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Guardar contacto"}
            </ActionButton>
          </div>
        )}
        onClose={() => setContactFormOpen(false)}
        open={contactFormOpen}
        size="lg"
        subtitle="Contacto operativo vinculado a un cliente del CRM."
        title={contactForm.id ? "Editar contacto" : "Nuevo contacto"}
      >
        <form className="inventory-modal-form" id="crm-contact-form" onSubmit={handleContactSubmit}>
          <section className="inventory-form-section">
            <SectionTitle title="Contacto" />
            <FormGrid>
              <Field label="Cliente">
                <select
                  onChange={async (event) => {
                    const nextClientId = event.target.value;
                    setContactForm((current) => ({ ...current, client_id: nextClientId }));
                    await loadClientContactOptions(nextClientId);
                  }}
                  value={contactForm.client_id}
                >
                  <option value="">Selecciona un cliente</option>
                  {clientOptions.map((client) => (
                    <option key={client.id} value={client.id}>
                      {clientDisplayName(client)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Nombre">
                <input onChange={(event) => setContactForm((current) => ({ ...current, nombre: event.target.value }))} required type="text" value={contactForm.nombre} />
              </Field>
              <Field label="Puesto">
                <input onChange={(event) => setContactForm((current) => ({ ...current, puesto: event.target.value }))} type="text" value={contactForm.puesto} />
              </Field>
              <Field label="Email">
                <input onChange={(event) => setContactForm((current) => ({ ...current, email: event.target.value }))} type="email" value={contactForm.email} />
              </Field>
              <Field label="Telefono">
                <input onChange={(event) => setContactForm((current) => ({ ...current, telefono: event.target.value }))} type="text" value={contactForm.telefono} />
              </Field>
              <Field label="WhatsApp">
                <input onChange={(event) => setContactForm((current) => ({ ...current, whatsapp: event.target.value }))} type="text" value={contactForm.whatsapp} />
              </Field>
              <Field label="Notas" span={2}>
                <textarea onChange={(event) => setContactForm((current) => ({ ...current, notas: event.target.value }))} rows={4} value={contactForm.notas} />
              </Field>
            </FormGrid>
            <label className="crm-checkbox-row">
              <input checked={contactForm.principal} onChange={(event) => setContactForm((current) => ({ ...current, principal: event.target.checked }))} type="checkbox" />
              <span>Marcar como contacto principal</span>
            </label>
            <label className="crm-checkbox-row">
              <input checked={contactForm.activo} onChange={(event) => setContactForm((current) => ({ ...current, activo: event.target.checked }))} type="checkbox" />
              <span>Contacto activo</span>
            </label>
          </section>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions">
            <ActionButton onClick={() => setOpportunityFormOpen(false)} size="sm" type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="crm-opportunity-form" size="sm" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Guardar oportunidad"}
            </ActionButton>
          </div>
        )}
        onClose={() => setOpportunityFormOpen(false)}
        open={opportunityFormOpen}
        size="xl"
        subtitle="Registra monto estimado, etapa y probabilidad para alimentar el pipeline."
        title={opportunityForm.id ? "Editar oportunidad" : "Nueva oportunidad"}
      >
        <form className="inventory-modal-form" id="crm-opportunity-form" onSubmit={handleOpportunitySubmit}>
          <section className="inventory-form-section">
            <SectionTitle title="Oportunidad" />
            <FormGrid>
              <Field label="Cliente">
                <select
                  onChange={async (event) => {
                    const nextClientId = event.target.value;
                    setOpportunityForm((current) => ({
                      ...current,
                      cliente_id: nextClientId,
                      contacto_id: "",
                    }));
                    await loadClientContactOptions(nextClientId);
                  }}
                  value={opportunityForm.cliente_id}
                >
                  <option value="">Selecciona un cliente</option>
                  {clientOptions.map((client) => (
                    <option key={client.id} value={client.id}>
                      {clientDisplayName(client)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Contacto">
                <select onChange={(event) => setOpportunityForm((current) => ({ ...current, contacto_id: event.target.value }))} value={opportunityForm.contacto_id}>
                  <option value="">Sin contacto</option>
                  {currentOpportunityContacts.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {contactDisplayName(contact)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Titulo" span={2}>
                <input onChange={(event) => setOpportunityForm((current) => ({ ...current, titulo: event.target.value }))} required type="text" value={opportunityForm.titulo} />
              </Field>
              <Field label="Descripcion" span={2}>
                <textarea onChange={(event) => setOpportunityForm((current) => ({ ...current, descripcion: event.target.value }))} rows={3} value={opportunityForm.descripcion} />
              </Field>
              <Field label="Etapa">
                <select onChange={(event) => setOpportunityForm((current) => ({ ...current, etapa: event.target.value }))} value={opportunityForm.etapa}>
                  {OPPORTUNITY_STAGE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Origen">
                <input onChange={(event) => setOpportunityForm((current) => ({ ...current, origen: event.target.value }))} type="text" value={opportunityForm.origen} />
              </Field>
              <Field label="Monto estimado">
                <input onChange={(event) => setOpportunityForm((current) => ({ ...current, monto_estimado: normalizeDecimalInput(event.target.value) }))} type="text" value={opportunityForm.monto_estimado} />
              </Field>
              <Field label="Probabilidad">
                <input onChange={(event) => setOpportunityForm((current) => ({ ...current, probabilidad: normalizeIntegerInput(event.target.value).slice(0, 3) }))} type="text" value={opportunityForm.probabilidad} />
              </Field>
              <Field label="Fecha estimada de cierre">
                <input onChange={(event) => setOpportunityForm((current) => ({ ...current, fecha_estimada_cierre: event.target.value }))} type="date" value={opportunityForm.fecha_estimada_cierre} />
              </Field>
              <Field label="Notas" span={2}>
                <textarea onChange={(event) => setOpportunityForm((current) => ({ ...current, notas: event.target.value }))} rows={4} value={opportunityForm.notas} />
              </Field>
            </FormGrid>
            <label className="crm-checkbox-row">
              <input checked={opportunityForm.activa} onChange={(event) => setOpportunityForm((current) => ({ ...current, activa: event.target.checked }))} type="checkbox" />
              <span>Oportunidad activa</span>
            </label>
          </section>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions">
            <ActionButton onClick={() => setOpportunityCloseOpen(false)} size="sm" type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="crm-opportunity-close-form" size="sm" tone={opportunityCloseForm.mode === "won" ? "primary" : "ghost"} type="submit">
              {opportunityCloseForm.mode === "won" ? "Cerrar como ganada" : "Cerrar como perdida"}
            </ActionButton>
          </div>
        )}
        onClose={() => setOpportunityCloseOpen(false)}
        open={opportunityCloseOpen}
        size="md"
        subtitle="Actualiza la etapa final sin salir del pipeline."
        title={opportunityCloseForm.mode === "won" ? "Cerrar oportunidad ganada" : "Cerrar oportunidad perdida"}
      >
        <form className="inventory-modal-form" id="crm-opportunity-close-form" onSubmit={handleOpportunityCloseSubmit}>
          <section className="inventory-form-section">
            <SectionTitle title={safeDisplayText(opportunityCloseForm.titulo, "Oportunidad")} />
            <FormGrid columns={1}>
              {opportunityCloseForm.mode === "lost" ? (
                <Field label="Motivo de perdida">
                  <textarea
                    onChange={(event) => setOpportunityCloseForm((current) => ({ ...current, motivo_perdida: event.target.value }))}
                    required
                    rows={3}
                    value={opportunityCloseForm.motivo_perdida}
                  />
                </Field>
              ) : null}
              <Field label="Notas">
                <textarea onChange={(event) => setOpportunityCloseForm((current) => ({ ...current, notas: event.target.value }))} rows={4} value={opportunityCloseForm.notas} />
              </Field>
            </FormGrid>
          </section>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions">
            <ActionButton onClick={() => setActivityFormOpen(false)} size="sm" type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="crm-activity-form" size="sm" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Guardar actividad"}
            </ActionButton>
          </div>
        )}
        onClose={() => setActivityFormOpen(false)}
        open={activityFormOpen}
        size="xl"
        subtitle="Seguimiento operativo por cliente, oportunidad y fecha de vencimiento."
        title={activityForm.id ? "Editar actividad" : "Nueva actividad"}
      >
        <form className="inventory-modal-form" id="crm-activity-form" onSubmit={handleActivitySubmit}>
          <section className="inventory-form-section">
            <SectionTitle title="Actividad" />
            <FormGrid>
              <Field label="Cliente">
                <select
                  onChange={async (event) => {
                    const nextClientId = event.target.value;
                    setActivityForm((current) => ({
                      ...current,
                      cliente_id: nextClientId,
                      oportunidad_id: "",
                      contacto_id: "",
                    }));
                    await loadClientContactOptions(nextClientId);
                  }}
                  value={activityForm.cliente_id}
                >
                  <option value="">Sin cliente</option>
                  {clientOptions.map((client) => (
                    <option key={client.id} value={client.id}>
                      {clientDisplayName(client)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Oportunidad">
                <select
                  onChange={async (event) => {
                    const nextOpportunityId = event.target.value;
                    const selectedOpportunity = opportunityOptions.find((item) => item.id === nextOpportunityId);
                    setActivityForm((current) => ({
                      ...current,
                      oportunidad_id: nextOpportunityId,
                      cliente_id: selectedOpportunity?.cliente_id || current.cliente_id,
                    }));
                    if (selectedOpportunity?.cliente_id) {
                      await loadClientContactOptions(selectedOpportunity.cliente_id);
                    }
                  }}
                  value={activityForm.oportunidad_id}
                >
                  <option value="">Sin oportunidad</option>
                  {currentActivityOpportunities.map((opportunity) => (
                    <option key={opportunity.id} value={opportunity.id}>
                      {opportunity.titulo}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Contacto">
                <select onChange={(event) => setActivityForm((current) => ({ ...current, contacto_id: event.target.value }))} value={activityForm.contacto_id}>
                  <option value="">Sin contacto</option>
                  {currentActivityContacts.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {contactDisplayName(contact)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Tipo">
                <select onChange={(event) => setActivityForm((current) => ({ ...current, tipo: event.target.value }))} value={activityForm.tipo}>
                  {ACTIVITY_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Titulo" span={2}>
                <input onChange={(event) => setActivityForm((current) => ({ ...current, titulo: event.target.value }))} required type="text" value={activityForm.titulo} />
              </Field>
              <Field label="Descripcion" span={2}>
                <textarea onChange={(event) => setActivityForm((current) => ({ ...current, descripcion: event.target.value }))} rows={3} value={activityForm.descripcion} />
              </Field>
              <Field label="Fecha de actividad">
                <input onChange={(event) => setActivityForm((current) => ({ ...current, fecha_actividad: event.target.value }))} required type="datetime-local" value={activityForm.fecha_actividad} />
              </Field>
              <Field label="Fecha de vencimiento">
                <input onChange={(event) => setActivityForm((current) => ({ ...current, fecha_vencimiento: event.target.value }))} type="datetime-local" value={activityForm.fecha_vencimiento} />
              </Field>
            </FormGrid>
            <label className="crm-checkbox-row">
              <input checked={activityForm.completada} onChange={(event) => setActivityForm((current) => ({ ...current, completada: event.target.checked }))} type="checkbox" />
              <span>Marcar como completada</span>
            </label>
            <label className="crm-checkbox-row">
              <input checked={activityForm.activo} onChange={(event) => setActivityForm((current) => ({ ...current, activo: event.target.checked }))} type="checkbox" />
              <span>Actividad activa</span>
            </label>
          </section>
        </form>
      </ModalShell>
    </div>
  );
}
