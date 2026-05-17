import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  createInventoryMovement,
  createMaterial,
  createWarehouse,
  getInventoryMovements,
  getMaterialKardex,
  getMaterials,
  getStock,
  getWarehouses,
  updateMaterial,
  updateWarehouse,
} from "../api/client";


const inventoryTabs = [
  { id: "almacenes", label: "Almacenes" },
  { id: "materiales", label: "Materiales" },
  { id: "existencias", label: "Existencias" },
  { id: "movimientos", label: "Movimientos" },
  { id: "kardex", label: "Kardex" },
];

const movementTypeOptions = [
  { value: "entrada", label: "Registrar entrada" },
  { value: "salida", label: "Registrar salida" },
  { value: "ajuste", label: "Registrar ajuste" },
];


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


function InventoryTabButton({ active, label, onClick }) {
  return (
    <button
      className={`inventory-tab-button ${active ? "active" : ""}`}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}


export default function InventoryPage() {
  const { token, empresaId } = useAuth();
  const [activeTab, setActiveTab] = useState("existencias");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warehouses, setWarehouses] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [stockItems, setStockItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [kardex, setKardex] = useState(null);
  const [warehouseForm, setWarehouseForm] = useState({
    id: "",
    nombre: "",
    codigo: "",
    descripcion: "",
    activo: true,
  });
  const [materialForm, setMaterialForm] = useState({
    id: "",
    sku: "",
    nombre: "",
    descripcion: "",
    categoria: "",
    unidad: "pieza",
    costo_unitario: "0",
    precio_venta: "0",
    stock_minimo: "0",
    activo: true,
  });
  const [movementForm, setMovementForm] = useState({
    almacen_id: "",
    material_id: "",
    tipo: "entrada",
    cantidad: "",
    cantidad_nueva: "",
    referencia_tipo: "manual",
    referencia_id: "",
    notas: "",
  });
  const [kardexFilters, setKardexFilters] = useState({
    material_id: "",
    almacen_id: "",
  });

  const lowStockCount = useMemo(
    () => stockItems.filter((item) => item.low_stock).length,
    [stockItems],
  );

  async function loadInventoryData() {
    if (!token || !empresaId) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const [warehouseResponse, materialResponse, stockResponse, movementResponse] = await Promise.all([
        getWarehouses({ token, empresaId }),
        getMaterials({ token, empresaId }),
        getStock({ token, empresaId }),
        getInventoryMovements({ token, empresaId }),
      ]);

      setWarehouses(warehouseResponse.items);
      setMaterials(materialResponse.items);
      setStockItems(stockResponse.items);
      setMovements(movementResponse.items);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar Inventario.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshInventoryData({ reloadKardex = true } = {}) {
    if (!token || !empresaId) {
      return;
    }

    const [warehouseResponse, materialResponse, stockResponse, movementResponse] = await Promise.all([
      getWarehouses({ token, empresaId }),
      getMaterials({ token, empresaId }),
      getStock({ token, empresaId }),
      getInventoryMovements({ token, empresaId }),
    ]);

    setWarehouses(warehouseResponse.items);
    setMaterials(materialResponse.items);
    setStockItems(stockResponse.items);
    setMovements(movementResponse.items);

    if (reloadKardex && kardexFilters.material_id) {
      const kardexResponse = await getMaterialKardex({
        materialId: kardexFilters.material_id,
        almacenId: kardexFilters.almacen_id || undefined,
        token,
        empresaId,
      });
      setKardex(kardexResponse);
    }
  }

  useEffect(() => {
    loadInventoryData();
  }, [token, empresaId]);

  useEffect(() => {
    if (warehouses.length > 0 && !movementForm.almacen_id) {
      setMovementForm((current) => ({ ...current, almacen_id: warehouses[0].id }));
    }
  }, [warehouses, movementForm.almacen_id]);

  useEffect(() => {
    if (materials.length > 0 && !movementForm.material_id) {
      setMovementForm((current) => ({ ...current, material_id: materials[0].id }));
    }
    if (materials.length > 0 && !kardexFilters.material_id) {
      setKardexFilters((current) => ({ ...current, material_id: materials[0].id }));
    }
  }, [materials, movementForm.material_id, kardexFilters.material_id]);

  function resetWarehouseForm() {
    setWarehouseForm({
      id: "",
      nombre: "",
      codigo: "",
      descripcion: "",
      activo: true,
    });
  }

  function resetMaterialForm() {
    setMaterialForm({
      id: "",
      sku: "",
      nombre: "",
      descripcion: "",
      categoria: "",
      unidad: "pieza",
      costo_unitario: "0",
      precio_venta: "0",
      stock_minimo: "0",
      activo: true,
    });
  }

  async function handleWarehouseSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      nombre: warehouseForm.nombre,
      codigo: warehouseForm.codigo,
      descripcion: warehouseForm.descripcion,
      activo: warehouseForm.activo,
    };

    try {
      if (warehouseForm.id) {
        await updateWarehouse({
          warehouseId: warehouseForm.id,
          token,
          empresaId,
          payload,
        });
        setSuccess("Almacen actualizado correctamente.");
      } else {
        await createWarehouse({ token, empresaId, payload });
        setSuccess("Almacen creado correctamente.");
      }

      resetWarehouseForm();
      await refreshInventoryData({ reloadKardex: false });
      setActiveTab("almacenes");
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el almacen.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMaterialSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      sku: materialForm.sku,
      nombre: materialForm.nombre,
      descripcion: materialForm.descripcion,
      categoria: materialForm.categoria,
      unidad: materialForm.unidad,
      costo_unitario: materialForm.costo_unitario,
      precio_venta: materialForm.precio_venta,
      stock_minimo: materialForm.stock_minimo,
      activo: materialForm.activo,
    };

    try {
      if (materialForm.id) {
        await updateMaterial({
          materialId: materialForm.id,
          token,
          empresaId,
          payload,
        });
        setSuccess("Material actualizado correctamente.");
      } else {
        await createMaterial({ token, empresaId, payload });
        setSuccess("Material creado correctamente.");
      }

      resetMaterialForm();
      await refreshInventoryData();
      setActiveTab("materiales");
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el material.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMovementSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    const payload = {
      almacen_id: movementForm.almacen_id,
      material_id: movementForm.material_id,
      tipo: movementForm.tipo,
      referencia_tipo: movementForm.referencia_tipo || "manual",
      referencia_id: movementForm.referencia_id || null,
      notas: movementForm.notas || null,
    };

    if (movementForm.tipo === "ajuste") {
      payload.cantidad_nueva = movementForm.cantidad_nueva;
    } else {
      payload.cantidad = movementForm.cantidad;
    }

    try {
      await createInventoryMovement({ token, empresaId, payload });
      setSuccess(
        movementForm.tipo === "entrada"
          ? "Entrada registrada correctamente."
          : movementForm.tipo === "salida"
          ? "Salida registrada correctamente."
          : "Ajuste registrado correctamente.",
      );
      setMovementForm((current) => ({
        ...current,
        cantidad: "",
        cantidad_nueva: "",
        referencia_id: "",
        notas: "",
      }));
      await refreshInventoryData();
      setActiveTab("movimientos");
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar el movimiento.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLoadKardex(nextMaterialId = kardexFilters.material_id) {
    if (!nextMaterialId) {
      setError("Selecciona un material para consultar su kardex.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const response = await getMaterialKardex({
        materialId: nextMaterialId,
        almacenId: kardexFilters.almacen_id || undefined,
        token,
        empresaId,
      });
      setKardex(response);
      setSuccess("Kardex actualizado.");
      setActiveTab("kardex");
    } catch (requestError) {
      setError(requestError.message || "No se pudo consultar el kardex.");
    } finally {
      setSubmitting(false);
    }
  }

  const currentMovementLabel =
    movementTypeOptions.find((option) => option.value === movementForm.tipo)?.label ?? "Registrar movimiento";

  if (loading) {
    return <div className="screen-center">Cargando inventario...</div>;
  }

  return (
    <section className="inventory-shell">
      <div className="hero-card inventory-hero">
        <div>
          <p className="eyebrow">Inventario Fase 1</p>
          <h2>Control multiempresa de almacenes, materiales y stock</h2>
          <p>
            La verdad del stock vive en existencias y movimientos. No se permite stock
            negativo y cada operacion queda auditada en backend.
          </p>
        </div>

        <div className="hero-grid">
          <article className="metric-card">
            <span>Almacenes</span>
            <strong>{warehouses.length}</strong>
          </article>
          <article className="metric-card">
            <span>Materiales</span>
            <strong>{materials.length}</strong>
          </article>
          <article className="metric-card">
            <span>Existencias</span>
            <strong>{stockItems.length}</strong>
          </article>
          <article className="metric-card">
            <span>Stock bajo</span>
            <strong>{lowStockCount}</strong>
          </article>
        </div>
      </div>

      <div className="inventory-tabs">
        {inventoryTabs.map((tab) => (
          <InventoryTabButton
            active={activeTab === tab.id}
            key={tab.id}
            label={tab.label}
            onClick={() => setActiveTab(tab.id)}
          />
        ))}
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}

      {activeTab === "almacenes" ? (
        <div className="inventory-grid">
          <form className="feature-card inventory-form-card" onSubmit={handleWarehouseSubmit}>
            <div className="feature-header">
              <p className="eyebrow">Almacenes</p>
              <h2>{warehouseForm.id ? "Editar almacen" : "Crear almacen"}</h2>
              <p>Define almacenes por empresa con codigo unico.</p>
            </div>

            <label>
              Nombre
              <input
                onChange={(event) =>
                  setWarehouseForm((current) => ({ ...current, nombre: event.target.value }))
                }
                required
                type="text"
                value={warehouseForm.nombre}
              />
            </label>

            <label>
              Codigo
              <input
                onChange={(event) =>
                  setWarehouseForm((current) => ({ ...current, codigo: event.target.value.toUpperCase() }))
                }
                required
                type="text"
                value={warehouseForm.codigo}
              />
            </label>

            <label>
              Descripcion
              <textarea
                onChange={(event) =>
                  setWarehouseForm((current) => ({ ...current, descripcion: event.target.value }))
                }
                rows={3}
                value={warehouseForm.descripcion}
              />
            </label>

            <label className="checkbox-row">
              <input
                checked={warehouseForm.activo}
                onChange={(event) =>
                  setWarehouseForm((current) => ({ ...current, activo: event.target.checked }))
                }
                type="checkbox"
              />
              <span>Almacen activo</span>
            </label>

            <div className="inventory-actions">
              <button className="primary-button" disabled={submitting} type="submit">
                {submitting
                  ? "Guardando..."
                  : warehouseForm.id
                  ? "Actualizar almacen"
                  : "Crear almacen"}
              </button>
              {warehouseForm.id ? (
                <button
                  className="ghost-button"
                  onClick={resetWarehouseForm}
                  type="button"
                >
                  Cancelar edicion
                </button>
              ) : null}
            </div>
          </form>

          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Listado</p>
              <h2>Almacenes registrados</h2>
            </div>

            {warehouses.length === 0 ? (
              <EmptyState
                note="Crea tu primer almacen para empezar a mover stock."
                title="No hay almacenes todavia."
              />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Nombre</th>
                      <th>Codigo</th>
                      <th>Estatus</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {warehouses.map((warehouse) => (
                      <tr key={warehouse.id}>
                        <td>
                          <strong>{warehouse.nombre}</strong>
                          <div className="table-note">{warehouse.descripcion || "Sin descripcion"}</div>
                        </td>
                        <td>{warehouse.codigo}</td>
                        <td>
                          <span className={`status-badge ${warehouse.activo ? "enabled" : "pending"}`}>
                            {warehouse.activo ? "Activo" : "Inactivo"}
                          </span>
                        </td>
                        <td>
                          <button
                            className="link-button"
                            onClick={() =>
                              setWarehouseForm({
                                id: warehouse.id,
                                nombre: warehouse.nombre,
                                codigo: warehouse.codigo,
                                descripcion: warehouse.descripcion || "",
                                activo: warehouse.activo,
                              })
                            }
                            type="button"
                          >
                            Editar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === "materiales" ? (
        <div className="inventory-grid">
          <form className="feature-card inventory-form-card" onSubmit={handleMaterialSubmit}>
            <div className="feature-header">
              <p className="eyebrow">Materiales</p>
              <h2>{materialForm.id ? "Editar material" : "Crear material"}</h2>
              <p>SKU unico por empresa y precios sin stock actual embebido.</p>
            </div>

            <div className="inventory-form-grid">
              <label>
                SKU
                <input
                  onChange={(event) =>
                    setMaterialForm((current) => ({ ...current, sku: event.target.value.toUpperCase() }))
                  }
                  required
                  type="text"
                  value={materialForm.sku}
                />
              </label>

              <label>
                Unidad
                <input
                  onChange={(event) =>
                    setMaterialForm((current) => ({ ...current, unidad: event.target.value }))
                  }
                  required
                  type="text"
                  value={materialForm.unidad}
                />
              </label>

              <label className="inventory-form-span-2">
                Nombre
                <input
                  onChange={(event) =>
                    setMaterialForm((current) => ({ ...current, nombre: event.target.value }))
                  }
                  required
                  type="text"
                  value={materialForm.nombre}
                />
              </label>

              <label>
                Categoria
                <input
                  onChange={(event) =>
                    setMaterialForm((current) => ({ ...current, categoria: event.target.value }))
                  }
                  type="text"
                  value={materialForm.categoria}
                />
              </label>

              <label>
                Stock minimo
                <input
                  min="0"
                  onChange={(event) =>
                    setMaterialForm((current) => ({
                      ...current,
                      stock_minimo: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  step="0.0001"
                  type="number"
                  value={materialForm.stock_minimo}
                />
              </label>

              <label>
                Costo unitario
                <input
                  min="0"
                  onChange={(event) =>
                    setMaterialForm((current) => ({
                      ...current,
                      costo_unitario: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  step="0.0001"
                  type="number"
                  value={materialForm.costo_unitario}
                />
              </label>

              <label>
                Precio de venta
                <input
                  min="0"
                  onChange={(event) =>
                    setMaterialForm((current) => ({
                      ...current,
                      precio_venta: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  step="0.0001"
                  type="number"
                  value={materialForm.precio_venta}
                />
              </label>

              <label className="inventory-form-span-2">
                Descripcion
                <textarea
                  onChange={(event) =>
                    setMaterialForm((current) => ({ ...current, descripcion: event.target.value }))
                  }
                  rows={3}
                  value={materialForm.descripcion}
                />
              </label>
            </div>

            <label className="checkbox-row">
              <input
                checked={materialForm.activo}
                onChange={(event) =>
                  setMaterialForm((current) => ({ ...current, activo: event.target.checked }))
                }
                type="checkbox"
              />
              <span>Material activo</span>
            </label>

            <div className="inventory-actions">
              <button className="primary-button" disabled={submitting} type="submit">
                {submitting
                  ? "Guardando..."
                  : materialForm.id
                  ? "Actualizar material"
                  : "Crear material"}
              </button>
              {materialForm.id ? (
                <button className="ghost-button" onClick={resetMaterialForm} type="button">
                  Cancelar edicion
                </button>
              ) : null}
            </div>
          </form>

          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Catalogo</p>
              <h2>Materiales registrados</h2>
            </div>

            {materials.length === 0 ? (
              <EmptyState
                note="Crea un material para empezar a registrar existencias y kardex."
                title="No hay materiales todavia."
              />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Material</th>
                      <th>Precio</th>
                      <th>Stock minimo</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {materials.map((material) => (
                      <tr key={material.id}>
                        <td>{material.sku}</td>
                        <td>
                          <strong>{material.nombre}</strong>
                          <div className="table-note">
                            {material.categoria || "Sin categoria"} | {material.unidad}
                          </div>
                        </td>
                        <td>{formatMoney(material.precio_venta)}</td>
                        <td>{formatNumber(material.stock_minimo)}</td>
                        <td className="inventory-row-actions">
                          <button
                            className="link-button"
                            onClick={() =>
                              setMaterialForm({
                                id: material.id,
                                sku: material.sku,
                                nombre: material.nombre,
                                descripcion: material.descripcion || "",
                                categoria: material.categoria || "",
                                unidad: material.unidad,
                                costo_unitario: String(material.costo_unitario),
                                precio_venta: String(material.precio_venta),
                                stock_minimo: String(material.stock_minimo),
                                activo: material.activo,
                              })
                            }
                            type="button"
                          >
                            Editar
                          </button>
                          <button
                            className="link-button"
                            onClick={() => {
                              setKardexFilters((current) => ({ ...current, material_id: material.id }));
                              handleLoadKardex(material.id);
                            }}
                            type="button"
                          >
                            Ver kardex
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === "existencias" ? (
        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Existencias</p>
            <h2>Stock por almacen y material</h2>
            <p>La existencia se calcula desde movimientos y nunca desde un stock pegado al material.</p>
          </div>

          {stockItems.length === 0 ? (
            <EmptyState
              note="Registra una entrada para que aparezca la primera existencia."
              title="No hay existencias registradas."
            />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Almacen</th>
                    <th>SKU</th>
                    <th>Material</th>
                    <th>Cantidad</th>
                    <th>Minimo</th>
                    <th>Estatus</th>
                  </tr>
                </thead>
                <tbody>
                  {stockItems.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.almacen_nombre}</strong>
                        <div className="table-note">{item.almacen_codigo}</div>
                      </td>
                      <td>{item.material_sku}</td>
                      <td>
                        <strong>{item.material_nombre}</strong>
                        <div className="table-note">{item.material_unidad}</div>
                      </td>
                      <td>{formatNumber(item.cantidad)}</td>
                      <td>{formatNumber(item.stock_minimo)}</td>
                      <td>
                        <span className={`status-badge ${item.low_stock ? "pending" : "enabled"}`}>
                          {item.low_stock ? "Stock bajo" : "OK"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      {activeTab === "movimientos" ? (
        <div className="inventory-grid">
          <form className="feature-card inventory-form-card" onSubmit={handleMovementSubmit}>
            <div className="feature-header">
              <p className="eyebrow">Movimientos</p>
              <h2>{currentMovementLabel}</h2>
              <p>No se permite stock negativo y cada movimiento genera auditoria.</p>
            </div>

            {warehouses.length === 0 || materials.length === 0 ? (
              <EmptyState
                note="Necesitas al menos un almacen y un material antes de mover inventario."
                title="Faltan datos base."
              />
            ) : (
              <>
                <div className="inventory-toggle-row">
                  {movementTypeOptions.map((option) => (
                    <button
                      className={`inventory-toggle-button ${
                        movementForm.tipo === option.value ? "active" : ""
                      }`}
                      key={option.value}
                      onClick={() =>
                        setMovementForm((current) => ({
                          ...current,
                          tipo: option.value,
                          cantidad: "",
                          cantidad_nueva: "",
                        }))
                      }
                      type="button"
                    >
                      {option.label}
                    </button>
                  ))}
                </div>

                <div className="inventory-form-grid">
                  <label>
                    Almacen
                    <select
                      onChange={(event) =>
                        setMovementForm((current) => ({ ...current, almacen_id: event.target.value }))
                      }
                      required
                      value={movementForm.almacen_id}
                    >
                      {warehouses.map((warehouse) => (
                        <option key={warehouse.id} value={warehouse.id}>
                          {warehouse.nombre} ({warehouse.codigo})
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Material
                    <select
                      onChange={(event) =>
                        setMovementForm((current) => ({ ...current, material_id: event.target.value }))
                      }
                      required
                      value={movementForm.material_id}
                    >
                      {materials.map((material) => (
                        <option key={material.id} value={material.id}>
                          {material.sku} - {material.nombre}
                        </option>
                      ))}
                    </select>
                  </label>

                  {movementForm.tipo === "ajuste" ? (
                    <label>
                      Cantidad nueva
                      <input
                        min="0"
                        onChange={(event) =>
                          setMovementForm((current) => ({
                            ...current,
                            cantidad_nueva: normalizeDecimalInput(event.target.value),
                          }))
                        }
                        required
                        step="0.0001"
                        type="number"
                        value={movementForm.cantidad_nueva}
                      />
                    </label>
                  ) : (
                    <label>
                      Cantidad
                      <input
                        min="0.0001"
                        onChange={(event) =>
                          setMovementForm((current) => ({
                            ...current,
                            cantidad: normalizeDecimalInput(event.target.value),
                          }))
                        }
                        required
                        step="0.0001"
                        type="number"
                        value={movementForm.cantidad}
                      />
                    </label>
                  )}

                  <label>
                    Referencia tipo
                    <input
                      onChange={(event) =>
                        setMovementForm((current) => ({ ...current, referencia_tipo: event.target.value }))
                      }
                      type="text"
                      value={movementForm.referencia_tipo}
                    />
                  </label>

                  <label>
                    Referencia ID
                    <input
                      onChange={(event) =>
                        setMovementForm((current) => ({ ...current, referencia_id: event.target.value }))
                      }
                      type="text"
                      value={movementForm.referencia_id}
                    />
                  </label>

                  <label className="inventory-form-span-2">
                    Notas
                    <textarea
                      onChange={(event) =>
                        setMovementForm((current) => ({ ...current, notas: event.target.value }))
                      }
                      rows={3}
                      value={movementForm.notas}
                    />
                  </label>
                </div>

                <button className="primary-button" disabled={submitting} type="submit">
                  {submitting ? "Registrando..." : currentMovementLabel}
                </button>
              </>
            )}
          </form>

          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Auditoria</p>
              <h2>Movimientos recientes</h2>
            </div>

            {movements.length === 0 ? (
              <EmptyState
                note="Cuando registres entradas, salidas o ajustes apareceran aqui."
                title="No hay movimientos todavia."
              />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Tipo</th>
                      <th>Material</th>
                      <th>Almacen</th>
                      <th>Cambio</th>
                      <th>Nuevo stock</th>
                    </tr>
                  </thead>
                  <tbody>
                    {movements.map((movement) => (
                      <tr key={movement.id}>
                        <td>{formatDateTime(movement.created_at)}</td>
                        <td>
                          <span className={`status-badge ${movement.tipo === "salida" ? "pending" : "enabled"}`}>
                            {movement.tipo}
                          </span>
                        </td>
                        <td>
                          <strong>{movement.material_sku}</strong>
                          <div className="table-note">{movement.material_nombre}</div>
                        </td>
                        <td>{movement.almacen_nombre}</td>
                        <td>{formatNumber(movement.cantidad)}</td>
                        <td>{formatNumber(movement.cantidad_nueva)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === "kardex" ? (
        <div className="inventory-grid">
          <div className="feature-card inventory-form-card">
            <div className="feature-header">
              <p className="eyebrow">Kardex</p>
              <h2>Consulta por material</h2>
              <p>Revisa el historial completo y el stock distribuido por almacen.</p>
            </div>

            {materials.length === 0 ? (
              <EmptyState
                note="Crea al menos un material para consultar su kardex."
                title="No hay materiales disponibles."
              />
            ) : (
              <>
                <label>
                  Material
                  <select
                    onChange={(event) =>
                      setKardexFilters((current) => ({ ...current, material_id: event.target.value }))
                    }
                    value={kardexFilters.material_id}
                  >
                    {materials.map((material) => (
                      <option key={material.id} value={material.id}>
                        {material.sku} - {material.nombre}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  Almacen (opcional)
                  <select
                    onChange={(event) =>
                      setKardexFilters((current) => ({ ...current, almacen_id: event.target.value }))
                    }
                    value={kardexFilters.almacen_id}
                  >
                    <option value="">Todos</option>
                    {warehouses.map((warehouse) => (
                      <option key={warehouse.id} value={warehouse.id}>
                        {warehouse.nombre} ({warehouse.codigo})
                      </option>
                    ))}
                  </select>
                </label>

                <button className="primary-button" disabled={submitting} onClick={() => handleLoadKardex()} type="button">
                  {submitting ? "Consultando..." : "Ver kardex"}
                </button>
              </>
            )}
          </div>

          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Detalle</p>
              <h2>Kardex del material</h2>
            </div>

            {!kardex ? (
              <EmptyState
                note="Selecciona un material y presiona Ver kardex."
                title="Sin consulta activa."
              />
            ) : (
              <div className="inventory-kardex-stack">
                <div className="module-board">
                  <article className="mini-card">
                    <span className="eyebrow">Material</span>
                    <strong>{kardex.material.sku}</strong>
                    <p>{kardex.material.nombre}</p>
                  </article>
                  <article className="mini-card">
                    <span className="eyebrow">Existencia total</span>
                    <strong>{formatNumber(kardex.existencia_total)}</strong>
                    <p>{kardex.material.unidad}</p>
                  </article>
                  <article className="mini-card">
                    <span className="eyebrow">Stock minimo</span>
                    <strong>{formatNumber(kardex.material.stock_minimo)}</strong>
                    <p>{kardex.material.unidad}</p>
                  </article>
                </div>

                {kardex.stock_por_almacen.length === 0 ? (
                  <EmptyState
                    note="Este material aun no tiene existencias registradas."
                    title="Sin stock por almacen."
                  />
                ) : (
                  <div className="table-wrap">
                    <table className="inventory-table">
                      <thead>
                        <tr>
                          <th>Almacen</th>
                          <th>Codigo</th>
                          <th>Cantidad</th>
                        </tr>
                      </thead>
                      <tbody>
                        {kardex.stock_por_almacen.map((item) => (
                          <tr key={item.almacen_id}>
                            <td>{item.almacen_nombre}</td>
                            <td>{item.almacen_codigo}</td>
                            <td>{formatNumber(item.cantidad)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {kardex.movements.length === 0 ? (
                  <EmptyState
                    note="Aun no hay movimientos para este material."
                    title="Sin historial."
                  />
                ) : (
                  <div className="table-wrap">
                    <table className="inventory-table">
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Tipo</th>
                          <th>Almacen</th>
                          <th>Cantidad</th>
                          <th>Anterior</th>
                          <th>Nueva</th>
                        </tr>
                      </thead>
                      <tbody>
                        {kardex.movements.map((movement) => (
                          <tr key={movement.id}>
                            <td>{formatDateTime(movement.created_at)}</td>
                            <td>{movement.tipo}</td>
                            <td>{movement.almacen_nombre}</td>
                            <td>{formatNumber(movement.cantidad)}</td>
                            <td>{formatNumber(movement.cantidad_anterior)}</td>
                            <td>{formatNumber(movement.cantidad_nueva)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
