import { useEffect, useMemo, useState } from "react";
import {
  Boxes,
  CheckCircle2,
  Eye,
  PackageCheck,
  Pencil,
  Plus,
  Send,
  ShoppingCart,
  XCircle,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  addRequisitionDetail,
  approveRequisition,
  cancelRequisition,
  createPurchaseOrderFromRequisition,
  createRequisition,
  deleteRequisitionDetail,
  fulfillRequisition,
  getMaterials,
  getRequisitionDetail,
  getSuppliers,
  getWarehouses,
  listPmProjects,
  listRequisitions,
  rejectRequisition,
  submitRequisition,
  updateRequisition,
  updateRequisitionDetail,
} from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  ActionButton,
  DataCard,
  DataTable,
  DEFAULT_PAGE_SIZE,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  MetricCard,
  ModalShell,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  StatusBadge,
  formatDate,
  formatDateTime,
  formatNumber,
  normalizeDecimalInput,
  safeDisplayText,
} from "./shared";


const defaultFilters = {
  q: "",
  estatus: "",
  proveedor_sugerido_id: "",
  proyecto: "",
  material_id: "",
  fecha_desde: "",
  fecha_hasta: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const emptyRequisitionForm = {
  id: "",
  folio: "",
  notas: "",
  proveedor_sugerido_id: "",
  es_proyecto: false,
  proyecto_id: "",
  proyecto_nombre_snapshot: "",
};

const emptyPurchaseOrderForm = {
  proveedor_id: "",
  almacen_destino_id: "",
  folio: "",
};


function createLineId() {
  return `line-${Math.random().toString(36).slice(2, 10)}`;
}


function createEmptyLine(materialId = "") {
  return {
    clientId: createLineId(),
    id: "",
    material_id: materialId,
    cantidad: "1",
    notas: "",
  };
}


function requisitionToForm(requisition) {
  if (!requisition) {
    return emptyRequisitionForm;
  }

  return {
    id: requisition.id,
    folio: requisition.folio ?? "",
    notas: requisition.notas ?? "",
    proveedor_sugerido_id: requisition.proveedor_sugerido_id ?? "",
    es_proyecto: Boolean(requisition.es_proyecto),
    proyecto_id: requisition.proyecto_id ?? "",
    proyecto_nombre_snapshot: requisition.proyecto_nombre_snapshot ?? "",
  };
}


function requisitionToLines(requisition) {
  if (!requisition?.details?.length) {
    return [];
  }

  return requisition.details.map((detail) => ({
    clientId: createLineId(),
    id: detail.id,
    material_id: detail.material_id,
    cantidad: String(detail.cantidad ?? ""),
    notas: detail.notas ?? "",
  }));
}


function getRequisitionStatusTone(status) {
  const normalized = String(status ?? "").toLowerCase();
  if (normalized === "aprobada") return "success";
  if (normalized === "surtida") return "success";
  if (normalized === "convertida_a_oc") return "info";
  if (normalized === "enviada") return "info";
  if (normalized === "parcial") return "warning";
  if (normalized === "rechazada" || normalized === "cancelada") return "danger";
  return "neutral";
}


function getRequisitionStatusLabel(status) {
  const labels = {
    borrador: "Borrador",
    enviada: "Enviada",
    aprobada: "Aprobada",
    rechazada: "Rechazada",
    cancelada: "Cancelada",
    parcial: "Parcial",
    surtida: "Surtida",
    convertida_a_oc: "Convertida a OC",
  };
  return labels[status] ?? safeDisplayText(status);
}

function getPriorityLabel(priority) {
  const labels = {
    baja: "Baja",
    normal: "Normal",
    alta: "Alta",
    urgente: "Urgente",
  };
  return labels[String(priority ?? "").toLowerCase()] ?? safeDisplayText(priority, "Normal");
}

function getPriorityTone(priority) {
  const normalized = String(priority ?? "").toLowerCase();
  if (normalized === "urgente") return "danger";
  if (normalized === "alta") return "warning";
  if (normalized === "baja") return "neutral";
  return "info";
}


function getLineStateLabel(status) {
  const labels = {
    pendiente: "Pendiente",
    parcial: "Parcial",
    surtido: "Surtido",
  };
  return labels[status] ?? safeDisplayText(status);
}


function getDetailPending(detail) {
  return Number(detail?.cantidad_pendiente ?? 0);
}


function canSubmitRequisition(requisition) {
  return requisition?.estatus === "borrador";
}


function canApproveRequisition(requisition) {
  return requisition?.estatus === "enviada";
}


function canRejectRequisition(requisition) {
  return ["enviada", "aprobada"].includes(requisition?.estatus) && Number(requisition?.cantidad_total_surtida ?? 0) <= 0;
}


function canCancelRequisition(requisition) {
  if (!requisition) {
    return false;
  }

  if (!["borrador", "enviada", "aprobada"].includes(requisition.estatus)) {
    return false;
  }

  return Number(requisition.cantidad_total_surtida ?? 0) <= 0 && !requisition.orden_compra_id;
}


function canFulfillRequisition(requisition) {
  if (!requisition) {
    return false;
  }
  return ["aprobada", "parcial"].includes(requisition.estatus) && !requisition.orden_compra_id && Number(requisition.cantidad_total_pendiente ?? 0) > 0;
}


function canCreatePurchaseOrder(requisition) {
  if (!requisition) {
    return false;
  }
  if (requisition.es_proyecto) {
    return false;
  }
  return ["aprobada", "parcial"].includes(requisition.estatus) && !requisition.orden_compra_id && Number(requisition.cantidad_total_pendiente ?? 0) > 0;
}


function getWarehouseStock(detail, warehouseId) {
  const match = detail?.stock_por_almacen?.find((item) => item.almacen_id === warehouseId);
  return Number(match?.stock_actual ?? 0);
}


function buildDefaultFulfillItems(details, warehouseId) {
  const mapped = {};
  for (const detail of details ?? []) {
    const pending = Number(detail.cantidad_pendiente ?? 0);
    const available = getWarehouseStock(detail, warehouseId);
    const suggested = pending > 0 ? Math.min(pending, available) : 0;
    mapped[detail.id] = suggested > 0 ? String(suggested) : "";
  }
  return mapped;
}


function formatCompactNumber(value) {
  return formatNumber(Number(value ?? 0));
}


export default function RequisitionsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { token, empresaId, membership } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [filters, setFilters] = useState(defaultFilters);
  const [requisitions, setRequisitions] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [materials, setMaterials] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [projects, setProjects] = useState([]);
  const [projectLookupAvailable, setProjectLookupAvailable] = useState(false);
  const [selectedRequisition, setSelectedRequisition] = useState(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [fulfillOpen, setFulfillOpen] = useState(false);
  const [purchaseOrderOpen, setPurchaseOrderOpen] = useState(false);
  const [form, setForm] = useState(emptyRequisitionForm);
  const [lines, setLines] = useState([]);
  const [materialSearch, setMaterialSearch] = useState("");
  const [purchaseOrderForm, setPurchaseOrderForm] = useState(emptyPurchaseOrderForm);
  const [fulfillForm, setFulfillForm] = useState({
    almacen_id: "",
    documento_referencia: "",
    notas: "",
    proyecto_id: "",
    proyecto_nombre_snapshot: "",
    items: {},
  });

  const isManager = ["owner", "admin"].includes(membership?.role ?? "");

  async function loadOptions() {
    const [materialResponse, supplierResponse, warehouseResponse] = await Promise.all([
      getMaterials({
        token,
        empresaId,
        filters: { activo: true, limit: 100, offset: 0 },
      }),
      getSuppliers({
        token,
        empresaId,
        filters: { activo: true, limit: 100, offset: 0 },
      }),
      getWarehouses({
        token,
        empresaId,
        filters: { activo: true, limit: 100, offset: 0 },
      }),
    ]);

    setMaterials(materialResponse.items ?? []);
    setSuppliers(supplierResponse.items ?? []);
    setWarehouses(warehouseResponse.items ?? []);

    try {
      const projectResponse = await listPmProjects({
        token,
        empresaId,
        filters: { activo: true, estatus: "activo", limit: 100, offset: 0 },
      });
      setProjects(projectResponse.items ?? []);
      setProjectLookupAvailable(true);
    } catch {
      setProjects([]);
      setProjectLookupAvailable(false);
    }
  }

  async function loadRequisitionList(nextFilters = filters) {
    const response = await listRequisitions({ token, empresaId, filters: nextFilters });
    setRequisitions(response.items ?? []);
    setMeta({
      total: response.total ?? 0,
      limit: response.limit ?? nextFilters.limit,
      offset: response.offset ?? nextFilters.offset,
    });
    return response.items ?? [];
  }

  async function loadRequisitionDocument(requisitionId) {
    const response = await getRequisitionDetail({ requisitionId, token, empresaId });
    setSelectedRequisition(response);
    return response;
  }

  function resetFeedback() {
    setError("");
    setSuccess("");
  }

  function resetEditorState() {
    setForm(emptyRequisitionForm);
    setLines([]);
    setMaterialSearch("");
  }

  function closeEditor() {
    setEditorOpen(false);
    resetEditorState();
  }

  function closeDetail() {
    setDetailOpen(false);
  }

  function closeFulfill() {
    setFulfillOpen(false);
    setFulfillForm({
      almacen_id: "",
      documento_referencia: "",
      notas: "",
      proyecto_id: "",
      proyecto_nombre_snapshot: "",
      items: {},
    });
  }

  function closePurchaseOrder() {
    setPurchaseOrderOpen(false);
    setPurchaseOrderForm(emptyPurchaseOrderForm);
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      resetFeedback();
      try {
        await loadOptions();
        await loadRequisitionList(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar las requisiciones.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  useEffect(() => {
    const openRequisitionId = location.state?.openRequisitionId;
    const successMessage = location.state?.successMessage;
    if (!openRequisitionId || !token || !empresaId) {
      return;
    }

    async function openFromNavigation() {
      try {
        const document = await loadRequisitionDocument(openRequisitionId);
        setSelectedRequisition(document);
        setDetailOpen(true);
        if (successMessage) {
          setSuccess(successMessage);
        }
      } catch (requestError) {
        setError(requestError.message || "No se pudo abrir la requisicion.");
      } finally {
        navigate(location.pathname, { replace: true, state: null });
      }
    }

    openFromNavigation();
  }, [location.state, token, empresaId, navigate, location.pathname]);

  const filteredMaterials = useMemo(() => {
    const normalized = materialSearch.trim().toLowerCase();
    const selectedMaterialIds = new Set(lines.map((line) => line.material_id));
    return materials.filter((material) => {
      if (!material.activo) {
        return false;
      }
      const matchesSearch =
        !normalized ||
        [material.nombre, material.sku, material.codigo_barras, material.categoria]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalized));
      if (!matchesSearch) {
        return false;
      }
      return !selectedMaterialIds.has(material.id);
    });
  }, [lines, materialSearch, materials]);

  const requisitionCounts = useMemo(() => {
    const counts = {
      borrador: 0,
      enviada: 0,
      aprobada: 0,
      parcial: 0,
      surtida: 0,
      convertida_a_oc: 0,
    };
    for (const requisition of requisitions) {
      if (counts[requisition.estatus] !== undefined) {
        counts[requisition.estatus] += 1;
      }
    }
    return counts;
  }, [requisitions]);

  const totalPending = useMemo(
    () => requisitions.reduce((accumulator, item) => accumulator + Number(item.cantidad_total_pendiente ?? 0), 0),
    [requisitions],
  );

  function addLineFromMaterial(materialId) {
    if (!materialId) {
      return;
    }
    setLines((current) => [...current, createEmptyLine(materialId)]);
    setMaterialSearch("");
  }

  function updateLine(clientId, field, value) {
    setLines((current) =>
      current.map((line) => (line.clientId === clientId ? { ...line, [field]: value } : line)),
    );
  }

  function removeLine(clientId) {
    setLines((current) => current.filter((line) => line.clientId !== clientId));
  }

  function openCreateEditor() {
    resetFeedback();
    resetEditorState();
    setForm({
      ...emptyRequisitionForm,
      proveedor_sugerido_id: suppliers[0]?.id ?? "",
    });
    setEditorOpen(true);
  }

  async function openEditEditor(requisitionId) {
    resetFeedback();
    setSaving(true);
    try {
      const document = await loadRequisitionDocument(requisitionId);
      setForm(requisitionToForm(document));
      setLines(requisitionToLines(document));
      setEditorOpen(true);
      setDetailOpen(false);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar la requisicion para edicion.");
    } finally {
      setSaving(false);
    }
  }

  async function openDetailModal(requisitionId) {
    resetFeedback();
    setSaving(true);
    try {
      const document = await loadRequisitionDocument(requisitionId);
      setSelectedRequisition(document);
      setDetailOpen(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle de la requisicion.");
    } finally {
      setSaving(false);
    }
  }

  async function syncRequisitionLines(requisitionId, currentDetails, nextLines) {
    const existingIds = new Set((currentDetails ?? []).map((detail) => detail.id));
    const nextExistingIds = new Set(nextLines.filter((line) => line.id).map((line) => line.id));

    for (const detail of currentDetails ?? []) {
      if (!nextExistingIds.has(detail.id)) {
        await deleteRequisitionDetail({
          requisitionId,
          detailId: detail.id,
          token,
          empresaId,
        });
      }
    }

    for (const line of nextLines) {
      const payload = {
        material_id: line.material_id,
        cantidad: Number(line.cantidad),
        notas: line.notas.trim() || null,
      };

      if (line.id && existingIds.has(line.id)) {
        await updateRequisitionDetail({
          requisitionId,
          detailId: line.id,
          token,
          empresaId,
          payload,
        });
      } else {
        await addRequisitionDetail({
          requisitionId,
          token,
          empresaId,
          payload,
        });
      }
    }
  }

  function buildHeaderPayload() {
    return {
      folio: form.folio.trim() || null,
      notas: form.notas.trim() || null,
      proveedor_sugerido_id: form.proveedor_sugerido_id || "",
      es_proyecto: Boolean(form.es_proyecto),
      proyecto_id: form.es_proyecto ? form.proyecto_id || "" : "",
      proyecto_nombre_snapshot: form.es_proyecto ? form.proyecto_nombre_snapshot.trim() || "" : "",
    };
  }

  async function handleSave(mode = "draft") {
    const invalidLine = lines.find(
      (line) => !line.material_id || Number(line.cantidad) <= 0 || Number.isNaN(Number(line.cantidad)),
    );
    if (invalidLine) {
      setError("Cada renglon debe tener material y una cantidad valida.");
      return;
    }
    if (mode === "submit" && lines.length === 0) {
      setError("Debes agregar al menos un material antes de enviar la requisicion.");
      return;
    }

    setSaving(true);
    resetFeedback();
    let requisitionId = form.id;
    try {
      let headerResponse;
      const payload = buildHeaderPayload();

      if (form.id) {
        headerResponse = await updateRequisition({
          requisitionId: form.id,
          token,
          empresaId,
          payload,
        });
      } else {
        headerResponse = await createRequisition({
          token,
          empresaId,
          payload,
        });
        requisitionId = headerResponse.id;
      }

      await syncRequisitionLines(requisitionId, headerResponse.details ?? [], lines);

      if (mode === "submit") {
        await submitRequisition({ requisitionId, token, empresaId });
      }

      const refreshed = await loadRequisitionDocument(requisitionId);
      setSelectedRequisition(refreshed);
      setDetailOpen(true);
      closeEditor();
      await loadRequisitionList(filters);
      setSuccess(mode === "submit" ? "Requisicion registrada y enviada." : form.id ? "Requisicion actualizada." : "Requisicion creada en borrador.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la requisicion.");
      if (requisitionId) {
        try {
          const partial = await loadRequisitionDocument(requisitionId);
          setSelectedRequisition(partial);
        } catch {
          // noop
        }
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(action, requisitionId) {
    setSaving(true);
    resetFeedback();
    try {
      let response;
      if (action === "submit") {
        response = await submitRequisition({ requisitionId, token, empresaId });
      } else if (action === "approve") {
        response = await approveRequisition({ requisitionId, token, empresaId, payload: { items: [] } });
      } else if (action === "reject") {
        const motivoRechazo = window.prompt("Indica el motivo del rechazo.");
        if (!motivoRechazo || !motivoRechazo.trim()) {
          setSaving(false);
          return null;
        }
        response = await rejectRequisition({
          requisitionId,
          token,
          empresaId,
          payload: { motivo_rechazo: motivoRechazo.trim() },
        });
      } else if (action === "cancel") {
        response = await cancelRequisition({ requisitionId, token, empresaId });
      } else {
        throw new Error("Acción de requisición no soportada.");
      }
      setSelectedRequisition(response);
      if (detailOpen && selectedRequisition?.id === requisitionId) {
        setSelectedRequisition(response);
      }
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
      return response;
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar el estatus de la requisición.");
      return null;
    } finally {
      setSaving(false);
    }
  }

  function openPurchaseOrderModal(requisition) {
    resetFeedback();
    setSelectedRequisition(requisition);
    setPurchaseOrderForm({
      proveedor_id: requisition.proveedor_sugerido_id || suppliers[0]?.id || "",
      almacen_destino_id: warehouses[0]?.id || "",
      folio: "",
    });
    setPurchaseOrderOpen(true);
  }

  async function openFulfillFromList(requisitionId) {
    setSaving(true);
    resetFeedback();
    try {
      const document = await loadRequisitionDocument(requisitionId);
      openFulfillModal(document);
    } catch (requestError) {
      setError(requestError.message || "No se pudo preparar el surtido.");
    } finally {
      setSaving(false);
    }
  }

  async function openPurchaseOrderFromList(requisitionId) {
    setSaving(true);
    resetFeedback();
    try {
      const document = await loadRequisitionDocument(requisitionId);
      openPurchaseOrderModal(document);
    } catch (requestError) {
      setError(requestError.message || "No se pudo preparar la orden de compra.");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreatePurchaseOrder() {
    if (!selectedRequisition) {
      return;
    }

    setSaving(true);
    resetFeedback();
    try {
      const order = await createPurchaseOrderFromRequisition({
        requisitionId: selectedRequisition.id,
        token,
        empresaId,
        payload: {
          proveedor_id: purchaseOrderForm.proveedor_id,
          almacen_destino_id: purchaseOrderForm.almacen_destino_id,
          folio: purchaseOrderForm.folio.trim() || null,
        },
      });
      closePurchaseOrder();
      await Promise.all([loadRequisitionDocument(selectedRequisition.id), loadRequisitionList(filters)]);
      navigate("/inventario/ordenes-compra", {
        state: {
          openOrderId: order.id,
          successMessage: `OC ${order.folio} creada desde la requisicion ${selectedRequisition.folio}.`,
        },
      });
    } catch (requestError) {
      setError(requestError.message || "No se pudo crear la orden de compra.");
    } finally {
      setSaving(false);
    }
  }

  function openFulfillModal(requisition) {
    const defaultWarehouseId = warehouses[0]?.id || "";
    setSelectedRequisition(requisition);
    setFulfillForm({
      almacen_id: defaultWarehouseId,
      documento_referencia: "",
      notas: "",
      proyecto_id: requisition.proyecto_id || "",
      proyecto_nombre_snapshot: requisition.proyecto_nombre_snapshot || "",
      items: buildDefaultFulfillItems(requisition.details ?? [], defaultWarehouseId),
    });
    setFulfillOpen(true);
  }

  async function handleApproveAndFulfill(requisition) {
    const approved = await handleStatusChange("approve", requisition.id);
    if (approved) {
      openFulfillModal(approved);
    }
  }

  async function handleFulfillSubmit() {
    if (!selectedRequisition) {
      return;
    }

    const payloadItems = (selectedRequisition.details ?? [])
      .map((detail) => {
        const quantity = Number(fulfillForm.items[detail.id] ?? 0);
        const pending = Number(detail.cantidad_pendiente ?? 0);
        const available = getWarehouseStock(detail, fulfillForm.almacen_id);
        return {
          detail,
          quantity,
          pending,
          available,
        };
      })
      .filter((entry) => entry.quantity > 0);

    if (!fulfillForm.almacen_id) {
      setError("Selecciona un almacen origen para surtir.");
      return;
    }
    if (payloadItems.length === 0) {
      setError("Debes capturar al menos una cantidad valida para surtir.");
      return;
    }

    const invalid = payloadItems.find(
      (entry) => entry.quantity > entry.pending || entry.quantity > entry.available,
    );
    if (invalid) {
      setError("Una o mas cantidades exceden lo pendiente o el stock disponible.");
      return;
    }

    setSaving(true);
    resetFeedback();
    try {
      const response = await fulfillRequisition({
        requisitionId: selectedRequisition.id,
        token,
        empresaId,
        payload: {
          almacen_id: fulfillForm.almacen_id,
          documento_referencia: fulfillForm.documento_referencia.trim() || null,
          notas: fulfillForm.notas.trim() || null,
          proyecto_id: fulfillForm.proyecto_id.trim() || null,
          proyecto_nombre_snapshot: fulfillForm.proyecto_nombre_snapshot.trim() || null,
          items: payloadItems.map((entry) => ({
            detail_id: entry.detail.id,
            cantidad_surtir: entry.quantity,
          })),
        },
      });
      setSelectedRequisition(response);
      closeFulfill();
      setDetailOpen(true);
      await loadRequisitionList(filters);
      setSuccess("Requisicion surtida e inventario actualizado.");
    } catch (requestError) {
      setError(requestError.message || "No se pudo surtir la requisicion.");
    } finally {
      setSaving(false);
    }
  }

  async function handleFilterSubmit(event) {
    event.preventDefault();
    const nextFilters = { ...filters, offset: 0 };
    setFilters(nextFilters);
    try {
      await loadRequisitionList(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron aplicar los filtros.");
    }
  }

  async function handlePaginate(direction) {
    const nextFilters = {
      ...filters,
      offset: direction === "next" ? meta.offset + meta.limit : Math.max(0, meta.offset - meta.limit),
    };
    setFilters(nextFilters);
    try {
      await loadRequisitionList(nextFilters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cambiar la pagina.");
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando requisiciones...</div>;
  }

  return (
    <div className="inventory-shell inventory-screen">
      <PageHeader
        eyebrow="Inventario operativo"
        title="Requisiciones"
        subtitle="Solicitudes de materiales vinculadas a proyectos."
        actions={
          <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateEditor} tone="primary" type="button">
            Nueva requisicion
          </ActionButton>
        }
      />

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard icon={<Send size={18} strokeWidth={1.9} />} label="Pendientes" meta="Enviadas para revisión" tone="info" value={requisitionCounts.enviada} />
        <MetricCard icon={<CheckCircle2 size={18} strokeWidth={1.9} />} label="Aprobadas" meta="Listas para surtir" tone="success" value={requisitionCounts.aprobada} />
        <MetricCard icon={<PackageCheck size={18} strokeWidth={1.9} />} label="Surtidas parcial" meta="Con faltantes por surtir" tone="warning" value={requisitionCounts.parcial} />
        <MetricCard icon={<Boxes size={18} strokeWidth={1.9} />} label="Surtidas" meta="Completadas desde inventario" tone="success" value={requisitionCounts.surtida} />
        <MetricCard icon={<ClipboardListIcon />} label="Borradores" meta="Aún sin enviar" tone="neutral" value={requisitionCounts.borrador} />
        <MetricCard icon={<ShoppingCart size={18} strokeWidth={1.9} />} label="Convertidas a OC" meta="Solo requisiciones generales" tone="info" value={requisitionCounts.convertida_a_oc} />
        <MetricCard icon={<Boxes size={18} strokeWidth={1.9} />} label="Pendiente" meta="Unidades aún sin surtir" tone="warning" value={formatCompactNumber(totalPending)} />
      </section>

      <FilterCard title="Filtros" subtitle="Búsqueda operativa de solicitudes.">
        <form className="inventory-filter-toolbar" onSubmit={handleFilterSubmit}>
          <div className="inventory-toolbar-grid">
            <SearchInput
              action={
                <ActionButton size="sm" tone="primary" type="submit">
                  Buscar
                </ActionButton>
              }
              hint="Busca por folio o notas."
              label="Buscar"
              onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
              placeholder="Folio o notas"
              value={filters.q}
            />
            <Field label="Estatus">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, estatus: event.target.value }))}
                value={filters.estatus}
              >
                <option value="">Todos</option>
                {["borrador", "enviada", "aprobada", "parcial", "surtida", "convertida_a_oc", "rechazada", "cancelada"].map((status) => (
                  <option key={status} value={status}>
                    {getRequisitionStatusLabel(status)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Proyecto">
              <input
                onChange={(event) => setFilters((current) => ({ ...current, proyecto: event.target.value }))}
                placeholder="Nombre o referencia"
                type="text"
                value={filters.proyecto}
              />
            </Field>
            <Field label="Material">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, material_id: event.target.value }))}
                value={filters.material_id}
              >
                <option value="">Todos</option>
                {materials.map((material) => (
                  <option key={material.id} value={material.id}>
                    {safeDisplayText(material.nombre)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Proveedor sugerido">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, proveedor_sugerido_id: event.target.value }))}
                value={filters.proveedor_sugerido_id}
              >
                <option value="">Todos</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.nombre}
                  </option>
                ))}
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
            <div className="inventory-actions inventory-actions-end">
              <ActionButton type="submit">Aplicar filtros</ActionButton>
              <ActionButton
                onClick={() => {
                  setFilters(defaultFilters);
                  loadRequisitionList(defaultFilters);
                }}
                type="button"
              >
                Limpiar
              </ActionButton>
              <ActionButton onClick={() => loadRequisitionList(filters)} type="button">
                Actualizar
              </ActionButton>
            </div>
          </div>
        </form>
      </FilterCard>

      <DataCard subtitle="Solicitudes de materiales vinculadas a proyectos." title="Requisiciones">
        <ResultMeta label="requisiciones" loaded={requisitions.length} total={meta.total} />
        {requisitions.length === 0 ? (
          <EmptyState
            action={
              <ActionButton onClick={openCreateEditor} tone="primary" type="button">
                Nueva requisicion
              </ActionButton>
            }
            note="No hay requisiciones registradas todavía. Las solicitudes creadas desde PM aparecerán aquí para aprobación y surtido."
            title="No hay requisiciones."
          />
        ) : (
          <>
            <DataTable columns={["Folio", "Proyecto", "Solicitante", "Prioridad", "Estatus", "Materiales", "Fecha", "Acciones"]}>
              <tbody>
                {requisitions.map((requisition) => (
                  <tr key={requisition.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(requisition.folio)}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(requisition.notas, "Sin notas")}</div>
                    </td>
                    <td>{safeDisplayText(requisition.proyecto_nombre_snapshot, "—")}</td>
                    <td>{safeDisplayText(requisition.solicitante_nombre, "—")}</td>
                    <td>
                      <StatusBadge tone={getPriorityTone(requisition.prioridad)}>
                        {getPriorityLabel(requisition.prioridad)}
                      </StatusBadge>
                    </td>
                    <td>
                      <StatusBadge tone={getRequisitionStatusTone(requisition.estatus)}>
                        {getRequisitionStatusLabel(requisition.estatus)}
                      </StatusBadge>
                    </td>
                    <td>{formatCompactNumber(requisition.total_renglones ?? requisition.details_count ?? 0)}</td>
                    <td>{formatDateTime(requisition.created_at)}</td>
                    <td>
                      <div className="inventory-actions">
                        <ActionButton icon={<Eye size={14} strokeWidth={1.9} />} onClick={() => openDetailModal(requisition.id)} size="sm" type="button">
                          Ver
                        </ActionButton>
                        {requisition.estatus === "borrador" ? (
                          <ActionButton icon={<Pencil size={14} strokeWidth={1.9} />} onClick={() => openEditEditor(requisition.id)} size="sm" type="button">
                            Editar
                          </ActionButton>
                        ) : null}
                        {canSubmitRequisition(requisition) ? (
                          <ActionButton onClick={() => handleStatusChange("submit", requisition.id)} size="sm" type="button">
                            Enviar
                          </ActionButton>
                        ) : null}
                        {canApproveRequisition(requisition) ? (
                          <ActionButton onClick={() => handleStatusChange("approve", requisition.id)} size="sm" type="button">
                            Aprobar
                          </ActionButton>
                        ) : null}
                        {canRejectRequisition(requisition) ? (
                          <ActionButton onClick={() => handleStatusChange("reject", requisition.id)} size="sm" tone="danger" type="button">
                            Rechazar
                          </ActionButton>
                        ) : null}
                        {canFulfillRequisition(requisition) ? (
                          <ActionButton onClick={() => openFulfillFromList(requisition.id)} size="sm" tone="primary" type="button">
                            Surtir
                          </ActionButton>
                        ) : null}
                        {canCreatePurchaseOrder(requisition) ? (
                          <ActionButton onClick={() => openPurchaseOrderFromList(requisition.id)} size="sm" type="button">
                            Crear OC
                          </ActionButton>
                        ) : null}
                        {canCancelRequisition(requisition) ? (
                          <ActionButton onClick={() => handleStatusChange("cancel", requisition.id)} size="sm" tone="danger" type="button">
                            Cancelar
                          </ActionButton>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <PaginationControls meta={meta} onNext={() => handlePaginate("next")} onPrevious={() => handlePaginate("previous")} />
          </>
        )}
      </DataCard>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeEditor} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} onClick={() => handleSave("draft")} type="button">
              {saving ? "Guardando..." : "Guardar borrador"}
            </ActionButton>
            <ActionButton disabled={saving} onClick={() => handleSave("submit")} tone="primary" type="button">
              {saving ? "Enviando..." : "Guardar y enviar"}
            </ActionButton>
          </div>
        }
        onClose={closeEditor}
        open={editorOpen}
        size="xl"
        subtitle="Solicitudes internas de materiales antes de surtir o convertir a orden de compra."
        title={form.id ? "Editar requisicion" : "Nueva requisicion"}
      >
        <div className="inventory-modal-form">
          <div className="inventory-form-section">
            <strong>Cabecera</strong>
            <FormGrid>
              <Field hint="Opcional" label="Folio">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, folio: event.target.value.toUpperCase() }))}
                  placeholder="Auto"
                  type="text"
                  value={form.folio}
                />
              </Field>
              <Field label="Tipo">
                <select
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      es_proyecto: event.target.value === "proyecto",
                      proyecto_id: event.target.value === "proyecto" ? current.proyecto_id : "",
                      proyecto_nombre_snapshot: event.target.value === "proyecto" ? current.proyecto_nombre_snapshot : "",
                    }))
                  }
                  value={form.es_proyecto ? "proyecto" : "general"}
                >
                  <option value="general">General</option>
                  <option value="proyecto">Proyecto</option>
                </select>
              </Field>
              <Field label="Proveedor sugerido">
                <select
                  onChange={(event) => setForm((current) => ({ ...current, proveedor_sugerido_id: event.target.value }))}
                  value={form.proveedor_sugerido_id}
                >
                  <option value="">Sin proveedor sugerido</option>
                  {suppliers.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>
                      {supplier.nombre}
                    </option>
                  ))}
                </select>
              </Field>
              {form.es_proyecto ? (
                <>
                  {projectLookupAvailable ? (
                    <Field hint="Selecciona un proyecto activo si PM esta habilitado." label="Proyecto">
                      <select
                        onChange={(event) => {
                          const project = projects.find((item) => item.id === event.target.value);
                          setForm((current) => ({
                            ...current,
                            proyecto_id: event.target.value,
                            proyecto_nombre_snapshot: project?.nombre ?? current.proyecto_nombre_snapshot,
                          }));
                        }}
                        value={form.proyecto_id}
                      >
                        <option value="">Selecciona un proyecto</option>
                        {projects.map((project) => (
                          <option key={project.id} value={project.id}>
                            {project.nombre}
                          </option>
                        ))}
                      </select>
                    </Field>
                  ) : null}
                  <Field hint="Se guarda como snapshot para trazabilidad." label={projectLookupAvailable ? "Nombre visible del proyecto" : "Proyecto"}>
                    <input
                      onChange={(event) =>
                        setForm((current) => ({ ...current, proyecto_nombre_snapshot: event.target.value }))
                      }
                      placeholder="Nombre o referencia del proyecto"
                      type="text"
                      value={form.proyecto_nombre_snapshot}
                    />
                  </Field>
                </>
              ) : null}
              <Field label="Notas / motivo" span={2}>
                <textarea
                  onChange={(event) => setForm((current) => ({ ...current, notas: event.target.value }))}
                  rows={4}
                  value={form.notas}
                />
              </Field>
            </FormGrid>
          </div>

          <div className="inventory-form-section">
            <strong>Renglones</strong>
            <div className="inventory-material-picker">
              <SearchInput
                hint="Busca por nombre, SKU, codigo de barras o categoria."
                label="Buscar material"
                onChange={(event) => setMaterialSearch(event.target.value)}
                placeholder="Buscar material..."
                value={materialSearch}
              />
              {filteredMaterials.length > 0 ? (
                <div className="inventory-actions inventory-actions-wrap">
                  {filteredMaterials.slice(0, 6).map((material) => (
                    <ActionButton key={material.id} onClick={() => addLineFromMaterial(material.id)} size="sm" type="button">
                      {material.sku} · {material.nombre}
                    </ActionButton>
                  ))}
                </div>
              ) : (
                <p className="table-note">No hay materiales adicionales para agregar con ese filtro.</p>
              )}
            </div>

            {lines.length === 0 ? (
              <EmptyState compact note="Agrega al menos un material antes de enviar la requisicion." title="Sin renglones" />
            ) : (
              <DataTable columns={["Material", "Cantidad solicitada", "Stock actual", "Proveedor sugerido", "Notas", "Acciones"]}>
                <tbody>
                  {lines.map((line) => {
                    const material = materials.find((item) => item.id === line.material_id);
                    return (
                      <tr key={line.clientId}>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(material?.nombre, "Material")}</div>
                          <div className="inventory-cell-sub">
                            {safeDisplayText(material?.sku, "Sin SKU")} · {safeDisplayText(material?.unidad, "Sin unidad")}
                          </div>
                        </td>
                        <td>
                          <input
                            min="0.0001"
                            onChange={(event) => updateLine(line.clientId, "cantidad", normalizeDecimalInput(event.target.value))}
                            step="0.0001"
                            type="number"
                            value={line.cantidad}
                          />
                        </td>
                        <td>{formatCompactNumber(material?.stock_total ?? 0)}</td>
                        <td>{safeDisplayText(material?.proveedor_principal_nombre, "—")}</td>
                        <td>
                          <input
                            onChange={(event) => updateLine(line.clientId, "notas", event.target.value)}
                            placeholder="Notas del renglon"
                            type="text"
                            value={line.notas}
                          />
                        </td>
                        <td>
                          <ActionButton icon={<XCircle size={14} strokeWidth={1.9} />} onClick={() => removeLine(line.clientId)} size="sm" tone="danger" type="button">
                            Quitar
                          </ActionButton>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </DataTable>
            )}
          </div>
        </div>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            {selectedRequisition?.estatus === "borrador" ? (
              <>
                <ActionButton disabled={saving} onClick={() => openEditEditor(selectedRequisition.id)} type="button">
                  Editar
                </ActionButton>
                <ActionButton disabled={saving} onClick={() => handleStatusChange("submit", selectedRequisition.id)} type="button">
                  Enviar
                </ActionButton>
              </>
            ) : null}
            {canApproveRequisition(selectedRequisition) ? (
              <ActionButton disabled={saving} onClick={() => handleStatusChange("approve", selectedRequisition.id)} type="button">
                Aprobar
              </ActionButton>
            ) : null}
            {canApproveRequisition(selectedRequisition) && selectedRequisition?.es_proyecto && isManager ? (
              <ActionButton disabled={saving} onClick={() => handleApproveAndFulfill(selectedRequisition)} type="button">
                Aprobar y surtir
              </ActionButton>
            ) : null}
            {canRejectRequisition(selectedRequisition) ? (
              <ActionButton disabled={saving} onClick={() => handleStatusChange("reject", selectedRequisition.id)} tone="danger" type="button">
                Rechazar
              </ActionButton>
            ) : null}
            {canFulfillRequisition(selectedRequisition) ? (
              <ActionButton disabled={saving} onClick={() => openFulfillModal(selectedRequisition)} tone="primary" type="button">
                Surtir
              </ActionButton>
            ) : null}
            {canCreatePurchaseOrder(selectedRequisition) ? (
              <ActionButton disabled={saving} onClick={() => openPurchaseOrderModal(selectedRequisition)} type="button">
                Crear OC
              </ActionButton>
            ) : null}
            {canCancelRequisition(selectedRequisition) ? (
              <ActionButton disabled={saving} onClick={() => handleStatusChange("cancel", selectedRequisition.id)} tone="danger" type="button">
                Cancelar
              </ActionButton>
            ) : null}
            <ActionButton onClick={closeDetail} type="button">
              Cerrar
            </ActionButton>
          </div>
        }
        onClose={closeDetail}
        open={detailOpen}
        size="xl"
        subtitle="Detalle operativo de la solicitud y su surtido desde inventario."
        title={selectedRequisition ? `Requisición ${selectedRequisition.folio}` : "Detalle de requisición"}
      >
        {selectedRequisition ? (
          <div className="inventory-modal-form">
            <div className="inventory-detail-grid">
              <div className="inventory-form-note">
                <strong>Estatus</strong>
                <p className="table-note">
                  <StatusBadge tone={getRequisitionStatusTone(selectedRequisition.estatus)}>
                    {getRequisitionStatusLabel(selectedRequisition.estatus)}
                  </StatusBadge>
                </p>
              </div>
              <div className="inventory-form-note">
                <strong>Tipo</strong>
                <p className="table-note">{selectedRequisition.es_proyecto ? "Proyecto" : "General"}</p>
              </div>
              <div className="inventory-form-note">
                <strong>Proyecto</strong>
                <p className="table-note">{safeDisplayText(selectedRequisition.proyecto_nombre_snapshot, "—")}</p>
              </div>
              <div className="inventory-form-note">
                <strong>Tarea</strong>
                <p className="table-note">{safeDisplayText(selectedRequisition.tarea_nombre_snapshot, "Proyecto general")}</p>
              </div>
              <div className="inventory-form-note">
                <strong>Partida</strong>
                <p className="table-note">{safeDisplayText(selectedRequisition.partida_nombre_snapshot, "Sin partida")}</p>
              </div>
              <div className="inventory-form-note">
                <strong>Proveedor sugerido</strong>
                <p className="table-note">{safeDisplayText(selectedRequisition.proveedor_sugerido_nombre, "—")}</p>
              </div>
              <div className="inventory-form-note">
                <strong>Orden vinculada</strong>
                <p className="table-note">{safeDisplayText(selectedRequisition.orden_compra_folio, "—")}</p>
              </div>
              <div className="inventory-form-note">
                <strong>Fechas</strong>
                <p className="table-note">
                  Creada: {formatDateTime(selectedRequisition.created_at)}
                  <br />
                  Actualizada: {formatDateTime(selectedRequisition.updated_at)}
                </p>
              </div>
            </div>

            {selectedRequisition.motivo_rechazo ? (
              <div className="inventory-form-note inventory-form-note-danger">
                <strong>Motivo de rechazo</strong>
                <p className="table-note">{safeDisplayText(selectedRequisition.motivo_rechazo)}</p>
              </div>
            ) : null}

            <div className="inventory-metric-grid inventory-metric-grid-4">
              <MetricCard label="Renglones" tone="neutral" value={formatCompactNumber(selectedRequisition.total_renglones)} />
              <MetricCard label="Solicitado" tone="info" value={formatCompactNumber(selectedRequisition.cantidad_total_solicitada)} />
              <MetricCard label="Aprobado" tone="info" value={formatCompactNumber(selectedRequisition.cantidad_total_aprobada ?? 0)} />
              <MetricCard label="Surtido" tone="success" value={formatCompactNumber(selectedRequisition.cantidad_total_surtida)} />
              <MetricCard label="Pendiente" tone="warning" value={formatCompactNumber(selectedRequisition.cantidad_total_pendiente)} />
            </div>

            <DataCard subtitle={selectedRequisition.notas || "Sin notas adicionales."} title="Renglones">
              {selectedRequisition.details?.length ? (
                <DataTable columns={["Material", "Solicitado", "Aprobado", "Surtido", "Pendiente", "Stock total", "Proveedor", "Estado"]}>
                  <tbody>
                    {selectedRequisition.details.map((detail) => (
                      <tr key={detail.id}>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(detail.material_nombre)}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(detail.material_sku)} · {safeDisplayText(detail.material_unidad)}</div>
                        </td>
                        <td>{formatCompactNumber(detail.cantidad)}</td>
                        <td>{formatCompactNumber(detail.cantidad_aprobada ?? detail.cantidad)}</td>
                        <td>{formatCompactNumber(detail.cantidad_surtida)}</td>
                        <td>{formatCompactNumber(detail.cantidad_pendiente)}</td>
                        <td>{formatCompactNumber(detail.stock_total)}</td>
                        <td>{safeDisplayText(detail.proveedor_sugerido_nombre, "—")}</td>
                        <td>
                          <StatusBadge tone={detail.estado_linea === "surtido" ? "success" : detail.estado_linea === "parcial" ? "warning" : "neutral"}>
                            {getLineStateLabel(detail.estado_linea)}
                          </StatusBadge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              ) : (
                <EmptyState compact note="La requisicion no tiene materiales cargados." title="Sin renglones" />
              )}
            </DataCard>

            <DataCard title="Trazabilidad">
              {selectedRequisition.movements?.length ? (
                <DataTable columns={["Fecha", "Almacen", "Material", "Cantidad", "Documento", "Proyecto", "Usuario"]}>
                  <tbody>
                    {selectedRequisition.movements.map((movement) => (
                      <tr key={movement.id}>
                        <td>{formatDateTime(movement.created_at)}</td>
                        <td>{safeDisplayText(movement.almacen_nombre)}</td>
                        <td>
                          <div className="inventory-cell-main">{safeDisplayText(movement.material_nombre)}</div>
                          <div className="inventory-cell-sub">{safeDisplayText(movement.material_sku)}</div>
                        </td>
                        <td>{formatCompactNumber(movement.cantidad)}</td>
                        <td>{safeDisplayText(movement.documento_referencia, "—")}</td>
                        <td>{safeDisplayText(movement.proyecto_nombre_snapshot || movement.proyecto_id, "—")}</td>
                        <td>{safeDisplayText(movement.created_by_nombre, "—")}</td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              ) : (
                <EmptyState
                  compact
                  note={selectedRequisition.orden_compra_id ? "La salida no se ha surtido desde inventario. La trazabilidad continua desde la orden de compra vinculada." : "Los surtidos desde inventario apareceran aqui cuando se registren."}
                  title="Sin movimientos relacionados"
                />
              )}
            </DataCard>
          </div>
        ) : null}
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeFulfill} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} onClick={handleFulfillSubmit} tone="primary" type="button">
              {saving ? "Registrando..." : "Confirmar surtido"}
            </ActionButton>
          </div>
        }
        onClose={closeFulfill}
        open={fulfillOpen}
        size="xl"
        subtitle="Esta accion descontara inventario del almacen seleccionado."
        title={selectedRequisition ? `Surtir requisicion ${selectedRequisition.folio}` : "Surtir requisicion"}
      >
        {selectedRequisition ? (
          <div className="inventory-modal-form">
            <div className="inventory-form-section">
              <strong>Cabecera de surtido</strong>
              <FormGrid>
                <Field label="Almacen origen">
                  <select
                    onChange={(event) =>
                      setFulfillForm((current) => ({
                        ...current,
                        almacen_id: event.target.value,
                        items: buildDefaultFulfillItems(selectedRequisition.details ?? [], event.target.value),
                      }))
                    }
                    value={fulfillForm.almacen_id}
                  >
                    <option value="">Selecciona un almacen</option>
                    {warehouses.map((warehouse) => (
                      <option key={warehouse.id} value={warehouse.id}>
                        {warehouse.nombre} ({warehouse.codigo})
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Documento / referencia">
                  <input
                    onChange={(event) => setFulfillForm((current) => ({ ...current, documento_referencia: event.target.value }))}
                    placeholder="Remision, ticket interno, etc."
                    type="text"
                    value={fulfillForm.documento_referencia}
                  />
                </Field>
                <Field label="Notas" span={2}>
                  <textarea
                    onChange={(event) => setFulfillForm((current) => ({ ...current, notas: event.target.value }))}
                    rows={3}
                    value={fulfillForm.notas}
                  />
                </Field>
                {selectedRequisition.es_proyecto ? (
                  <>
                    <Field label="Proyecto">
                      <input readOnly type="text" value={fulfillForm.proyecto_nombre_snapshot || fulfillForm.proyecto_id} />
                    </Field>
                    <Field label="Contexto PM">
                      <input
                        readOnly
                        type="text"
                        value={
                          [
                            safeDisplayText(selectedRequisition.tarea_nombre_snapshot, ""),
                            safeDisplayText(selectedRequisition.partida_nombre_snapshot, ""),
                          ]
                            .filter(Boolean)
                            .join(" · ") || "Proyecto general"
                        }
                      />
                    </Field>
                  </>
                ) : null}
              </FormGrid>
            </div>

            <DataCard title="Renglones pendientes">
              <DataTable columns={["Material", "Solicitado", "Surtido", "Pendiente", "Stock en almacen", "Cantidad a surtir"]}>
                <tbody>
                  {selectedRequisition.details
                    .filter((detail) => Number(detail.cantidad_pendiente ?? 0) > 0)
                    .map((detail) => {
                      const available = getWarehouseStock(detail, fulfillForm.almacen_id);
                      const pending = Number(detail.cantidad_pendiente ?? 0);
                      const hasShortage = available < pending;
                      return (
                        <tr key={detail.id}>
                          <td>
                            <div className="inventory-cell-main">{safeDisplayText(detail.material_nombre)}</div>
                            <div className="inventory-cell-sub">{safeDisplayText(detail.material_sku)}</div>
                          </td>
                          <td>{formatCompactNumber(detail.cantidad)}</td>
                          <td>{formatCompactNumber(detail.cantidad_surtida)}</td>
                          <td>{formatCompactNumber(pending)}</td>
                          <td>
                            <div className="inventory-cell-main">{formatCompactNumber(available)}</div>
                            {hasShortage ? <div className="inventory-cell-sub">Stock insuficiente para surtir todo.</div> : null}
                          </td>
                          <td>
                            <input
                              max={Math.max(0, Math.min(pending, available))}
                              min="0"
                              onChange={(event) =>
                                setFulfillForm((current) => ({
                                  ...current,
                                  items: {
                                    ...current.items,
                                    [detail.id]: normalizeDecimalInput(event.target.value),
                                  },
                                }))
                              }
                              step="0.0001"
                              type="number"
                              value={fulfillForm.items[detail.id] ?? ""}
                            />
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </DataTable>
            </DataCard>
          </div>
        ) : null}
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closePurchaseOrder} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              disabled={saving || !purchaseOrderForm.proveedor_id || !purchaseOrderForm.almacen_destino_id}
              onClick={handleCreatePurchaseOrder}
              tone="primary"
              type="button"
            >
              {saving ? "Creando..." : "Crear OC"}
            </ActionButton>
          </div>
        }
        onClose={closePurchaseOrder}
        open={purchaseOrderOpen}
        size="medium"
        subtitle="La requisicion quedara vinculada a la orden de compra creada."
        title="Crear orden de compra"
      >
        <FormGrid>
          <Field label="Proveedor">
            <select
              onChange={(event) => setPurchaseOrderForm((current) => ({ ...current, proveedor_id: event.target.value }))}
              value={purchaseOrderForm.proveedor_id}
            >
              <option value="">Selecciona un proveedor</option>
              {suppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.nombre}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Almacen destino">
            <select
              onChange={(event) =>
                setPurchaseOrderForm((current) => ({ ...current, almacen_destino_id: event.target.value }))
              }
              value={purchaseOrderForm.almacen_destino_id}
            >
              <option value="">Selecciona un almacen</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.nombre} ({warehouse.codigo})
                </option>
              ))}
            </select>
          </Field>
          <Field hint="Opcional" label="Folio OC">
            <input
              onChange={(event) => setPurchaseOrderForm((current) => ({ ...current, folio: event.target.value.toUpperCase() }))}
              placeholder="Auto"
              type="text"
              value={purchaseOrderForm.folio}
            />
          </Field>
        </FormGrid>
      </ModalShell>
    </div>
  );
}


function ClipboardListIcon() {
  return <ShoppingCart size={18} strokeWidth={1.9} />;
}
