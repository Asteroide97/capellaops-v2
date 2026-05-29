import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  BadgeCheck,
  ClipboardList,
  DollarSign,
  Eye,
  PackageCheck,
  Pencil,
  Plus,
  Send,
  Truck,
  Warehouse,
  XCircle,
} from "lucide-react";

import { useAuth } from "../../auth/AuthContext";
import {
  addPurchaseOrderDetail,
  cancelPurchaseOrder,
  createPurchaseOrder,
  deletePurchaseOrderDetail,
  getMaterials,
  getPurchaseOrderDetail,
  getSuppliers,
  getWarehouses,
  issuePurchaseOrder,
  listPurchaseOrders,
  receivePurchaseOrder,
  updatePurchaseOrder,
  updatePurchaseOrderDetail,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  DEFAULT_PAGE_SIZE,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  ModalShell,
  MetricCard,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  formatDate,
  formatDateTime,
  formatMoney,
  formatNumber,
  normalizeDecimalInput,
  safeDisplayText,
} from "./shared";


const defaultFilters = {
  q: "",
  proveedor_id: "",
  almacen_destino_id: "",
  estatus: "",
  fecha_desde: "",
  fecha_hasta: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultEditorForm = {
  id: "",
  folio: "",
  proveedor_id: "",
  almacen_destino_id: "",
  notas: "",
  requisicion_id: "",
  requisicion_folio: "",
};

const defaultReceiveForm = {
  documento_referencia: "",
  notas: "",
  cantidades: {},
};


function statusLabel(value) {
  const map = {
    borrador: "Borrador",
    emitida: "Emitida",
    recibida_parcial: "Recepción parcial",
    recibida: "Recibida",
    cancelada: "Cancelada",
  };
  return map[value] ?? value ?? "—";
}


function statusTone(value) {
  switch (value) {
    case "emitida":
      return "info";
    case "recibida_parcial":
      return "warning";
    case "recibida":
      return "success";
    case "cancelada":
      return "danger";
    case "borrador":
    default:
      return "neutral";
  }
}


function lineStatusLabel(value) {
  const map = {
    pendiente: "Pendiente",
    parcial: "Parcial",
    completa: "Completa",
  };
  return map[value] ?? value ?? "—";
}


function canEditOrder(order) {
  return order?.estatus === "borrador";
}


function canIssueOrder(order) {
  return order?.estatus === "borrador";
}


function canReceiveOrder(order) {
  return ["emitida", "recibida_parcial"].includes(order?.estatus || "");
}


function canCancelOrder(order) {
  return ["borrador", "emitida"].includes(order?.estatus || "") && Number(order?.cantidad_total_recibida || 0) <= 0;
}


function buildLineFromMaterial(material) {
  return {
    localKey: `new-${material.id}-${crypto.randomUUID()}`,
    id: "",
    material_id: material.id,
    material_sku: material.sku,
    material_nombre: material.nombre,
    material_unidad: material.unidad,
    cantidad: "1",
    costo_unitario: String(material.costo_promedio_actual ?? material.costo_unitario ?? 0),
  };
}


function buildLineFromDetail(detail) {
  return {
    localKey: detail.id,
    id: detail.id,
    material_id: detail.material_id,
    material_sku: detail.material_sku,
    material_nombre: detail.material_nombre,
    material_unidad: detail.material_unidad,
    cantidad: String(detail.cantidad),
    costo_unitario: String(detail.costo_unitario),
  };
}


function calculateLineSubtotal(line) {
  return Number(line.cantidad || 0) * Number(line.costo_unitario || 0);
}


function buildSuccessMessage(mode, order) {
  if (mode === "issue") {
    return `OC ${order.folio} guardada y emitida.`;
  }
  return `OC ${order.folio} guardada en borrador.`;
}


export default function PurchaseOrdersPage() {
  const { token, empresaId } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

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
  const [detailOpen, setDetailOpen] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [editorForm, setEditorForm] = useState(defaultEditorForm);
  const [editorLines, setEditorLines] = useState([]);
  const [materialSearch, setMaterialSearch] = useState("");
  const [materialToAddId, setMaterialToAddId] = useState("");
  const [receiveForm, setReceiveForm] = useState(defaultReceiveForm);

  async function loadOptions() {
    const [supplierResponse, warehouseResponse, materialResponse] = await Promise.all([
      getSuppliers({ token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
      getWarehouses({ token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
      getMaterials({ token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
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
    const response = await listPurchaseOrders({ token, empresaId, filters: nextFilters });
    setOrders(response.items);
    setMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    return response;
  }

  async function loadOrderDocument(orderId) {
    const response = await getPurchaseOrderDetail({ orderId, token, empresaId });
    setSelectedOrder(response);
    return response;
  }

  function resetEditorForm(defaultSupplierId = suppliers[0]?.id || "", defaultWarehouseId = warehouses[0]?.id || "") {
    setEditorForm({
      ...defaultEditorForm,
      proveedor_id: defaultSupplierId,
      almacen_destino_id: defaultWarehouseId,
    });
    setEditorLines([]);
    setMaterialSearch("");
    setMaterialToAddId(materials[0]?.id || "");
  }

  function openCreateModal() {
    resetEditorForm();
    setEditorOpen(true);
    setError("");
    setSuccess("");
  }

  function loadEditorFromOrder(order) {
    setEditorForm({
      id: order.id,
      folio: order.folio,
      proveedor_id: order.proveedor_id,
      almacen_destino_id: order.almacen_destino_id,
      notas: order.notas || "",
      requisicion_id: order.requisicion_id || "",
      requisicion_folio: order.requisicion_folio || "",
    });
    setEditorLines(order.details.map(buildLineFromDetail));
    setMaterialSearch("");
    setMaterialToAddId(materials[0]?.id || "");
    setEditorOpen(true);
  }

  async function openEditModal(orderId) {
    setSubmitting(true);
    setError("");
    try {
      const order = await loadOrderDocument(orderId);
      loadEditorFromOrder(order);
    } catch (requestError) {
      setError(requestError.message || "No se pudo abrir la orden de compra.");
    } finally {
      setSubmitting(false);
    }
  }

  async function openDetailModal(orderId) {
    setSubmitting(true);
    setError("");
    try {
      await loadOrderDocument(orderId);
      setDetailOpen(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle de la orden.");
    } finally {
      setSubmitting(false);
    }
  }

  function openReceiveModal(order) {
    const cantidades = {};
    for (const detail of order.details) {
      const pendiente = Number(detail.cantidad_pendiente || 0);
      if (pendiente > 0) {
        cantidades[detail.id] = String(pendiente);
      }
    }
    setReceiveForm({
      ...defaultReceiveForm,
      cantidades,
    });
    setDetailOpen(false);
    setReceiveOpen(true);
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
        resetEditorForm(options.supplierItems[0]?.id || "", options.warehouseItems[0]?.id || "");
        await loadOrderList(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar las órdenes de compra.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  useEffect(() => {
    async function handleNavigationState() {
      const openOrderId = location.state?.openOrderId;
      const successMessage = location.state?.successMessage;
      if (!openOrderId || !token || !empresaId || loading) {
        return;
      }

      try {
        await loadOrderDocument(openOrderId);
        setDetailOpen(true);
        if (successMessage) {
          setSuccess(successMessage);
        }
      } catch (requestError) {
        setError(requestError.message || "No se pudo abrir la orden vinculada.");
      } finally {
        navigate(location.pathname, { replace: true, state: null });
      }
    }

    handleNavigationState();
  }, [location.pathname, location.state, token, empresaId, loading, navigate]);

  const filteredMaterials = useMemo(() => {
    const normalizedQuery = materialSearch.trim().toLowerCase();
    if (!normalizedQuery) {
      return materials;
    }
    return materials.filter((material) =>
      [material.nombre, material.sku, material.codigo_barras, material.categoria]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedQuery)),
    );
  }, [materials, materialSearch]);

  const previewTotals = useMemo(() => {
    const subtotal = editorLines.reduce((sum, line) => sum + calculateLineSubtotal(line), 0);
    return {
      subtotal,
      total: subtotal,
    };
  }, [editorLines]);

  const kpis = useMemo(() => {
    return orders.reduce(
      (accumulator, order) => {
        accumulator.total += Number(order.total || 0);
        accumulator.pendiente += Number(order.cantidad_total_pendiente || 0);
        if (order.estatus === "borrador") accumulator.borradores += 1;
        if (order.estatus === "emitida") accumulator.emitidas += 1;
        if (order.estatus === "recibida_parcial") accumulator.parciales += 1;
        if (order.estatus === "recibida") accumulator.recibidas += 1;
        return accumulator;
      },
      {
        borradores: 0,
        emitidas: 0,
        parciales: 0,
        recibidas: 0,
        total: 0,
        pendiente: 0,
      },
    );
  }, [orders]);

  const receiveSummary = useMemo(() => {
    return Object.entries(receiveForm.cantidades).reduce(
      (accumulator, [detailId, quantityValue]) => {
        const quantity = Number(quantityValue || 0);
        if (quantity <= 0 || !selectedOrder) {
          return accumulator;
        }
        const detail = selectedOrder.details.find((item) => item.id === detailId);
        if (!detail) {
          return accumulator;
        }
        accumulator.unidades += quantity;
        accumulator.total += quantity * Number(detail.costo_unitario || 0);
        return accumulator;
      },
      { unidades: 0, total: 0 },
    );
  }, [receiveForm.cantidades, selectedOrder]);

  async function applyFilters(event) {
    event?.preventDefault?.();
    const nextFilters = { ...filters, offset: 0 };
    setFilters(nextFilters);
    setError("");
    try {
      await loadOrderList(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar los filtros.");
    }
  }

  async function resetFilters() {
    setFilters(defaultFilters);
    setError("");
    try {
      await loadOrderList(defaultFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron reiniciar los filtros.");
    }
  }

  async function refreshList() {
    setError("");
    try {
      await loadOrderList(filters);
      if (selectedOrder?.id) {
        await loadOrderDocument(selectedOrder.id);
      }
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el listado.");
    }
  }

  function addLineToEditor() {
    const material = materials.find((item) => item.id === materialToAddId);
    if (!material) {
      setError("Selecciona un material para agregarlo a la orden.");
      return;
    }
    if (editorLines.some((line) => line.material_id === material.id)) {
      setError("Ese material ya está agregado. Ajusta la cantidad en el renglón existente.");
      return;
    }
    setEditorLines((current) => [...current, buildLineFromMaterial(material)]);
    setError("");
  }

  function updateEditorLine(localKey, key, value) {
    setEditorLines((current) =>
      current.map((line) =>
        line.localKey === localKey
          ? {
              ...line,
              [key]: value,
            }
          : line,
      ),
    );
  }

  function removeEditorLine(localKey) {
    setEditorLines((current) => current.filter((line) => line.localKey !== localKey));
  }

  async function handleSaveOrder(mode = "draft") {
    if (!editorForm.proveedor_id) {
      setError("Selecciona un proveedor.");
      return;
    }
    if (!editorForm.almacen_destino_id) {
      setError("Selecciona un almacén destino.");
      return;
    }
    if (mode === "issue" && editorLines.length === 0) {
      setError("Agrega al menos un renglón antes de emitir la orden.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    let workingOrderId = editorForm.id || "";

    try {
      const headerPayload = {
        folio: editorForm.folio || null,
        proveedor_id: editorForm.proveedor_id,
        almacen_destino_id: editorForm.almacen_destino_id,
        notas: editorForm.notas || null,
      };

      const headerResponse = editorForm.id
        ? await updatePurchaseOrder({ orderId: editorForm.id, token, empresaId, payload: headerPayload })
        : await createPurchaseOrder({ token, empresaId, payload: headerPayload });

      workingOrderId = headerResponse.id;
      const existingDetails = (selectedOrder?.id === headerResponse.id ? selectedOrder.details : []).map((detail) => detail.id);
      const nextDetailIds = new Set(editorLines.filter((line) => line.id).map((line) => line.id));

      for (const existingId of existingDetails) {
        if (!nextDetailIds.has(existingId)) {
          await deletePurchaseOrderDetail({
            orderId: headerResponse.id,
            detailId: existingId,
            token,
            empresaId,
          });
        }
      }

      for (const line of editorLines) {
        const payload = {
          material_id: line.material_id,
          cantidad: Number(line.cantidad || 0),
          costo_unitario: Number(line.costo_unitario || 0),
        };
        if (line.id) {
          await updatePurchaseOrderDetail({
            orderId: headerResponse.id,
            detailId: line.id,
            token,
            empresaId,
            payload,
          });
        } else {
          await addPurchaseOrderDetail({
            orderId: headerResponse.id,
            token,
            empresaId,
            payload,
          });
        }
      }

      let finalOrder = await getPurchaseOrderDetail({ orderId: headerResponse.id, token, empresaId });
      if (mode === "issue") {
        finalOrder = await issuePurchaseOrder({ orderId: headerResponse.id, token, empresaId });
      }

      await loadOrderList(filters);
      setSelectedOrder(finalOrder);
      setDetailOpen(true);
      setEditorOpen(false);
      resetEditorForm();
      setSuccess(buildSuccessMessage(mode, finalOrder));
    } catch (requestError) {
      if (workingOrderId) {
        try {
          const currentOrder = await loadOrderDocument(workingOrderId);
          setDetailOpen(true);
          setEditorOpen(false);
          setError(
            `${requestError.message || "No se pudo guardar la orden de compra."} Revisa la orden ${currentOrder.folio} antes de continuar.`,
          );
        } catch {
          setError(requestError.message || "No se pudo guardar la orden de compra.");
        }
      } else {
        setError(requestError.message || "No se pudo guardar la orden de compra.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEmitOrder(orderId) {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await issuePurchaseOrder({ orderId, token, empresaId });
      setSelectedOrder(response);
      setDetailOpen(true);
      await loadOrderList(filters);
      setSuccess(`OC ${response.folio} emitida correctamente.`);
    } catch (requestError) {
      setError(requestError.message || "No se pudo emitir la orden de compra.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancelOrder(orderId) {
    if (!window.confirm("La orden quedará cancelada y ya no podrá emitirse ni recibirse. ¿Continuar?")) {
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const response = await cancelPurchaseOrder({ orderId, token, empresaId });
      setSelectedOrder(response);
      setDetailOpen(true);
      await loadOrderList(filters);
      setSuccess(`OC ${response.folio} cancelada.`);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cancelar la orden de compra.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReceiveOrder() {
    if (!selectedOrder) {
      return;
    }

    const items = Object.entries(receiveForm.cantidades)
      .map(([detail_id, cantidad]) => ({ detail_id, cantidad: Number(cantidad || 0) }))
      .filter((item) => item.cantidad > 0);

    if (items.length === 0) {
      setError("Captura al menos una cantidad válida por recibir.");
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
        payload: {
          documento_referencia: receiveForm.documento_referencia || null,
          notas: receiveForm.notas || null,
          items,
        },
      });
      setSelectedOrder(response);
      setReceiveOpen(false);
      setDetailOpen(true);
      await loadOrderList(filters);
      setSuccess("Recepción registrada e inventario actualizado.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar la recepción.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando órdenes de compra...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        actions={
          <ActionButton icon={<Plus size={16} />} onClick={openCreateModal} size="sm" tone="primary" type="button">
            Nueva OC
          </ActionButton>
        }
        eyebrow="Inventario operativo"
        subtitle="Emisión y recepción de compras."
        title="Órdenes de compra"
      />

      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>Error operativo</strong>
          <p>{error}</p>
        </div>
      ) : null}
      {success ? (
        <div className="inventory-form-note inventory-form-note-success">
          <strong>Operación completada</strong>
          <p>{success}</p>
        </div>
      ) : null}

      <section className="inventory-metric-grid inventory-metric-grid-5">
        <MetricCard icon={<ClipboardList size={16} />} label="Borradores" meta="En resultados" tone="neutral" value={kpis.borradores} />
        <MetricCard icon={<Send size={16} />} label="Emitidas" meta="Pendientes de recibir" tone="info" value={kpis.emitidas} />
        <MetricCard icon={<PackageCheck size={16} />} label="Parciales" meta="Recepciones incompletas" tone="warning" value={kpis.parciales} />
        <MetricCard icon={<BadgeCheck size={16} />} label="Recibidas" meta="Cerradas por recepción" tone="success" value={kpis.recibidas} />
        <MetricCard icon={<DollarSign size={16} />} label="Total comprado" meta={`${formatNumber(kpis.pendiente)} unidades pendientes`} tone="success" value={formatMoney(kpis.total)} />
      </section>

      <FilterCard title="Filtros de órdenes" subtitle="Consulta por proveedor, almacén, estatus o rango de fechas.">
        <form className="inventory-filter-grid inventory-filter-grid-wide" onSubmit={applyFilters}>
          <SearchInput
            label="Buscar orden"
            onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
            placeholder="Folio o notas"
            value={filters.q}
          />

          <Field label="Proveedor">
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
          </Field>

          <Field label="Almacén destino">
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
          </Field>

          <Field label="Estatus">
            <select
              onChange={(event) => setFilters((current) => ({ ...current, estatus: event.target.value }))}
              value={filters.estatus}
            >
              <option value="">Todos</option>
              <option value="borrador">Borrador</option>
              <option value="emitida">Emitida</option>
              <option value="recibida_parcial">Recepción parcial</option>
              <option value="recibida">Recibida</option>
              <option value="cancelada">Cancelada</option>
            </select>
          </Field>

          <Field label="Fecha desde">
            <input
              onChange={(event) => setFilters((current) => ({ ...current, fecha_desde: event.target.value }))}
              type="date"
              value={filters.fecha_desde}
            />
          </Field>

          <Field label="Fecha hasta">
            <input
              onChange={(event) => setFilters((current) => ({ ...current, fecha_hasta: event.target.value }))}
              type="date"
              value={filters.fecha_hasta}
            />
          </Field>

          <div className="inventory-actions">
            <ActionButton icon={<Eye size={16} />} size="sm" tone="primary" type="submit">
              Aplicar filtros
            </ActionButton>
            <ActionButton onClick={resetFilters} size="sm" type="button">
              Limpiar
            </ActionButton>
            <ActionButton onClick={refreshList} size="sm" type="button">
              Actualizar
            </ActionButton>
          </div>
        </form>
      </FilterCard>

      <DataCard
        actions={<ResultMeta label="órdenes" loaded={orders.length} total={meta.total} />}
        subtitle="Borradores, emisión y recepción conectada con Inventario."
        title="Órdenes registradas"
      >
        {orders.length === 0 ? (
          <EmptyState
            action={
              <ActionButton icon={<Plus size={16} />} onClick={openCreateModal} size="sm" tone="primary" type="button">
                Nueva OC
              </ActionButton>
            }
            note="Crea la primera orden para comenzar a recibir inventario."
            title="No hay órdenes de compra."
          />
        ) : (
          <>
            <DataTable
              columns={[
                { key: "folio", label: "Folio" },
                { key: "proveedor", label: "Proveedor" },
                { key: "almacen", label: "Almacén destino" },
                { key: "estatus", label: "Estatus" },
                { key: "renglones", label: "Renglones" },
                { key: "total", label: "Total" },
                { key: "recibido", label: "Recibido" },
                { key: "pendiente", label: "Pendiente" },
                { key: "fecha", label: "Fecha" },
                { key: "acciones", label: "Acciones" },
              ]}
            >
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td>
                      <div className="inventory-cell-main">{order.folio}</div>
                      <div className="inventory-cell-sub">{order.requisicion_folio ? `Req. ${order.requisicion_folio}` : "Manual"}</div>
                    </td>
                    <td>
                      <div className="inventory-cell-main">{order.proveedor_nombre}</div>
                      <div className="inventory-cell-sub">{order.notas || "Sin notas"}</div>
                    </td>
                    <td>{order.almacen_destino_nombre}</td>
                    <td>
                      <StatusBadge tone={statusTone(order.estatus)}>{statusLabel(order.estatus)}</StatusBadge>
                    </td>
                    <td>{formatNumber(order.cantidad_renglones)}</td>
                    <td>{formatMoney(order.total)}</td>
                    <td>{formatNumber(order.cantidad_total_recibida)}</td>
                    <td>{formatNumber(order.cantidad_total_pendiente)}</td>
                    <td>{formatDateTime(order.created_at)}</td>
                    <td className="inventory-row-actions">
                      <button className="link-button" onClick={() => openDetailModal(order.id)} type="button">
                        Ver detalle
                      </button>
                      {canEditOrder(order) ? (
                        <button className="link-button" onClick={() => openEditModal(order.id)} type="button">
                          Editar
                        </button>
                      ) : null}
                      {canIssueOrder(order) ? (
                        <button className="link-button" onClick={() => handleEmitOrder(order.id)} type="button">
                          Emitir
                        </button>
                      ) : null}
                      {canReceiveOrder(order) ? (
                        <button
                          className="link-button"
                          onClick={async () => {
                            const detail = await loadOrderDocument(order.id);
                            openReceiveModal(detail);
                          }}
                          type="button"
                        >
                          Recibir
                        </button>
                      ) : null}
                      {canCancelOrder(order) ? (
                        <button className="link-button" onClick={() => handleCancelOrder(order.id)} type="button">
                          Cancelar
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>

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
      </DataCard>

      <ModalShell
        footer={
          <>
            <ActionButton
              disabled={submitting}
              icon={<ClipboardList size={16} />}
              onClick={() => handleSaveOrder("draft")}
              tone="primary"
              type="button"
            >
              {submitting ? "Guardando..." : "Guardar borrador"}
            </ActionButton>
            <ActionButton
              disabled={submitting || editorLines.length === 0}
              icon={<Send size={16} />}
              onClick={() => handleSaveOrder("issue")}
              type="button"
            >
              Guardar y emitir
            </ActionButton>
            <ActionButton
              onClick={() => {
                setEditorOpen(false);
                resetEditorForm();
              }}
              type="button"
            >
              Cancelar
            </ActionButton>
          </>
        }
        onClose={() => {
          setEditorOpen(false);
          resetEditorForm();
        }}
        open={editorOpen}
        size="xl"
        subtitle="Crea borradores, arma renglones y emite la compra cuando esté lista para el proveedor."
        title={editorForm.id ? "Editar orden de compra" : "Nueva orden de compra"}
      >
        <div className="inventory-modal-form">
          <section className="inventory-form-section">
            <SectionTitle subtitle="Proveedor, almacén destino y referencia del documento." title="Cabecera" />
            <FormGrid>
              <Field hint="Opcional" label="Folio">
                <input
                  onChange={(event) => setEditorForm((current) => ({ ...current, folio: event.target.value.toUpperCase() }))}
                  placeholder="Auto"
                  type="text"
                  value={editorForm.folio}
                />
              </Field>

              <Field label="Proveedor">
                <select
                  onChange={(event) => setEditorForm((current) => ({ ...current, proveedor_id: event.target.value }))}
                  value={editorForm.proveedor_id}
                >
                  <option value="">Selecciona un proveedor</option>
                  {suppliers.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>
                      {supplier.nombre}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Almacén destino">
                <select
                  onChange={(event) => setEditorForm((current) => ({ ...current, almacen_destino_id: event.target.value }))}
                  value={editorForm.almacen_destino_id}
                >
                  <option value="">Selecciona un almacén</option>
                  {warehouses.map((warehouse) => (
                    <option key={warehouse.id} value={warehouse.id}>
                      {warehouse.nombre} ({warehouse.codigo})
                    </option>
                  ))}
                </select>
              </Field>

              <Field hint="Opcional" label="Requisición vinculada">
                <input disabled type="text" value={editorForm.requisicion_folio || "Sin requisición vinculada"} />
              </Field>

              <Field label="Notas" span={2}>
                <textarea
                  onChange={(event) => setEditorForm((current) => ({ ...current, notas: event.target.value }))}
                  rows={3}
                  value={editorForm.notas}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Busca materiales y arma la orden con cantidades y costo unitario." title="Renglones" />
            <div className="inventory-material-picker">
              <FormGrid>
                <SearchInput
                  hint="Filtra por nombre, SKU, categoría o código de barras."
                  label="Buscar material"
                  onChange={(event) => setMaterialSearch(event.target.value)}
                  placeholder="Material, SKU o código"
                  value={materialSearch}
                />

                <Field label="Material a agregar">
                  <select onChange={(event) => setMaterialToAddId(event.target.value)} value={materialToAddId}>
                    {filteredMaterials.length === 0 ? <option value="">Sin coincidencias</option> : null}
                    {filteredMaterials.map((material) => (
                      <option key={material.id} value={material.id}>
                        {material.sku} · {material.nombre}
                      </option>
                    ))}
                  </select>
                </Field>
              </FormGrid>

              <div className="inventory-actions">
                <ActionButton icon={<Plus size={16} />} onClick={addLineToEditor} size="sm" type="button">
                  Agregar material
                </ActionButton>
              </div>
            </div>

            {editorLines.length === 0 ? (
              <EmptyState compact note="Agrega al menos un renglón para emitir la orden." title="Sin renglones en la OC" />
            ) : (
              <DataTable
                columns={[
                  { key: "material", label: "Material" },
                  { key: "cantidad", label: "Cantidad" },
                  { key: "costo", label: "Costo unitario" },
                  { key: "subtotal", label: "Subtotal" },
                  { key: "acciones", label: "Acciones" },
                ]}
              >
                <tbody>
                  {editorLines.map((line) => (
                    <tr key={line.localKey}>
                      <td>
                        <div className="inventory-cell-main">
                          {line.material_sku} · {line.material_nombre}
                        </div>
                        <div className="inventory-cell-sub">{line.material_unidad}</div>
                      </td>
                      <td>
                        <input
                          min="0.0001"
                          onChange={(event) => updateEditorLine(line.localKey, "cantidad", normalizeDecimalInput(event.target.value))}
                          step="0.0001"
                          type="number"
                          value={line.cantidad}
                        />
                      </td>
                      <td>
                        <input
                          min="0"
                          onChange={(event) =>
                            updateEditorLine(line.localKey, "costo_unitario", normalizeDecimalInput(event.target.value))
                          }
                          step="0.0001"
                          type="number"
                          value={line.costo_unitario}
                        />
                      </td>
                      <td>{formatMoney(calculateLineSubtotal(line))}</td>
                      <td>
                        <button className="link-button" onClick={() => removeEditorLine(line.localKey)} type="button">
                          Quitar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            )}
          </section>

          <section className="inventory-metric-grid inventory-metric-grid-4">
            <MetricCard icon={<ClipboardList size={16} />} label="Renglones" meta="Vista previa local" value={editorLines.length} />
            <MetricCard icon={<Truck size={16} />} label="Proveedor" meta="Seleccionado" value={suppliers.find((item) => item.id === editorForm.proveedor_id)?.nombre || "—"} />
            <MetricCard icon={<Warehouse size={16} />} label="Almacén" meta="Destino" value={warehouses.find((item) => item.id === editorForm.almacen_destino_id)?.codigo || "—"} />
            <MetricCard icon={<DollarSign size={16} />} label="Total estimado" meta="Se recalcula en backend" tone="success" value={formatMoney(previewTotals.total)} />
          </section>
        </div>
      </ModalShell>

      <ModalShell
        footer={
          <>
            {selectedOrder && canEditOrder(selectedOrder) ? (
              <ActionButton
                icon={<Pencil size={16} />}
                onClick={() => {
                  setDetailOpen(false);
                  loadEditorFromOrder(selectedOrder);
                }}
                type="button"
              >
                Editar
              </ActionButton>
            ) : null}
            {selectedOrder && canIssueOrder(selectedOrder) ? (
              <ActionButton icon={<Send size={16} />} onClick={() => handleEmitOrder(selectedOrder.id)} type="button">
                Emitir
              </ActionButton>
            ) : null}
            {selectedOrder && canReceiveOrder(selectedOrder) ? (
              <ActionButton icon={<PackageCheck size={16} />} onClick={() => openReceiveModal(selectedOrder)} tone="primary" type="button">
                Recibir
              </ActionButton>
            ) : null}
            {selectedOrder && canCancelOrder(selectedOrder) ? (
              <ActionButton icon={<XCircle size={16} />} onClick={() => handleCancelOrder(selectedOrder.id)} tone="danger" type="button">
                Cancelar
              </ActionButton>
            ) : null}
            <ActionButton onClick={() => setDetailOpen(false)} type="button">
              Cerrar
            </ActionButton>
          </>
        }
        onClose={() => setDetailOpen(false)}
        open={detailOpen}
        size="xl"
        subtitle="Consulta renglones, cantidades recibidas y trazabilidad básica de inventario."
        title={selectedOrder ? `OC ${selectedOrder.folio}` : "Detalle de orden de compra"}
      >
        {!selectedOrder ? null : (
          <div className="inventory-modal-form">
            <section className="inventory-form-section">
              <SectionTitle
                actions={<StatusBadge tone={statusTone(selectedOrder.estatus)}>{statusLabel(selectedOrder.estatus)}</StatusBadge>}
                subtitle="Datos principales del documento"
                title="Cabecera"
              />
              <div className="inventory-detail-grid purchase-order-detail-grid">
                <div>
                  <strong>Proveedor</strong>
                  <p>{selectedOrder.proveedor_nombre}</p>
                </div>
                <div>
                  <strong>Almacén destino</strong>
                  <p>{selectedOrder.almacen_destino_nombre}</p>
                </div>
                <div>
                  <strong>Fecha de creación</strong>
                  <p>{formatDateTime(selectedOrder.created_at)}</p>
                </div>
                <div>
                  <strong>Última actualización</strong>
                  <p>{formatDateTime(selectedOrder.updated_at)}</p>
                </div>
                <div>
                  <strong>Requisición vinculada</strong>
                  <p>{selectedOrder.requisicion_folio || "Sin vínculo"}</p>
                </div>
                <div>
                  <strong>Total</strong>
                  <p>{formatMoney(selectedOrder.total)}</p>
                </div>
                <div className="inventory-form-span-2">
                  <strong>Notas</strong>
                  <p>{selectedOrder.notas || "Sin notas"}</p>
                </div>
              </div>
            </section>

            <section className="inventory-metric-grid inventory-metric-grid-4">
              <MetricCard label="Renglones" value={selectedOrder.cantidad_renglones} />
              <MetricCard label="Ordenado" value={formatNumber(selectedOrder.cantidad_total_ordenada)} />
              <MetricCard label="Recibido" tone="success" value={formatNumber(selectedOrder.cantidad_total_recibida)} />
              <MetricCard label="Pendiente" tone={Number(selectedOrder.cantidad_total_pendiente) > 0 ? "warning" : "neutral"} value={formatNumber(selectedOrder.cantidad_total_pendiente)} />
            </section>

            <section className="inventory-form-section">
              <SectionTitle subtitle="Cantidades ordenadas, recibidas y pendientes por renglón." title="Renglones" />
              <DataTable
                columns={[
                  { key: "material", label: "Material" },
                  { key: "ordenada", label: "Ordenada" },
                  { key: "recibida", label: "Recibida" },
                  { key: "pendiente", label: "Pendiente" },
                  { key: "costo", label: "Costo unitario" },
                  { key: "subtotal", label: "Subtotal" },
                  { key: "estado", label: "Estado" },
                ]}
              >
                <tbody>
                  {selectedOrder.details.map((detail) => (
                    <tr key={detail.id}>
                      <td>
                        <div className="inventory-cell-main">{detail.material_nombre}</div>
                        <div className="inventory-cell-sub">{detail.material_sku}</div>
                      </td>
                      <td>{formatNumber(detail.cantidad)}</td>
                      <td>{formatNumber(detail.cantidad_recibida)}</td>
                      <td>{formatNumber(detail.cantidad_pendiente)}</td>
                      <td>{formatMoney(detail.costo_unitario)}</td>
                      <td>{formatMoney(detail.total_linea)}</td>
                      <td>
                        <StatusBadge tone={detail.estado_linea === "completa" ? "success" : detail.estado_linea === "parcial" ? "warning" : "neutral"}>
                          {lineStatusLabel(detail.estado_linea)}
                        </StatusBadge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </section>

            <section className="inventory-form-section">
              <SectionTitle subtitle="Las recepciones generan entradas de inventario trazables por referencia de OC." title="Recepciones y trazabilidad" />
              {selectedOrder.movements.length === 0 ? (
                <div className="inventory-form-note">
                  <strong>Trazabilidad disponible en movimientos de inventario</strong>
                  <p>Aún no existen recepciones aplicadas para esta orden de compra.</p>
                </div>
              ) : (
                <DataTable
                  columns={[
                    { key: "fecha", label: "Fecha" },
                    { key: "material", label: "Material" },
                    { key: "cantidad", label: "Cantidad" },
                    { key: "documento", label: "Documento" },
                    { key: "usuario", label: "Registró" },
                  ]}
                >
                  <tbody>
                    {selectedOrder.movements.map((movement) => (
                      <tr key={movement.id}>
                        <td>{formatDateTime(movement.created_at)}</td>
                        <td>
                          <div className="inventory-cell-main">{movement.material_nombre}</div>
                          <div className="inventory-cell-sub">{movement.material_sku}</div>
                        </td>
                        <td>{formatNumber(movement.cantidad)}</td>
                        <td>{safeDisplayText(movement.documento_referencia, "Sin documento")}</td>
                        <td>{safeDisplayText(movement.created_by_nombre, "Sistema")}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              )}
            </section>
          </div>
        )}
      </ModalShell>

      <ModalShell
        footer={
          <>
            <ActionButton
              disabled={submitting || receiveSummary.unidades <= 0}
              icon={<PackageCheck size={16} />}
              onClick={handleReceiveOrder}
              tone="primary"
              type="button"
            >
              {submitting ? "Aplicando..." : "Confirmar recepción"}
            </ActionButton>
            <ActionButton onClick={() => setReceiveOpen(false)} type="button">
              Cerrar
            </ActionButton>
          </>
        }
        onClose={() => setReceiveOpen(false)}
        open={receiveOpen}
        size="xl"
        subtitle="Esta recepción aumentará inventario en el almacén destino."
        title={selectedOrder ? `Recibir OC ${selectedOrder.folio}` : "Recibir orden de compra"}
      >
        {!selectedOrder ? null : (
          <div className="inventory-modal-form">
            <section className="inventory-form-section">
              <SectionTitle subtitle="Datos de recepción y documento asociado." title="Recepción" />
              <FormGrid>
                <Field label="Proveedor">
                  <input disabled type="text" value={selectedOrder.proveedor_nombre} />
                </Field>
                <Field label="Almacén destino">
                  <input disabled type="text" value={selectedOrder.almacen_destino_nombre} />
                </Field>
                <Field hint="Remisión, factura o referencia del proveedor" label="Documento de referencia">
                  <input
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        documento_referencia: event.target.value,
                      }))
                    }
                    type="text"
                    value={receiveForm.documento_referencia}
                  />
                </Field>
                <Field label="Notas de recepción" span={2}>
                  <textarea
                    onChange={(event) =>
                      setReceiveForm((current) => ({
                        ...current,
                        notas: event.target.value,
                      }))
                    }
                    rows={3}
                    value={receiveForm.notas}
                  />
                </Field>
              </FormGrid>
            </section>

            <section className="inventory-form-section">
              <SectionTitle subtitle="No puedes recibir más de lo pendiente por renglón." title="Cantidades por recibir" />
              <DataTable
                columns={[
                  { key: "material", label: "Material" },
                  { key: "ordenada", label: "Ordenada" },
                  { key: "recibida", label: "Recibida" },
                  { key: "pendiente", label: "Pendiente" },
                  { key: "recibir_ahora", label: "Recibir ahora" },
                  { key: "costo", label: "Costo unitario" },
                ]}
              >
                <tbody>
                  {selectedOrder.details.map((detail) => {
                    const pending = Number(detail.cantidad_pendiente || 0);
                    return (
                      <tr key={detail.id}>
                        <td>
                          <div className="inventory-cell-main">{detail.material_nombre}</div>
                          <div className="inventory-cell-sub">{detail.material_sku}</div>
                        </td>
                        <td>{formatNumber(detail.cantidad)}</td>
                        <td>{formatNumber(detail.cantidad_recibida)}</td>
                        <td>{formatNumber(detail.cantidad_pendiente)}</td>
                        <td>
                          {pending > 0 ? (
                            <input
                              max={pending}
                              min="0"
                              onChange={(event) =>
                                setReceiveForm((current) => ({
                                  ...current,
                                  cantidades: {
                                    ...current.cantidades,
                                    [detail.id]: normalizeDecimalInput(event.target.value),
                                  },
                                }))
                              }
                              step="0.0001"
                              type="number"
                              value={receiveForm.cantidades[detail.id] ?? ""}
                            />
                          ) : (
                            <span className="table-note">Completo</span>
                          )}
                        </td>
                        <td>{formatMoney(detail.costo_unitario)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </DataTable>
            </section>

            <section className="inventory-metric-grid inventory-metric-grid-4">
              <MetricCard label="Folio" value={selectedOrder.folio} />
              <MetricCard label="Unidades a recibir" tone={receiveSummary.unidades > 0 ? "warning" : "neutral"} value={formatNumber(receiveSummary.unidades)} />
              <MetricCard label="Valor estimado" tone="success" value={formatMoney(receiveSummary.total)} />
              <MetricCard label="Pendiente tras recepción" value={formatNumber(Math.max(Number(selectedOrder.cantidad_total_pendiente) - receiveSummary.unidades, 0))} />
            </section>
          </div>
        )}
      </ModalShell>
    </div>
  );
}
