import { useEffect, useState } from "react";
import { Calendar, Flag, Folder, Gauge, Plus, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  createPmProject,
  deactivatePmProject,
  listPmProjects,
  updatePmProject,
} from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  ActionButton,
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
  StatusBadge,
  formatDate,
  formatMoney,
  safeDisplayText,
  DEFAULT_PAGE_SIZE,
} from "../inventory/shared";
import {
  formatPercent,
  getPriorityLabel,
  getPriorityTone,
  getProjectStatusLabel,
  getProjectStatusTone,
  priorityOptions,
  projectStatusOptions,
} from "./shared";


const defaultProjectForm = {
  nombre: "",
  codigo: "",
  descripcion: "",
  tipo_proyecto: "",
  estatus: "borrador",
  prioridad: "media",
  fecha_inicio: "",
  fecha_fin_planificada: "",
  fecha_fin_real: "",
  porcentaje_avance: "0",
  responsable_nombre_snapshot: "",
  cliente_nombre_snapshot: "",
  presupuesto_estimado: "0",
  activo: true,
};

const defaultFilters = {
  q: "",
  estatus: "",
  prioridad: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


function projectToForm(project) {
  if (!project) {
    return defaultProjectForm;
  }

  return {
    nombre: project.nombre ?? "",
    codigo: project.codigo ?? "",
    descripcion: project.descripcion ?? "",
    tipo_proyecto: project.tipo_proyecto ?? "",
    estatus: project.estatus ?? "borrador",
    prioridad: project.prioridad ?? "media",
    fecha_inicio: project.fecha_inicio ?? "",
    fecha_fin_planificada: project.fecha_fin_planificada ?? "",
    fecha_fin_real: project.fecha_fin_real ?? "",
    porcentaje_avance: project.porcentaje_avance ?? "0",
    responsable_nombre_snapshot: project.responsable_nombre_snapshot ?? "",
    cliente_nombre_snapshot: project.cliente_nombre_snapshot ?? "",
    presupuesto_estimado: project.presupuesto_estimado ?? "0",
    activo: Boolean(project.activo),
  };
}


function toProjectPayload(form) {
  return {
    nombre: form.nombre.trim(),
    codigo: form.codigo.trim() || null,
    descripcion: form.descripcion.trim() || null,
    tipo_proyecto: form.tipo_proyecto.trim() || null,
    estatus: form.estatus,
    prioridad: form.prioridad,
    fecha_inicio: form.fecha_inicio || null,
    fecha_fin_planificada: form.fecha_fin_planificada || null,
    fecha_fin_real: form.fecha_fin_real || null,
    porcentaje_avance: Number(form.porcentaje_avance || 0),
    responsable_nombre_snapshot: form.responsable_nombre_snapshot.trim() || null,
    cliente_nombre_snapshot: form.cliente_nombre_snapshot.trim() || null,
    presupuesto_estimado: Number(form.presupuesto_estimado || 0),
    activo: Boolean(form.activo),
  };
}


export default function PMProjectsPage() {
  const navigate = useNavigate();
  const { empresaId, token } = useAuth();
  const [filters, setFilters] = useState(defaultFilters);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [projects, setProjects] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [projectForm, setProjectForm] = useState(defaultProjectForm);

  async function loadProjects(nextFilters = filters) {
    setLoading(true);
    setError("");
    try {
      const response = await listPmProjects({ token, empresaId, filters: nextFilters });
      setProjects(response.items ?? []);
      setMeta({
        total: response.total ?? 0,
        limit: response.limit ?? nextFilters.limit,
        offset: response.offset ?? nextFilters.offset,
      });
    } catch (requestError) {
      setError(requestError.message || "No se pudieron cargar los proyectos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token || !empresaId) {
      return;
    }
    loadProjects(filters);
  }, [token, empresaId]);

  function resetFeedback() {
    setError("");
    setSuccess("");
  }

  function openCreateModal() {
    resetFeedback();
    setEditingProject(null);
    setProjectForm(defaultProjectForm);
    setModalOpen(true);
  }

  function openEditModal(project) {
    resetFeedback();
    setEditingProject(project);
    setProjectForm(projectToForm(project));
    setModalOpen(true);
  }

  function closeModal() {
    if (saving) {
      return;
    }
    setModalOpen(false);
    setEditingProject(null);
    setProjectForm(defaultProjectForm);
  }

  async function handleFilterSubmit(event) {
    event.preventDefault();
    const nextFilters = { ...filters, offset: 0 };
    setFilters(nextFilters);
    await loadProjects(nextFilters);
  }

  async function handleSaveProject(event) {
    event.preventDefault();
    setSaving(true);
    resetFeedback();
    try {
      const payload = toProjectPayload(projectForm);
      if (editingProject?.id) {
        await updatePmProject({ projectId: editingProject.id, token, empresaId, payload });
        setSuccess("Proyecto actualizado.");
      } else {
        await createPmProject({ token, empresaId, payload });
        setSuccess("Proyecto creado.");
      }
      closeModal();
      await loadProjects(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el proyecto.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateProject(project) {
    setSaving(true);
    resetFeedback();
    try {
      await deactivatePmProject({ projectId: project.id, token, empresaId });
      setSuccess("Proyecto desactivado.");
      await loadProjects(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar el proyecto.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePaginate(direction) {
    const nextOffset =
      direction === "next"
        ? filters.offset + filters.limit
        : Math.max(0, filters.offset - filters.limit);
    const nextFilters = { ...filters, offset: nextOffset };
    setFilters(nextFilters);
    await loadProjects(nextFilters);
  }

  const activeProjects = projects.filter((item) => item.estatus === "activo").length;
  const lateProjects = projects.filter((item) => item.task_stats?.vencidas > 0).length;

  return (
    <div className="inventory-shell inventory-screen pm-screen">
      <PageHeader
        eyebrow="PM Core"
        title="Proyectos"
        subtitle="Portafolio base de proyectos, responsables y avance operativo."
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={() => navigate("/pm")} type="button">
              Dashboard PM
            </ActionButton>
            <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateModal} tone="primary" type="button">
              Nuevo proyecto
            </ActionButton>
          </div>
        }
      />

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard icon={<Folder size={18} strokeWidth={1.9} />} label="Proyectos cargados" meta="Pagina actual" tone="info" value={projects.length} />
        <MetricCard icon={<Folder size={18} strokeWidth={1.9} />} label="Activos" meta="Estatus activo" tone="success" value={activeProjects} />
        <MetricCard icon={<Calendar size={18} strokeWidth={1.9} />} label="Con tareas vencidas" meta="Alerta operativa" tone="warning" value={lateProjects} />
        <MetricCard icon={<Gauge size={18} strokeWidth={1.9} />} label="Total listado" meta="Segun filtros" tone="neutral" value={meta.total} />
      </section>

      <FilterCard title="Filtros" subtitle="Búsqueda y clasificación de proyectos.">
        <form className="inventory-filter-toolbar" onSubmit={handleFilterSubmit}>
          <div className="inventory-toolbar-grid">
            <SearchInput
              action={
                <ActionButton icon={<Search size={16} strokeWidth={1.9} />} size="sm" tone="primary" type="submit">
                  Buscar
                </ActionButton>
              }
              hint="Busca por nombre, código, descripción o cliente."
              label="Buscar"
              onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
              placeholder="Buscar proyectos..."
              value={filters.q}
            />
            <Field label="Estatus">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, estatus: event.target.value }))}
                value={filters.estatus}
              >
                <option value="">Todos</option>
                {projectStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Prioridad">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, prioridad: event.target.value }))}
                value={filters.prioridad}
              >
                <option value="">Todas</option>
                {priorityOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <div className="inventory-actions inventory-actions-end">
              <ActionButton
                onClick={() => {
                  setFilters(defaultFilters);
                  loadProjects(defaultFilters);
                }}
                size="sm"
                type="button"
              >
                Limpiar
              </ActionButton>
              <ActionButton onClick={() => loadProjects(filters)} size="sm" type="button">
                Actualizar
              </ActionButton>
            </div>
          </div>
        </form>
      </FilterCard>

      <DataCard subtitle="Listado operativo de proyectos activos o históricos." title="Portafolio">
        <ResultMeta label="proyectos" loaded={projects.length} total={meta.total} />
        {loading ? (
          <div className="table-note">Cargando proyectos...</div>
        ) : projects.length === 0 ? (
          <EmptyState
            action={
              <ActionButton onClick={openCreateModal} tone="primary" type="button">
                Crear primer proyecto
              </ActionButton>
            }
            note="Los proyectos PM viven fuera del placeholder de Inventario > Proyectos."
            title="No hay proyectos cargados"
          />
        ) : (
          <>
            <DataTable columns={["Proyecto", "Estatus", "Prioridad", "Responsable", "Avance", "Fin planificada", "Acciones"]}>
              <tbody>
                {projects.map((project) => (
                  <tr key={project.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(project.nombre)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(project.codigo, "Sin código")}</div>
                    </td>
                    <td>
                      <StatusBadge tone={getProjectStatusTone(project.estatus)}>{getProjectStatusLabel(project.estatus)}</StatusBadge>
                    </td>
                    <td>
                      <StatusBadge tone={getPriorityTone(project.prioridad)}>{getPriorityLabel(project.prioridad)}</StatusBadge>
                    </td>
                    <td>{safeDisplayText(project.responsable_nombre_snapshot, "Sin responsable")}</td>
                    <td>
                      <div className="inventory-cell-main">{formatPercent(project.porcentaje_avance)}</div>
                      <div className="inventory-cell-sub">
                        {project.task_stats?.completadas ?? 0}/{project.task_stats?.total ?? 0} tareas
                      </div>
                    </td>
                    <td>{safeDisplayText(formatDate(project.fecha_fin_planificada), "-")}</td>
                    <td>
                      <div className="inventory-actions">
                        <ActionButton onClick={() => navigate(`/pm/projects/${project.id}`)} size="sm" tone="primary" type="button">
                          Abrir
                        </ActionButton>
                        <ActionButton onClick={() => openEditModal(project)} size="sm" type="button">
                          Editar
                        </ActionButton>
                        <ActionButton
                          icon={<Flag size={14} strokeWidth={1.9} />}
                          onClick={() => handleDeactivateProject(project)}
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
            <PaginationControls
              meta={meta}
              onNext={() => handlePaginate("next")}
              onPrevious={() => handlePaginate("previous")}
            />
          </>
        )}
      </DataCard>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-project-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingProject ? "Guardar proyecto" : "Crear proyecto"}
            </ActionButton>
          </div>
        }
        onClose={closeModal}
        open={modalOpen}
        size="wide"
        subtitle="Base operativa para proyectos, tareas, miembros y comentarios."
        title={editingProject ? "Editar proyecto" : "Nuevo proyecto"}
      >
        <form className="inventory-modal-form" id="pm-project-form" onSubmit={handleSaveProject}>
          <FormGrid>
            <Field label="Nombre">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, nombre: event.target.value }))}
                required
                type="text"
                value={projectForm.nombre}
              />
            </Field>
            <Field label="Código">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, codigo: event.target.value }))}
                type="text"
                value={projectForm.codigo}
              />
            </Field>
            <Field label="Estatus">
              <select
                onChange={(event) => setProjectForm((current) => ({ ...current, estatus: event.target.value }))}
                value={projectForm.estatus}
              >
                {projectStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Prioridad">
              <select
                onChange={(event) => setProjectForm((current) => ({ ...current, prioridad: event.target.value }))}
                value={projectForm.prioridad}
              >
                {priorityOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tipo de proyecto">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, tipo_proyecto: event.target.value }))}
                type="text"
                value={projectForm.tipo_proyecto}
              />
            </Field>
            <Field label="Responsable">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, responsable_nombre_snapshot: event.target.value }))}
                type="text"
                value={projectForm.responsable_nombre_snapshot}
              />
            </Field>
            <Field label="Cliente">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, cliente_nombre_snapshot: event.target.value }))}
                type="text"
                value={projectForm.cliente_nombre_snapshot}
              />
            </Field>
            <Field label="Presupuesto estimado">
              <input
                min="0"
                onChange={(event) => setProjectForm((current) => ({ ...current, presupuesto_estimado: event.target.value }))}
                step="0.01"
                type="number"
                value={projectForm.presupuesto_estimado}
              />
            </Field>
            <Field label="Fecha inicio">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, fecha_inicio: event.target.value }))}
                type="date"
                value={projectForm.fecha_inicio}
              />
            </Field>
            <Field label="Fecha fin planificada">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, fecha_fin_planificada: event.target.value }))}
                type="date"
                value={projectForm.fecha_fin_planificada}
              />
            </Field>
            <Field label="Fecha fin real">
              <input
                onChange={(event) => setProjectForm((current) => ({ ...current, fecha_fin_real: event.target.value }))}
                type="date"
                value={projectForm.fecha_fin_real}
              />
            </Field>
            <Field hint="Si el proyecto ya tiene tareas activas, el backend recalcula este valor." label="Avance manual (%)">
              <input
                max="100"
                min="0"
                onChange={(event) => setProjectForm((current) => ({ ...current, porcentaje_avance: event.target.value }))}
                step="1"
                type="number"
                value={projectForm.porcentaje_avance}
              />
            </Field>
            <Field label="Descripción" span={2}>
              <textarea
                onChange={(event) => setProjectForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={5}
                value={projectForm.descripcion}
              />
            </Field>
          </FormGrid>
          <div className="inventory-form-note">
            <strong>Presupuesto</strong>
            <p className="table-note">Presupuesto estimado actual: {formatMoney(projectForm.presupuesto_estimado || 0)}</p>
          </div>
        </form>
      </ModalShell>
    </div>
  );
}
