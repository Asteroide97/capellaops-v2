import { useEffect, useState } from "react";
import { Calendar, CheckSquare, FolderKanban, Gauge, TriangleAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getPmDashboard } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  MetricCard,
  PageHeader,
  ResultMeta,
  StatusBadge,
  formatDate,
  safeDisplayText,
} from "../inventory/shared";
import {
  getPriorityLabel,
  getPriorityTone,
  getProjectStatusLabel,
  getProjectStatusTone,
  getTaskStatusLabel,
  getTaskStatusTone,
} from "./shared";


function StatusDistribution({ items, kind }) {
  if (!items?.length) {
    return <EmptyState compact note="Sin distribucion disponible." title="Sin datos" />;
  }

  return (
    <div className="pm-status-distribution">
      {items.map((item) => (
        <div className="pm-status-distribution-item" key={`${kind}-${item.estatus}`}>
          <div className="pm-inline-metadata">
            <StatusBadge tone={kind === "project" ? getProjectStatusTone(item.estatus) : getTaskStatusTone(item.estatus)}>
              {kind === "project" ? getProjectStatusLabel(item.estatus) : getTaskStatusLabel(item.estatus)}
            </StatusBadge>
          </div>
          <strong>{item.total}</strong>
        </div>
      ))}
    </div>
  );
}


export default function PMDashboardPage() {
  const navigate = useNavigate();
  const { empresaId, token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dashboard, setDashboard] = useState(null);

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const response = await getPmDashboard({ token, empresaId });
      setDashboard(response);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el dashboard de proyectos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token || !empresaId) {
      return;
    }

    loadDashboard();
  }, [token, empresaId]);

  if (loading) {
    return <div className="screen-center">Cargando dashboard PM...</div>;
  }

  return (
    <div className="inventory-shell inventory-screen pm-screen">
      <PageHeader
        eyebrow="PM Core"
        title="Gestion de Proyectos"
        subtitle="Dashboard operativo para proyectos, tareas y seguimiento basico."
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={() => navigate("/pm/projects")} type="button">
              Ver proyectos
            </ActionButton>
            <ActionButton onClick={() => navigate("/pm/projects")} tone="primary" type="button">
              Nuevo proyecto
            </ActionButton>
          </div>
        }
      />

      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>No se pudo cargar PM</strong>
          <p className="table-note">{error}</p>
        </div>
      ) : null}

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard
          icon={<FolderKanban size={18} strokeWidth={1.9} />}
          label="Proyectos activos"
          meta="Con trabajo en curso"
          tone="success"
          value={dashboard?.kpis?.proyectos_activos ?? 0}
        />
        <MetricCard
          icon={<TriangleAlert size={18} strokeWidth={1.9} />}
          label="Proyectos atrasados"
          meta="Fecha objetivo vencida"
          tone="warning"
          value={dashboard?.kpis?.proyectos_atrasados ?? 0}
        />
        <MetricCard
          icon={<Calendar size={18} strokeWidth={1.9} />}
          label="Tareas vencidas"
          meta="Pendientes de atencion"
          tone="danger"
          value={dashboard?.kpis?.tareas_vencidas ?? 0}
        />
        <MetricCard
          icon={<CheckSquare size={18} strokeWidth={1.9} />}
          label="Tareas pendientes"
          meta="Backlog operativo"
          tone="info"
          value={dashboard?.kpis?.tareas_pendientes ?? 0}
        />
      </section>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Distribucion de proyectos activos por estatus." title="Proyectos por estatus">
          <StatusDistribution items={dashboard?.proyectos_por_estatus ?? []} kind="project" />
        </DataCard>
        <DataCard subtitle="Distribucion de tareas activas por estatus." title="Tareas por estatus">
          <StatusDistribution items={dashboard?.tareas_por_estatus ?? []} kind="task" />
        </DataCard>
      </div>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard
          actions={
            <ActionButton onClick={() => navigate("/pm/projects")} size="sm" type="button">
              Ir a proyectos
            </ActionButton>
          }
          subtitle="Proyectos que requieren atencion en el corto plazo."
          title="Proximos proyectos a vencer"
        >
          <ResultMeta
            label="proyectos"
            loaded={dashboard?.proyectos_proximos?.length ?? 0}
            total={dashboard?.proyectos_proximos?.length ?? 0}
          />
          {(dashboard?.proyectos_proximos?.length ?? 0) === 0 ? (
            <EmptyState compact note="No hay proyectos proximos a vencer." title="Sin alertas de proyecto" />
          ) : (
            <DataTable columns={["Proyecto", "Fecha", "Prioridad", "Responsable"]}>
              <tbody>
                {(dashboard?.proyectos_proximos ?? []).map((item) => (
                  <tr key={`project-${item.project_id}-${item.fecha}`}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(item.proyecto_nombre)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(item.titulo)}</div>
                    </td>
                    <td>{safeDisplayText(formatDate(item.fecha), "-")}</td>
                    <td>
                      <StatusBadge tone={getPriorityTone(item.prioridad)}>{getPriorityLabel(item.prioridad)}</StatusBadge>
                    </td>
                    <td>{safeDisplayText(item.responsable_nombre, "Sin responsable")}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>

        <DataCard
          actions={
            <ActionButton onClick={() => navigate("/pm/projects")} size="sm" type="button">
              Revisar tareas
            </ActionButton>
          }
          subtitle="Tareas vencidas o proximas a vencer."
          title="Vencimientos operativos"
        >
          <ResultMeta
            label="tareas"
            loaded={(dashboard?.proximos_vencimientos?.length ?? 0) + (dashboard?.tareas_vencidas_items?.length ?? 0)}
            total={(dashboard?.proximos_vencimientos?.length ?? 0) + (dashboard?.tareas_vencidas_items?.length ?? 0)}
          />
          {(dashboard?.proximos_vencimientos?.length ?? 0) + (dashboard?.tareas_vencidas_items?.length ?? 0) === 0 ? (
            <EmptyState compact note="No hay tareas proximas o vencidas." title="Sin vencimientos" />
          ) : (
            <DataTable columns={["Tarea", "Fecha", "Estatus", "Prioridad"]}>
              <tbody>
                {[...(dashboard?.tareas_vencidas_items ?? []), ...(dashboard?.proximos_vencimientos ?? [])].map((item) => (
                  <tr key={`task-${item.task_id}-${item.fecha}`}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(item.titulo)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(item.proyecto_nombre)}</div>
                    </td>
                    <td>{safeDisplayText(formatDate(item.fecha), "-")}</td>
                    <td>
                      <StatusBadge tone={getTaskStatusTone(item.estatus)}>{getTaskStatusLabel(item.estatus)}</StatusBadge>
                    </td>
                    <td>
                      <StatusBadge tone={getPriorityTone(item.prioridad)}>{getPriorityLabel(item.prioridad)}</StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      </div>

      <DataCard title="Indicadores rapidos">
        <div className="inventory-metric-grid inventory-metric-grid-4">
          <MetricCard
            icon={<Gauge size={18} strokeWidth={1.9} />}
            label="Tareas en progreso"
            meta="Trabajo activo"
            tone="info"
            value={dashboard?.kpis?.tareas_en_progreso ?? 0}
          />
          <MetricCard
            icon={<CheckSquare size={18} strokeWidth={1.9} />}
            label="Tareas completadas"
            meta="Cerradas correctamente"
            tone="success"
            value={dashboard?.kpis?.tareas_completadas ?? 0}
          />
        </div>
      </DataCard>
    </div>
  );
}
