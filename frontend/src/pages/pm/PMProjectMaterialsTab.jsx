import { useEffect, useMemo, useState } from "react";
import { ClipboardList, Factory, PackageMinus, PackageOpen, RotateCcw, ScrollText, Plus } from "lucide-react";

import {
  addPmProjectMaterialPlan,
  consumePmProjectMaterial,
  createPmProjectMaterialRequisition,
  deactivatePmProjectMaterialPlan,
  getMaterialKardex,
  getMaterials,
  getPmProjectBudget,
  getPmProjectMaterials,
  getStock,
  getWarehouses,
  listPmTasks,
  returnPmProjectMaterial,
  updatePmProjectMaterialPlan,
} from "../../api/client";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FormGrid,
  MetricCard,
  ModalShell,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  formatDate,
  formatDateTime,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";


const defaultPlanForm = {
  tarea_id: "",
  material_id: "",
  cantidad_planificada: "",
  costo_unitario_estimado: "",
  observaciones: "",
};

const defaultMovementForm = {
  material_id: "",
  almacen_id: "",
  cantidad: "",
  tarea_id: "",
  partida_id: "",
  notas: "",
};

const defaultRequisitionForm = {
  almacen_destino_id: "",
  notas: "",
  items: {},
};

function buildDefaultRequisitionItems(plans) {
  return plans.reduce((accumulator, plan) => {
    accumulator[plan.id] = {
      selected: Number(plan.cantidad_pendiente || 0) > 0,
      cantidad_solicitada: Number(plan.cantidad_pendiente || 0) > 0 ? String(plan.cantidad_pendiente) : "0",
    };
    return accumulator;
  }, {});
}

function getPlanStatusTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "completo") {
    return "success";
  }
  if (normalized === "parcial") {
    return "warning";
  }
  if (normalized === "cancelado") {
    return "danger";
  }
  return "neutral";
}

function getMovementOriginLabel(origin) {
  if (origin === "requisicion_surtida") {
    return "Requisición surtida";
  }
  if (origin === "devolucion_proyecto") {
    return "Devolución";
  }
  if (origin === "ajuste_admin") {
    return "Ajuste administrativo";
  }
  return "Consumo directo";
}

function getMovementOriginTone(origin) {
  if (origin === "requisicion_surtida") {
    return "success";
  }
  if (origin === "devolucion_proyecto") {
    return "warning";
  }
  if (origin === "ajuste_admin") {
    return "info";
  }
  return "neutral";
}

function buildMovementSeed(plan = null, movement = null) {
  return {
    material_id: plan?.material_id ?? movement?.material_id ?? "",
    almacen_id: movement?.almacen_id ?? "",
    cantidad: "",
    tarea_id: plan?.tarea_id ?? movement?.tarea_id ?? "",
    partida_id: movement?.partida_id ?? "",
    notas: "",
  };
}

function buildBudgetItemOptions(bundle) {
  const items = bundle?.budget?.items ?? [];
  return items
    .filter((item) => item.activo !== false && item.tipo === "partida")
    .map((item) => ({
      id: item.id,
      nombre: item.nombre,
      codigo: item.codigo,
    }))
    .sort((left, right) =>
      `${safeDisplayText(left.codigo)} ${safeDisplayText(left.nombre)}`.localeCompare(
        `${safeDisplayText(right.codigo)} ${safeDisplayText(right.nombre)}`,
        "es",
      ),
    );
}

function buildMaterialStockMap(stockItems) {
  return stockItems.reduce((accumulator, stock) => {
    if (!accumulator[stock.material_id]) {
      accumulator[stock.material_id] = {};
    }
    accumulator[stock.material_id][stock.almacen_id] = Number(stock.cantidad || 0);
    return accumulator;
  }, {});
}

function getSignedQuantityLabel(consumption) {
  const quantity = Number(consumption?.cantidad_consumida || 0);
  return formatNumber(quantity);
}

function getSignedMoneyLabel(consumption) {
  return formatMoney(consumption?.costo_total_snapshot || 0);
}

export default function PMProjectMaterialsTab({
  canEdit = false,
  canManage = false,
  empresaId,
  onChanged,
  project,
  projectEditable = true,
  projectId,
  token,
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [materialsResponse, setMaterialsResponse] = useState(null);
  const [inventoryMaterials, setInventoryMaterials] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [budgetItems, setBudgetItems] = useState([]);
  const [stockItems, setStockItems] = useState([]);
  const [materialSearch, setMaterialSearch] = useState("");
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [planForm, setPlanForm] = useState(defaultPlanForm);
  const [showPlanCostOptions, setShowPlanCostOptions] = useState(false);
  const [requisitionModalOpen, setRequisitionModalOpen] = useState(false);
  const [requisitionForm, setRequisitionForm] = useState(defaultRequisitionForm);
  const [movementModalState, setMovementModalState] = useState({ open: false, mode: "consume", seed: defaultMovementForm });
  const [movementForm, setMovementForm] = useState(defaultMovementForm);
  const [kardexModal, setKardexModal] = useState({ open: false, loading: false, error: "", data: null, materialName: "" });

  const plans = materialsResponse?.plans ?? [];
  const consumptions = materialsResponse?.consumptions ?? [];
  const summary = materialsResponse?.summary;
  const canOperate = canEdit && projectEditable;
  const stockMap = useMemo(() => buildMaterialStockMap(stockItems), [stockItems]);

  const filteredMaterials = useMemo(() => {
    const q = materialSearch.trim().toLowerCase();
    if (!q) {
      return inventoryMaterials;
    }
    return inventoryMaterials.filter((material) =>
      [material.sku, material.nombre, material.codigo_barras, material.categoria]
        .filter(Boolean)
        .some((value) => safeDisplayText(value, "").toLowerCase().includes(q)),
    );
  }, [inventoryMaterials, materialSearch]);

  const pendingPlans = useMemo(
    () => plans.filter((plan) => Number(plan.cantidad_pendiente || 0) > 0 && plan.activo),
    [plans],
  );

  const materialsById = useMemo(
    () => Object.fromEntries(inventoryMaterials.map((material) => [material.id, material])),
    [inventoryMaterials],
  );

  const movementSelectedMaterial = materialsById[movementForm.material_id] ?? null;
  const availableStock = Number(stockMap[movementForm.material_id]?.[movementForm.almacen_id] || 0);
  const movementAutoCost = useMemo(() => {
    if (!movementSelectedMaterial) {
      return 0;
    }
    const averageCost = Number(movementSelectedMaterial.costo_promedio_actual || 0);
    if (averageCost > 0) {
      return averageCost;
    }
    const referenceCost = Number(movementSelectedMaterial.costo_unitario || 0);
    return referenceCost > 0 ? referenceCost : 0;
  }, [movementSelectedMaterial]);

  const planRealCostMap = useMemo(() => {
    return consumptions.reduce((accumulator, item) => {
      const key = `${item.material_id}:${item.tarea_id ?? ""}`;
      accumulator[key] = (accumulator[key] || 0) + Number(item.costo_total_snapshot || 0);
      return accumulator;
    }, {});
  }, [consumptions]);

  async function loadMaterialsTab({ preserveSuccess = true } = {}) {
    if (!token || !empresaId || !projectId) {
      return;
    }
    setLoading(true);
    if (!preserveSuccess) {
      setSuccess("");
    }
    setError("");
    try {
      const [projectMaterialsResponse, materialsCatalogResponse, warehousesResponse, tasksResponse, budgetResponse, stockResponse] =
        await Promise.all([
          getPmProjectMaterials({ projectId, token, empresaId }),
          getMaterials({ token, empresaId, filters: { activo: true, limit: 300, offset: 0 } }),
          getWarehouses({ token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
          listPmTasks({ projectId, token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
          getPmProjectBudget({ projectId, token, empresaId }).catch(() => null),
          getStock({ token, empresaId, filters: { limit: 1000, offset: 0 } }),
        ]);
      setMaterialsResponse(projectMaterialsResponse);
      setInventoryMaterials(materialsCatalogResponse.items ?? []);
      setWarehouses(warehousesResponse.items ?? []);
      setTasks(tasksResponse.items ?? []);
      setBudgetItems(buildBudgetItemOptions(budgetResponse));
      setStockItems(stockResponse.items ?? []);
      setRequisitionForm((current) => ({
        ...current,
        almacen_destino_id: current.almacen_destino_id || warehousesResponse.items?.[0]?.id || "",
      }));
    } catch (requestError) {
      setError(requestError.message || "No se pudieron cargar los materiales del proyecto.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMaterialsTab();
  }, [token, empresaId, projectId]);

  function closePlanModal(force = false) {
    if (saving && !force) {
      return;
    }
    setEditingPlan(null);
    setPlanForm(defaultPlanForm);
    setShowPlanCostOptions(false);
    setMaterialSearch("");
    setPlanModalOpen(false);
  }

  function openCreatePlanModal() {
    setEditingPlan(null);
    setPlanForm(defaultPlanForm);
    setShowPlanCostOptions(false);
    setMaterialSearch("");
    setPlanModalOpen(true);
  }

  function openEditPlanModal(plan) {
    setEditingPlan(plan);
    setPlanForm({
      tarea_id: plan.tarea_id ?? "",
      material_id: plan.material_id ?? "",
      cantidad_planificada: plan.cantidad_planificada ?? "",
      costo_unitario_estimado: plan.costo_unitario_estimado ?? "",
      observaciones: plan.observaciones ?? "",
    });
    setShowPlanCostOptions(false);
    setMaterialSearch(`${safeDisplayText(plan.material_sku_snapshot)} ${safeDisplayText(plan.material_nombre_snapshot)}`);
    setPlanModalOpen(true);
  }

  function openRequisitionModal(initialPlans = pendingPlans) {
    const availablePlans = initialPlans.filter((plan) => Number(plan.cantidad_pendiente || 0) > 0 && plan.activo);
    setRequisitionForm({
      almacen_destino_id: warehouses[0]?.id ?? "",
      notas: "",
      items: buildDefaultRequisitionItems(availablePlans),
    });
    setRequisitionModalOpen(true);
  }

  function closeRequisitionModal(force = false) {
    if (saving && !force) {
      return;
    }
    setRequisitionModalOpen(false);
    setRequisitionForm(defaultRequisitionForm);
  }

  function openMovementModal(mode, { plan = null, movement = null } = {}) {
    const nextSeed = buildMovementSeed(plan, movement);
    const fallbackWarehouseId =
      movement?.almacen_id ||
      Object.keys(stockMap[nextSeed.material_id] || {}).find((warehouseId) => Number(stockMap[nextSeed.material_id]?.[warehouseId] || 0) > 0) ||
      warehouses[0]?.id ||
      "";
    nextSeed.almacen_id = nextSeed.almacen_id || fallbackWarehouseId;
    setMovementModalState({ open: true, mode, seed: nextSeed });
    setMovementForm(nextSeed);
  }

  function closeMovementModal(force = false) {
    if (saving && !force) {
      return;
    }
    setMovementModalState({ open: false, mode: "consume", seed: defaultMovementForm });
    setMovementForm(defaultMovementForm);
  }

  async function openKardexModal(materialId, materialName) {
    setKardexModal({ open: true, loading: true, error: "", data: null, materialName });
    try {
      const response = await getMaterialKardex({ materialId, token, empresaId });
      setKardexModal({ open: true, loading: false, error: "", data: response, materialName });
    } catch (requestError) {
      setKardexModal({
        open: true,
        loading: false,
        error: requestError.message || "No se pudo cargar el kardex del material.",
        data: null,
        materialName,
      });
    }
  }

  async function handleSavePlan(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        tarea_id: planForm.tarea_id || null,
        material_id: planForm.material_id,
        cantidad_planificada: Number(planForm.cantidad_planificada || 0),
        costo_unitario_estimado:
          showPlanCostOptions && planForm.costo_unitario_estimado !== ""
            ? Number(planForm.costo_unitario_estimado || 0)
            : null,
        observaciones: planForm.observaciones.trim() || null,
      };
      if (editingPlan?.id) {
        await updatePmProjectMaterialPlan({ projectId, planId: editingPlan.id, token, empresaId, payload });
        setSuccess("Material planeado actualizado.");
      } else {
        await addPmProjectMaterialPlan({ projectId, token, empresaId, payload });
        setSuccess("Material planeado agregado.");
      }
      await loadMaterialsTab();
      closePlanModal(true);
      await onChanged?.();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el material planeado.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivatePlan(plan) {
    if (!window.confirm("El material planeado se desactivará del proyecto. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmProjectMaterialPlan({ projectId, planId: plan.id, token, empresaId });
      setSuccess("Material planeado desactivado.");
      await loadMaterialsTab();
      await onChanged?.();
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar el material planeado.");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateRequisition(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const items = pendingPlans
        .map((plan) => ({
          plan_id: plan.id,
          selected: Boolean(requisitionForm.items?.[plan.id]?.selected),
          cantidad_solicitada: Number(requisitionForm.items?.[plan.id]?.cantidad_solicitada || 0),
        }))
        .filter((item) => item.selected && item.cantidad_solicitada > 0)
        .map((item) => ({
          plan_id: item.plan_id,
          cantidad_solicitada: item.cantidad_solicitada,
        }));

      if (items.length === 0) {
        throw new Error("Selecciona al menos un material pendiente para crear la requisición.");
      }

      const response = await createPmProjectMaterialRequisition({
        projectId,
        token,
        empresaId,
        payload: {
          almacen_destino_id: requisitionForm.almacen_destino_id,
          notas: requisitionForm.notas.trim() || null,
          items,
        },
      });
      setSuccess(`Requisición ${safeDisplayText(response.folio)} creada como borrador.`);
      await loadMaterialsTab();
      closeRequisitionModal(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo crear la requisición del proyecto.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveMovement(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      if (!movementForm.material_id) {
        throw new Error("Selecciona un material.");
      }
      if (!movementForm.almacen_id) {
        throw new Error("Selecciona un almacén.");
      }
      const quantity = Number(movementForm.cantidad || 0);
      if (quantity <= 0) {
        throw new Error("La cantidad debe ser mayor a cero.");
      }
      if (movementModalState.mode === "consume" && quantity > availableStock) {
        throw new Error("No hay stock suficiente en este almacén.");
      }

      const payload = {
        material_id: movementForm.material_id,
        almacen_id: movementForm.almacen_id,
        cantidad: quantity,
        tarea_id: movementForm.tarea_id || null,
        partida_id: movementForm.partida_id || null,
        notas: movementForm.notas.trim() || null,
      };
      const nextResponse =
        movementModalState.mode === "consume"
          ? await consumePmProjectMaterial({ projectId, token, empresaId, payload })
          : await returnPmProjectMaterial({ projectId, token, empresaId, payload });
      setMaterialsResponse(nextResponse);
      setSuccess(
        movementModalState.mode === "consume"
          ? "Material consumido y registrado en inventario."
          : "Material devuelto al almacén.",
      );
      closeMovementModal(true);
      await loadMaterialsTab();
      await onChanged?.();
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar el movimiento del material.");
    } finally {
      setSaving(false);
    }
  }

  const consumptionRowsForKardex = useMemo(() => {
    const movementRows = kardexModal.data?.movements ?? [];
    return movementRows.filter((movement) => movement.proyecto_id === projectId);
  }, [kardexModal.data, projectId]);

  if (loading) {
    return <div className="screen-center">Cargando materiales del proyecto...</div>;
  }

  return (
    <div className="inventory-content-grid">
      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-5">
        <MetricCard
          icon={<Factory size={18} strokeWidth={1.9} />}
          label="Costo planeado"
          meta="Materiales del proyecto"
          tone="info"
          value={formatMoney(summary?.costo_estimado ?? 0)}
        />
        <MetricCard
          icon={<PackageMinus size={18} strokeWidth={1.9} />}
          label="Costo real"
          meta="Consumo neto desde inventario"
          tone="success"
          value={formatMoney(summary?.costo_real ?? 0)}
        />
        <MetricCard
          icon={<ClipboardList size={18} strokeWidth={1.9} />}
          label="Diferencia"
          meta="Real vs planeado"
          tone={Number(summary?.variacion ?? 0) > 0 ? "warning" : "neutral"}
          value={formatMoney(summary?.variacion ?? 0)}
        />
        <MetricCard
          icon={<PackageOpen size={18} strokeWidth={1.9} />}
          label="Planeado"
          meta="Cantidad total"
          tone="neutral"
          value={formatNumber(summary?.total_materiales_planeados ?? 0)}
        />
        <MetricCard
          icon={<RotateCcw size={18} strokeWidth={1.9} />}
          label="Consumido neto"
          meta="Consumo menos devoluciones"
          tone="warning"
          value={formatNumber(summary?.total_materiales_consumidos ?? 0)}
        />
      </section>

      <div className="inventory-form-note">
        <strong>Inventario es la fuente de verdad</strong>
        <p className="table-note">
          Cada consumo o devolución actualiza existencias, movimientos, Kardex y costo real del proyecto.
        </p>
      </div>

      <DataCard
        actions={
          <div className="inventory-actions">
            <ActionButton
              disabled={!canOperate || pendingPlans.length === 0}
              icon={<ClipboardList size={16} strokeWidth={1.9} />}
              onClick={() => openRequisitionModal()}
              type="button"
            >
              Crear requisición
            </ActionButton>
            <ActionButton
              disabled={!canOperate}
              icon={<PackageMinus size={16} strokeWidth={1.9} />}
              onClick={() => openMovementModal("consume")}
              type="button"
            >
              Consumir material
            </ActionButton>
            <ActionButton
              disabled={!canOperate}
              icon={<RotateCcw size={16} strokeWidth={1.9} />}
              onClick={() => openMovementModal("return")}
              type="button"
            >
              Devolver material
            </ActionButton>
            <ActionButton
              disabled={!canOperate}
              icon={<Plus size={16} strokeWidth={1.9} />}
              onClick={openCreatePlanModal}
              tone="primary"
              type="button"
            >
              Agregar material planeado
            </ActionButton>
          </div>
        }
        subtitle="Planeado vs consumido real por material, tarea y almacén principal."
        title="Materiales del proyecto"
      >
        <ResultMeta label="materiales" loaded={plans.length} total={plans.length} />
        {plans.length === 0 ? (
          <EmptyState
            compact
            note="Agrega materiales planeados para controlar consumo real y costo del proyecto."
            title="Sin materiales planeados"
          />
        ) : (
          <DataTable
            columns={[
              "Material",
              "Unidad",
              "Planeado",
              "Consumido",
              "Pendiente",
              "Costo real",
              "Almacén principal",
              "Acciones",
            ]}
          >
            <tbody>
              {plans.map((plan) => {
                const planKey = `${plan.material_id}:${plan.tarea_id ?? ""}`;
                return (
                  <tr key={plan.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(plan.material_nombre_snapshot)}</div>
                      <div className="inventory-cell-sub">
                        {safeDisplayText(plan.material_sku_snapshot, "—")} · {safeDisplayText(plan.tarea_titulo, "Proyecto general")}
                      </div>
                    </td>
                    <td>{safeDisplayText(plan.unidad, "—")}</td>
                    <td>{formatNumber(plan.cantidad_planificada)}</td>
                    <td>
                      <div className="inventory-cell-main">{formatNumber(plan.cantidad_consumida_real)}</div>
                      <StatusBadge tone={getPlanStatusTone(plan.estatus)}>{safeDisplayText(plan.estatus, "planeado")}</StatusBadge>
                    </td>
                    <td>{formatNumber(plan.cantidad_pendiente)}</td>
                    <td>{formatMoney(planRealCostMap[planKey] ?? 0)}</td>
                    <td>{safeDisplayText(plan.almacen_principal_nombre, "—")}</td>
                    <td>
                      <div className="table-actions">
                        <ActionButton onClick={() => openKardexModal(plan.material_id, plan.material_nombre_snapshot)} size="sm" type="button">
                          Kardex
                        </ActionButton>
                        {canOperate ? (
                          <>
                            <ActionButton onClick={() => openMovementModal("consume", { plan })} size="sm" type="button">
                              Consumir
                            </ActionButton>
                            <ActionButton
                              disabled={Number(plan.cantidad_consumida_real || 0) <= 0}
                              onClick={() => openMovementModal("return", { plan })}
                              size="sm"
                              type="button"
                            >
                              Devolver
                            </ActionButton>
                            <ActionButton onClick={() => openEditPlanModal(plan)} size="sm" type="button">
                              Editar
                            </ActionButton>
                            <ActionButton
                              disabled={Number(plan.cantidad_pendiente || 0) <= 0}
                              onClick={() => openRequisitionModal([plan])}
                              size="sm"
                              type="button"
                            >
                              Requisición
                            </ActionButton>
                            <ActionButton onClick={() => handleDeactivatePlan(plan)} size="sm" tone="danger" type="button">
                              Quitar
                            </ActionButton>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <DataCard subtitle="Historial neto de consumos y devoluciones vinculados al proyecto." title="Movimientos reales">
        <ResultMeta label="movimientos" loaded={consumptions.length} total={consumptions.length} />
        {consumptions.length === 0 ? (
          <EmptyState
            compact
            note="Los movimientos aparecerán cuando registres consumos, devoluciones o surtas requisiciones vinculadas al proyecto."
            title="Sin movimientos reales"
          />
        ) : (
          <DataTable
            columns={[
              "Fecha",
              "Material",
              "Cantidad",
              "Costo total",
              "Origen",
              "Almacén",
              "Tarea / partida",
              "Movimiento",
              "Notas",
            ]}
          >
            <tbody>
              {consumptions.map((consumption) => (
                <tr key={consumption.id}>
                  <td>{safeDisplayText(formatDateTime(consumption.created_at), "—")}</td>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(consumption.material_nombre_snapshot)}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(consumption.material_sku_snapshot, "—")}</div>
                  </td>
                  <td>{getSignedQuantityLabel(consumption)}</td>
                  <td>{getSignedMoneyLabel(consumption)}</td>
                  <td>
                    <StatusBadge tone={getMovementOriginTone(consumption.origen)}>
                      {getMovementOriginLabel(consumption.origen)}
                    </StatusBadge>
                  </td>
                  <td>{safeDisplayText(consumption.almacen_nombre, "—")}</td>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(consumption.tarea_titulo, "Proyecto general")}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(consumption.partida_nombre, "—")}</div>
                  </td>
                  <td>{safeDisplayText(consumption.movimiento_id, "—")}</td>
                  <td>{safeDisplayText(consumption.notas, "—")}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closePlanModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-project-material-plan-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingPlan ? "Actualizar material" : "Agregar material"}
            </ActionButton>
          </div>
        }
        onClose={closePlanModal}
        open={planModalOpen}
        size="large"
        subtitle="Selecciona el material, la tarea y la cantidad. El costo planeado se calculará automáticamente."
        title={editingPlan ? "Editar material planeado" : "Agregar material planeado"}
      >
        <form className="inventory-modal-form" id="pm-project-material-plan-form" onSubmit={handleSavePlan}>
          <SectionTitle subtitle="Busca por nombre, SKU o código de barras." title="Material" />
          <SearchInput
            onChange={(event) => setMaterialSearch(event.target.value)}
            placeholder="Filtrar materiales para seleccionar..."
            value={materialSearch}
          />
          <FormGrid>
            <Field label="Material" span={2}>
              <select
                onChange={(event) => setPlanForm((current) => ({ ...current, material_id: event.target.value }))}
                required
                value={planForm.material_id}
              >
                <option value="">Selecciona un material</option>
                {filteredMaterials.map((material) => (
                  <option key={material.id} value={material.id}>
                    {safeDisplayText(material.sku)} · {safeDisplayText(material.nombre)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Tarea asociada">
              <select
                onChange={(event) => setPlanForm((current) => ({ ...current, tarea_id: event.target.value }))}
                value={planForm.tarea_id}
              >
                <option value="">Proyecto general</option>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {safeDisplayText(task.titulo)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Cantidad planeada">
              <input
                min="0"
                onChange={(event) => setPlanForm((current) => ({ ...current, cantidad_planificada: event.target.value }))}
                required
                step="0.0001"
                type="number"
                value={planForm.cantidad_planificada}
              />
            </Field>

            <Field label="Observaciones" span={2}>
              <textarea
                onChange={(event) => setPlanForm((current) => ({ ...current, observaciones: event.target.value }))}
                rows={4}
                value={planForm.observaciones}
              />
            </Field>
          </FormGrid>

          <details className="inventory-optional-panel" open={showPlanCostOptions}>
            <summary
              onClick={(event) => {
                event.preventDefault();
                setShowPlanCostOptions((current) => !current);
              }}
            >
              Opciones de costeo
            </summary>
            <div className="inventory-optional-panel-body">
              <Field
                hint="Déjalo vacío para usar el costo actual del material."
                label="Costo unitario estimado, opcional"
              >
                <input
                  min="0"
                  onChange={(event) => setPlanForm((current) => ({ ...current, costo_unitario_estimado: event.target.value }))}
                  placeholder="Auto"
                  step="0.0001"
                  type="number"
                  value={planForm.costo_unitario_estimado}
                />
              </Field>
            </div>
          </details>
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeMovementModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-project-material-movement-form" tone="primary" type="submit">
              {saving
                ? movementModalState.mode === "consume"
                  ? "Consumiendo..."
                  : "Devolviendo..."
                : movementModalState.mode === "consume"
                  ? "Consumir material"
                  : "Devolver material"}
            </ActionButton>
          </div>
        }
        onClose={closeMovementModal}
        open={movementModalState.open}
        size="large"
        subtitle={
          movementModalState.mode === "consume"
            ? "Registra una salida real desde inventario y actualiza el costo del proyecto."
            : "Registra una devolución al almacén y ajusta el costo real del proyecto."
        }
        title={movementModalState.mode === "consume" ? "Consumir material" : "Devolver material"}
      >
        <form className="inventory-modal-form" id="pm-project-material-movement-form" onSubmit={handleSaveMovement}>
          <div className={`inventory-form-note ${movementAutoCost > 0 ? "" : "inventory-form-note-warning"}`}>
            <strong>{movementAutoCost > 0 ? "Costo automático" : "Sin costo registrado"}</strong>
            <p className="table-note">
              {movementAutoCost > 0
                ? "Se usará el costo actual del material para calcular el costo real del proyecto."
                : "Este material no tiene costo registrado. El movimiento se guardará con costo $0.00."}
            </p>
          </div>
          <FormGrid>
            <Field label="Material">
              <select
                onChange={(event) => {
                  const nextMaterialId = event.target.value;
                  const nextWarehouseId =
                    Object.keys(stockMap[nextMaterialId] || {}).find((warehouseId) => Number(stockMap[nextMaterialId]?.[warehouseId] || 0) > 0) ||
                    warehouses[0]?.id ||
                    "";
                  setMovementForm((current) => ({
                    ...current,
                    material_id: nextMaterialId,
                    almacen_id: current.almacen_id || nextWarehouseId,
                  }));
                }}
                required
                value={movementForm.material_id}
              >
                <option value="">Selecciona un material</option>
                {inventoryMaterials.map((material) => (
                  <option key={material.id} value={material.id}>
                    {safeDisplayText(material.sku)} · {safeDisplayText(material.nombre)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Almacén">
              <select
                onChange={(event) => setMovementForm((current) => ({ ...current, almacen_id: event.target.value }))}
                required
                value={movementForm.almacen_id}
              >
                <option value="">Selecciona un almacén</option>
                {warehouses.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {safeDisplayText(warehouse.nombre)} ({safeDisplayText(warehouse.codigo)})
                  </option>
                ))}
              </select>
            </Field>

            <Field hint={`Disponible: ${formatNumber(availableStock)}`} label="Cantidad">
              <input
                max={movementModalState.mode === "consume" ? availableStock : undefined}
                min="0"
                onChange={(event) => setMovementForm((current) => ({ ...current, cantidad: event.target.value }))}
                required
                step="0.0001"
                type="number"
                value={movementForm.cantidad}
              />
            </Field>

            <Field label="Tarea">
              <select
                onChange={(event) => setMovementForm((current) => ({ ...current, tarea_id: event.target.value }))}
                value={movementForm.tarea_id}
              >
                <option value="">Proyecto general</option>
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {safeDisplayText(task.titulo)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Partida">
              <select
                onChange={(event) => setMovementForm((current) => ({ ...current, partida_id: event.target.value }))}
                value={movementForm.partida_id}
              >
                <option value="">Sin partida</option>
                {budgetItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {safeDisplayText(item.codigo, "Partida")} · {safeDisplayText(item.nombre)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Notas" span={2}>
              <textarea
                onChange={(event) => setMovementForm((current) => ({ ...current, notas: event.target.value }))}
                rows={3}
                value={movementForm.notas}
              />
            </Field>
          </FormGrid>

          {movementSelectedMaterial ? (
            <div className="inventory-form-note">
              <strong>{safeDisplayText(movementSelectedMaterial.nombre)}</strong>
              <p className="table-note">
                Stock total: {formatNumber(movementSelectedMaterial.stock_total ?? 0)} · Unidad: {safeDisplayText(movementSelectedMaterial.unidad)}
              </p>
            </div>
          ) : null}
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeRequisitionModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-project-material-requisition-form" tone="primary" type="submit">
              {saving ? "Guardando..." : "Crear requisición"}
            </ActionButton>
          </div>
        }
        onClose={closeRequisitionModal}
        open={requisitionModalOpen}
        size="large"
        subtitle={`Solicitud de materiales para ${safeDisplayText(project?.nombre, "el proyecto activo")}.`}
        title="Crear requisición desde proyecto"
      >
        <form className="inventory-modal-form" id="pm-project-material-requisition-form" onSubmit={handleCreateRequisition}>
          <FormGrid>
            <Field label="Almacén destino">
              <select
                onChange={(event) => setRequisitionForm((current) => ({ ...current, almacen_destino_id: event.target.value }))}
                required
                value={requisitionForm.almacen_destino_id}
              >
                <option value="">Selecciona un almacén</option>
                {warehouses.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {safeDisplayText(warehouse.nombre)} ({safeDisplayText(warehouse.codigo)})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Notas" span={2}>
              <textarea
                onChange={(event) => setRequisitionForm((current) => ({ ...current, notas: event.target.value }))}
                rows={3}
                value={requisitionForm.notas}
              />
            </Field>
          </FormGrid>

          <SectionTitle subtitle="Incluye solo materiales con pendiente real." title="Materiales a solicitar" />
          {pendingPlans.length === 0 ? (
            <EmptyState compact note="No hay materiales pendientes para solicitar." title="Sin pendientes" />
          ) : (
            <DataTable columns={["Material", "Pendiente", "Solicitar", "Seleccionar"]}>
              <tbody>
                {pendingPlans.map((plan) => {
                  const currentItem = requisitionForm.items?.[plan.id] ?? {
                    selected: false,
                    cantidad_solicitada: "0",
                  };
                  return (
                    <tr key={plan.id}>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(plan.material_nombre_snapshot)}</div>
                        <div className="inventory-cell-sub">{safeDisplayText(plan.material_sku_snapshot)}</div>
                      </td>
                      <td>{formatNumber(plan.cantidad_pendiente)}</td>
                      <td>
                        <input
                          max={Number(plan.cantidad_pendiente || 0)}
                          min="0"
                          onChange={(event) =>
                            setRequisitionForm((current) => ({
                              ...current,
                              items: {
                                ...current.items,
                                [plan.id]: {
                                  ...current.items?.[plan.id],
                                  cantidad_solicitada: event.target.value,
                                },
                              },
                            }))
                          }
                          step="0.0001"
                          type="number"
                          value={currentItem.cantidad_solicitada}
                        />
                      </td>
                      <td>
                        <label className="inventory-inline-checkbox">
                          <input
                            checked={Boolean(currentItem.selected)}
                            onChange={(event) =>
                              setRequisitionForm((current) => ({
                                ...current,
                                items: {
                                  ...current.items,
                                  [plan.id]: {
                                    ...current.items?.[plan.id],
                                    selected: event.target.checked,
                                  },
                                },
                              }))
                            }
                            type="checkbox"
                          />
                          Incluir
                        </label>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>
          )}
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton onClick={() => setKardexModal({ open: false, loading: false, error: "", data: null, materialName: "" })} type="button">
              Cerrar
            </ActionButton>
          </div>
        }
        onClose={() => setKardexModal({ open: false, loading: false, error: "", data: null, materialName: "" })}
        open={kardexModal.open}
        size="large"
        subtitle="Movimientos del material filtrados al proyecto actual."
        title={`Kardex · ${safeDisplayText(kardexModal.materialName, "Material")}`}
      >
        {kardexModal.loading ? (
          <div className="screen-center">Cargando kardex...</div>
        ) : kardexModal.error ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo cargar el kardex</strong>
            <p className="table-note">{kardexModal.error}</p>
          </div>
        ) : consumptionRowsForKardex.length === 0 ? (
          <EmptyState compact note="Ese material todavía no tiene movimientos ligados a este proyecto." title="Sin movimientos del proyecto" />
        ) : (
          <DataTable columns={["Fecha", "Tipo", "Cantidad", "Almacén", "Tarea", "Partida", "Costo", "Notas"]}>
            <tbody>
              {consumptionRowsForKardex.map((movement) => (
                <tr key={movement.id}>
                  <td>{safeDisplayText(formatDateTime(movement.created_at), "—")}</td>
                  <td>
                    <StatusBadge tone={movement.tipo === "entrada" ? "warning" : "success"}>
                      {movement.referencia_tipo === "DEVOLUCION_PROYECTO" ? "Devolución" : "Consumo"}
                    </StatusBadge>
                  </td>
                  <td>{formatNumber(movement.cantidad)}</td>
                  <td>{safeDisplayText(movement.almacen_nombre, "—")}</td>
                  <td>{safeDisplayText(movement.pm_tarea_nombre_snapshot, "Proyecto general")}</td>
                  <td>{safeDisplayText(movement.pm_partida_nombre_snapshot, "—")}</td>
                  <td>{formatMoney(movement.costo_total_snapshot ?? 0)}</td>
                  <td>{safeDisplayText(movement.notas, "—")}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </ModalShell>
    </div>
  );
}
