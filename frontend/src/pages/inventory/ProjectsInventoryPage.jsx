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
  return movement.referencia_tipo === "DEVOLUCION_PROYECTO" ? "Devolución" : "Consumo";
}

function SectionDivider() {
  return <div className="inventory-divider" />;
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
    const items = response.items ?? [];
    setProjects(items);
    setMeta({
      total: response.total ?? 0,
      limit: response.limit ?? nextFilters.limit,
      offset: response.offset ?? nextFilters.offset,
    });
    return items;
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
        getInventoryProjectMovements({
          projectId,
          token,
          empresaId,
          filters: { limit: 100, offset: 0 },
        }),
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
    setLoading(true);
    setError("");
    try {
      const nextFilters = { ...filters, offset: nextOffset };
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
        title="Inventario por proyecto"
        subtitle="Consulta materiales consumidos, devoluciones y costos reales vinculados a proyectos."
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
        title="Proyectos con consumo de inventario"
        subtitle="Resumen de consumos netos de inventario vinculados a proyectos PM."
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={handleApplyFilters} size="sm" tone="primary" type="button">
              Actualizar
            </ActionButton>
          </div>
        }
      >
        <SearchInput
          label="Buscar proyecto"
          hint="Busca por nombre o código del proyecto."
          placeholder="Nombre o código del proyecto"
          value={filters.q}
          onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              handleApplyFilters();
            }
          }}
        />
        <ResultMeta label="proyectos" loaded={projects.length} total={meta.total} />

        {projects.length === 0 ? (
          <EmptyState
            compact
            title="Sin consumos por proyecto"
            note="No hay consumos por proyecto todavía. Cuando consumas materiales desde PM, aparecerán aquí."
          />
        ) : (
          <>
            <DataTable
              columns={[
                "Proyecto",
                "Estatus",
                "Materiales consumidos",
                "Costo real de materiales",
                "Movimientos",
                "Último movimiento",
                "Acciones",
              ]}
            >
              <tbody>
                {projects.map((project) => (
                  <tr
                    key={project.project_id}
                    className={selectedProject?.project_id === project.project_id ? "inventory-row-selected" : ""}
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
                          Abrir proyecto PM
                        </ActionButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>

            <PaginationControls
              total={meta.total}
              limit={meta.limit}
              offset={meta.offset}
              onPageChange={handlePageChange}
            />
          </>
        )}
      </DataCard>

      <DataCard
        title={selectedProject ? `Detalle · ${safeDisplayText(selectedProject.nombre)}` : "Detalle del proyecto"}
        subtitle="Materiales netos consumidos por el proyecto seleccionado."
      >
        {!selectedProject ? (
          <EmptyState
            compact
            title="Sin proyecto seleccionado"
            note="Selecciona un proyecto para ver su consumo de materiales."
          />
        ) : detailLoading ? (
          <div className="screen-center">Cargando detalle del proyecto...</div>
        ) : (
          <>
            {projectMaterials.length === 0 ? (
              <EmptyState
                compact
                title="Sin materiales consumidos"
                note="Este proyecto todavía no tiene movimientos netos de materiales."
              />
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
              <EmptyState compact title="Sin movimientos" note="No hay movimientos registrados para este proyecto." />
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
