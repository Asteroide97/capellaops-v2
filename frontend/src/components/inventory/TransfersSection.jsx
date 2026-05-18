import { useEffect, useState } from "react";

import {
  addTransferDetail,
  cancelTransfer,
  confirmTransfer,
  createTransfer,
  deleteTransferDetail,
  getMaterials,
  getTransferDetail,
  getTransfers,
  getWarehouses,
  updateTransfer,
  updateTransferDetail,
} from "../../api/client";


const DEFAULT_PAGE_SIZE = 25;

const transferFilterDefaults = {
  q: "",
  almacen_origen_id: "",
  almacen_destino_id: "",
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


function formatMoney(value) {
  const numericValue = Number(value ?? 0);
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 2,
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


export default function TransfersSection({ active, token, empresaId, onInventoryChanged }) {
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warehouseOptions, setWarehouseOptions] = useState([]);
  const [materialOptions, setMaterialOptions] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [transferMeta, setTransferMeta] = useState({
    total: 0,
    limit: DEFAULT_PAGE_SIZE,
    offset: 0,
  });
  const [transferFilters, setTransferFilters] = useState(transferFilterDefaults);
  const [selectedTransfer, setSelectedTransfer] = useState(null);
  const [transferForm, setTransferForm] = useState({
    id: "",
    folio: "",
    almacen_origen_id: "",
    almacen_destino_id: "",
    notas: "",
  });
  const [detailForm, setDetailForm] = useState({
    id: "",
    material_id: "",
    cantidad: "",
    costo_unitario_snapshot: "",
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

  async function loadTransferList(nextFilters = transferFilters) {
    const response = await getTransfers({ token, empresaId, filters: nextFilters });
    setTransfers(response.items);
    setTransferMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    return response;
  }

  async function loadTransferDocument(transferId) {
    const response = await getTransferDetail({ transferId, token, empresaId });
    setSelectedTransfer(response);
    setTransferForm({
      id: response.id,
      folio: response.folio,
      almacen_origen_id: response.almacen_origen_id,
      almacen_destino_id: response.almacen_destino_id,
      notas: response.notas || "",
    });
    return response;
  }

  function resetTransferForm() {
    setTransferForm({
      id: "",
      folio: "",
      almacen_origen_id: warehouseOptions[0]?.id || "",
      almacen_destino_id: warehouseOptions[1]?.id || "",
      notas: "",
    });
    setSelectedTransfer(null);
    resetDetailForm();
  }

  function resetDetailForm() {
    setDetailForm({
      id: "",
      material_id: materialOptions[0]?.id || "",
      cantidad: "",
      costo_unitario_snapshot: "",
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
      await loadTransferList(transferFilters);
      setInitialized(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron cargar las transferencias.");
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
    if (warehouseOptions.length > 0 && !transferForm.almacen_origen_id) {
      setTransferForm((current) => ({ ...current, almacen_origen_id: warehouseOptions[0].id }));
    }
    if (warehouseOptions.length > 1 && !transferForm.almacen_destino_id) {
      setTransferForm((current) => ({ ...current, almacen_destino_id: warehouseOptions[1].id }));
    }
  }, [warehouseOptions, transferForm.almacen_destino_id, transferForm.almacen_origen_id]);

  useEffect(() => {
    if (materialOptions.length > 0 && !detailForm.material_id) {
      setDetailForm((current) => ({ ...current, material_id: materialOptions[0].id }));
    }
  }, [materialOptions, detailForm.material_id]);

  async function handleTransferSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      folio: transferForm.folio || null,
      almacen_origen_id: transferForm.almacen_origen_id,
      almacen_destino_id: transferForm.almacen_destino_id,
      notas: transferForm.notas || null,
    };

    try {
      const response = transferForm.id
        ? await updateTransfer({ transferId: transferForm.id, token, empresaId, payload })
        : await createTransfer({ token, empresaId, payload });
      await loadTransferList(transferFilters);
      setSelectedTransfer(response);
      setTransferForm({
        id: response.id,
        folio: response.folio,
        almacen_origen_id: response.almacen_origen_id,
        almacen_destino_id: response.almacen_destino_id,
        notas: response.notas || "",
      });
      setSuccess(transferForm.id ? "Transferencia actualizada." : "Transferencia creada en borrador.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la transferencia.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDetailSubmit(event) {
    event.preventDefault();
    if (!selectedTransfer) {
      setError("Primero crea o selecciona una transferencia.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      material_id: detailForm.material_id,
      cantidad: detailForm.cantidad,
      costo_unitario_snapshot: detailForm.costo_unitario_snapshot || null,
    };

    try {
      const response = detailForm.id
        ? await updateTransferDetail({
            transferId: selectedTransfer.id,
            detailId: detailForm.id,
            token,
            empresaId,
            payload,
          })
        : await addTransferDetail({
            transferId: selectedTransfer.id,
            token,
            empresaId,
            payload,
          });
      setSelectedTransfer(response);
      await loadTransferList(transferFilters);
      setSuccess(detailForm.id ? "Detalle actualizado." : "Detalle agregado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteDetail(detailId) {
    if (!selectedTransfer) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await deleteTransferDetail({
        transferId: selectedTransfer.id,
        detailId,
        token,
        empresaId,
      });
      setSelectedTransfer(response);
      await loadTransferList(transferFilters);
      setSuccess("Detalle eliminado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo eliminar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmTransfer() {
    if (!selectedTransfer) {
      return;
    }
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await confirmTransfer({ transferId: selectedTransfer.id, token, empresaId });
      setSelectedTransfer(response);
      await loadTransferList(transferFilters);
      setSuccess("Transferencia confirmada.");
      await onInventoryChanged?.();
    } catch (requestError) {
      setError(requestError.message || "No se pudo confirmar la transferencia.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancelTransfer() {
    if (!selectedTransfer) {
      return;
    }
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await cancelTransfer({ transferId: selectedTransfer.id, token, empresaId });
      setSelectedTransfer(response);
      await loadTransferList(transferFilters);
      setSuccess("Transferencia cancelada.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo cancelar la transferencia.");
    } finally {
      setSubmitting(false);
    }
  }

  async function applyFilters(event) {
    event.preventDefault();
    setError("");
    try {
      const nextFilters = { ...transferFilters, offset: 0 };
      setTransferFilters(nextFilters);
      await loadTransferList(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron filtrar las transferencias.");
    }
  }

  async function handlePageChange(nextOffset) {
    const nextFilters = { ...transferFilters, offset: nextOffset };
    setTransferFilters(nextFilters);
    try {
      await loadTransferList(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar la pagina de transferencias.");
    }
  }

  async function handleSelectTransfer(transferId) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      await loadTransferDocument(transferId);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar la transferencia.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!active) {
    return null;
  }

  if (loading) {
    return <div className="screen-center">Cargando transferencias...</div>;
  }

  const selectedIsDraft = selectedTransfer?.estatus === "borrador";

  return (
    <div className="inventory-grid">
      <div className="inventory-kardex-stack">
        <form className="feature-card inventory-form-card" onSubmit={handleTransferSubmit}>
          <div className="feature-header">
            <p className="eyebrow">Transferencias</p>
            <h2>{transferForm.id ? "Editar transferencia" : "Crear transferencia"}</h2>
            <p>Confirma la salida del almacen origen y la entrada al almacen destino en una sola operacion.</p>
          </div>

          {error ? <p className="form-error">{error}</p> : null}
          {success ? <p className="form-success">{success}</p> : null}

          <div className="inventory-form-grid">
            <label>
              Folio interno
              <input
                onChange={(event) =>
                  setTransferForm((current) => ({ ...current, folio: event.target.value.toUpperCase() }))
                }
                placeholder="Auto"
                type="text"
                value={transferForm.folio}
              />
            </label>

            <label>
              Estatus
              <input disabled type="text" value={selectedTransfer?.estatus || "borrador"} />
            </label>

            <label>
              Almacen origen
              <select
                disabled={Boolean(selectedTransfer && !selectedIsDraft)}
                onChange={(event) =>
                  setTransferForm((current) => ({ ...current, almacen_origen_id: event.target.value }))
                }
                required
                value={transferForm.almacen_origen_id}
              >
                {warehouseOptions.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.nombre} ({warehouse.codigo})
                  </option>
                ))}
              </select>
            </label>

            <label>
              Almacen destino
              <select
                disabled={Boolean(selectedTransfer && !selectedIsDraft)}
                onChange={(event) =>
                  setTransferForm((current) => ({ ...current, almacen_destino_id: event.target.value }))
                }
                required
                value={transferForm.almacen_destino_id}
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
                  setTransferForm((current) => ({ ...current, notas: event.target.value }))
                }
                rows={3}
                value={transferForm.notas}
              />
            </label>
          </div>

          <div className="inventory-actions">
            <button className="primary-button" disabled={submitting} type="submit">
              {submitting ? "Guardando..." : transferForm.id ? "Actualizar transferencia" : "Crear transferencia"}
            </button>
            <button className="ghost-button" onClick={resetTransferForm} type="button">
              Nueva transferencia
            </button>
            {selectedTransfer && selectedIsDraft ? (
              <>
                <button className="ghost-button" disabled={submitting} onClick={handleConfirmTransfer} type="button">
                  Confirmar transferencia
                </button>
                <button className="ghost-button" disabled={submitting} onClick={handleCancelTransfer} type="button">
                  Cancelar borrador
                </button>
              </>
            ) : null}
          </div>
        </form>

        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Detalle</p>
            <h2>Materiales de la transferencia</h2>
            {selectedTransfer ? (
              <p className="table-note">
                {selectedTransfer.folio} | {selectedTransfer.almacen_origen_nombre} hacia {selectedTransfer.almacen_destino_nombre}
              </p>
            ) : null}
          </div>

          {!selectedTransfer ? (
            <EmptyState
              title="Sin transferencia activa."
              note="Crea una transferencia o abre un borrador para agregar materiales."
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
                    Cantidad
                    <input
                      min="0.0001"
                      onChange={(event) =>
                        setDetailForm((current) => ({
                          ...current,
                          cantidad: normalizeDecimalInput(event.target.value),
                        }))
                      }
                      required
                      step="0.0001"
                      type="number"
                      value={detailForm.cantidad}
                    />
                  </label>

                  <label>
                    Costo snapshot
                    <input
                      min="0"
                      onChange={(event) =>
                        setDetailForm((current) => ({
                          ...current,
                          costo_unitario_snapshot: normalizeDecimalInput(event.target.value),
                        }))
                      }
                      placeholder="Opcional"
                      step="0.0001"
                      type="number"
                      value={detailForm.costo_unitario_snapshot}
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
                  title="Transferencia cerrada."
                  note="En esta fase no se permite editar ni revertir transferencias confirmadas o canceladas."
                />
              )}

              {selectedTransfer.details.length === 0 ? (
                <EmptyState
                  title="Sin materiales."
                  note="Agrega al menos un material para poder confirmar esta transferencia."
                />
              ) : (
                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>Material</th>
                        <th>Cantidad</th>
                        <th>Costo snapshot</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedTransfer.details.map((detail) => (
                        <tr key={detail.id}>
                          <td>{detail.material_sku}</td>
                          <td>
                            <strong>{detail.material_nombre}</strong>
                            <div className="table-note">{detail.material_unidad}</div>
                          </td>
                          <td>{formatNumber(detail.cantidad)}</td>
                          <td>{detail.costo_unitario_snapshot ? formatMoney(detail.costo_unitario_snapshot) : "-"}</td>
                          <td className="inventory-row-actions">
                            {selectedIsDraft ? (
                              <>
                                <button
                                  className="link-button"
                                  onClick={() =>
                                    setDetailForm({
                                      id: detail.id,
                                      material_id: detail.material_id,
                                      cantidad: String(detail.cantidad),
                                      costo_unitario_snapshot: detail.costo_unitario_snapshot
                                        ? String(detail.costo_unitario_snapshot)
                                        : "",
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
                              <span className="table-note">Solo lectura</span>
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
          <h2>Transferencias registradas</h2>
          <ResultMeta label="transferencias" loaded={transfers.length} total={transferMeta.total} />
        </div>

        <form className="inventory-filter-grid" onSubmit={applyFilters}>
          <label>
            Buscar
            <input
              onChange={(event) =>
                setTransferFilters((current) => ({ ...current, q: event.target.value }))
              }
              placeholder="Folio o notas"
              type="text"
              value={transferFilters.q}
            />
          </label>

          <label>
            Almacen origen
            <select
              onChange={(event) =>
                setTransferFilters((current) => ({ ...current, almacen_origen_id: event.target.value }))
              }
              value={transferFilters.almacen_origen_id}
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
            Almacen destino
            <select
              onChange={(event) =>
                setTransferFilters((current) => ({ ...current, almacen_destino_id: event.target.value }))
              }
              value={transferFilters.almacen_destino_id}
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
                setTransferFilters((current) => ({ ...current, estatus: event.target.value }))
              }
              value={transferFilters.estatus}
            >
              <option value="">Todos</option>
              <option value="borrador">Borrador</option>
              <option value="confirmada">Confirmada</option>
              <option value="cancelada">Cancelada</option>
            </select>
          </label>

          <label>
            Fecha desde
            <input
              onChange={(event) =>
                setTransferFilters((current) => ({ ...current, fecha_desde: event.target.value }))
              }
              type="datetime-local"
              value={transferFilters.fecha_desde}
            />
          </label>

          <label>
            Fecha hasta
            <input
              onChange={(event) =>
                setTransferFilters((current) => ({ ...current, fecha_hasta: event.target.value }))
              }
              type="datetime-local"
              value={transferFilters.fecha_hasta}
            />
          </label>

          <div className="inventory-actions">
            <button className="ghost-button" type="submit">
              Aplicar filtros
            </button>
            <button
              className="ghost-button"
              onClick={async () => {
                setTransferFilters(transferFilterDefaults);
                try {
                  await loadTransferList(transferFilterDefaults);
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

        {transfers.length === 0 ? (
          <EmptyState
            title="No hay transferencias."
            note="Crea una transferencia en borrador y agregale materiales."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Ruta</th>
                    <th>Estatus</th>
                    <th>Materiales</th>
                    <th>Fecha</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {transfers.map((transfer) => (
                    <tr key={transfer.id}>
                      <td>{transfer.folio}</td>
                      <td>
                        <strong>{transfer.almacen_origen_nombre}</strong>
                        <div className="table-note">hacia {transfer.almacen_destino_nombre}</div>
                      </td>
                      <td>
                        <span className={`status-badge ${transfer.estatus === "confirmada" ? "enabled" : "pending"}`}>
                          {transfer.estatus}
                        </span>
                      </td>
                      <td>{transfer.detalles_count}</td>
                      <td>{formatDateTime(transfer.created_at)}</td>
                      <td className="inventory-row-actions">
                        <button className="link-button" onClick={() => handleSelectTransfer(transfer.id)} type="button">
                          Ver detalle
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PaginationControls
              meta={transferMeta}
              onNext={() => handlePageChange(transferMeta.offset + transferMeta.limit)}
              onPrevious={() => handlePageChange(Math.max(0, transferMeta.offset - transferMeta.limit))}
            />
          </>
        )}
      </div>
    </div>
  );
}
