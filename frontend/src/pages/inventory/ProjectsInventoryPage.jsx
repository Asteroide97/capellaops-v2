import { useEffect, useState } from "react";
import { FolderKanban, PackageMinus, ScrollText } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import {
  getInventoryProjectMaterials,
  getInventoryProjectMovements,
  getInventoryProjects,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  MetricCard,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  StatusBadge,
  formatDateTime,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "./shared";


const defaultFilters = {
  q: "",
  limit: 25,
  offset: 0,
};


function getProjectStatusTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "activo") {
    return "success";
  }
  if (normalized === "en_pausa") {
    return "warning";
  }
  if (normalized === "cancelado") {
    return "danger";
  }
  return "neutral";
}


function getMovementLabel(movement) {
  if (movement.referencia_tipo === "DEVOLUCION_PROYECTO") {
    return "Devolución";
  }
  return "Consumo";
}


export default function ProjectsInventoryPage() {
  const navigate = useNavigate();
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [projects, setProjects] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: 25, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [selectedProject, setSelectedProject] = useState(null);
  const [projectMaterials, setProjectMaterials] = useState([]);
  const [projectMovements, setProjectMovements] = useState([]);

  async function loadProjects(nextFilters = filters) {
    const response = await getInventoryProjects({ token, empresaId, filters: nextFilters });
    setProjects(response.items ?? []);
    setMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    return response.items ?? [];
  }

  async function loadProjectDetail(projectId) {
    if (!projectId) {
      setProjectMaterials([]);
      setProjectMovements([]);
      return;
    }
    setDetailLoading(true);
    setError("");
    try {
      const [materialsResponse, movementsResponse] = await Promise.all([
        getInventoryProjectMaterials({ projectId, token, empresaId }),
        getInventoryProjectMovements({ projectId, token, empresaId, filters: { limit: 100, offset: 0 } }),
      ]);
      setProjectMaterials(materialsResponse.items ?? []);
      setProjectMovements(movementsResponse.items ?? []);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle del proyecto.");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }
      setLoading(true);
      setError("");
      try {
        const items = await loadProjects(defaultFilters);
        const firstProject = items[0] ?? null;
        setSelectedProject(firstProject);
        if (firstProject?.project_id) {
          await loadProjectDetail(firstProject.project_id);
        }
      } catch (requestError) {
        setError(requestError.message || "No se pudo cargar el inventario por proyecto.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  async function handleApplyFilters() {
    setLoading(true);
    setError("");
    try {
      const nextFilters = { ...filters, offset: 0 };
      const items = await loadProjects(nextFilters);
      setFilters(nextFilters);
      const nextSelected =
        items.find((item) => item.project_id === selectedProject?.project_id) ??
        items[0] ??
        null;
      setSelectedProject(nextSelected);
      await loadProjectDetail(nextSelected?.project_id ?? "");
    } catch (requestError) {
      setError(requestError.message || "No se pudo aplicar el filtro.");
    } finally {
      setLoading(false);
    }
  }

  async function handlePageChange(nextOffset) {
    const nextFilters = { ...filters, offset: nextOffset };
    setLoading(true);
    setError("");
    try {
      const items = await loadProjects(nextFilters);
      setFilters(nextFilters);
      const nextSelected =
        items.find((item) => item.project_id === selectedProject?.project_id) ??
        items[0] ??
        null;
      setSelectedProject(nextSelected);
      await loadProjectDetail(nextSelected?.project_id ?? "");
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar de página.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectProject(project) {
    setSelectedProject(project);
    await loadProjectDetail(project.project_id);
  }

  if (loading) {
    return <div className="screen-center">Cargando inventario por proyecto...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        eyebrow="Inventario"
        subtitle="Consulta materiales consumidos, devoluciones y costos reales vinculados a proyectos."
        title="Inventario por proyecto"
      />

      {error ? <p className="form-error">{error}</p> : null}

      <div className="inventory-metric-grid inventory-metric-grid-3">
        <MetricCard
          icon={<FolderKanban size={18} strokeWidth={1.9} />}
          label="Proyectos con consumo"
          meta="Movimientos ligados a PM"
          tone="info"
          value={String(meta.total || 0)}
        />
        <MetricCard
          icon={<PackageMinus size={18} strokeWidth={1.9} />}
          label="Costo real visible"
          meta="Proyecto seleccionado"
          tone="success"
          value={formatMoney(selectedProject?.costo_materiales_real ?? 0)}
        />
        <MetricCard
          icon={<ScrollText size={18} strokeWidth={1.9} />}
          label="Movimientos"
          meta="Proyecto seleccionado"
          tone="warning"
          value={String(projectMovements.length)}
        />
      </div>

      <DataCard
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={handleApplyFilters} size="sm" tone="primary" type="button">
              Actualizar
            </ActionButton>
          </div>
        }
        subtitle="Resumen de consumos netos de inventario vinculados a proyectos PM."
        title="Proyectos con consumo de inventario"
      >
        <SearchInput
          hint="Busca por nombre o código del proyecto."
          label="Buscar proyecto"
          onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              handleApplyFilters();
            }
          }}
          placeholder="Nombre o código del proyecto"
          value={filters.q}
        />
        <ResultMeta label="proyectos" loaded={projects.length} total={meta.total} />
        {projects.length === 0 ? (
          <EmptyState
            compact
            note="Todavía no hay consumos de inventario asociados a proyectos."
            title="Sin consumo por proyecto"
          />
        ) : (
          <>
            <DataTable
              columns={[
                "Proyecto",
                "Estatus",
                "Material consumido",
                "Costo real",
                "Movimientos",
                "Último movimiento",
                "Acciones",
              ]}
            >
              <tbody>
                {projects.map((project) => (
                  <tr
                    className={selectedProject?.project_id === project.project_id ? "inventory-row-selected" : ""}
                    key={project.project_id}
                  >
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(project.nombre)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(project.codigo, "Sin código")}</div>
                    </td>
                    <td>
                      <StatusBadge tone={getProjectStatusTone(project.estatus)}>
                        {safeDisplayText(project.estatus, "activo")}
                      </StatusBadge>
                    </td>
                    <td>{formatNumber(project.total_materiales_consumidos)}</td>
                    <td>{formatMoney(project.costo_materiales_real)}</td>
                    <td>{project.movimientos_count}</td>
                    <td>{safeDisplayText(formatDateTime(project.ultimo_movimiento_at), "—")}</td>
                    <td>
                      <div className="table-actions">
                        <ActionButton onClick={() => handleSelectProject(project)} size="sm" type="button">
                          Ver detalle
                        </ActionButton>
                        <ActionButton
                          onClick={() => navigate(`/pm/projects/${project.project_id}`, { state: { pmView: "materiales" } })}
                          size="sm"
                          tone="primary"
                          type="button"
                        >
                          Ir a PM
                        </ActionButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <PaginationControls
              limit={meta.limit}
              offset={meta.offset}
              onPageChange={handlePageChange}
              total={meta.total}
            />
          </>
        )}
      </DataCard>

      <DataCard
        subtitle="Materiales netos consumidos por el proyecto seleccionado."
        title={selectedProject ? `Detalle · ${safeDisplayText(selectedProject.nombre)}` : "Detalle del proyecto"}
      >
        {!selectedProject ? (
          <EmptyState compact note="Selecciona un proyecto para ver su consumo de materiales." title="Sin proyecto seleccionado" />
        ) : detailLoading ? (
          <div className="screen-center">Cargando detalle del proyecto...</div>
        ) : (
          <>
            {projectMaterials.length === 0 ? (
              <EmptyState compact note="El proyecto todavía no tiene movimientos netos de materiales." title="Sin materiales consumidos" />
            ) : (
              <DataTable
                columns={[
                  "Material",
                  "Unidad",
                  "Cantidad neta",
                  "Costo total",
                  "Almacenes",
                  "Tareas",
                  "Partidas",
                  "Última salida",
                ]}
              >
                <tbody>
                  {projectMaterials.map((item) => (
                    <tr key={item.material_id}>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(item.material_nombre)}</div>
                        <div className="inventory-cell-sub">{safeDisplayText(item.material_sku, "—")}</div>
                      </td>
                      <td>{safeDisplayText(item.unidad, "—")}</td>
                      <td>{formatNumber(item.cantidad_consumida)}</td>
                      <td>{formatMoney(item.costo_total)}</td>
                      <td>{item.almacenes_involucrados.length ? item.almacenes_involucrados.join(", ") : "—"}</td>
                      <td>{item.tarea_titulos.length ? item.tarea_titulos.join(", ") : "—"}</td>
                      <td>{item.partida_titulos.length ? item.partida_titulos.join(", ") : "—"}</td>
                      <td>{safeDisplayText(formatDateTime(item.ultima_salida_at), "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            )}

            <SectionDivider />

            {projectMovements.length === 0 ? (
              <EmptyState compact note="No hay movimientos registrados para este proyecto." title="Sin movimientos" />
            ) : (
              <DataTable
                columns={[
                  "Fecha",
                  "Tipo",
                  "Material",
                  "Cantidad",
                  "Costo",
                  "Almacén",
                  "Tarea",
                  "Partida",
                ]}
              >
                <tbody>
                  {projectMovements.map((movement) => (
                    <tr key={movement.id}>
                      <td>{safeDisplayText(formatDateTime(movement.created_at), "—")}</td>
                      <td>
                        <StatusBadge tone={movement.tipo === "entrada" ? "warning" : "success"}>
                          {getMovementLabel(movement)}
                        </StatusBadge>
                      </td>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(movement.material_nombre)}</div>
                        <div className="inventory-cell-sub">{safeDisplayText(movement.material_sku, "—")}</div>
                      </td>
                      <td>{formatNumber(movement.cantidad)}</td>
                      <td>{formatMoney(movement.costo_total_snapshot ?? 0)}</td>
                      <td>{safeDisplayText(movement.almacen_nombre, "—")}</td>
                      <td>{safeDisplayText(movement.pm_tarea_nombre_snapshot, "Proyecto general")}</td>
                      <td>{safeDisplayText(movement.pm_partida_nombre_snapshot, "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            )}
          </>
        )}
      </DataCard>
    </div>
  );
}


function SectionDivider() {
  return <div className="inventory-divider" />;
}
