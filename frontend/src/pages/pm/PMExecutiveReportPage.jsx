import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRightLeft,
  BarChart3,
  CircleDollarSign,
  FolderKanban,
  RefreshCw,
  ShieldAlert,
  Wallet,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getPmExecutiveReport } from "../../api/client";
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
  PageHeader,
  ResultMeta,
  StatusBadge,
  formatDate,
  formatMoney,
  safeDisplayText,
} from "../inventory/shared";
import {
  formatPercent,
  getExecutiveHealthLabel,
  getExecutiveHealthTone,
  normalizePmCopy,
  getPriorityLabel,
  getPriorityTone,
  getProjectStatusLabel,
  getProjectStatusTone,
  pmExecutiveHealthOptions,
  priorityOptions,
  projectStatusOptions,
} from "./shared";


const defaultFilters = {
  estatus: "",
  prioridad: "",
  responsable_id: "",
  fecha_desde: "",
  fecha_hasta: "",
  salud: "",
  con_alertas: false,
  con_pendiente_cobro: false,
  limit: 100,
  offset: 0,
};

const riskSeverityToneMap = {
  critical: "danger",
  warning: "warning",
  info: "info",
};

const riskSeverityLabelMap = {
  critical: "Crítico",
  warning: "Atención",
  info: "Info",
};


function getReportErrorMessage(error) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  return "No se pudo cargar el reporte ejecutivo.";
}


function buildRequestParams(filters) {
  return {
    estatus: filters.estatus || undefined,
    prioridad: filters.prioridad || undefined,
    responsable_id: filters.responsable_id || undefined,
    fecha_desde: filters.fecha_desde || undefined,
    fecha_hasta: filters.fecha_hasta || undefined,
    salud: filters.salud || undefined,
    con_alertas: filters.con_alertas ? true : undefined,
    con_pendiente_cobro: filters.con_pendiente_cobro ? true : undefined,
    limit: filters.limit ?? 100,
    offset: filters.offset ?? 0,
  };
}


function getProjectActionLabel(item) {
  if (Number(item?.pendiente_cobrar ?? 0) > 0) {
    return "Cobro pendiente";
  }
  if (Number(item?.cambios_pendientes ?? 0) > 0) {
    return "Cambio pendiente";
  }
  if (Number(item?.alertas_criticas ?? 0) > 0) {
    return "Atender alertas";
  }
  return "Ver proyecto";
}


export default function PMExecutiveReportPage() {
  const navigate = useNavigate();
  const { empresaId, token } = useAuth();
  const [filters, setFilters] = useState(defaultFilters);
  const [appliedFilters, setAppliedFilters] = useState(defaultFilters);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);

  const availableResponsibles = useMemo(() => {
    const items = (report?.projects ?? [])
      .filter((item) => item?.responsable_id && item?.responsable_nombre)
      .map((item) => ({
        value: item.responsable_id,
        label: item.responsable_nombre,
      }));
    return [...new Map(items.map((item) => [item.value, item])).values()].sort((left, right) =>
      left.label.localeCompare(right.label, "es-MX"),
    );
  }, [report]);

  async function loadReport(currentFilters = appliedFilters, { keepLoading = false } = {}) {
    if (!token || !empresaId) {
      return;
    }

    if (keepLoading) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const response = await getPmExecutiveReport({
        token,
        empresaId,
        params: buildRequestParams(currentFilters),
      });
      setReport(response);
    } catch (requestError) {
      setError(getReportErrorMessage(requestError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadReport(appliedFilters);
  }, [token, empresaId, appliedFilters]);

  function handleFilterChange(event) {
    const { name, type, checked, value } = event.target;
    const nextValue = type === "checkbox" ? checked : value;
    const nextFilters = {
      ...filters,
      [name]: nextValue,
    };
    setFilters(nextFilters);
    if (type === "checkbox" && (name === "con_alertas" || name === "con_pendiente_cobro")) {
      setAppliedFilters({
        ...nextFilters,
        offset: 0,
      });
    }
  }

  function handleApplyFilters() {
    setAppliedFilters({
      ...filters,
      offset: 0,
    });
  }

  function handleClearFilters() {
    setFilters(defaultFilters);
    setAppliedFilters(defaultFilters);
  }

  function goToProject(projectId, pmView = null) {
    navigate(`/pm/projects/${projectId}`, pmView ? { state: { pmView } } : undefined);
  }

  if (loading && !report) {
    return <div className="screen-center">Cargando reporte ejecutivo PM...</div>;
  }

  return (
    <div className="inventory-shell inventory-screen pm-screen pm-executive-screen">
      <PageHeader
        eyebrow="PM"
        title="Reporte ejecutivo PM"
        subtitle="Vista consolidada de avance, riesgos, costos, estimaciones y cobros."
        actions={(
          <div className="inventory-actions">
            <ActionButton onClick={() => loadReport(appliedFilters, { keepLoading: true })} type="button">
              {refreshing ? "Actualizando..." : "Actualizar"}
            </ActionButton>
            <ActionButton onClick={() => navigate("/pm/projects")} type="button">
              Ir a proyectos
            </ActionButton>
          </div>
        )}
      />

      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>No se pudo cargar el reporte</strong>
          <p className="table-note">{error}</p>
        </div>
      ) : null}

      <FilterCard
        actions={(
          <div className="inventory-actions">
            <ActionButton onClick={handleClearFilters} type="button">
              Limpiar
            </ActionButton>
            <ActionButton onClick={handleApplyFilters} tone="primary" type="button">
              Aplicar filtros
            </ActionButton>
          </div>
        )}
        subtitle="Filtra por estado operativo, salud, prioridad, responsable y condiciones de cobro."
        title="Filtros"
      >
        <FormGrid className="pm-executive-filter-grid">
          <Field label="Estatus">
            <select name="estatus" onChange={handleFilterChange} value={filters.estatus}>
              <option value="">Todos</option>
              {projectStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Salud">
            <select name="salud" onChange={handleFilterChange} value={filters.salud}>
              <option value="">Todas</option>
              {pmExecutiveHealthOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Prioridad">
            <select name="prioridad" onChange={handleFilterChange} value={filters.prioridad}>
              <option value="">Todas</option>
              {priorityOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field hint="Disponible con base en los proyectos cargados en esta vista." label="Responsable">
            <select name="responsable_id" onChange={handleFilterChange} value={filters.responsable_id}>
              <option value="">Todos</option>
              {availableResponsibles.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Fin desde">
            <input name="fecha_desde" onChange={handleFilterChange} type="date" value={filters.fecha_desde} />
          </Field>
          <Field label="Fin hasta">
            <input name="fecha_hasta" onChange={handleFilterChange} type="date" value={filters.fecha_hasta} />
          </Field>
          <Field className="pm-executive-check-field" label="Solo con alertas">
            <label className="pm-inline-checkbox">
              <input checked={filters.con_alertas} name="con_alertas" onChange={handleFilterChange} type="checkbox" />
              <span>Mostrar solo proyectos con alertas abiertas</span>
            </label>
          </Field>
          <Field className="pm-executive-check-field" label="Solo con pendiente por cobrar">
            <label className="pm-inline-checkbox">
              <input
                checked={filters.con_pendiente_cobro}
                name="con_pendiente_cobro"
                onChange={handleFilterChange}
                type="checkbox"
              />
              <span>Mostrar solo proyectos con saldo pendiente</span>
            </label>
          </Field>
        </FormGrid>
      </FilterCard>

      <DataCard subtitle="Resumen rápido para lectura de dirección y seguimiento semanal." title="KPIs globales">
        <div className="inventory-metric-grid inventory-metric-grid-5">
          <MetricCard
            icon={<FolderKanban size={18} strokeWidth={1.9} />}
            label="Proyectos activos"
            meta="Operando hoy"
            tone="success"
            value={report?.kpis?.proyectos_activos ?? 0}
          />
          <MetricCard
            icon={<AlertTriangle size={18} strokeWidth={1.9} />}
            label="Proyectos atrasados"
            meta="Fecha fin vencida"
            tone="warning"
            value={report?.kpis?.proyectos_atrasados ?? 0}
          />
          <MetricCard
            icon={<ShieldAlert size={18} strokeWidth={1.9} />}
            label="En riesgo"
            meta="Salud no verde"
            tone={(report?.kpis?.proyectos_en_riesgo ?? 0) > 0 ? "danger" : "success"}
            value={report?.kpis?.proyectos_en_riesgo ?? 0}
          />
          <MetricCard
            icon={<AlertTriangle size={18} strokeWidth={1.9} />}
            label="Alertas críticas"
            meta="Abiertas"
            tone={(report?.kpis?.alertas_criticas_abiertas ?? 0) > 0 ? "danger" : "neutral"}
            value={report?.kpis?.alertas_criticas_abiertas ?? 0}
          />
          <MetricCard
            icon={<ArrowRightLeft size={18} strokeWidth={1.9} />}
            label="Cambios pendientes"
            meta="Esperando aprobación"
            tone={(report?.kpis?.cambios_pendientes_aprobacion ?? 0) > 0 ? "warning" : "neutral"}
            value={report?.kpis?.cambios_pendientes_aprobacion ?? 0}
          />
        </div>
        <div className="inventory-metric-grid inventory-metric-grid-5">
          <MetricCard
            icon={<BarChart3 size={18} strokeWidth={1.9} />}
            label="Estimaciones pendientes"
            meta="En aprobación"
            tone={(report?.kpis?.estimaciones_pendientes_aprobacion ?? 0) > 0 ? "warning" : "neutral"}
            value={report?.kpis?.estimaciones_pendientes_aprobacion ?? 0}
          />
          <MetricCard
            icon={<CircleDollarSign size={18} strokeWidth={1.9} />}
            label="Presupuesto total"
            meta="Base del portafolio"
            tone="neutral"
            value={formatMoney(report?.kpis?.presupuesto_total_aprobado ?? 0)}
          />
          <MetricCard
            icon={<Wallet size={18} strokeWidth={1.9} />}
            label="Costo real"
            meta="Acumulado"
            tone="danger"
            value={formatMoney(report?.kpis?.costo_real_total ?? 0)}
          />
          <MetricCard
            icon={<CircleDollarSign size={18} strokeWidth={1.9} />}
            label="Cobrado"
            meta="Recuperado"
            tone="success"
            value={formatMoney(report?.kpis?.total_cobrado ?? 0)}
          />
          <MetricCard
            icon={<Wallet size={18} strokeWidth={1.9} />}
            label="Pendiente por cobrar"
            meta="Cartera PM"
            tone={(Number(report?.kpis?.pendiente_por_cobrar ?? 0) > 0 ? "warning" : "success")}
            value={formatMoney(report?.kpis?.pendiente_por_cobrar ?? 0)}
          />
        </div>
      </DataCard>

      <div className="inventory-content-grid inventory-content-grid-2">
        <DataCard subtitle="Portafolio económico consolidado del filtro actual." title="Resumen financiero">
          <div className="pm-executive-financial-grid">
            <div className="pm-executive-financial-item">
              <span>Presupuesto total</span>
              <strong>{formatMoney(report?.financial_summary?.presupuesto_total ?? 0)}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Costo real total</span>
              <strong>{formatMoney(report?.financial_summary?.costo_real_total ?? 0)}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Variación de costo</span>
              <strong>{formatMoney(report?.financial_summary?.variacion_costo ?? 0)}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Total estimado</span>
              <strong>{formatMoney(report?.financial_summary?.total_estimado ?? 0)}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Total aprobado</span>
              <strong>{formatMoney(report?.financial_summary?.total_aprobado ?? 0)}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Total cobrado</span>
              <strong>{formatMoney(report?.financial_summary?.total_cobrado ?? 0)}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Pendiente por cobrar</span>
              <strong>{formatMoney(report?.financial_summary?.pendiente_por_cobrar ?? 0)}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>% cobrado sobre estimado</span>
              <strong>{formatPercent(report?.financial_summary?.porcentaje_cobrado_sobre_estimado ?? 0)}</strong>
            </div>
          </div>
        </DataCard>

        <DataCard subtitle="Lectura operativa del portafolio para priorizar atención." title="Alertas y salud">
          <div className="pm-executive-financial-grid">
            <div className="pm-executive-financial-item">
              <span>Alertas abiertas</span>
              <strong>{report?.alerts_summary?.abiertas ?? 0}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Críticas</span>
              <strong>{report?.alerts_summary?.criticas ?? 0}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Warning</span>
              <strong>{report?.alerts_summary?.warning ?? 0}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Info</span>
              <strong>{report?.alerts_summary?.info ?? 0}</strong>
            </div>
            <div className="pm-executive-financial-item">
              <span>Margen estimado global</span>
              <strong>{formatMoney(report?.kpis?.margen_estimado_global ?? 0)}</strong>
            </div>
          </div>
        </DataCard>
      </div>

      <DataCard
        subtitle="Comparativo ejecutivo por proyecto para detectar atraso, sobrecosto y presión de cobro."
        title="Proyectos"
      >
        <ResultMeta
          label="proyectos en esta vista"
          loaded={report?.projects?.length ?? 0}
          total={report?.projects?.length ?? 0}
        />
        {(report?.projects?.length ?? 0) === 0 ? (
          <EmptyState
            compact
            note="No hay proyectos que coincidan con los filtros actuales."
            title="Sin proyectos"
          />
        ) : (
          <DataTable columns={["Proyecto", "Salud", "Avance", "Fin planificada", "Desviación", "Finanzas", "Cobro", "Alertas", "Acciones"]}>
            <tbody>
              {(report?.projects ?? []).map((item) => (
                <tr key={item.project_id}>
                  <td>
                    <div className="pm-executive-project-cell">
                      <strong>{normalizePmCopy(safeDisplayText(item.nombre))}</strong>
                      <span>
                        {safeDisplayText(item.codigo, "Sin código")} ·{" "}
                        <StatusBadge tone={getProjectStatusTone(item.estatus)}>{getProjectStatusLabel(item.estatus)}</StatusBadge>
                      </span>
                      <span>
                        {safeDisplayText(item.responsable_nombre, "Sin responsable")} ·{" "}
                        <StatusBadge tone={getPriorityTone(item.prioridad)}>{getPriorityLabel(item.prioridad)}</StatusBadge>
                      </span>
                    </div>
                  </td>
                  <td>
                    <div className="pm-executive-health-cell">
                      <StatusBadge tone={getExecutiveHealthTone(item.health)}>
                        {item.health_label || getExecutiveHealthLabel(item.health)}
                      </StatusBadge>
                      {item.health_reasons?.length ? (
                        <span className="pm-executive-reasons">
                          {item.health_reasons.map((reason) => normalizePmCopy(safeDisplayText(reason))).join(" · ")}
                        </span>
                      ) : (
                        <span className="table-note">Sin hallazgos críticos.</span>
                      )}
                    </div>
                  </td>
                  <td>{formatPercent(item.porcentaje_avance ?? 0)}</td>
                  <td>{formatDate(item.fecha_fin_planificada)}</td>
                  <td>
                    <div className="pm-executive-numeric-cell">
                      <strong>{safeDisplayText(item.desviacion_dias, 0)} días</strong>
                      <span className="table-note">Fin actual: {formatDate(item.fecha_fin_actual)}</span>
                    </div>
                  </td>
                  <td>
                    <div className="pm-executive-numeric-cell">
                      <strong>{formatMoney(item.presupuesto ?? 0)}</strong>
                      <span className="table-note">Costo real: {formatMoney(item.costo_real ?? 0)}</span>
                      <span className="table-note">Variación: {formatMoney(item.variacion_costo ?? 0)}</span>
                    </div>
                  </td>
                  <td>
                    <div className="pm-executive-numeric-cell">
                      <strong>{formatMoney(item.total_cobrado ?? 0)}</strong>
                      <span className="table-note">Estimado: {formatMoney(item.total_estimado ?? 0)}</span>
                      <span className="table-note">Pendiente: {formatMoney(item.pendiente_cobrar ?? 0)}</span>
                    </div>
                  </td>
                  <td>
                    <div className="pm-executive-numeric-cell">
                      <strong>{safeDisplayText(item.alertas_abiertas, 0)} abiertas</strong>
                      <span className="table-note">{safeDisplayText(item.alertas_criticas, 0)} críticas</span>
                      <span className="table-note">{safeDisplayText(item.cambios_pendientes, 0)} cambios pendientes</span>
                    </div>
                  </td>
                  <td>
                    <div className="pm-executive-actions">
                      <ActionButton onClick={() => goToProject(item.project_id)} size="sm" type="button">
                        {getProjectActionLabel(item)}
                      </ActionButton>
                      <ActionButton onClick={() => goToProject(item.project_id, "baseline")} size="sm" type="button">
                        Ver línea base
                      </ActionButton>
                      <ActionButton onClick={() => goToProject(item.project_id, "estimaciones")} size="sm" type="button">
                        Ver estimaciones
                      </ActionButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <DataCard subtitle="Lista consolidada de riesgos y siguientes acciones sugeridas." title="Riesgos">
        {(report?.risks?.length ?? 0) === 0 ? (
          <EmptyState
            compact
            note="No hay riesgos abiertos para los filtros actuales."
            title="Sin riesgos críticos"
          />
        ) : (
          <DataTable columns={["Proyecto", "Riesgo", "Severidad", "Descripción", "Acción sugerida"]}>
            <tbody>
              {(report?.risks ?? []).map((risk, index) => (
                <tr key={`${risk.project_id}-${risk.tipo_riesgo}-${index}`}>
                  <td>{normalizePmCopy(safeDisplayText(risk.proyecto_nombre))}</td>
                  <td>{safeDisplayText(risk.tipo_riesgo)}</td>
                  <td>
                    <StatusBadge tone={riskSeverityToneMap[risk.severidad] ?? "neutral"}>
                      {riskSeverityLabelMap[risk.severidad] ?? safeDisplayText(risk.severidad)}
                    </StatusBadge>
                  </td>
                  <td>{normalizePmCopy(safeDisplayText(risk.descripcion))}</td>
                  <td>{normalizePmCopy(safeDisplayText(risk.accion_sugerida, "Sin acción sugerida"))}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>
    </div>
  );
}
