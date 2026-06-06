import { useEffect, useMemo, useState } from "react";
import {
  BadgeDollarSign,
  Calculator,
  ClipboardList,
  Factory,
  PackageOpen,
  Plus,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";

import {
  approvePmBudget,
  cancelPmBudget,
  createPmBudgetIndirect,
  createPmBudgetItem,
  createPmBudgetItemLabor,
  createPmBudgetItemMaterial,
  createPmProjectBudget,
  deactivatePmBudgetIndirect,
  deactivatePmBudgetItem,
  deactivatePmBudgetItemLabor,
  deactivatePmBudgetItemMaterial,
  getMaterials,
  getPmProjectBudget,
  refreshPmProjectBudget,
  updatePmBudget,
  updatePmBudgetIndirect,
  updatePmBudgetItem,
  updatePmBudgetItemLabor,
  updatePmBudgetItemMaterial,
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
  StatusBadge,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";
import { formatPercent, pmRateRoleOptions } from "./shared";


const defaultBudgetForm = {
  nombre: "Presupuesto base",
  moneda: "MXN",
  indirectos_pct: "0",
  notas: "",
};

const defaultItemForm = {
  parent_id: "",
  codigo: "",
  nombre: "",
  descripcion: "",
  tipo: "partida",
  unidad: "",
  cantidad: "1",
  margen_pct: "0",
  precio_unitario_manual: "",
  orden: "0",
};

const defaultMaterialForm = {
  material_id: "",
  material_nombre_snapshot: "",
  material_sku_snapshot: "",
  unidad: "",
  cantidad_por_unidad: "0",
  costo_unitario: "",
  proveedor_nombre_snapshot: "",
};

const defaultLaborForm = {
  rol: "",
  descripcion: "",
  horas_por_unidad: "0",
  tarifa_hora: "",
};

const defaultIndirectForm = {
  nombre: "",
  tipo: "monto",
  porcentaje: "",
  monto: "0",
};

const budgetStatusLabels = {
  borrador: "Borrador",
  aprobado: "Aprobado",
  sustituido: "Sustituido",
  cancelado: "Cancelado",
};

const itemTypeLabels = {
  capitulo: "Capítulo",
  partida: "Partida",
};

const indirectTypeLabels = {
  porcentaje: "Porcentaje",
  monto: "Monto fijo",
};

const budgetGuideSteps = [
  {
    key: "base",
    title: "Paso 1: Presupuesto base",
    note: "Crea el presupuesto del proyecto y define moneda, margen e indirectos generales.",
  },
  {
    key: "items",
    title: "Paso 2: Capítulos y partidas",
    note: "Organiza el presupuesto por capítulos y partidas.",
  },
  {
    key: "breakdown",
    title: "Paso 3: Desglose de costo",
    note: "Agrega materiales y mano de obra a cada partida.",
  },
  {
    key: "indirects",
    title: "Paso 4: Indirectos y margen",
    note: "Agrega gastos generales, administración, fletes u otros costos.",
  },
  {
    key: "actual",
    title: "Paso 5: Comparativo real",
    note: "Compara presupuesto contra costos reales del proyecto.",
  },
];


function getBudgetStatusTone(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "aprobado") {
    return "success";
  }
  if (normalized === "cancelado") {
    return "danger";
  }
  if (normalized === "sustituido") {
    return "warning";
  }
  return "neutral";
}


function getItemTypeTone(type) {
  return type === "capitulo" ? "info" : "neutral";
}


function numericValue(value) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}


function getErrorMessage(error, fallback) {
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message.trim();
  }
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  return fallback;
}


function buildBudgetForm(budget, fallbackName) {
  if (!budget) {
    return {
      ...defaultBudgetForm,
      nombre: fallbackName || defaultBudgetForm.nombre,
    };
  }
  return {
    nombre: budget.nombre ?? fallbackName ?? defaultBudgetForm.nombre,
    moneda: budget.moneda ?? "MXN",
    indirectos_pct: budget.indirectos_pct ?? "0",
    notas: budget.notas ?? "",
  };
}


function buildItemForm(item) {
  if (!item) {
    return defaultItemForm;
  }
  return {
    parent_id: item.parent_id ?? "",
    codigo: item.codigo ?? "",
    nombre: item.nombre ?? "",
    descripcion: item.descripcion ?? "",
    tipo: item.tipo ?? "partida",
    unidad: item.unidad ?? "",
    cantidad: item.cantidad ?? "1",
    margen_pct: item.margen_pct ?? "0",
    precio_unitario_manual: item.precio_unitario_manual ?? "",
    orden: item.orden ?? "0",
  };
}


function buildMaterialForm(component) {
  if (!component) {
    return defaultMaterialForm;
  }
  return {
    material_id: component.material_id ?? "",
    material_nombre_snapshot: component.material_nombre_snapshot ?? "",
    material_sku_snapshot: component.material_sku_snapshot ?? "",
    unidad: component.unidad ?? "",
    cantidad_por_unidad: component.cantidad_por_unidad ?? "0",
    costo_unitario: component.costo_unitario ?? "",
    proveedor_nombre_snapshot: component.proveedor_nombre_snapshot ?? "",
  };
}


function buildLaborForm(component) {
  if (!component) {
    return defaultLaborForm;
  }
  return {
    rol: component.rol ?? "",
    descripcion: component.descripcion ?? "",
    horas_por_unidad: component.horas_por_unidad ?? "0",
    tarifa_hora: component.tarifa_hora ?? "",
  };
}


function buildIndirectForm(indirect) {
  if (!indirect) {
    return defaultIndirectForm;
  }
  return {
    nombre: indirect.nombre ?? "",
    tipo: indirect.tipo ?? "monto",
    porcentaje: indirect.porcentaje ?? "",
    monto: indirect.monto ?? "0",
  };
}


function buildTree(activeItems) {
  const chapters = activeItems
    .filter((item) => item.tipo === "capitulo")
    .sort((left, right) => Number(left.orden ?? 0) - Number(right.orden ?? 0));
  return {
    chapters: chapters.map((chapter) => ({
      chapter,
      items: activeItems
        .filter((item) => item.tipo === "partida" && item.parent_id === chapter.id)
        .sort((left, right) => Number(left.orden ?? 0) - Number(right.orden ?? 0)),
    })),
    looseItems: activeItems
      .filter((item) => item.tipo === "partida" && !item.parent_id)
      .sort((left, right) => Number(left.orden ?? 0) - Number(right.orden ?? 0)),
  };
}

function getBudgetItemTotals(item) {
  const cost = numericValue(item?.subtotal_costo);
  const sale = numericValue(item?.subtotal_venta);
  return {
    cost,
    sale,
    margin: sale - cost,
  };
}

function getChapterDisplayTotals(chapter, chapterItems) {
  const fallbackTotals = getBudgetItemTotals(chapter);
  if (!chapterItems.length) {
    return fallbackTotals;
  }
  const cost = chapterItems.reduce((sum, item) => sum + numericValue(item?.subtotal_costo), 0);
  const sale = chapterItems.reduce((sum, item) => sum + numericValue(item?.subtotal_venta), 0);
  return {
    cost,
    sale,
    margin: sale - cost,
  };
}


export default function PMProjectBudgetTab({
  canManage = false,
  empresaId,
  onChanged,
  projectEditable = true,
  project,
  projectId,
  token,
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [bundle, setBundle] = useState(null);
  const [materialsCatalog, setMaterialsCatalog] = useState([]);
  const [activeBudgetModal, setActiveBudgetModal] = useState("");

  const [editingBudget, setEditingBudget] = useState(null);
  const [editingItem, setEditingItem] = useState(null);
  const [editingMaterial, setEditingMaterial] = useState(null);
  const [editingLabor, setEditingLabor] = useState(null);
  const [editingIndirect, setEditingIndirect] = useState(null);

  const [budgetForm, setBudgetForm] = useState(defaultBudgetForm);
  const [itemForm, setItemForm] = useState(defaultItemForm);
  const [materialForm, setMaterialForm] = useState(defaultMaterialForm);
  const [laborForm, setLaborForm] = useState(defaultLaborForm);
  const [indirectForm, setIndirectForm] = useState(defaultIndirectForm);
  const [selectedItemId, setSelectedItemId] = useState(null);

  const budget = bundle?.budget ?? null;
  const vsActual = bundle?.vs_actual ?? null;
  const items = useMemo(() => budget?.items ?? [], [budget]);
  const indirects = useMemo(() => budget?.indirects ?? [], [budget]);
  const activeItems = useMemo(() => items.filter((item) => item.activo), [items]);
  const chapterOptions = useMemo(
    () => activeItems.filter((item) => item.tipo === "capitulo"),
    [activeItems],
  );
  const budgetTree = useMemo(() => buildTree(activeItems), [activeItems]);
  const selectedBudgetItem = useMemo(
    () => activeItems.find((item) => item.id === selectedItemId) ?? activeItems.find((item) => item.tipo === "partida") ?? activeItems[0] ?? null,
    [activeItems, selectedItemId],
  );
  const selectedOperationalItem = selectedBudgetItem?.tipo === "partida" ? selectedBudgetItem : null;
  const projectBudgetBase = numericValue(project?.presupuesto_estimado);
  const canEditBudget = canManage && projectEditable;
  const budgetCalculatedCost = numericValue(budget?.total_costo ?? vsActual?.presupuesto_detallado_costo);
  const budgetSaleTotal = numericValue(budget?.total_venta ?? vsActual?.presupuesto_detallado_venta);
  const budgetEstimatedMargin = numericValue(budget?.margen_estimado ?? vsActual?.margen_estimado);
  const projectActualCost = numericValue(vsActual?.costo_real_total);
  const varianceAgainstActual = numericValue(vsActual?.variacion ?? (budgetCalculatedCost - projectActualCost));
  const selectedOperationalItemMarginAmount = numericValue(selectedOperationalItem?.subtotal_venta) - numericValue(selectedOperationalItem?.subtotal_costo);

  async function loadBudgetTab({ background = false } = {}) {
    if (!token || !empresaId || !projectId) {
      return;
    }
    if (!background) {
      setLoading(true);
    }
    setError("");
    try {
      const [budgetResponse, materialsResponse] = await Promise.all([
        getPmProjectBudget({ projectId, token, empresaId }),
        getMaterials({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
      ]);
      setBundle(budgetResponse);
      setMaterialsCatalog(materialsResponse.items ?? []);
      setSelectedItemId((current) => {
        const nextItems = budgetResponse?.budget?.items?.filter((item) => item.activo) ?? [];
        if (current && nextItems.some((item) => item.id === current)) {
          return current;
        }
        return nextItems.find((item) => item.tipo === "partida")?.id ?? nextItems[0]?.id ?? null;
      });
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo cargar el presupuesto del proyecto."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBudgetTab();
  }, [token, empresaId, projectId]);

  function notifyChanged() {
    onChanged?.();
  }

  function closeBudgetModal() {
    if (saving) {
      return;
    }
    setActiveBudgetModal("");
    setEditingBudget(null);
    setEditingItem(null);
    setEditingMaterial(null);
    setEditingLabor(null);
    setEditingIndirect(null);
    setBudgetForm(defaultBudgetForm);
    setItemForm(defaultItemForm);
    setMaterialForm(defaultMaterialForm);
    setLaborForm(defaultLaborForm);
    setIndirectForm(defaultIndirectForm);
  }

  function openBudgetModal(type, payload = null, event = null) {
    event?.preventDefault?.();
    event?.stopPropagation?.();
    setError("");
    setSuccess("");

    if (!canEditBudget) {
      setError("No tienes permiso para editar el presupuesto de este proyecto.");
      return;
    }

    if (type !== "budget" && !budget?.id) {
      setError("Primero crea el presupuesto del proyecto.");
      return;
    }

    if ((type === "material" || type === "labor") && !selectedOperationalItem && !payload) {
      setError("Primero crea o selecciona una partida.");
      return;
    }

    setEditingBudget(null);
    setEditingItem(null);
    setEditingMaterial(null);
    setEditingLabor(null);
    setEditingIndirect(null);

    if (type === "budget") {
      const targetBudget = payload ?? budget ?? null;
      setEditingBudget(targetBudget);
      setBudgetForm(buildBudgetForm(targetBudget, targetBudget?.nombre ?? "Presupuesto base"));
      setActiveBudgetModal("budget");
      return;
    }

    if (type === "chapter" || type === "item") {
      const targetItem = payload ?? null;
      setEditingItem(targetItem);
      if (targetItem) {
        setItemForm(buildItemForm(targetItem));
      } else {
        setItemForm({
          ...defaultItemForm,
          tipo: type === "chapter" ? "capitulo" : "partida",
          parent_id: type === "item" ? chapterOptions[0]?.id ?? "" : "",
        });
      }
      setActiveBudgetModal(type);
      return;
    }

    if (type === "material") {
      setEditingMaterial(payload ?? null);
      setMaterialForm(payload ? buildMaterialForm(payload) : defaultMaterialForm);
      setActiveBudgetModal("material");
      return;
    }

    if (type === "labor") {
      setEditingLabor(payload ?? null);
      setLaborForm(payload ? buildLaborForm(payload) : defaultLaborForm);
      setActiveBudgetModal("labor");
      return;
    }

    if (type === "indirect") {
      setEditingIndirect(payload ?? null);
      setIndirectForm(payload ? buildIndirectForm(payload) : defaultIndirectForm);
      setActiveBudgetModal("indirect");
    }
  }

  function closeItemModal() {
    closeBudgetModal();
  }

  function closeMaterialModal() {
    closeBudgetModal();
  }

  function closeLaborModal() {
    closeBudgetModal();
  }

  function closeIndirectModal() {
    closeBudgetModal();
  }

  function openCreateBudgetModal(event) {
    openBudgetModal("budget", null, event);
  }

  function openEditBudgetModal(event) {
    openBudgetModal("budget", budget, event);
  }

  function openCreateItemModal(type = "partida", event = null) {
    openBudgetModal(type === "capitulo" ? "chapter" : "item", null, event);
  }

  function openEditItemModal(item, event = null) {
    openBudgetModal(item?.tipo === "capitulo" ? "chapter" : "item", item, event);
  }

  function openCreateMaterialModal(event) {
    openBudgetModal("material", null, event);
  }

  function openEditMaterialModal(component, event = null) {
    openBudgetModal("material", component, event);
  }

  function openCreateLaborModal(event) {
    openBudgetModal("labor", null, event);
  }

  function openEditLaborModal(component, event = null) {
    openBudgetModal("labor", component, event);
  }

  function openCreateIndirectModal(event) {
    openBudgetModal("indirect", null, event);
  }

  function openEditIndirectModal(indirect, event = null) {
    openBudgetModal("indirect", indirect, event);
  }

  async function handleQuickCreateBudget({ useProjectBase = false } = {}) {
    if (!canEditBudget) {
      setError("No tienes permiso para editar el presupuesto de este proyecto.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await createPmProjectBudget({
        projectId,
        token,
        empresaId,
        payload: {
          nombre: "Presupuesto base",
          moneda: "MXN",
          indirectos_pct: 0,
          utilidad_pct: 0,
          notas: useProjectBase && Number(project?.presupuesto_estimado ?? 0) > 0
            ? "Inicializado desde el presupuesto base del proyecto."
            : "",
        },
      });
      setSuccess(useProjectBase ? "Presupuesto creado usando el presupuesto base del proyecto." : "Presupuesto creado.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo crear el presupuesto."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveBudget(event) {
    event.preventDefault();
    if (!canEditBudget) {
      setError("No tienes permiso para editar el presupuesto de este proyecto.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        nombre: budgetForm.nombre.trim() || "Presupuesto base",
        moneda: (budgetForm.moneda || "MXN").trim().toUpperCase(),
        indirectos_pct: numericValue(budgetForm.indirectos_pct),
        utilidad_pct: 0,
        notas: budgetForm.notas.trim() || null,
      };
      if (editingBudget?.id) {
        await updatePmBudget({ budgetId: editingBudget.id, token, empresaId, payload });
        setSuccess("Presupuesto actualizado.");
      } else {
        await createPmProjectBudget({ projectId, token, empresaId, payload });
        setSuccess("Presupuesto creado.");
      }
      closeBudgetModal();
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar el presupuesto."));
    } finally {
      setSaving(false);
    }
  }

  async function handleApproveBudget() {
    if (!canEditBudget) {
      setError("No tienes permiso para aprobar el presupuesto de este proyecto.");
      return;
    }
    if (!budget?.id) {
      return;
    }
    if (activeItems.filter((item) => item.tipo === "partida").length === 0) {
      setError("Agrega al menos una partida antes de aprobar.");
      return;
    }
    if (!window.confirm("Se aprobará el presupuesto activo del proyecto. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await approvePmBudget({ budgetId: budget.id, token, empresaId });
      setSuccess("Presupuesto aprobado.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo aprobar el presupuesto."));
    } finally {
      setSaving(false);
    }
  }

  async function handleCancelBudget() {
    if (!canEditBudget) {
      setError("No tienes permiso para cancelar el presupuesto de este proyecto.");
      return;
    }
    if (!budget?.id || !window.confirm("El presupuesto se marcará como cancelado. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await cancelPmBudget({ budgetId: budget.id, token, empresaId });
      setSuccess("Presupuesto cancelado.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo cancelar el presupuesto."));
    } finally {
      setSaving(false);
    }
  }

  async function handleRefreshBudget() {
    if (!projectId) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await refreshPmProjectBudget({ projectId, token, empresaId });
      setSuccess("Totales del presupuesto actualizados.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudieron refrescar los totales."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveItem(event) {
    event.preventDefault();
    if (!canEditBudget) {
      setError("No tienes permiso para editar partidas en este proyecto.");
      return;
    }
    if (!budget?.id) {
      setError("Primero crea el presupuesto del proyecto.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        parent_id: itemForm.tipo === "capitulo" ? null : itemForm.parent_id || null,
        codigo: itemForm.codigo.trim() || null,
        nombre: itemForm.nombre.trim(),
        descripcion: itemForm.descripcion.trim() || null,
        tipo: itemForm.tipo,
        unidad: itemForm.tipo === "capitulo" ? null : itemForm.unidad.trim() || null,
        cantidad: itemForm.tipo === "capitulo" ? Math.max(1, numericValue(itemForm.cantidad || 1)) : numericValue(itemForm.cantidad),
        margen_pct: numericValue(itemForm.margen_pct),
        precio_unitario_manual: itemForm.precio_unitario_manual === "" ? null : numericValue(itemForm.precio_unitario_manual),
        orden: Math.max(0, Math.trunc(numericValue(itemForm.orden))),
      };
      let response;
      if (editingItem?.id) {
        response = await updatePmBudgetItem({ itemId: editingItem.id, token, empresaId, payload });
        setSuccess(editingItem.tipo === "capitulo" ? "Capítulo actualizado." : "Partida actualizada.");
      } else {
        response = await createPmBudgetItem({ budgetId: budget.id, token, empresaId, payload });
        setSuccess(itemForm.tipo === "capitulo" ? "Capítulo agregado." : "Partida agregada.");
      }
      closeItemModal();
      await loadBudgetTab({ background: true });
      setSelectedItemId(response?.id ?? selectedItemId);
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar la partida."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateItem(item) {
    if (!canEditBudget) {
      setError("No tienes permiso para editar partidas en este proyecto.");
      return;
    }
    if (!item?.id || !window.confirm("La partida se desactivará del presupuesto activo. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmBudgetItem({ itemId: item.id, token, empresaId });
      setSuccess(item.tipo === "capitulo" ? "Capítulo desactivado." : "Partida desactivada.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo desactivar la partida."));
    } finally {
      setSaving(false);
    }
  }

  function handleCatalogMaterialChange(materialId) {
    const nextMaterial = materialsCatalog.find((material) => material.id === materialId);
    if (!nextMaterial) {
      setMaterialForm((current) => ({ ...current, material_id: "" }));
      return;
    }
    setMaterialForm((current) => ({
      ...current,
      material_id: nextMaterial.id,
      material_nombre_snapshot: nextMaterial.nombre ?? current.material_nombre_snapshot,
      material_sku_snapshot: nextMaterial.sku ?? current.material_sku_snapshot,
      unidad: nextMaterial.unidad ?? current.unidad,
      costo_unitario: current.costo_unitario === "" ? nextMaterial.costo_promedio_actual ?? nextMaterial.costo_unitario ?? "" : current.costo_unitario,
    }));
  }

  async function handleSaveMaterial(event) {
    event.preventDefault();
    if (!canEditBudget) {
      setError("No tienes permiso para editar materiales presupuestados en este proyecto.");
      return;
    }
    if (!selectedOperationalItem?.id) {
      setError("Primero crea o selecciona una partida.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        material_id: materialForm.material_id || null,
        material_nombre_snapshot: materialForm.material_nombre_snapshot.trim() || null,
        material_sku_snapshot: materialForm.material_sku_snapshot.trim() || null,
        unidad: materialForm.unidad.trim() || null,
        cantidad_por_unidad: numericValue(materialForm.cantidad_por_unidad),
        costo_unitario: materialForm.costo_unitario === "" ? null : numericValue(materialForm.costo_unitario),
        proveedor_nombre_snapshot: materialForm.proveedor_nombre_snapshot.trim() || null,
      };
      if (editingMaterial?.id) {
        await updatePmBudgetItemMaterial({ componentId: editingMaterial.id, token, empresaId, payload });
        setSuccess("Material actualizado.");
      } else {
        await createPmBudgetItemMaterial({ itemId: selectedOperationalItem.id, token, empresaId, payload });
        setSuccess("Material agregado a la partida.");
      }
      closeMaterialModal();
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar el material."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateMaterial(component) {
    if (!canEditBudget) {
      setError("No tienes permiso para editar materiales presupuestados en este proyecto.");
      return;
    }
    if (!component?.id || !window.confirm("El material se quitará del desglose de costo. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmBudgetItemMaterial({ componentId: component.id, token, empresaId });
      setSuccess("Material quitado de la partida.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo quitar el material."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveLabor(event) {
    event.preventDefault();
    if (!canEditBudget) {
      setError("No tienes permiso para editar la mano de obra presupuestada en este proyecto.");
      return;
    }
    if (!selectedOperationalItem?.id) {
      setError("Primero crea o selecciona una partida.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        rol: laborForm.rol || null,
        descripcion: laborForm.descripcion.trim() || null,
        horas_por_unidad: numericValue(laborForm.horas_por_unidad),
        tarifa_hora: laborForm.tarifa_hora === "" ? null : numericValue(laborForm.tarifa_hora),
      };
      if (editingLabor?.id) {
        await updatePmBudgetItemLabor({ componentId: editingLabor.id, token, empresaId, payload });
        setSuccess("Mano de obra actualizada.");
      } else {
        await createPmBudgetItemLabor({ itemId: selectedOperationalItem.id, token, empresaId, payload });
        setSuccess("Mano de obra agregada a la partida.");
      }
      closeLaborModal();
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar la mano de obra."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateLabor(component) {
    if (!canEditBudget) {
      setError("No tienes permiso para editar la mano de obra presupuestada en este proyecto.");
      return;
    }
    if (!component?.id || !window.confirm("La mano de obra se quitará del desglose de costo. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmBudgetItemLabor({ componentId: component.id, token, empresaId });
      setSuccess("Mano de obra quitada de la partida.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo quitar la mano de obra."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveIndirect(event) {
    event.preventDefault();
    if (!canEditBudget) {
      setError("No tienes permiso para editar costos indirectos en este proyecto.");
      return;
    }
    if (!budget?.id) {
      setError("Primero crea el presupuesto del proyecto.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        nombre: indirectForm.nombre.trim(),
        tipo: indirectForm.tipo,
        porcentaje: indirectForm.tipo === "porcentaje" ? numericValue(indirectForm.porcentaje) : null,
        monto: indirectForm.tipo === "monto" ? numericValue(indirectForm.monto) : 0,
      };
      if (editingIndirect?.id) {
        await updatePmBudgetIndirect({ indirectId: editingIndirect.id, token, empresaId, payload });
        setSuccess("Costo indirecto actualizado.");
      } else {
        await createPmBudgetIndirect({ budgetId: budget.id, token, empresaId, payload });
        setSuccess("Costo indirecto agregado.");
      }
      closeIndirectModal();
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo guardar el costo indirecto."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateIndirect(indirect) {
    if (!canEditBudget) {
      setError("No tienes permiso para editar costos indirectos en este proyecto.");
      return;
    }
    if (!indirect?.id || !window.confirm("El costo indirecto se quitará del presupuesto activo. ¿Continuar?")) {
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmBudgetIndirect({ indirectId: indirect.id, token, empresaId });
      setSuccess("Costo indirecto desactivado.");
      await loadBudgetTab({ background: true });
      notifyChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "No se pudo desactivar el costo indirecto."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando presupuesto...</div>;
  }

  return (
    <div className="inventory-content-grid pm-budget-stack">
      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      {budgetCalculatedCost > 0 && projectActualCost > budgetCalculatedCost ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>Presupuesto superado</strong>
          <p className="table-note">El costo real ya rebasa el presupuesto detallado del proyecto.</p>
        </div>
      ) : null}

      <section className="pm-budget-guide-grid">
        {budgetGuideSteps.map((step) => (
          <article className="pm-budget-guide-card" key={step.key}>
            <strong>{step.title}</strong>
            <p>{step.note}</p>
          </article>
        ))}
      </section>

      <DataCard
        actions={(
          <div className="inventory-actions inventory-actions-wrap">
            {!budget ? (
              <>
                <ActionButton disabled={saving || !canEditBudget} icon={<Plus size={16} strokeWidth={1.9} />} onClick={() => handleQuickCreateBudget()} tone="primary" type="button">
                  Crear presupuesto
                </ActionButton>
                <ActionButton
                  disabled={saving || !canEditBudget}
                  onClick={() => handleQuickCreateBudget({ useProjectBase: true })}
                  type="button"
                >
                  Usar presupuesto base del proyecto
                </ActionButton>
                <ActionButton disabled={saving || !canEditBudget} onClick={openCreateBudgetModal} type="button">
                  Configurar cabecera
                </ActionButton>
              </>
            ) : (
              <>
                <ActionButton disabled={!canEditBudget} onClick={openEditBudgetModal} type="button">
                  Editar
                </ActionButton>
                <ActionButton disabled={saving || budget.estatus === "aprobado" || !canEditBudget} onClick={handleApproveBudget} tone="primary" type="button">
                  Aprobar presupuesto
                </ActionButton>
                <ActionButton disabled={saving || budget.estatus === "cancelado" || !canEditBudget} onClick={handleCancelBudget} tone="danger" type="button">
                  Cancelar
                </ActionButton>
              </>
            )}
            <ActionButton disabled={saving || !budget} icon={<RefreshCw size={16} strokeWidth={1.9} />} onClick={handleRefreshBudget} type="button">
              Actualizar totales
            </ActionButton>
          </div>
        )}
        subtitle="Crea el presupuesto y define la base económica del proyecto."
        title="Presupuesto del proyecto"
      >
        {!budget ? (
          <EmptyState
            action={(
              <div className="inventory-actions inventory-actions-wrap">
                <ActionButton disabled={saving || !canEditBudget} onClick={() => handleQuickCreateBudget()} tone="primary" type="button">
                  Crear presupuesto
                </ActionButton>
                <ActionButton
                  disabled={saving || !canEditBudget}
                  onClick={() => handleQuickCreateBudget({ useProjectBase: true })}
                  type="button"
                >
                  Usar presupuesto base del proyecto
                </ActionButton>
              </div>
            )}
            compact
            note={Number(project?.presupuesto_estimado ?? 0) > 0
              ? `Presupuesto base actual: ${formatMoney(project?.presupuesto_estimado ?? 0)}`
              : "Crea un presupuesto para organizar capítulos, partidas, materiales, mano de obra e indirectos."}
            title="Este proyecto aún no tiene presupuesto detallado"
          />
        ) : (
          <div className="pm-budget-header-grid">
            <div className="pm-project-header-item">
              <span>Nombre</span>
              <strong>{safeDisplayText(budget.nombre)}</strong>
            </div>
            <div className="pm-project-header-item">
              <span>Versión</span>
              <strong>{formatNumber(budget.version ?? 1)}</strong>
            </div>
            <div className="pm-project-header-item">
              <span>Estatus</span>
              <strong>
                <StatusBadge tone={getBudgetStatusTone(budget.estatus)}>
                  {budgetStatusLabels[budget.estatus] ?? safeDisplayText(budget.estatus)}
                </StatusBadge>
              </strong>
            </div>
            <div className="pm-project-header-item">
              <span>Moneda</span>
              <strong>{safeDisplayText(budget.moneda, "MXN")}</strong>
            </div>
            <div className="pm-project-header-item">
              <span>Indirectos base</span>
              <strong>{formatPercent(budget.indirectos_pct ?? 0)}</strong>
            </div>
            <div className="pm-project-header-item">
              <span>Aprobación</span>
              <strong>{budget.aprobado_at ? "Aprobado" : "Pendiente"}</strong>
            </div>
          </div>
        )}
      </DataCard>

      <section className="inventory-metric-grid inventory-metric-grid-6">
        <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Presupuesto base" meta="Referencia del proyecto" tone="neutral" value={formatMoney(projectBudgetBase)} />
        <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Costo calculado" meta="Partidas + indirectos" tone="info" value={formatMoney(budgetCalculatedCost)} />
        <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Precio de venta" meta="Total venta" tone="success" value={formatMoney(budgetSaleTotal)} />
        <MetricCard icon={<Calculator size={18} strokeWidth={1.9} />} label="Margen estimado" meta="Venta - costo" tone={budgetEstimatedMargin < 0 ? "danger" : "warning"} value={formatMoney(budgetEstimatedMargin)} />
        <MetricCard icon={<Factory size={18} strokeWidth={1.9} />} label="Costo real actual" meta="Materiales + horas" tone="danger" value={formatMoney(projectActualCost)} />
        <MetricCard icon={<TriangleAlert size={18} strokeWidth={1.9} />} label="Variación contra real" meta="Costo calculado - costo real" tone={varianceAgainstActual < 0 ? "danger" : "success"} value={formatMoney(varianceAgainstActual)} />
      </section>

      <div className="inventory-content-grid inventory-content-grid-2 pm-budget-workspace">
        <DataCard
          actions={(
            <div className="inventory-actions inventory-actions-wrap">
              {canEditBudget ? (
                <>
                  <ActionButton disabled={!budget} icon={<Plus size={16} strokeWidth={1.9} />} onClick={(event) => openCreateItemModal("capitulo", event)} type="button">
                    Agregar capítulo
                  </ActionButton>
                  <ActionButton disabled={!budget} icon={<Plus size={16} strokeWidth={1.9} />} onClick={(event) => openCreateItemModal("partida", event)} tone="primary" type="button">
                    Agregar partida
                  </ActionButton>
                </>
              ) : null}
            </div>
          )}
          subtitle="Organiza el presupuesto por capítulos y partidas."
          title="Estructura del presupuesto"
        >
          {!budget ? (
            <EmptyState compact note="Primero crea el presupuesto del proyecto." title="Sin presupuesto" />
          ) : activeItems.length === 0 ? (
            <EmptyState
              action={canEditBudget ? (
                <div className="inventory-actions inventory-actions-wrap">
                  <ActionButton onClick={(event) => openCreateItemModal("capitulo", event)} type="button">
                    Agregar capítulo
                  </ActionButton>
                  <ActionButton onClick={(event) => openCreateItemModal("partida", event)} tone="primary" type="button">
                    Agregar primera partida
                  </ActionButton>
                </div>
              ) : null}
              compact
              note="Todavía no hay capítulos ni partidas."
              title="Sin estructura"
            />
          ) : (
            <div className="pm-budget-tree">
              {budgetTree.chapters.map(({ chapter, items: chapterItems }) => {
                const chapterTotals = getChapterDisplayTotals(chapter, chapterItems);
                return (
                <div className="pm-budget-tree-group" key={chapter.id}>
                  <div className={`pm-budget-tree-node is-chapter ${selectedBudgetItem?.id === chapter.id ? "is-selected" : ""}`}>
                    <button className="pm-budget-tree-button" onClick={() => setSelectedItemId(chapter.id)} type="button">
                      <div className="pm-budget-tree-copy">
                        <strong>{safeDisplayText(chapter.codigo ? `${chapter.codigo} · ${chapter.nombre}` : chapter.nombre)}</strong>
                        <span>{itemTypeLabels[chapter.tipo]}</span>
                        <span className="pm-budget-tree-summary">
                          Costo {formatMoney(chapterTotals.cost)} · Venta {formatMoney(chapterTotals.sale)} · Margen {formatMoney(chapterTotals.margin)}
                        </span>
                      </div>
                    </button>
                    {canEditBudget ? (
                      <div className="table-actions">
                        <ActionButton onClick={(event) => openEditItemModal(chapter, event)} size="sm" type="button">
                          Editar
                        </ActionButton>
                        <ActionButton onClick={() => handleDeactivateItem(chapter)} size="sm" tone="danger" type="button">
                          Desactivar
                        </ActionButton>
                      </div>
                    ) : null}
                  </div>

                  {chapterItems.length === 0 ? (
                    <div className="pm-budget-tree-empty">Este capítulo todavía no tiene partidas.</div>
                  ) : (
                    <div className="pm-budget-tree-children">
                      {chapterItems.map((item) => (
                        <div className={`pm-budget-tree-node ${selectedBudgetItem?.id === item.id ? "is-selected" : ""}`} key={item.id}>
                          <button className="pm-budget-tree-button" onClick={() => setSelectedItemId(item.id)} type="button">
                            <div className="pm-budget-tree-copy">
                              <strong>{safeDisplayText(item.codigo ? `${item.codigo} · ${item.nombre}` : item.nombre)}</strong>
                              <span>
                                Cantidad {formatNumber(item.cantidad ?? 0)} · Unidad {safeDisplayText(item.unidad, "Sin unidad")}
                              </span>
                              <span className="pm-budget-tree-summary">
                                Costo {formatMoney(getBudgetItemTotals(item).cost)} · Venta {formatMoney(getBudgetItemTotals(item).sale)} · Margen {formatMoney(getBudgetItemTotals(item).margin)}
                              </span>
                            </div>
                            <StatusBadge tone={getItemTypeTone(item.tipo)}>{itemTypeLabels[item.tipo] ?? safeDisplayText(item.tipo)}</StatusBadge>
                          </button>
                          {canEditBudget ? (
                            <div className="table-actions">
                              <ActionButton onClick={(event) => openEditItemModal(item, event)} size="sm" type="button">
                                Editar
                              </ActionButton>
                              <ActionButton onClick={() => handleDeactivateItem(item)} size="sm" tone="danger" type="button">
                                Desactivar
                              </ActionButton>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                );
              })}

              {budgetTree.looseItems.length > 0 ? (
                <div className="pm-budget-tree-group">
                  <div className="pm-budget-tree-group-label">Partidas sin capítulo</div>
                  <div className="pm-budget-tree-children">
                    {budgetTree.looseItems.map((item) => (
                      <div className={`pm-budget-tree-node ${selectedBudgetItem?.id === item.id ? "is-selected" : ""}`} key={item.id}>
                        <button className="pm-budget-tree-button" onClick={() => setSelectedItemId(item.id)} type="button">
                          <div className="pm-budget-tree-copy">
                            <strong>{safeDisplayText(item.codigo ? `${item.codigo} · ${item.nombre}` : item.nombre)}</strong>
                            <span>
                              Cantidad {formatNumber(item.cantidad ?? 0)} · Unidad {safeDisplayText(item.unidad, "Sin unidad")}
                            </span>
                            <span className="pm-budget-tree-summary">
                              Costo {formatMoney(getBudgetItemTotals(item).cost)} · Venta {formatMoney(getBudgetItemTotals(item).sale)} · Margen {formatMoney(getBudgetItemTotals(item).margin)}
                            </span>
                          </div>
                        </button>
                        {canEditBudget ? (
                          <div className="table-actions">
                            <ActionButton onClick={(event) => openEditItemModal(item, event)} size="sm" type="button">
                              Editar
                            </ActionButton>
                            <ActionButton onClick={() => handleDeactivateItem(item)} size="sm" tone="danger" type="button">
                              Desactivar
                            </ActionButton>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </DataCard>

        <div className="pm-budget-side-stack">
          <DataCard
          actions={(
            <div className="inventory-actions inventory-actions-wrap">
              {canEditBudget ? (
                <>
                  <ActionButton disabled={!selectedOperationalItem} icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateMaterialModal} type="button">
                    Agregar material
                  </ActionButton>
                  <ActionButton disabled={!selectedOperationalItem} icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateLaborModal} tone="primary" type="button">
                    Agregar mano de obra
                  </ActionButton>
                </>
              ) : null}
              </div>
            )}
            subtitle={selectedOperationalItem
              ? "Agrega los materiales y la mano de obra necesarios para calcular el costo unitario. También conocido como APU."
              : "Selecciona una partida para revisar su desglose de costo."}
            title={selectedOperationalItem ? `Desglose de costos de la partida · ${safeDisplayText(selectedOperationalItem.nombre)}` : "Desglose de costos de la partida"}
          >
            {!budget ? (
              <EmptyState compact note="Primero crea el presupuesto del proyecto." title="Sin presupuesto" />
            ) : !selectedOperationalItem ? (
              <EmptyState
                action={canEditBudget ? (
                  <ActionButton onClick={(event) => openCreateItemModal("partida", event)} tone="primary" type="button">
                    Agregar partida
                  </ActionButton>
                ) : null}
                compact
                note="Selecciona una partida para agregar materiales y mano de obra."
                title="Sin partida seleccionada"
              />
            ) : (
              <div className="pm-budget-apu-stack">
                <div className="inventory-metric-grid inventory-metric-grid-3">
                  <MetricCard icon={<PackageOpen size={18} strokeWidth={1.9} />} label="Costo unitario" meta="Materiales + mano de obra" tone="info" value={formatMoney(selectedOperationalItem.costo_unitario ?? 0)} />
                  <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Precio unitario" meta="Venta por unidad" tone="success" value={formatMoney(selectedOperationalItem.precio_unitario ?? 0)} />
                  <MetricCard icon={<Calculator size={18} strokeWidth={1.9} />} label="Margen aplicado (%)" meta="Porcentaje configurado" tone="warning" value={formatPercent(selectedOperationalItem.margen_pct ?? 0)} />
                  <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Margen en pesos" meta="Venta - costo" tone={selectedOperationalItemMarginAmount < 0 ? "danger" : "success"} value={formatMoney(selectedOperationalItemMarginAmount)} />
                  <MetricCard icon={<ClipboardList size={18} strokeWidth={1.9} />} label="Cantidad" meta="Volumen de partida" tone="neutral" value={formatNumber(selectedOperationalItem.cantidad ?? 0)} />
                  <MetricCard icon={<Factory size={18} strokeWidth={1.9} />} label="Costo de la partida" meta="Cantidad × costo unitario" tone="info" value={formatMoney(selectedOperationalItem.subtotal_costo ?? 0)} />
                  <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Venta de la partida" meta="Cantidad × precio unitario" tone="success" value={formatMoney(selectedOperationalItem.subtotal_venta ?? 0)} />
                </div>

                <DataCard subtitle="Materiales requeridos por unidad de esta partida." title="Materiales de la partida">
                  {(selectedOperationalItem.materials?.length ?? 0) === 0 ? (
                    <EmptyState compact note="Sin materiales en esta partida." title="Sin materiales" />
                  ) : (
                    <DataTable columns={["Material", "Cantidad por unidad", "Costo unitario", "Total", "Acciones"]}>
                      <tbody>
                        {selectedOperationalItem.materials.map((component) => (
                          <tr key={component.id}>
                            <td>
                              <div className="inventory-cell-main">{safeDisplayText(component.material_nombre_snapshot)}</div>
                              <div className="inventory-cell-sub">{safeDisplayText(component.material_sku_snapshot, "Sin SKU")}</div>
                            </td>
                            <td>{formatNumber(component.cantidad_por_unidad ?? 0)}</td>
                            <td>{formatMoney(component.costo_unitario ?? 0)}</td>
                            <td>{formatMoney(component.costo_total ?? 0)}</td>
                            <td>
                              {canEditBudget ? (
                                <div className="table-actions">
                                  <ActionButton onClick={(event) => openEditMaterialModal(component, event)} size="sm" type="button">
                                    Editar
                                  </ActionButton>
                                  <ActionButton onClick={() => handleDeactivateMaterial(component)} size="sm" tone="danger" type="button">
                                    Quitar
                                  </ActionButton>
                                </div>
                              ) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </DataTable>
                  )}
                </DataCard>

                <DataCard subtitle="Horas y tarifa estimadas por unidad de esta partida." title="Mano de obra de la partida">
                  {(selectedOperationalItem.labor_components?.length ?? 0) === 0 ? (
                    <EmptyState compact note="Sin mano de obra en esta partida." title="Sin mano de obra" />
                  ) : (
                    <DataTable columns={["Rol / descripción", "Horas por unidad", "Tarifa por hora", "Total", "Acciones"]}>
                      <tbody>
                        {selectedOperationalItem.labor_components.map((component) => (
                          <tr key={component.id}>
                            <td>
                              <div className="inventory-cell-main">{safeDisplayText(component.rol, "Sin rol")}</div>
                              <div className="inventory-cell-sub">{safeDisplayText(component.descripcion, "Sin descripción")}</div>
                            </td>
                            <td>{formatNumber(component.horas_por_unidad ?? 0)}</td>
                            <td>{formatMoney(component.tarifa_hora ?? 0)}</td>
                            <td>{formatMoney(component.costo_total ?? 0)}</td>
                            <td>
                              {canEditBudget ? (
                                <div className="table-actions">
                                  <ActionButton onClick={(event) => openEditLaborModal(component, event)} size="sm" type="button">
                                    Editar
                                  </ActionButton>
                                  <ActionButton onClick={() => handleDeactivateLabor(component)} size="sm" tone="danger" type="button">
                                    Quitar
                                  </ActionButton>
                                </div>
                              ) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </DataTable>
                  )}
                </DataCard>
              </div>
            )}
          </DataCard>

          <DataCard
          actions={(
            canEditBudget ? (
              <ActionButton disabled={!budget} icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateIndirectModal} tone="primary" type="button">
                Agregar indirecto
              </ActionButton>
            ) : null
          )}
            subtitle="Agrega gastos generales del proyecto: administración, fletes, supervisión, herramientas, viáticos u otros."
            title="Costos indirectos"
          >
            {(indirects?.length ?? 0) === 0 ? (
              <EmptyState compact note="Sin costos indirectos." title="Sin costos indirectos" />
            ) : (
              <DataTable columns={["Concepto", "Tipo", "Valor", "Monto calculado", "Acciones"]}>
                <tbody>
                  {indirects.map((indirect) => (
                    <tr key={indirect.id}>
                      <td>{safeDisplayText(indirect.nombre)}</td>
                      <td>{indirectTypeLabels[indirect.tipo] ?? safeDisplayText(indirect.tipo)}</td>
                      <td>{indirect.tipo === "porcentaje" ? formatPercent(indirect.porcentaje ?? 0) : formatMoney(indirect.monto ?? 0)}</td>
                      <td>{formatMoney(indirect.monto ?? 0)}</td>
                      <td>
                        {canEditBudget ? (
                          <div className="table-actions">
                            <ActionButton onClick={(event) => openEditIndirectModal(indirect, event)} size="sm" type="button">
                              Editar
                            </ActionButton>
                            <ActionButton onClick={() => handleDeactivateIndirect(indirect)} size="sm" tone="danger" type="button">
                              Quitar
                            </ActionButton>
                          </div>
                        ) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            )}
          </DataCard>

          <DataCard subtitle="Compara presupuesto detallado contra costos reales acumulados del proyecto." title="Comparativo real">
            <div className="pm-detail-list">
              <div className="pm-detail-list-item">
                <div>
                  <strong>Presupuesto base</strong>
                  <span>Referencia guardada en el proyecto</span>
                </div>
                <strong>{formatMoney(projectBudgetBase)}</strong>
              </div>
              <div className="pm-detail-list-item">
                <div>
                  <strong>Costo calculado</strong>
                  <span>{vsActual?.presupuesto_origen === "detallado" ? "Presupuesto detallado activo" : "Presupuesto simple"}</span>
                </div>
                <strong>{formatMoney(budgetCalculatedCost)}</strong>
              </div>
              <div className="pm-detail-list-item">
                <div>
                  <strong>Real materiales</strong>
                  <span>Consumo acumulado</span>
                </div>
                <strong>{formatMoney(vsActual?.costo_materiales_real ?? 0)}</strong>
              </div>
              <div className="pm-detail-list-item">
                <div>
                  <strong>Real horas</strong>
                  <span>Labor acumulada</span>
                </div>
                <strong>{formatMoney(vsActual?.costo_horas_real ?? 0)}</strong>
              </div>
              <div className="pm-detail-list-item">
                <div>
                  <strong>Real total</strong>
                  <span>Materiales + horas</span>
                </div>
                <strong>{formatMoney(vsActual?.costo_real_total ?? 0)}</strong>
              </div>
              <div className="pm-detail-list-item">
                <div>
                  <strong>Variación</strong>
                  <span>Costo calculado - costo real</span>
                </div>
                <strong>{formatMoney(varianceAgainstActual)}</strong>
              </div>
              <div className="pm-detail-list-item">
                <div>
                  <strong>Consumo del presupuesto</strong>
                  <span>Porcentaje usado hasta hoy</span>
                </div>
                <strong>{formatPercent(vsActual?.porcentaje_consumido ?? 0)}</strong>
              </div>
            </div>
          </DataCard>
        </div>
      </div>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeBudgetModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-budget-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingBudget ? "Guardar cambios" : "Crear presupuesto"}
            </ActionButton>
          </div>
        )}
        onClose={closeBudgetModal}
        open={activeBudgetModal === "budget"}
        subtitle="Crea el presupuesto del proyecto y define moneda, margen e indirectos generales."
        title={editingBudget ? "Editar presupuesto" : "Crear presupuesto"}
      >
        <form className="inventory-modal-form" id="pm-budget-form" onSubmit={handleSaveBudget}>
          <FormGrid columns={2}>
            <Field label="Nombre del presupuesto">
              <input
                onChange={(event) => setBudgetForm((current) => ({ ...current, nombre: event.target.value }))}
                required
                value={budgetForm.nombre}
              />
            </Field>
            <Field label="Moneda">
              <input
                maxLength={8}
                onChange={(event) => setBudgetForm((current) => ({ ...current, moneda: event.target.value }))}
                value={budgetForm.moneda}
              />
            </Field>
            <Field label="Indirectos generales %">
              <input
                min="0"
                onChange={(event) => setBudgetForm((current) => ({ ...current, indirectos_pct: event.target.value }))}
                step="0.01"
                type="number"
                value={budgetForm.indirectos_pct}
              />
            </Field>
            <Field label="Notas">
              <textarea
                onChange={(event) => setBudgetForm((current) => ({ ...current, notas: event.target.value }))}
                rows={4}
                value={budgetForm.notas}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeItemModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-budget-item-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingItem ? "Guardar cambios" : itemForm.tipo === "capitulo" ? "Crear capítulo" : "Crear partida"}
            </ActionButton>
          </div>
        )}
        onClose={closeItemModal}
        open={activeBudgetModal === "chapter" || activeBudgetModal === "item"}
        subtitle={itemForm.tipo === "capitulo" ? "Organiza el presupuesto en grandes frentes de trabajo." : "Registra una partida operativa para después agregar materiales y mano de obra."}
        title={editingItem ? "Editar partida" : itemForm.tipo === "capitulo" ? "Agregar capítulo" : "Agregar partida"}
      >
        <form className="inventory-modal-form" id="pm-budget-item-form" onSubmit={handleSaveItem}>
          <FormGrid columns={2}>
            <Field label="Tipo">
              <select
                onChange={(event) => setItemForm((current) => ({
                  ...current,
                  tipo: event.target.value,
                  parent_id: event.target.value === "capitulo" ? "" : current.parent_id,
                }))}
                value={itemForm.tipo}
              >
                <option value="capitulo">Capítulo</option>
                <option value="partida">Partida</option>
              </select>
            </Field>
            <Field label="Código opcional">
              <input onChange={(event) => setItemForm((current) => ({ ...current, codigo: event.target.value }))} value={itemForm.codigo} />
            </Field>
            <Field label="Capítulo padre">
              <select
                disabled={itemForm.tipo === "capitulo"}
                onChange={(event) => setItemForm((current) => ({ ...current, parent_id: event.target.value }))}
                value={itemForm.parent_id}
              >
                <option value="">Sin capítulo</option>
                {chapterOptions
                  .filter((option) => option.id !== editingItem?.id)
                  .map((option) => (
                    <option key={option.id} value={option.id}>
                      {safeDisplayText(option.codigo ? `${option.codigo} · ${option.nombre}` : option.nombre)}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label={itemForm.tipo === "capitulo" ? "Nombre del capítulo" : "Nombre de la partida"}>
              <input onChange={(event) => setItemForm((current) => ({ ...current, nombre: event.target.value }))} required value={itemForm.nombre} />
            </Field>
            <Field label="Descripción opcional">
              <textarea onChange={(event) => setItemForm((current) => ({ ...current, descripcion: event.target.value }))} rows={4} value={itemForm.descripcion} />
            </Field>
            <Field label="Unidad">
              <input disabled={itemForm.tipo === "capitulo"} onChange={(event) => setItemForm((current) => ({ ...current, unidad: event.target.value }))} value={itemForm.unidad} />
            </Field>
            <Field label="Cantidad">
              <input min="0" onChange={(event) => setItemForm((current) => ({ ...current, cantidad: event.target.value }))} step="0.01" type="number" value={itemForm.cantidad} />
            </Field>
            <Field label="Margen esperado %">
              <input min="0" onChange={(event) => setItemForm((current) => ({ ...current, margen_pct: event.target.value }))} step="0.01" type="number" value={itemForm.margen_pct} />
            </Field>
            <Field label="Precio unitario manual opcional">
              <input min="0" onChange={(event) => setItemForm((current) => ({ ...current, precio_unitario_manual: event.target.value }))} step="0.01" type="number" value={itemForm.precio_unitario_manual} />
            </Field>
            <Field label="Orden">
              <input min="0" onChange={(event) => setItemForm((current) => ({ ...current, orden: event.target.value }))} step="1" type="number" value={itemForm.orden} />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeMaterialModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-budget-material-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingMaterial ? "Guardar cambios" : "Agregar material"}
            </ActionButton>
          </div>
        )}
        onClose={closeMaterialModal}
        open={activeBudgetModal === "material"}
        subtitle="Agrega materiales necesarios para calcular el costo unitario de la partida."
        title={editingMaterial ? "Editar material" : "Agregar material"}
      >
        <form className="inventory-modal-form" id="pm-budget-material-form" onSubmit={handleSaveMaterial}>
          <FormGrid columns={2}>
            <Field label="Buscar material del catálogo">
              <select onChange={(event) => handleCatalogMaterialChange(event.target.value)} value={materialForm.material_id}>
                <option value="">Captura manual</option>
                {materialsCatalog.map((material) => (
                  <option key={material.id} value={material.id}>
                    {safeDisplayText(material.sku ? `${material.sku} · ${material.nombre}` : material.nombre)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Nombre del material">
              <input
                onChange={(event) => setMaterialForm((current) => ({ ...current, material_nombre_snapshot: event.target.value }))}
                required={!materialForm.material_id}
                value={materialForm.material_nombre_snapshot}
              />
            </Field>
            <Field label="SKU opcional">
              <input onChange={(event) => setMaterialForm((current) => ({ ...current, material_sku_snapshot: event.target.value }))} value={materialForm.material_sku_snapshot} />
            </Field>
            <Field label="Unidad">
              <input onChange={(event) => setMaterialForm((current) => ({ ...current, unidad: event.target.value }))} value={materialForm.unidad} />
            </Field>
            <Field label="Cantidad por unidad">
              <input min="0" onChange={(event) => setMaterialForm((current) => ({ ...current, cantidad_por_unidad: event.target.value }))} step="0.0001" type="number" value={materialForm.cantidad_por_unidad} />
            </Field>
            <Field label="Costo unitario">
              <input min="0" onChange={(event) => setMaterialForm((current) => ({ ...current, costo_unitario: event.target.value }))} step="0.0001" type="number" value={materialForm.costo_unitario} />
            </Field>
            <Field label="Proveedor opcional">
              <input onChange={(event) => setMaterialForm((current) => ({ ...current, proveedor_nombre_snapshot: event.target.value }))} value={materialForm.proveedor_nombre_snapshot} />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeLaborModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-budget-labor-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingLabor ? "Guardar cambios" : "Agregar mano de obra"}
            </ActionButton>
          </div>
        )}
        onClose={closeLaborModal}
        open={activeBudgetModal === "labor"}
        subtitle="Agrega horas estimadas y tarifa para calcular el costo unitario de la partida."
        title={editingLabor ? "Editar mano de obra" : "Agregar mano de obra"}
      >
        <form className="inventory-modal-form" id="pm-budget-labor-form" onSubmit={handleSaveLabor}>
          <FormGrid columns={2}>
            <Field label="Rol o perfil">
              <select onChange={(event) => setLaborForm((current) => ({ ...current, rol: event.target.value }))} value={laborForm.rol}>
                <option value="">Sin rol</option>
                {pmRateRoleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Descripción">
              <input onChange={(event) => setLaborForm((current) => ({ ...current, descripcion: event.target.value }))} value={laborForm.descripcion} />
            </Field>
            <Field label="Horas por unidad">
              <input min="0" onChange={(event) => setLaborForm((current) => ({ ...current, horas_por_unidad: event.target.value }))} step="0.0001" type="number" value={laborForm.horas_por_unidad} />
            </Field>
            <Field label="Tarifa por hora">
              <input min="0" onChange={(event) => setLaborForm((current) => ({ ...current, tarifa_hora: event.target.value }))} step="0.0001" type="number" value={laborForm.tarifa_hora} />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={(
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeIndirectModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-budget-indirect-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingIndirect ? "Guardar cambios" : "Agregar indirecto"}
            </ActionButton>
          </div>
        )}
        onClose={closeIndirectModal}
        open={activeBudgetModal === "indirect"}
        subtitle="Agrega gastos generales, administración, fletes, supervisión u otros costos del proyecto."
        title={editingIndirect ? "Editar costo indirecto" : "Agregar costo indirecto"}
      >
        <form className="inventory-modal-form" id="pm-budget-indirect-form" onSubmit={handleSaveIndirect}>
          <FormGrid columns={2}>
            <Field label="Nombre del costo">
              <input onChange={(event) => setIndirectForm((current) => ({ ...current, nombre: event.target.value }))} required value={indirectForm.nombre} />
            </Field>
            <Field label="Tipo">
              <select onChange={(event) => setIndirectForm((current) => ({ ...current, tipo: event.target.value }))} value={indirectForm.tipo}>
                <option value="monto">Monto fijo</option>
                <option value="porcentaje">Porcentaje</option>
              </select>
            </Field>
            <Field label="Porcentaje">
              <input
                disabled={indirectForm.tipo !== "porcentaje"}
                min="0"
                onChange={(event) => setIndirectForm((current) => ({ ...current, porcentaje: event.target.value }))}
                step="0.01"
                type="number"
                value={indirectForm.porcentaje}
              />
            </Field>
            <Field label="Monto">
              <input
                disabled={indirectForm.tipo !== "monto"}
                min="0"
                onChange={(event) => setIndirectForm((current) => ({ ...current, monto: event.target.value }))}
                step="0.01"
                type="number"
                value={indirectForm.monto}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>
    </div>
  );
}
