import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import {
  addRequisitionDetail,
  approveRequisition,
  cancelRequisition,
  createRequisition,
  deleteRequisitionDetail,
  getMaterials,
  getRequisitionDetail,
  getRequisitions,
  rejectRequisition,
  submitRequisition,
  updateRequisition,
  updateRequisitionDetail,
} from "../../api/client";
import {
  DEFAULT_PAGE_SIZE,
  EmptyState,
  formatDateTime,
  formatNumber,
  normalizeDecimalInput,
  PaginationControls,
  ResultMeta,
} from "./shared";


const defaultFilters = {
  q: "",
  estatus: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


export default function RequisitionsPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [materials, setMaterials] = useState([]);
  const [requisitions, setRequisitions] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [selectedRequisition, setSelectedRequisition] = useState(null);
  const [form, setForm] = useState({
    id: "",
    folio: "",
    notas: "",
  });
  const [detailForm, setDetailForm] = useState({
    id: "",
    material_id: "",
    cantidad: "",
    notas: "",
  });

  async function loadMaterialsOptions() {
    const response = await getMaterials({
      token,
      empresaId,
      filters: { activo: true, limit: 200, offset: 0 },
    });
    setMaterials(response.items);
    return response.items;
  }

  async function loadRequisitionList(nextFilters = filters) {
    const response = await getRequisitions({ token, empresaId, filters: nextFilters });
    setRequisitions(response.items);
    setMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
  }

  async function loadRequisitionDocument(requisitionId) {
    const response = await getRequisitionDetail({ requisitionId, token, empresaId });
    setSelectedRequisition(response);
    setForm({
      id: response.id,
      folio: response.folio,
      notas: response.notas || "",
    });
    return response;
  }

  function resetForm() {
    setForm({
      id: "",
      folio: "",
      notas: "",
    });
    setSelectedRequisition(null);
    resetDetailForm();
  }

  function resetDetailForm() {
    setDetailForm({
      id: "",
      material_id: materials[0]?.id || "",
      cantidad: "",
      notas: "",
    });
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const materialItems = await loadMaterialsOptions();
        if (materialItems.length > 0) {
          setDetailForm((current) => ({ ...current, material_id: current.material_id || materialItems[0].id }));
        }
        await loadRequisitionList(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar las requisiciones.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        folio: form.folio || null,
        notas: form.notas || null,
      };
      const response = form.id
        ? await updateRequisition({ requisitionId: form.id, token, empresaId, payload })
        : await createRequisition({ token, empresaId, payload });
      setSelectedRequisition(response);
      setForm({
        id: response.id,
        folio: response.folio,
        notas: response.notas || "",
      });
      await loadRequisitionList(filters);
      setSuccess(form.id ? "Requisición actualizada." : "Requisición creada en borrador.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la requisición.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDetailSubmit(event) {
    event.preventDefault();
    if (!selectedRequisition) {
      setError("Primero crea o selecciona una requisición.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        material_id: detailForm.material_id,
        cantidad: detailForm.cantidad,
        notas: detailForm.notas || null,
      };
      const response = detailForm.id
        ? await updateRequisitionDetail({
            requisitionId: selectedRequisition.id,
            detailId: detailForm.id,
            token,
            empresaId,
            payload,
          })
        : await addRequisitionDetail({
            requisitionId: selectedRequisition.id,
            token,
            empresaId,
            payload,
          });
      setSelectedRequisition(response);
      await loadRequisitionList(filters);
      setSuccess(detailForm.id ? "Detalle actualizado." : "Detalle agregado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteDetail(detailId) {
    if (!selectedRequisition) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await deleteRequisitionDetail({
        requisitionId: selectedRequisition.id,
        detailId,
        token,
        empresaId,
      });
      setSelectedRequisition(response);
      await loadRequisitionList(filters);
      setSuccess("Detalle eliminado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo eliminar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStatusAction(action) {
    if (!selectedRequisition) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const handler =
        action === "submit"
          ? submitRequisition
          : action === "approve"
            ? approveRequisition
            : action === "reject"
              ? rejectRequisition
              : cancelRequisition;

      const response = await handler({
        requisitionId: selectedRequisition.id,
        token,
        empresaId,
      });
      setSelectedRequisition(response);
      await loadRequisitionList(filters);
      setSuccess(
        action === "submit"
          ? "Requisición enviada."
          : action === "approve"
            ? "Requisición aprobada."
            : action === "reject"
              ? "Requisición rechazada."
              : "Requisición cancelada.",
      );
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar el estatus.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando requisiciones...</div>;
  }

  const selectedIsDraft = selectedRequisition?.estatus === "borrador";
  const selectedIsSent = selectedRequisition?.estatus === "enviada";

  return (
    <div className="inventory-grid">
      <div className="inventory-kardex-stack">
        <form className="feature-card inventory-form-card" onSubmit={handleSubmit}>
          <div className="feature-header">
            <p className="eyebrow">Compras internas</p>
            <h2>{form.id ? "Editar requisición" : "Crear requisición"}</h2>
            <p>Documenta solicitudes internas antes de convertirlas en compra o surtido.</p>
          </div>

          {error ? <p className="form-error">{error}</p> : null}
          {success ? <p className="form-success">{success}</p> : null}

          <div className="inventory-form-grid">
            <label>
              Folio
              <input
                onChange={(event) => setForm((current) => ({ ...current, folio: event.target.value.toUpperCase() }))}
                placeholder="Auto"
                type="text"
                value={form.folio}
              />
            </label>

            <label>
              Estatus
              <input disabled type="text" value={selectedRequisition?.estatus || "borrador"} />
            </label>

            <label className="inventory-form-span-2">
              Notas
              <textarea
                onChange={(event) => setForm((current) => ({ ...current, notas: event.target.value }))}
                rows={3}
                value={form.notas}
              />
            </label>
          </div>

          <div className="inventory-actions">
            <button className="primary-button" disabled={submitting} type="submit">
              {submitting ? "Guardando..." : form.id ? "Actualizar requisición" : "Crear requisición"}
            </button>
            <button className="ghost-button" onClick={resetForm} type="button">
              Nueva requisición
            </button>
            {selectedRequisition && selectedIsDraft ? (
              <button className="ghost-button" disabled={submitting} onClick={() => handleStatusAction("submit")} type="button">
                Enviar
              </button>
            ) : null}
            {selectedRequisition && selectedIsSent ? (
              <>
                <button className="ghost-button" disabled={submitting} onClick={() => handleStatusAction("approve")} type="button">
                  Aprobar
                </button>
                <button className="ghost-button" disabled={submitting} onClick={() => handleStatusAction("reject")} type="button">
                  Rechazar
                </button>
              </>
            ) : null}
            {selectedRequisition && ["borrador", "enviada", "aprobada"].includes(selectedRequisition.estatus) ? (
              <button className="ghost-button" disabled={submitting} onClick={() => handleStatusAction("cancel")} type="button">
                Cancelar
              </button>
            ) : null}
          </div>
        </form>

        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Detalle</p>
            <h2>Materiales solicitados</h2>
            {selectedRequisition ? <p className="table-note">{selectedRequisition.folio}</p> : null}
          </div>

          {!selectedRequisition ? (
            <EmptyState
              title="Sin requisición activa."
              note="Crea una requisición o abre un borrador para agregar materiales."
            />
          ) : (
            <>
              {selectedIsDraft ? (
                <form className="inventory-filter-grid" onSubmit={handleDetailSubmit}>
                  <label>
                    Material
                    <select
                      onChange={(event) => setDetailForm((current) => ({ ...current, material_id: event.target.value }))}
                      required
                      value={detailForm.material_id}
                    >
                      {materials.map((material) => (
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

                  <label className="inventory-form-span-2">
                    Notas
                    <textarea
                      onChange={(event) => setDetailForm((current) => ({ ...current, notas: event.target.value }))}
                      rows={2}
                      value={detailForm.notas}
                    />
                  </label>

                  <div className="inventory-actions">
                    <button className="ghost-button" disabled={submitting} type="submit">
                      {detailForm.id ? "Actualizar detalle" : "Agregar material"}
                    </button>
                    {detailForm.id ? (
                      <button className="ghost-button" onClick={resetDetailForm} type="button">
                        Cancelar edición
                      </button>
                    ) : null}
                  </div>
                </form>
              ) : (
                <EmptyState
                  title="Requisición cerrada."
                  note="En esta fase solo se permite editar requisiciones en borrador."
                />
              )}

              {selectedRequisition.details.length === 0 ? (
                <EmptyState
                  title="Sin materiales."
                  note="Agrega al menos un material antes de enviar la requisición."
                />
              ) : (
                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>Material</th>
                        <th>Cantidad</th>
                        <th>Notas</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRequisition.details.map((detail) => (
                        <tr key={detail.id}>
                          <td>{detail.material_sku}</td>
                          <td>
                            <strong>{detail.material_nombre}</strong>
                            <div className="table-note">{detail.material_unidad}</div>
                          </td>
                          <td>{formatNumber(detail.cantidad)}</td>
                          <td>{detail.notas || "Sin notas"}</td>
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
                                      notas: detail.notas || "",
                                    })
                                  }
                                  type="button"
                                >
                                  Editar
                                </button>
                                <button className="link-button" onClick={() => handleDeleteDetail(detail.id)} type="button">
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
          <h2>Requisiciones registradas</h2>
          <ResultMeta label="requisiciones" loaded={requisitions.length} total={meta.total} />
        </div>

        <form
          className="inventory-filter-grid"
          onSubmit={async (event) => {
            event.preventDefault();
            const nextFilters = { ...filters, offset: 0 };
            setFilters(nextFilters);
            try {
              await loadRequisitionList(nextFilters);
            } catch (requestError) {
              setError(requestError.message || "No se pudieron filtrar las requisiciones.");
            }
          }}
        >
          <label>
            Buscar
            <input
              onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
              placeholder="Folio o notas"
              type="text"
              value={filters.q}
            />
          </label>

          <label>
            Estatus
            <select
              onChange={(event) => setFilters((current) => ({ ...current, estatus: event.target.value }))}
              value={filters.estatus}
            >
              <option value="">Todos</option>
              <option value="borrador">Borrador</option>
              <option value="enviada">Enviada</option>
              <option value="aprobada">Aprobada</option>
              <option value="rechazada">Rechazada</option>
              <option value="surtida">Surtida</option>
              <option value="cancelada">Cancelada</option>
            </select>
          </label>

          <div className="inventory-actions">
            <button className="ghost-button" type="submit">
              Aplicar filtros
            </button>
            <button
              className="ghost-button"
              onClick={async () => {
                setFilters(defaultFilters);
                try {
                  await loadRequisitionList(defaultFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron reiniciar los filtros.");
                }
              }}
              type="button"
            >
              Limpiar
            </button>
            <button
              className="ghost-button"
              onClick={async () => {
                try {
                  await loadRequisitionList(filters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo actualizar el listado.");
                }
              }}
              type="button"
            >
              Actualizar
            </button>
          </div>
        </form>

        {requisitions.length === 0 ? (
          <EmptyState
            title="No hay requisiciones."
            note="Crea la primera requisición para comenzar el flujo interno de compras."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Solicitante</th>
                    <th>Estatus</th>
                    <th>Detalles</th>
                    <th>Fecha</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {requisitions.map((requisition) => (
                    <tr key={requisition.id}>
                      <td>{requisition.folio}</td>
                      <td>{requisition.solicitante_nombre}</td>
                      <td>
                        <span className={`status-badge ${requisition.estatus === "aprobada" ? "enabled" : "pending"}`}>
                          {requisition.estatus}
                        </span>
                      </td>
                      <td>{requisition.details_count}</td>
                      <td>{formatDateTime(requisition.created_at)}</td>
                      <td className="inventory-row-actions">
                        <button className="link-button" onClick={() => loadRequisitionDocument(requisition.id)} type="button">
                          Ver detalle
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PaginationControls
              meta={meta}
              onNext={async () => {
                const nextFilters = { ...filters, offset: meta.offset + meta.limit };
                setFilters(nextFilters);
                try {
                  await loadRequisitionList(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadRequisitionList(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}
