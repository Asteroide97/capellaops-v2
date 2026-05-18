import { useEffect, useState } from "react";

import {
  addCountDetail,
  applyCount,
  cancelCount,
  createCount,
  deleteCountDetail,
  getCountDetail,
  getCounts,
  getMaterials,
  getWarehouses,
  updateCount,
  updateCountDetail,
} from "../../api/client";


const DEFAULT_PAGE_SIZE = 25;

const countFilterDefaults = {
  q: "",
  almacen_id: "",
  estatus: "",
  fecha_desde: "",
  fecha_hasta: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


function formatNumber(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    minimumFractionDigits: Number.isInteger(numericValue) ? 0 : 2,
    maximumFractionDigits: 4,
  }).format(Number.isNaN(numericValue) ? 0 : numericValue);
}


function normalizeDecimalInput(value) {
  return value.replace(",", ".").replace(/[^\d.]/g, "");
}


function EmptyState({ title, note }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{note}</p>
    </div>
  );
}


function ResultMeta({ loaded, total, label }) {
  return <p className="table-note">Mostrando {loaded} de {total} {label}.</p>;
}


function PaginationControls({ meta, onPrevious, onNext }) {
  const canGoPrevious = meta.offset > 0;
  const canGoNext = meta.offset + meta.limit < meta.total;

  return (
    <div className="inventory-pagination">
      <span className="table-note">
        Pagina {Math.floor(meta.offset / meta.limit) + 1} de {Math.max(1, Math.ceil(meta.total / meta.limit))}
      </span>
      <div className="inventory-actions">
        <button className="ghost-button" disabled={!canGoPrevious} onClick={onPrevious} type="button">
          Anterior
        </button>
        <button className="ghost-button" disabled={!canGoNext} onClick={onNext} type="button">
          Siguiente
        </button>
      </div>
    </div>
  );
}


export default function CountsSection({ active, token, empresaId, onInventoryChanged }) {
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warehouseOptions, setWarehouseOptions] = useState([]);
  const [materialOptions, setMaterialOptions] = useState([]);
  const [counts, setCounts] = useState([]);
  const [countMeta, setCountMeta] = useState({
    total: 0,
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
  });
  const [countFilters, setCountFilters] = useState(countFilterDefaults);
  const [selectedCount, setSelectedCount] = useState(null);
  const [countForm, setCountForm] = useState({
    id: "",
    folio: "",
    almacen_id: "",
    notas: "",
  });
  const [detailForm, setDetailForm] = useState({
    id: "",
    material_id: "",
    cantidad_fisica: "",
  });

  async function loadOptions() {
    const [warehouseResponse, materialResponse] = await Promise.all([
      getWarehouses({
        token,
        empresaId,
        filters: { activo: true, limit: 200, offset: 0 },
      }),
      getMaterials({
        token,
        empresaId,
        filters: { activo: true, limit: 200, offset: 0 },
      }),
    ]);
    setWarehouseOptions(warehouseResponse.items);
    setMaterialOptions(materialResponse.items);
  }

  async function loadCountList(nextFilters = countFilters) {
    const response = await getCounts({ token, empresaId, filters: nextFilters });
    setCounts(response.items);
    setCountMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    return response;
  }

  async function loadCountDocument(countId) {
    const response = await getCountDetail({ countId, token, empresaId });
    setSelectedCount(response);
    setCountForm({
      id: response.id,
      folio: response.folio,
      almacen_id: response.almacen_id,
      notas: response.notas || "",
    });
    return response;
  }

  function resetCountForm() {
    setCountForm({
      id: "",
      folio: "",
      almacen_id: warehouseOptions[0]?.id || "",
      notas: "",
    });
    setSelectedCount(null);
    resetDetailForm();
  }

  function resetDetailForm() {
    setDetailForm({
      id: "",
      material_id: materialOptions[0]?.id || "",
      cantidad_fisica: "",
    });
  }

  async function initializeSection() {
    if (!token || !empresaId) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      await loadOptions();
      await loadCountList(countFilters);
      setInitialized(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron cargar los conteos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (active && !initialized) {
      initializeSection();
    }
  }, [active, initialized, token, empresaId]);

  useEffect(() => {
    if (warehouseOptions.length > 0 && !countForm.almacen_id) {
      setCountForm((current) => ({ ...current, almacen_id: warehouseOptions[0].id }));
    }
  }, [warehouseOptions, countForm.almacen_id]);

  useEffect(() => {
    if (materialOptions.length > 0 && !detailForm.material_id) {
      setDetailForm((current) => ({ ...current, material_id: materialOptions[0].id }));
    }
  }, [materialOptions, detailForm.material_id]);

  async function handleCountSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      folio: countForm.folio || null,
      almacen_id: countForm.almacen_id,
      notas: countForm.notas || null,
    };

    try {
      const response = countForm.id
        ? await updateCount({ countId: countForm.id, token, empresaId, payload })
        : await createCount({ token, empresaId, payload });
      await loadCountList(countFilters);
      setSelectedCount(response);
      setCountForm({
        id: response.id,
        folio: response.folio,
        almacen_id: response.almacen_id,
        notas: response.notas || "",
      });
      setSuccess(countForm.id ? "Conteo actualizado." : "Conteo creado en borrador.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el conteo.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDetailSubmit(event) {
    event.preventDefault();
    if (!selectedCount) {
      setError("Primero crea o selecciona un conteo.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      material_id: detailForm.material_id,
      cantidad_fisica: detailForm.cantidad_fisica,
    };

    try {
      const response = detailForm.id
        ? await updateCountDetail({
            countId: selectedCount.id,
            detailId: detailForm.id,
            token,
            empresaId,
            payload,
          })
        : await addCountDetail({
            countId: selectedCount.id,
            token,
            empresaId,
            payload,
          });
      setSelectedCount(response);
      await loadCountList(countFilters);
      setSuccess(detailForm.id ? "Detalle actualizado." : "Detalle agregado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteDetail(detailId) {
    if (!selectedCount) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await deleteCountDetail({
        countId: selectedCount.id,
        detailId,
        token,
        empresaId,
      });
      setSelectedCount(response);
      await loadCountList(countFilters);
      setSuccess("Detalle eliminado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo eliminar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApplyCount() {
    if (!selectedCount) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await applyCount({ countId: selectedCount.id, token, empresaId });
      setSelectedCount(response);
      await loadCountList(countFilters);
      setSuccess("Conteo aplicado.");
      await onInventoryChanged?.();
    } catch (requestError) {
      setError(requestError.message || "No se pudo aplicar el conteo.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancelCount() {
    if (!selectedCount) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await cancelCount({ countId: selectedCount.id, token, empresaId });
      setSelectedCount(response);
      await loadCountList(countFilters);
      setSuccess("Conteo cancelado.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo cancelar el conteo.");
    } finally {
      setSubmitting(false);
    }
  }

  async function applyFilters(event) {
    event.preventDefault();
    setError("");
    try {
      const nextFilters = { ...countFilters, offset: 0 };
      setCountFilters(nextFilters);
      await loadCountList(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron filtrar los conteos.");
    }
  }

  async function handlePageChange(nextOffset) {
    const nextFilters = { ...countFilters, offset: nextOffset };
    setCountFilters(nextFilters);
    try {
      await loadCountList(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar la pagina de conteos.");
    }
  }

  async function handleSelectCount(countId) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await loadCountDocument(countId);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el conteo.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!active) {
    return null;
  }

  if (loading) {
    return <div className="screen-center">Cargando conteos fisicos...</div>;
  }

  const selectedIsDraft = selectedCount?.estatus === "borrador";

  return (
    <div className="inventory-grid">
      <div className="inventory-kardex-stack">
        <form className="feature-card inventory-form-card" onSubmit={handleCountSubmit}>
          <div className="feature-header">
            <p className="eyebrow">Conteos fisicos</p>
            <h2>{countForm.id ? "Editar conteo" : "Crear conteo"}</h2>
            <p>Congela una foto del sistema, captura la cantidad fisica y aplica ajustes auditables.</p>
          </div>

          {error ? <p className="form-error">{error}</p> : null}
          {success ? <p className="form-success">{success}</p> : null}

          <div className="inventory-form-grid">
            <label>
              Folio interno
              <input
                onChange={(event) =>
                  setCountForm((current) => ({ ...current, folio: event.target.value.toUpperCase() }))
                }
                placeholder="Auto"
                type="text"
                value={countForm.folio}
              />
            </label>

            <label>
              Estatus
              <input disabled type="text" value={selectedCount?.estatus || "borrador"} />
            </label>

            <label>
              Almacen
              <select
                disabled={Boolean(selectedCount && !selectedIsDraft)}
                onChange={(event) =>
                  setCountForm((current) => ({ ...current, almacen_id: event.target.value }))
                }
                required
                value={countForm.almacen_id}
              >
                {warehouseOptions.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.nombre} ({warehouse.codigo})
                  </option>
                ))}
              </select>
            </label>

            <label className="inventory-form-span-2">
              Notas
              <textarea
                onChange={(event) =>
                  setCountForm((current) => ({ ...current, notas: event.target.value }))
                }
                rows={3}
                value={countForm.notas}
              />
            </label>
          </div>

          <div className="inventory-actions">
            <button className="primary-button" disabled={submitting} type="submit">
              {submitting ? "Guardando..." : countForm.id ? "Actualizar conteo" : "Crear conteo"}
            </button>
            <button className="ghost-button" onClick={resetCountForm} type="button">
              Nuevo conteo
            </button>
            {selectedCount && selectedIsDraft ? (
              <>
                <button className="ghost-button" disabled={submitting} onClick={handleApplyCount} type="button">
                  Aplicar conteo
                </button>
                <button className="ghost-button" disabled={submitting} onClick={handleCancelCount} type="button">
                  Cancelar borrador
                </button>
              </>
            ) : null}
          </div>
        </form>

        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Detalle</p>
            <h2>Materiales del conteo</h2>
            {selectedCount ? (
              <p className="table-note">
                {selectedCount.folio} | almacen {selectedCount.almacen_nombre}
              </p>
            ) : null}
          </div>

          {!selectedCount ? (
            <EmptyState
              title="Sin conteo activo."
              note="Crea un conteo o abre un borrador para capturar cantidades fisicas."
            />
          ) : (
            <>
              {selectedIsDraft ? (
                <form className="inventory-filter-grid" onSubmit={handleDetailSubmit}>
                  <label>
                    Material
                    <select
                      onChange={(event) =>
                        setDetailForm((current) => ({ ...current, material_id: event.target.value }))
                      }
                      required
                      value={detailForm.material_id}
                    >
                      {materialOptions.map((material) => (
                        <option key={material.id} value={material.id}>
                          {material.sku} - {material.nombre}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Cantidad fisica
                    <input
                      min="0"
                      onChange={(event) =>
                        setDetailForm((current) => ({
                          ...current,
                          cantidad_fisica: normalizeDecimalInput(event.target.value),
                        }))
                      }
                      required
                      step="0.0001"
                      type="number"
                      value={detailForm.cantidad_fisica}
                    />
                  </label>

                  <div className="inventory-actions">
                    <button className="ghost-button" disabled={submitting} type="submit">
                      {detailForm.id ? "Actualizar detalle" : "Agregar material"}
                    </button>
                    {detailForm.id ? (
                      <button className="ghost-button" onClick={resetDetailForm} type="button">
                        Cancelar edicion
                      </button>
                    ) : null}
                  </div>
                </form>
              ) : (
                <EmptyState
                  title="Conteo cerrado."
                  note="En esta fase no se permite editar ni revertir conteos aplicados o cancelados."
                />
              )}

              {selectedCount.details.length === 0 ? (
                <EmptyState
                  title="Sin materiales."
                  note="Agrega al menos un material para capturar diferencias contra el sistema."
                />
              ) : (
                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>Material</th>
                        <th>Sistema</th>
                        <th>Fisico</th>
                        <th>Diferencia</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedCount.details.map((detail) => (
                        <tr key={detail.id}>
                          <td>{detail.material_sku}</td>
                          <td>
                            <strong>{detail.material_nombre}</strong>
                            <div className="table-note">{detail.material_unidad}</div>
                          </td>
                          <td>{formatNumber(detail.cantidad_sistema_snapshot)}</td>
                          <td>{formatNumber(detail.cantidad_fisica)}</td>
                          <td>
                            <span
                              className={`status-badge ${
                                Number(detail.diferencia) === 0 ? "enabled" : "pending"
                              }`}
                            >
                              {formatNumber(detail.diferencia)}
                            </span>
                          </td>
                          <td className="inventory-row-actions">
                            {selectedIsDraft ? (
                              <>
                                <button
                                  className="link-button"
                                  onClick={() =>
                                    setDetailForm({
                                      id: detail.id,
                                      material_id: detail.material_id,
                                      cantidad_fisica: String(detail.cantidad_fisica),
                                    })
                                  }
                                  type="button"
                                >
                                  Editar
                                </button>
                                <button
                                  className="link-button"
                                  onClick={() => handleDeleteDetail(detail.id)}
                                  type="button"
                                >
                                  Eliminar
                                </button>
                              </>
                            ) : (
                              <span className="table-note">
                                {detail.ajuste_movimiento_id ? "Ajuste aplicado" : "Sin ajuste"}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Listado</p>
          <h2>Conteos registrados</h2>
          <ResultMeta label="conteos" loaded={counts.length} total={countMeta.total} />
        </div>

        <form className="inventory-filter-grid" onSubmit={applyFilters}>
          <label>
            Buscar
            <input
              onChange={(event) =>
                setCountFilters((current) => ({ ...current, q: event.target.value }))
              }
              placeholder="Folio o notas"
              type="text"
              value={countFilters.q}
            />
          </label>

          <label>
            Almacen
            <select
              onChange={(event) =>
                setCountFilters((current) => ({ ...current, almacen_id: event.target.value }))
              }
              value={countFilters.almacen_id}
            >
              <option value="">Todos</option>
              {warehouseOptions.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.nombre} ({warehouse.codigo})
                </option>
              ))}
            </select>
          </label>

          <label>
            Estatus
            <select
              onChange={(event) =>
                setCountFilters((current) => ({ ...current, estatus: event.target.value }))
              }
              value={countFilters.estatus}
            >
              <option value="">Todos</option>
              <option value="borrador">Borrador</option>
              <option value="aplicado">Aplicado</option>
              <option value="cancelado">Cancelado</option>
            </select>
          </label>

          <label>
            Fecha desde
            <input
              onChange={(event) =>
                setCountFilters((current) => ({ ...current, fecha_desde: event.target.value }))
              }
              type="datetime-local"
              value={countFilters.fecha_desde}
            />
          </label>

          <label>
            Fecha hasta
            <input
              onChange={(event) =>
                setCountFilters((current) => ({ ...current, fecha_hasta: event.target.value }))
              }
              type="datetime-local"
              value={countFilters.fecha_hasta}
            />
          </label>

          <div className="inventory-actions">
            <button className="ghost-button" type="submit">
              Aplicar filtros
            </button>
            <button
              className="ghost-button"
              onClick={async () => {
                setCountFilters(countFilterDefaults);
                try {
                  await loadCountList(countFilterDefaults);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron reiniciar los filtros.");
                }
              }}
              type="button"
            >
              Limpiar
            </button>
          </div>
        </form>

        {counts.length === 0 ? (
          <EmptyState
            title="No hay conteos."
            note="Crea un conteo en borrador para capturar diferencias fisicas."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Almacen</th>
                    <th>Estatus</th>
                    <th>Materiales</th>
                    <th>Fecha</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {counts.map((count) => (
                    <tr key={count.id}>
                      <td>{count.folio}</td>
                      <td>{count.almacen_nombre}</td>
                      <td>
                        <span className={`status-badge ${count.estatus === "aplicado" ? "enabled" : "pending"}`}>
                          {count.estatus}
                        </span>
                      </td>
                      <td>{count.detalles_count}</td>
                      <td>{formatDateTime(count.created_at)}</td>
                      <td className="inventory-row-actions">
                        <button className="link-button" onClick={() => handleSelectCount(count.id)} type="button">
                          Ver detalle
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PaginationControls
              meta={countMeta}
              onNext={() => handlePageChange(countMeta.offset + countMeta.limit)}
              onPrevious={() => handlePageChange(Math.max(0, countMeta.offset - countMeta.limit))}
            />
          </>
        )}
      </div>
    </div>
  );
}
