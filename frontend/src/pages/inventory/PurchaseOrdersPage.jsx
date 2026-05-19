import { useEffect, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import {
  addPurchaseOrderDetail,
  createPurchaseOrder,
  deletePurchaseOrderDetail,
  getMaterials,
  getPurchaseOrderDetail,
  getPurchaseOrders,
  getSuppliers,
  getWarehouses,
  issuePurchaseOrder,
  receivePurchaseOrder,
  updatePurchaseOrder,
  updatePurchaseOrderDetail,
} from "../../api/client";
import {
  DEFAULT_PAGE_SIZE,
  EmptyState,
  formatDateTime,
  formatMoney,
  formatNumber,
  normalizeDecimalInput,
  PaginationControls,
  ResultMeta,
} from "./shared";


const defaultFilters = {
  q: "",
  estatus: "",
  proveedor_id: "",
  almacen_destino_id: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};


export default function PurchaseOrdersPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [suppliers, setSuppliers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [orders, setOrders] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [form, setForm] = useState({
    id: "",
    folio: "",
    proveedor_id: "",
    almacen_destino_id: "",
    notas: "",
  });
  const [detailForm, setDetailForm] = useState({
    id: "",
    material_id: "",
    cantidad: "",
    costo_unitario: "",
  });
  const [receiveQuantities, setReceiveQuantities] = useState({});

  async function loadOptions() {
    const [supplierResponse, warehouseResponse, materialResponse] = await Promise.all([
      getSuppliers({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
      getWarehouses({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
      getMaterials({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
    ]);
    setSuppliers(supplierResponse.items);
    setWarehouses(warehouseResponse.items);
    setMaterials(materialResponse.items);
    return {
      supplierItems: supplierResponse.items,
      warehouseItems: warehouseResponse.items,
      materialItems: materialResponse.items,
    };
  }

  async function loadOrderList(nextFilters = filters) {
    const response = await getPurchaseOrders({ token, empresaId, filters: nextFilters });
    setOrders(response.items);
    setMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
  }

  async function loadOrderDocument(orderId) {
    const response = await getPurchaseOrderDetail({ orderId, token, empresaId });
    setSelectedOrder(response);
    setForm({
      id: response.id,
      folio: response.folio,
      proveedor_id: response.proveedor_id,
      almacen_destino_id: response.almacen_destino_id,
      notas: response.notas || "",
    });
    setReceiveQuantities({});
    return response;
  }

  function resetForm() {
    setForm({
      id: "",
      folio: "",
      proveedor_id: suppliers[0]?.id || "",
      almacen_destino_id: warehouses[0]?.id || "",
      notas: "",
    });
    setSelectedOrder(null);
    resetDetailForm();
    setReceiveQuantities({});
  }

  function resetDetailForm() {
    setDetailForm({
      id: "",
      material_id: materials[0]?.id || "",
      cantidad: "",
      costo_unitario: "",
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
        const options = await loadOptions();
        setForm((current) => ({
          ...current,
          proveedor_id: current.proveedor_id || options.supplierItems[0]?.id || "",
          almacen_destino_id: current.almacen_destino_id || options.warehouseItems[0]?.id || "",
        }));
        setDetailForm((current) => ({
          ...current,
          material_id: current.material_id || options.materialItems[0]?.id || "",
        }));
        await loadOrderList(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar las órdenes de compra.");
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
        proveedor_id: form.proveedor_id,
        almacen_destino_id: form.almacen_destino_id,
        notas: form.notas || null,
      };
      const response = form.id
        ? await updatePurchaseOrder({ orderId: form.id, token, empresaId, payload })
        : await createPurchaseOrder({ token, empresaId, payload });
      setSelectedOrder(response);
      setForm({
        id: response.id,
        folio: response.folio,
        proveedor_id: response.proveedor_id,
        almacen_destino_id: response.almacen_destino_id,
        notas: response.notas || "",
      });
      await loadOrderList(filters);
      setSuccess(form.id ? "Orden de compra actualizada." : "Orden de compra creada en borrador.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la orden de compra.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDetailSubmit(event) {
    event.preventDefault();
    if (!selectedOrder) {
      setError("Primero crea o selecciona una orden de compra.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        material_id: detailForm.material_id,
        cantidad: detailForm.cantidad,
        costo_unitario: detailForm.costo_unitario,
      };
      const response = detailForm.id
        ? await updatePurchaseOrderDetail({
            orderId: selectedOrder.id,
            detailId: detailForm.id,
            token,
            empresaId,
            payload,
          })
        : await addPurchaseOrderDetail({
            orderId: selectedOrder.id,
            token,
            empresaId,
            payload,
          });
      setSelectedOrder(response);
      await loadOrderList(filters);
      setSuccess(detailForm.id ? "Detalle actualizado." : "Detalle agregado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteDetail(detailId) {
    if (!selectedOrder) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await deletePurchaseOrderDetail({
        orderId: selectedOrder.id,
        detailId,
        token,
        empresaId,
      });
      setSelectedOrder(response);
      await loadOrderList(filters);
      setSuccess("Detalle eliminado.");
      resetDetailForm();
    } catch (requestError) {
      setError(requestError.message || "No se pudo eliminar el detalle.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleIssueOrder() {
    if (!selectedOrder) {
      return;
    }
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await issuePurchaseOrder({ orderId: selectedOrder.id, token, empresaId });
      setSelectedOrder(response);
      await loadOrderList(filters);
      setSuccess("Orden de compra emitida.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo emitir la orden de compra.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReceiveOrder() {
    if (!selectedOrder) {
      return;
    }

    const items = selectedOrder.details
      .map((detail) => ({
        detail_id: detail.id,
        cantidad: receiveQuantities[detail.id],
      }))
      .filter((item) => Number(item.cantidad) > 0);

    if (items.length === 0) {
      setError("Captura al menos una cantidad por recibir.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await receivePurchaseOrder({
        orderId: selectedOrder.id,
        token,
        empresaId,
        payload: { items },
      });
      setSelectedOrder(response);
      setReceiveQuantities({});
      await loadOrderList(filters);
      setSuccess("Recepción aplicada correctamente.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo recibir la orden de compra.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando órdenes de compra...</div>;
  }

  const selectedIsDraft = selectedOrder?.estatus === "borrador";
  const selectedCanReceive = ["emitida", "recibida_parcial"].includes(selectedOrder?.estatus || "");

  return (
    <div className="inventory-grid">
      <div className="inventory-kardex-stack">
        <form className="feature-card inventory-form-card" onSubmit={handleSubmit}>
          <div className="feature-header">
            <p className="eyebrow">Compras</p>
            <h2>{form.id ? "Editar orden de compra" : "Crear orden de compra"}</h2>
            <p>Emite compras y recibe inventario directamente en el almacén destino.</p>
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
              <input disabled type="text" value={selectedOrder?.estatus || "borrador"} />
            </label>

            <label>
              Proveedor
              <select
                disabled={Boolean(selectedOrder && !selectedIsDraft)}
                onChange={(event) => setForm((current) => ({ ...current, proveedor_id: event.target.value }))}
                required
                value={form.proveedor_id}
              >
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.nombre}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Almacén destino
              <select
                disabled={Boolean(selectedOrder && !selectedIsDraft)}
                onChange={(event) => setForm((current) => ({ ...current, almacen_destino_id: event.target.value }))}
                required
                value={form.almacen_destino_id}
              >
                {warehouses.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {warehouse.nombre} ({warehouse.codigo})
                  </option>
                ))}
              </select>
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
              {submitting ? "Guardando..." : form.id ? "Actualizar orden" : "Crear orden"}
            </button>
            <button className="ghost-button" onClick={resetForm} type="button">
              Nueva orden
            </button>
            {selectedOrder && selectedIsDraft ? (
              <button className="ghost-button" disabled={submitting} onClick={handleIssueOrder} type="button">
                Emitir
              </button>
            ) : null}
            {selectedOrder && selectedCanReceive ? (
              <button className="ghost-button" disabled={submitting} onClick={handleReceiveOrder} type="button">
                Recibir
              </button>
            ) : null}
          </div>
        </form>

        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Detalle</p>
            <h2>Renglones de la orden</h2>
            {selectedOrder ? (
              <p className="table-note">
                {selectedOrder.folio} | proveedor {selectedOrder.proveedor_nombre}
              </p>
            ) : null}
          </div>

          {!selectedOrder ? (
            <EmptyState
              title="Sin orden activa."
              note="Crea una orden o abre un borrador para agregar materiales."
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

                  <label>
                    Costo unitario
                    <input
                      min="0"
                      onChange={(event) =>
                        setDetailForm((current) => ({
                          ...current,
                          costo_unitario: normalizeDecimalInput(event.target.value),
                        }))
                      }
                      required
                      step="0.0001"
                      type="number"
                      value={detailForm.costo_unitario}
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
                  title="Orden cerrada para edición."
                  note="En esta fase solo se permite editar órdenes de compra en borrador."
                />
              )}

              {selectedOrder.details.length === 0 ? (
                <EmptyState
                  title="Sin materiales."
                  note="Agrega al menos un renglón antes de emitir la orden."
                />
              ) : (
                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>Material</th>
                        <th>Cantidad</th>
                        <th>Recibido</th>
                        <th>Costo</th>
                        <th>Total</th>
                        <th>Recibir ahora</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedOrder.details.map((detail) => {
                        const remaining = Number(detail.cantidad) - Number(detail.cantidad_recibida);
                        return (
                          <tr key={detail.id}>
                            <td>{detail.material_sku}</td>
                            <td>
                              <strong>{detail.material_nombre}</strong>
                              <div className="table-note">{detail.material_unidad}</div>
                            </td>
                            <td>{formatNumber(detail.cantidad)}</td>
                            <td>{formatNumber(detail.cantidad_recibida)}</td>
                            <td>{formatMoney(detail.costo_unitario)}</td>
                            <td>{formatMoney(detail.total_linea)}</td>
                            <td>
                              {selectedCanReceive && remaining > 0 ? (
                                <input
                                  min="0"
                                  onChange={(event) =>
                                    setReceiveQuantities((current) => ({
                                      ...current,
                                      [detail.id]: normalizeDecimalInput(event.target.value),
                                    }))
                                  }
                                  placeholder={`Pendiente ${formatNumber(remaining)}`}
                                  step="0.0001"
                                  type="number"
                                  value={receiveQuantities[detail.id] || ""}
                                />
                              ) : (
                                <span className="table-note">Sin recepción</span>
                              )}
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
                                        cantidad: String(detail.cantidad),
                                        costo_unitario: String(detail.costo_unitario),
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
                                <span className="table-note">
                                  {remaining > 0 ? "Pendiente de recibir" : "Completo"}
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {selectedOrder ? (
                <div className="module-board">
                  <article className="mini-card">
                    <span className="eyebrow">Subtotal</span>
                    <strong>{formatMoney(selectedOrder.subtotal)}</strong>
                  </article>
                  <article className="mini-card">
                    <span className="eyebrow">Impuestos</span>
                    <strong>{formatMoney(selectedOrder.impuesto_total)}</strong>
                  </article>
                  <article className="mini-card">
                    <span className="eyebrow">Total</span>
                    <strong>{formatMoney(selectedOrder.total)}</strong>
                  </article>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>

      <div className="feature-card inventory-table-card">
        <div className="feature-header">
          <p className="eyebrow">Listado</p>
          <h2>Órdenes de compra registradas</h2>
          <ResultMeta label="órdenes" loaded={orders.length} total={meta.total} />
        </div>

        <form
          className="inventory-filter-grid"
          onSubmit={async (event) => {
            event.preventDefault();
            const nextFilters = { ...filters, offset: 0 };
            setFilters(nextFilters);
            try {
              await loadOrderList(nextFilters);
            } catch (requestError) {
              setError(requestError.message || "No se pudieron filtrar las órdenes.");
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
              <option value="emitida">Emitida</option>
              <option value="recibida_parcial">Recibida parcial</option>
              <option value="recibida">Recibida</option>
              <option value="cancelada">Cancelada</option>
            </select>
          </label>

          <label>
            Proveedor
            <select
              onChange={(event) => setFilters((current) => ({ ...current, proveedor_id: event.target.value }))}
              value={filters.proveedor_id}
            >
              <option value="">Todos</option>
              {suppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.nombre}
                </option>
              ))}
            </select>
          </label>

          <label>
            Almacén destino
            <select
              onChange={(event) => setFilters((current) => ({ ...current, almacen_destino_id: event.target.value }))}
              value={filters.almacen_destino_id}
            >
              <option value="">Todos</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.nombre} ({warehouse.codigo})
                </option>
              ))}
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
                  await loadOrderList(defaultFilters);
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
                  await loadOrderList(filters);
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

        {orders.length === 0 ? (
          <EmptyState
            title="No hay órdenes de compra."
            note="Crea la primera orden para comenzar a recibir inventario."
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Proveedor</th>
                    <th>Almacén</th>
                    <th>Estatus</th>
                    <th>Total</th>
                    <th>Fecha</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id}>
                      <td>{order.folio}</td>
                      <td>{order.proveedor_nombre}</td>
                      <td>{order.almacen_destino_nombre}</td>
                      <td>
                        <span className={`status-badge ${order.estatus === "recibida" ? "enabled" : "pending"}`}>
                          {order.estatus}
                        </span>
                      </td>
                      <td>{formatMoney(order.total)}</td>
                      <td>{formatDateTime(order.created_at)}</td>
                      <td className="inventory-row-actions">
                        <button className="link-button" onClick={() => loadOrderDocument(order.id)} type="button">
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
                  await loadOrderList(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadOrderList(nextFilters);
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
