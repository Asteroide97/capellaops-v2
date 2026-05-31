import { useEffect, useState } from "react";
import { Calendar, CheckSquare, DollarSign, FolderKanban, Gauge, TriangleAlert } from "lucide-react";
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
  formatMoney,
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
    return <EmptyState compact note="Sin distribución disponible." title="Sin datos" />;
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
        title="Gestión de Proyectos"
        subtitle="Dashboard operativo para proyectos, tareas y seguimiento básico."
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={() => navigate("/pm/rates")} type="button">
              Tarifas PM
            </ActionButton>
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
          meta="Pendientes de atención"
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

      <section className="inventory-metric-grid inventory-metric-grid-3">
        <MetricCard
          icon={<DollarSign size={18} strokeWidth={1.9} />}
          label="Costo estimado materiales"
          meta="Planeación acumulada"
          tone="info"
          value={formatMoney(dashboard?.kpis?.costo_materiales_estimado_total ?? 0)}
        />
        <MetricCard
          icon={<DollarSign size={18} strokeWidth={1.9} />}
          label="Costo real materiales"
          meta="Consumo acumulado"
          tone="success"
          value={formatMoney(dashboard?.kpis?.costo_materiales_real_total ?? 0)}
        />
        <MetricCard
          icon={<TriangleAlert size={18} strokeWidth={1.9} />}
          label="Variación materiales"
          meta="Real contra estimado"
          tone={Number(dashboard?.kpis?.variacion_materiales_total ?? 0) > 0 ? "warning" : "neutral"}
          value={formatMoney(dashboard?.kpis?.variacion_materiales_total ?? 0)}
        />
      </section>

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard
          icon={<Calendar size={18} strokeWidth={1.9} />}
          label="Horas totales"
          meta="Registros acumulados"
          tone="info"
          value={dashboard?.kpis?.horas_totales ?? 0}
        />
        <MetricCard
          icon={<DollarSign size={18} strokeWidth={1.9} />}
          label="Costo horas real"
          meta="Labor acumulada"
          tone="warning"
          value={formatMoney(dashboard?.kpis?.costo_horas_real ?? 0)}
        />
        <MetricCard
          icon={<DollarSign size={18} strokeWidth={1.9} />}
          label="Costo total real"
          meta="Materiales + horas"
          tone="danger"
          value={formatMoney(dashboard?.kpis?.costo_total_real ?? 0)}
        />
        <MetricCard
          icon={<TriangleAlert size={18} strokeWidth={1.9} />}
          label="Horas sin tarifa"
          meta="Pendientes de configuración"
          tone={Number(dashboard?.kpis?.horas_sin_tarifa ?? 0) > 0 ? "warning" : "neutral"}
          value={dashboard?.kpis?.horas_sin_tarifa ?? 0}
        />
      </section>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Distribución de proyectos activos por estatus." title="Proyectos por estatus">
          <StatusDistribution items={dashboard?.proyectos_por_estatus ?? []} kind="project" />
        </DataCard>
        <DataCard subtitle="Distribución de tareas activas por estatus." title="Tareas por estatus">
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
          subtitle="Proyectos que requieren atención en el corto plazo."
          title="Próximos proyectos a vencer"
        >
          <ResultMeta
            label="proyectos"
            loaded={dashboard?.proyectos_proximos?.length ?? 0}
            total={dashboard?.proyectos_proximos?.length ?? 0}
          />
          {(dashboard?.proyectos_proximos?.length ?? 0) === 0 ? (
            <EmptyState compact note="No hay proyectos próximos a vencer." title="Sin alertas de proyecto" />
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
          subtitle="Tareas vencidas o próximas a vencer."
          title="Vencimientos operativos"
        >
          <ResultMeta
            label="tareas"
            loaded={(dashboard?.proximos_vencimientos?.length ?? 0) + (dashboard?.tareas_vencidas_items?.length ?? 0)}
            total={(dashboard?.proximos_vencimientos?.length ?? 0) + (dashboard?.tareas_vencidas_items?.length ?? 0)}
          />
          {(dashboard?.proximos_vencimientos?.length ?? 0) + (dashboard?.tareas_vencidas_items?.length ?? 0) === 0 ? (
            <EmptyState compact note="No hay tareas próximas o vencidas." title="Sin vencimientos" />
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

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Mayor consumo real de materiales por proyecto." title="Top proyectos por costo de materiales">
          {(dashboard?.top_proyectos_por_costo_materiales?.length ?? 0) === 0 ? (
            <EmptyState compact note="Aún no hay consumo de materiales acumulado." title="Sin costos registrados" />
          ) : (
            <DataTable columns={["Proyecto", "Real", "Estimado", "Variación"]}>
              <tbody>
                {(dashboard?.top_proyectos_por_costo_materiales ?? []).map((item) => (
                  <tr key={item.project_id}>
                    <td>{safeDisplayText(item.proyecto_nombre)}</td>
                    <td>{formatMoney(item.costo_materiales_real ?? 0)}</td>
                    <td>{formatMoney(item.costo_materiales_estimado ?? 0)}</td>
                    <td>{formatMoney(item.variacion_materiales ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>

        <DataCard subtitle="Proyectos cuyo costo de materiales ya rebasa el presupuesto cargado." title="Sobre presupuesto materiales">
          {(dashboard?.proyectos_sobre_presupuesto_materiales?.length ?? 0) === 0 ? (
            <EmptyState compact note="No hay proyectos sobre presupuesto por materiales." title="Sin alertas" />
          ) : (
            <DataTable columns={["Proyecto", "Costo real", "Presupuesto", "Variación"]}>
              <tbody>
                {(dashboard?.proyectos_sobre_presupuesto_materiales ?? []).map((item) => (
                  <tr key={item.project_id}>
                    <td>{safeDisplayText(item.proyecto_nombre)}</td>
                    <td>{formatMoney(item.costo_materiales_real ?? 0)}</td>
                    <td>{formatMoney(item.presupuesto_estimado ?? 0)}</td>
                    <td>{formatMoney(item.variacion_presupuesto ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      </div>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Proyectos con mayor costo real total acumulado." title="Top proyectos por costo total">
          {(dashboard?.top_proyectos_por_costo_total?.length ?? 0) === 0 ? (
            <EmptyState compact note="Aún no hay costos totales acumulados." title="Sin costos registrados" />
          ) : (
            <DataTable columns={["Proyecto", "Materiales", "Horas", "Costo total", "Presupuesto"]}>
              <tbody>
                {(dashboard?.top_proyectos_por_costo_total ?? []).map((item) => (
                  <tr key={`total-${item.project_id}`}>
                    <td>{safeDisplayText(item.proyecto_nombre)}</td>
                    <td>{formatMoney(item.costo_materiales_real ?? 0)}</td>
                    <td>{formatMoney(item.costo_horas_real ?? 0)}</td>
                    <td>{formatMoney(item.costo_total_real ?? 0)}</td>
                    <td>{formatMoney(item.presupuesto_estimado ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>

        <DataCard subtitle="Proyectos cuyo costo total ya supera el presupuesto." title="Proyectos sobre presupuesto">
          {(dashboard?.proyectos_sobre_presupuesto?.length ?? 0) === 0 ? (
            <EmptyState compact note="No hay proyectos sobre presupuesto total." title="Sin alertas" />
          ) : (
            <DataTable columns={["Proyecto", "Costo total", "Presupuesto", "Variación"]}>
              <tbody>
                {(dashboard?.proyectos_sobre_presupuesto ?? []).map((item) => (
                  <tr key={`budget-${item.project_id}`}>
                    <td>{safeDisplayText(item.proyecto_nombre)}</td>
                    <td>{formatMoney(item.costo_total_real ?? 0)}</td>
                    <td>{formatMoney(item.presupuesto_estimado ?? 0)}</td>
                    <td>{formatMoney(item.variacion_presupuesto ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      </div>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Usuarios con mayor carga horaria registrada." title="Top usuarios por horas">
          {(dashboard?.top_usuarios_por_horas?.length ?? 0) === 0 ? (
            <EmptyState compact note="Aún no hay horas registradas." title="Sin horas" />
          ) : (
            <DataTable columns={["Usuario", "Horas", "Costo"]}>
              <tbody>
                {(dashboard?.top_usuarios_por_horas ?? []).map((item, index) => (
                  <tr key={`user-hours-${item.usuario_id ?? item.usuario_email ?? index}`}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(item.usuario_nombre, "Sin nombre")}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(item.usuario_email, "—")}</div>
                    </td>
                    <td>{item.horas_totales ?? 0}</td>
                    <td>{formatMoney(item.costo_total ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>

        <DataCard subtitle="Usuarios con mayor costo laboral acumulado." title="Top usuarios por costo">
          {(dashboard?.top_usuarios_por_costo?.length ?? 0) === 0 ? (
            <EmptyState compact note="Aún no hay costos horarios acumulados." title="Sin costos" />
          ) : (
            <DataTable columns={["Usuario", "Horas", "Costo"]}>
              <tbody>
                {(dashboard?.top_usuarios_por_costo ?? []).map((item, index) => (
                  <tr key={`user-cost-${item.usuario_id ?? item.usuario_email ?? index}`}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(item.usuario_nombre, "Sin nombre")}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(item.usuario_email, "—")}</div>
                    </td>
                    <td>{item.horas_totales ?? 0}</td>
                    <td>{formatMoney(item.costo_total ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </DataCard>
      </div>
    </div>
  );
}
