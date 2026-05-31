import { useEffect, useMemo, useState } from "react";
import { ClipboardList, Factory, PackageMinus, PackageOpen, Plus } from "lucide-react";

import {
  addPmProjectMaterialPlan,
  createPmProjectMaterialRequisition,
  deactivatePmProjectMaterialPlan,
  getMaterials,
  getPmProjectMaterials,
  getWarehouses,
  listPmTasks,
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


function getConsumptionOriginLabel(origin) {
  if (origin === "requisicion_surtida") {
    return "Requisición surtida";
  }
  if (origin === "ajuste_admin") {
    return "Ajuste administrativo";
  }
  return "Movimiento manual";
}


function getConsumptionOriginTone(origin) {
  if (origin === "requisicion_surtida") {
    return "success";
  }
  if (origin === "ajuste_admin") {
    return "warning";
  }
  return "info";
}


export default function PMProjectMaterialsTab({
  empresaId,
  project,
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
  const [materialSearch, setMaterialSearch] = useState("");
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [planForm, setPlanForm] = useState(defaultPlanForm);
  const [requisitionModalOpen, setRequisitionModalOpen] = useState(false);
  const [requisitionForm, setRequisitionForm] = useState({ almacen_destino_id: "", notas: "", items: {} });

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

  const plans = materialsResponse?.plans ?? [];
  const consumptions = materialsResponse?.consumptions ?? [];
  const summary = materialsResponse?.summary;
  const pendingPlans = useMemo(
    () => plans.filter((plan) => Number(plan.cantidad_pendiente || 0) > 0 && plan.activo),
    [plans],
  );

  async function loadMaterialsTab() {
    if (!token || !empresaId || !projectId) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [projectMaterialsResponse, materialsCatalogResponse, warehousesResponse, tasksResponse] = await Promise.all([
        getPmProjectMaterials({ projectId, token, empresaId }),
        getMaterials({ token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
        getWarehouses({ token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
        listPmTasks({ projectId, token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
      ]);
      setMaterialsResponse(projectMaterialsResponse);
      setInventoryMaterials(materialsCatalogResponse.items ?? []);
      setWarehouses(warehousesResponse.items ?? []);
      setTasks(tasksResponse.items ?? []);
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

  function openCreatePlanModal() {
    setEditingPlan(null);
    setPlanForm(defaultPlanForm);
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
    setMaterialSearch(`${safeDisplayText(plan.material_sku_snapshot)} ${safeDisplayText(plan.material_nombre_snapshot)}`);
    setPlanModalOpen(true);
  }

  function closePlanModal() {
    if (saving) {
      return;
    }
    setEditingPlan(null);
    setPlanForm(defaultPlanForm);
    setMaterialSearch("");
    setPlanModalOpen(false);
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

  function closeRequisitionModal() {
    if (saving) {
      return;
    }
    setRequisitionModalOpen(false);
    setRequisitionForm({ almacen_destino_id: warehouses[0]?.id ?? "", notas: "", items: {} });
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
          planForm.costo_unitario_estimado === "" ? null : Number(planForm.costo_unitario_estimado || 0),
        observaciones: planForm.observaciones.trim() || null,
      };
      if (editingPlan?.id) {
        await updatePmProjectMaterialPlan({ projectId, planId: editingPlan.id, token, empresaId, payload });
        setSuccess("Material planeado actualizado.");
      } else {
        await addPmProjectMaterialPlan({ projectId, token, empresaId, payload });
        setSuccess("Material planeado agregado.");
      }
      closePlanModal();
      await loadMaterialsTab();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el material planeado.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivatePlan(plan) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmProjectMaterialPlan({ projectId, planId: plan.id, token, empresaId });
      setSuccess("Material planeado desactivado.");
      await loadMaterialsTab();
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
      closeRequisitionModal();
      await loadMaterialsTab();
    } catch (requestError) {
      setError(requestError.message || "No se pudo crear la requisición del proyecto.");
    } finally {
      setSaving(false);
    }
  }

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
          label="Costo estimado materiales"
          meta="Planeación del proyecto"
          tone="info"
          value={formatMoney(summary?.costo_estimado ?? 0)}
        />
        <MetricCard
          icon={<PackageMinus size={18} strokeWidth={1.9} />}
          label="Costo real materiales"
          meta="Consumo acumulado"
          tone="success"
          value={formatMoney(summary?.costo_real ?? 0)}
        />
        <MetricCard
          icon={<ClipboardList size={18} strokeWidth={1.9} />}
          label="Variación"
          meta="Real vs estimado"
          tone={Number(summary?.variacion ?? 0) > 0 ? "warning" : "neutral"}
          value={formatMoney(summary?.variacion ?? 0)}
        />
        <MetricCard
          icon={<PackageOpen size={18} strokeWidth={1.9} />}
          label="Materiales planeados"
          meta="Cantidad total planeada"
          tone="neutral"
          value={formatNumber(summary?.total_materiales_planeados ?? 0)}
        />
        <MetricCard
          icon={<PackageMinus size={18} strokeWidth={1.9} />}
          label="Materiales consumidos"
          meta="Cantidad total consumida"
          tone="warning"
          value={formatNumber(summary?.total_materiales_consumidos ?? 0)}
        />
      </section>

      <div className="inventory-form-note">
        <strong>Consumo real conectado a Inventario</strong>
        <p className="table-note">
          Los consumos reales se generan al surtir requisiciones o registrar salidas de inventario vinculadas al proyecto.
        </p>
      </div>

      <DataCard
        actions={
          <div className="inventory-actions">
            <ActionButton
              disabled={pendingPlans.length === 0}
              icon={<ClipboardList size={16} strokeWidth={1.9} />}
              onClick={() => openRequisitionModal()}
              type="button"
            >
              Crear requisición
            </ActionButton>
            <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreatePlanModal} tone="primary" type="button">
              Agregar material
            </ActionButton>
          </div>
        }
        subtitle="Materiales planeados, pendiente por solicitar y costo estimado."
        title="Plan de materiales"
      >
        <ResultMeta label="materiales" loaded={plans.length} total={plans.length} />
        {plans.length === 0 ? (
          <EmptyState
            compact
            note="Agrega materiales planeados para comparar consumo real contra estimado."
            title="Sin materiales planeados"
          />
        ) : (
          <DataTable
            columns={[
              "Material",
              "SKU",
              "Cantidad planificada",
              "Unidad",
              "Costo estimado",
              "Consumido real",
              "Pendiente",
              "Estatus",
              "Acciones",
            ]}
          >
            <tbody>
              {plans.map((plan) => (
                <tr key={plan.id}>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(plan.material_nombre_snapshot)}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(plan.tarea_titulo, "Proyecto general")}</div>
                  </td>
                  <td>{safeDisplayText(plan.material_sku_snapshot, "—")}</td>
                  <td>{formatNumber(plan.cantidad_planificada)}</td>
                  <td>{safeDisplayText(plan.unidad, "—")}</td>
                  <td>{formatMoney(plan.costo_total_estimado)}</td>
                  <td>{formatNumber(plan.cantidad_consumida_real)}</td>
                  <td>{formatNumber(plan.cantidad_pendiente)}</td>
                  <td>
                    <StatusBadge tone={getPlanStatusTone(plan.estatus)}>
                      {safeDisplayText(plan.estatus, "planeado")}
                    </StatusBadge>
                  </td>
                  <td>
                    <div className="table-actions">
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
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <DataCard subtitle="Salidas reales de inventario aplicadas al proyecto." title="Consumo real">
        <ResultMeta label="consumos" loaded={consumptions.length} total={consumptions.length} />
        {consumptions.length === 0 ? (
          <EmptyState
            compact
            note="Los consumos aparecerán cuando se surtan requisiciones o se registren salidas vinculadas al proyecto."
            title="Sin consumos reales"
          />
        ) : (
          <DataTable
            columns={[
              "Fecha",
              "Material",
              "Cantidad consumida",
              "Costo unitario",
              "Costo total",
              "Origen",
              "Requisición",
              "Movimiento",
              "Documento",
              "Notas",
            ]}
          >
            <tbody>
              {consumptions.map((consumption) => (
                <tr key={consumption.id}>
                  <td>{safeDisplayText(formatDate(consumption.created_at), "—")}</td>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(consumption.material_nombre_snapshot)}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(consumption.material_sku_snapshot, "—")}</div>
                  </td>
                  <td>{formatNumber(consumption.cantidad_consumida)}</td>
                  <td>{formatMoney(consumption.costo_unitario_snapshot)}</td>
                  <td>{formatMoney(consumption.costo_total_snapshot)}</td>
                  <td>
                    <StatusBadge tone={getConsumptionOriginTone(consumption.origen)}>
                      {getConsumptionOriginLabel(consumption.origen)}
                    </StatusBadge>
                  </td>
                  <td>{safeDisplayText(consumption.requisicion_id, "—")}</td>
                  <td>{safeDisplayText(consumption.movimiento_id, "—")}</td>
                  <td>{safeDisplayText(consumption.documento_referencia, "—")}</td>
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
        subtitle="Material planeado para controlar cantidades y costo estimado del proyecto."
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

            <Field label="Cantidad planificada">
              <input
                min="0"
                onChange={(event) => setPlanForm((current) => ({ ...current, cantidad_planificada: event.target.value }))}
                required
                step="0.0001"
                type="number"
                value={planForm.cantidad_planificada}
              />
            </Field>

            <Field hint="Opcional; si se deja vacío usa costo actual del material." label="Costo unitario estimado">
              <input
                min="0"
                onChange={(event) => setPlanForm((current) => ({ ...current, costo_unitario_estimado: event.target.value }))}
                step="0.0001"
                type="number"
                value={planForm.costo_unitario_estimado}
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
            <Field label="Almacen destino">
              <select
                onChange={(event) => setRequisitionForm((current) => ({ ...current, almacen_destino_id: event.target.value }))}
                required
                value={requisitionForm.almacen_destino_id}
              >
                <option value="">Selecciona un almacen</option>
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

          <SectionTitle subtitle="Selecciona solo materiales con pendiente real." title="Materiales a solicitar" />
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
    </div>
  );
}
