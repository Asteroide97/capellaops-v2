import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import { getMaterialKardex, getMaterials, getWarehouses } from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  PageHeader,
  SearchInput,
  StatusBadge,
  formatDateTime,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "./shared";


const defaultFilters = {
  q: "",
  material_id: "",
  almacen_id: "",
  tipo: "",
  fecha_desde: "",
  fecha_hasta: "",
};

const movementToneMap = {
  entrada: "success",
  salida: "danger",
  ajuste: "warning",
};


function getEntradaValue(movement) {
  if (movement.tipo === "entrada") {
    return movement.cantidad;
  }
  if (movement.tipo === "ajuste" && Number(movement.cantidad) > 0) {
    return movement.cantidad;
  }
  return 0;
}


function getSalidaValue(movement) {
  if (movement.tipo === "salida") {
    return movement.cantidad;
  }
  if (movement.tipo === "ajuste" && Number(movement.cantidad) < 0) {
    return Math.abs(Number(movement.cantidad));
  }
  return 0;
}


function matchesQuery(movement, q) {
  if (!q) {
    return true;
  }

  const normalized = q.trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  return [
    movement.material_nombre,
    movement.material_sku,
    movement.motivo,
    movement.notas,
    movement.proyecto_nombre_snapshot,
    movement.proyecto_id,
  ]
    .filter(Boolean)
    .some((value) => safeDisplayText(value, "").toLowerCase().includes(normalized));
}


function withinDateRange(movement, fromValue, toValue) {
  const timestamp = movement.created_at ? new Date(movement.created_at).getTime() : null;
  if (!timestamp) {
    return true;
  }

  if (fromValue) {
    const fromTimestamp = new Date(fromValue).getTime();
    if (!Number.isNaN(fromTimestamp) && timestamp < fromTimestamp) {
      return false;
    }
  }

  if (toValue) {
    const toTimestamp = new Date(toValue).getTime();
    if (!Number.isNaN(toTimestamp) && timestamp > toTimestamp) {
      return false;
    }
  }

  return true;
}


export default function KardexPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [materials, setMaterials] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [filters, setFilters] = useState(defaultFilters);
  const [kardex, setKardex] = useState(null);

  const filteredMovements = useMemo(() => {
    if (!kardex) {
      return [];
    }

    return kardex.movements.filter((movement) => {
      if (filters.tipo && movement.tipo !== filters.tipo) {
        return false;
      }

      if (!matchesQuery(movement, filters.q)) {
        return false;
      }

      if (!withinDateRange(movement, filters.fecha_desde, filters.fecha_hasta)) {
        return false;
      }

      return true;
    });
  }, [filters.fecha_desde, filters.fecha_hasta, filters.q, filters.tipo, kardex]);

  async function loadOptions() {
    const [warehouseResponse, materialResponse] = await Promise.all([
      getWarehouses({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
      getMaterials({ token, empresaId, filters: { activo: true, limit: 500, offset: 0 } }),
    ]);
    setWarehouses(warehouseResponse.items);
    setMaterials(materialResponse.items);
    return {
      warehouseItems: warehouseResponse.items,
      materialItems: materialResponse.items,
    };
  }

  async function loadKardex(materialId = filters.material_id, warehouseId = filters.almacen_id) {
    if (!materialId) {
      setKardex(null);
      return;
    }

    const response = await getMaterialKardex({
      materialId,
      almacenId: warehouseId || undefined,
      token,
      empresaId,
    });
    setKardex(response);
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const options = await loadOptions();
        const defaultMaterialId = options.materialItems[0]?.id || "";
        const nextFilters = {
          ...defaultFilters,
          material_id: defaultMaterialId,
        };
        setFilters(nextFilters);
        if (defaultMaterialId) {
          await loadKardex(defaultMaterialId, "");
        }
      } catch (requestError) {
        setError(requestError.message || "No se pudo cargar el kardex.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  async function handleApplyFilters() {
    if (!filters.material_id) {
      setKardex(null);
      setSuccess("");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await loadKardex(filters.material_id, filters.almacen_id);
      setSuccess("Kardex actualizado.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo consultar el kardex.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetFilters() {
    const nextFilters = {
      ...defaultFilters,
      material_id: materials[0]?.id || "",
    };
    setFilters(nextFilters);
    setError("");
    setSuccess("");

    if (!nextFilters.material_id) {
      setKardex(null);
      return;
    }

    try {
      await loadKardex(nextFilters.material_id, "");
    } catch (requestError) {
      setError(requestError.message || "No se pudo reiniciar la consulta.");
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando kardex...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        actions={
          <ActionButton onClick={handleApplyFilters} size="sm" type="button">
            Actualizar
          </ActionButton>
        }
        eyebrow="Inventario"
        subtitle="Registro inmutable de todos los movimientos de inventario con costeo"
        title="Kardex de Inventario"
      />

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}

      <FilterCard>
        {materials.length === 0 ? (
          <EmptyState
            note="Crea al menos un material para consultar su historial de inventario."
            title="No hay materiales disponibles"
          />
        ) : (
          <>
            <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
              <SearchInput
                hint="Filtra el historial cargado por material, SKU, motivo o proyecto."
                label="Buscar en kardex"
                onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    handleApplyFilters();
                  }
                }}
                placeholder="Material, SKU, motivo o proyecto"
                value={filters.q}
              />

              <FormGrid className="inventory-filter-grid-wide">
                <Field label="Material">
                  <select
                    onChange={(event) => setFilters((current) => ({ ...current, material_id: event.target.value }))}
                    value={filters.material_id}
                  >
                    <option value="">Selecciona un material</option>
                    {materials.map((material) => (
                      <option key={material.id} value={material.id}>
                        {safeDisplayText(material.sku)} - {safeDisplayText(material.nombre)}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Almacén">
                  <select
                    onChange={(event) => setFilters((current) => ({ ...current, almacen_id: event.target.value }))}
                    value={filters.almacen_id}
                  >
                    <option value="">Todos</option>
                    {warehouses.map((warehouse) => (
                      <option key={warehouse.id} value={warehouse.id}>
                        {safeDisplayText(warehouse.nombre)} ({safeDisplayText(warehouse.codigo)})
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Tipo">
                  <select
                    onChange={(event) => setFilters((current) => ({ ...current, tipo: event.target.value }))}
                    value={filters.tipo}
                  >
                    <option value="">Todos</option>
                    <option value="entrada">Entrada</option>
                    <option value="salida">Salida</option>
                    <option value="ajuste">Ajuste</option>
                  </select>
                </Field>

                <Field label="Fecha desde">
                  <input
                    onChange={(event) => setFilters((current) => ({ ...current, fecha_desde: event.target.value }))}
                    type="datetime-local"
                    value={filters.fecha_desde}
                  />
                </Field>

                <Field label="Fecha hasta">
                  <input
                    onChange={(event) => setFilters((current) => ({ ...current, fecha_hasta: event.target.value }))}
                    type="datetime-local"
                    value={filters.fecha_hasta}
                  />
                </Field>
              </FormGrid>

              <div className="inventory-actions">
                <ActionButton disabled={submitting} onClick={handleApplyFilters} size="sm" tone="primary" type="button">
                  {submitting ? "Consultando..." : "Filtrar"}
                </ActionButton>
                <ActionButton onClick={handleResetFilters} size="sm" type="button">
                  Limpiar
                </ActionButton>
                <ActionButton
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      q: "",
                      tipo: "",
                      fecha_desde: "",
                      fecha_hasta: "",
                    }))
                  }
                  size="sm"
                  type="button"
                >
                  Limpiar vista
                </ActionButton>
              </div>
            </div>
          </>
        )}
      </FilterCard>

      {!kardex ? (
        <EmptyState
          note="Selecciona un material y consulta su historial para ver el detalle del kardex."
          title="Sin consulta activa"
        />
      ) : (
        <>
          <div className="inventory-metric-grid inventory-metric-grid-4">
            <article className="inventory-metric-card info">
              <span className="inventory-metric-label">Material</span>
              <strong className="inventory-metric-value">{safeDisplayText(kardex.material.sku)}</strong>
              <p className="table-note">{safeDisplayText(kardex.material.nombre)}</p>
            </article>
            <article className="inventory-metric-card success">
              <span className="inventory-metric-label">Existencia total</span>
              <strong className="inventory-metric-value">{formatNumber(kardex.existencia_total)}</strong>
              <p className="table-note">{safeDisplayText(kardex.material.unidad)}</p>
            </article>
            <article className="inventory-metric-card warning">
              <span className="inventory-metric-label">Costo promedio</span>
              <strong className="inventory-metric-value">
                {formatMoney(kardex.material.costo_promedio_actual ?? kardex.material.costo_unitario)}
              </strong>
              <p className="table-note">Costo base actual</p>
            </article>
            <article className="inventory-metric-card neutral">
              <span className="inventory-metric-label">Valor inventario</span>
              <strong className="inventory-metric-value">{formatMoney(kardex.material.valor_inventario)}</strong>
              <p className="table-note">Calculado desde existencias</p>
            </article>
          </div>

          <div className="inventory-content-grid inventory-content-grid-2">
            <DataCard subtitle="Distribución actual del material por almacén" title="Existencias por almacén">
              {kardex.stock_por_almacen.length === 0 ? (
                <EmptyState
                  compact
                  note="Este material todavía no tiene existencias distribuidas."
                  title="Sin existencias por almacén"
                />
              ) : (
                <DataTable
                  columns={[
                    { key: "almacen", label: "Almacén" },
                    { key: "codigo", label: "Código" },
                    { key: "cantidad", label: "Cantidad" },
                  ]}
                >
                  <tbody>
                    {kardex.stock_por_almacen.map((item) => (
                      <tr key={item.almacen_id}>
                        <td>{safeDisplayText(item.almacen_nombre || item.almacen)}</td>
                        <td>{safeDisplayText(item.almacen_codigo || item.codigo)}</td>
                        <td>{formatNumber(item.cantidad)}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </DataCard>

            <DataCard subtitle="Estado actual del material" title="Ficha de referencia">
              <div className="inventory-detail-grid">
                <div>
                  <strong>SKU</strong>
                  <p>{safeDisplayText(kardex.material.sku)}</p>
                </div>
                <div>
                  <strong>Categoría</strong>
                  <p>{safeDisplayText(kardex.material.categoria)}</p>
                </div>
                <div>
                  <strong>Proveedor principal</strong>
                  <p>{safeDisplayText(kardex.material.proveedor_principal_nombre)}</p>
                </div>
                <div>
                  <strong>Ubicación</strong>
                  <p>{safeDisplayText(kardex.material.ubicacion_texto)}</p>
                </div>
              </div>
            </DataCard>
          </div>

          <DataCard
            actions={<span className="table-note">{filteredMovements.length} movimientos visibles</span>}
            subtitle="El listado respeta únicamente los datos que el backend expone hoy"
            title="Historial de movimientos"
          >
            {filteredMovements.length === 0 ? (
              <EmptyState
                compact
                note="No hay movimientos que coincidan con los filtros activos."
                title="Sin resultados"
              />
            ) : (
              <DataTable
                columns={[
                  { key: "fecha", label: "Fecha" },
                  { key: "tipo", label: "Tipo" },
                  { key: "material", label: "Material" },
                  { key: "motivo", label: "Motivo" },
                  { key: "entrada", label: "Entrada" },
                  { key: "salida", label: "Salida" },
                  { key: "balance", label: "Balance" },
                  { key: "costo", label: "Costo unitario" },
                  { key: "costo_promedio", label: "Costo promedio" },
                  { key: "valor", label: "Valor inventario" },
                  { key: "usuario", label: "Usuario" },
                  { key: "proyecto", label: "Proyecto" },
                ]}
              >
                <tbody>
                  {filteredMovements.map((movement) => (
                    <tr key={movement.id}>
                      <td>{formatDateTime(movement.created_at)}</td>
                      <td>
                        <StatusBadge tone={movementToneMap[movement.tipo] ?? "neutral"}>{movement.tipo}</StatusBadge>
                      </td>
                      <td>
                        <div className="inventory-cell-main">
                          {safeDisplayText(
                            movement.material_nombre ||
                              movement.material?.nombre ||
                              movement.material?.sku ||
                              movement.material_id,
                          )}
                        </div>
                        <div className="inventory-cell-sub">
                          {safeDisplayText(movement.material_sku || movement.material?.sku || movement.material_id)}
                        </div>
                      </td>
                      <td>{safeDisplayText(movement.motivo || movement.notas)}</td>
                      <td className="inventory-value-positive">{formatNumber(getEntradaValue(movement))}</td>
                      <td className="inventory-value-negative">{formatNumber(getSalidaValue(movement))}</td>
                      <td className="inventory-balance-cell">{formatNumber(movement.cantidad_nueva)}</td>
                      <td>
                        {movement.costo_unitario_snapshot != null
                          ? formatMoney(movement.costo_unitario_snapshot)
                          : "—"}
                      </td>
                      <td>
                        {movement.costo_promedio_snapshot != null
                          ? formatMoney(movement.costo_promedio_snapshot)
                          : "—"}
                      </td>
                      <td>{movement.valor_inventario != null ? formatMoney(movement.valor_inventario) : "—"}</td>
                      <td>{safeDisplayText(movement.created_by_nombre || movement.created_by)}</td>
                      <td>{safeDisplayText(movement.proyecto_nombre_snapshot || movement.proyecto_id)}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            )}
          </DataCard>
        </>
      )}
    </div>
  );
}
