import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { createMaterial, getMaterials, getSuppliers, updateMaterial } from "../../api/client";
import {
  ActionButton,
  DEFAULT_PAGE_SIZE,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  MaterialImage,
  ModalShell,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  StockBadge,
  buttonClassName,
  formatMoney,
  formatNumber,
  formatPlanLabel,
  normalizeDecimalInput,
  parseBooleanFilter,
  safeDisplayText,
} from "./shared";


const baseFilters = {
  q: "",
  categoria: "",
  proveedor_principal_id: "",
  activo: "",
  stock_bajo: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultForm = {
  id: "",
  sku: "",
  nombre: "",
  descripcion: "",
  categoria: "",
  subcategoria: "",
  unidad: "pieza",
  costo_unitario: "0",
  costo_promedio_actual: "",
  precio_venta: "0",
  stock_minimo: "0",
  stock_maximo: "0",
  ubicacion_texto: "",
  proveedor_principal_id: "",
  lead_time_dias: "0",
  codigo_barras: "",
  imagen_url: "",
  imagenes_extra_text: "",
  activo: true,
};

const MATERIALS_LOAD_ERROR = "No se pudieron cargar los materiales. Intenta actualizar.";


function parseExtraImages(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}


function downloadCsv(filename, rows) {
  const content = rows
    .map((row) =>
      row
        .map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`)
        .join(","),
    )
    .join("\n");

  const blob = new Blob([`\uFEFF${content}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}


export default function MaterialsPage() {
  const { token, empresaId, empresa } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const urlQuery = searchParams.get("q") ?? "";
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [notice, setNotice] = useState("");
  const [materials, setMaterials] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(() => ({ ...baseFilters, q: urlQuery }));
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(defaultForm);

  const planLabel = formatPlanLabel(empresa?.plan_code);
  const allSelected = materials.length > 0 && selectedIds.length === materials.length;
  const selectedCount = selectedIds.length;

  const skuMeta = useMemo(() => `SKUs registrados: ${meta.total}`, [meta.total]);

  async function loadSuppliersOptions() {
    const response = await getSuppliers({
      token,
      empresaId,
      filters: { activo: true, limit: 100, offset: 0 },
    });
    setSuppliers(response.items);
  }

  async function loadMaterialsPage(nextFilters = filters) {
    const response = await getMaterials({
      token,
      empresaId,
      filters: {
        ...nextFilters,
        activo: parseBooleanFilter(nextFilters.activo),
        stock_bajo: parseBooleanFilter(nextFilters.stock_bajo),
      },
    });

    setMaterials(response.items);
    setMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
    });
    setSelectedIds([]);
  }

  async function applyFilters(nextFilters) {
    setFilters(nextFilters);
    if (nextFilters.q) {
      setSearchParams({ q: nextFilters.q });
    } else {
      setSearchParams({});
    }
    await loadMaterialsPage(nextFilters);
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        await Promise.all([loadSuppliersOptions(), loadMaterialsPage({ ...baseFilters, q: urlQuery })]);
      } catch {
        setError(MATERIALS_LOAD_ERROR);
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  useEffect(() => {
    if (!urlQuery || urlQuery === filters.q) {
      return;
    }

    const nextFilters = { ...filters, q: urlQuery, offset: 0 };
    setFilters(nextFilters);
    loadMaterialsPage(nextFilters).catch(() => {
      setError(MATERIALS_LOAD_ERROR);
    });
  }, [urlQuery]);

  function resetForm() {
    setForm(defaultForm);
  }

  function openCreateModal() {
    resetForm();
    setError("");
    setSuccess("");
    setNotice("");
    setModalOpen(true);
  }

  function openEditModal(material) {
    setForm({
      id: material.id,
      sku: material.sku,
      nombre: material.nombre,
      descripcion: material.descripcion || "",
      categoria: material.categoria || "",
      subcategoria: material.subcategoria || "",
      unidad: material.unidad,
      costo_unitario: String(material.costo_unitario ?? 0),
      costo_promedio_actual: material.costo_promedio_actual != null ? String(material.costo_promedio_actual) : "",
      precio_venta: String(material.precio_venta ?? 0),
      stock_minimo: String(material.stock_minimo ?? 0),
      stock_maximo: String(material.stock_maximo ?? 0),
      ubicacion_texto: material.ubicacion_texto || "",
      proveedor_principal_id: material.proveedor_principal_id || "",
      lead_time_dias: String(material.lead_time_dias ?? 0),
      codigo_barras: material.codigo_barras || "",
      imagen_url: material.imagen_url || "",
      imagenes_extra_text: (material.imagenes_extra || []).join("\n"),
      activo: material.activo,
    });
    setError("");
    setSuccess("");
    setNotice("");
    setModalOpen(true);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const payload = {
        sku: form.sku,
        nombre: form.nombre,
        descripcion: form.descripcion || null,
        categoria: form.categoria,
        subcategoria: form.subcategoria || null,
        unidad: form.unidad,
        costo_unitario: form.costo_unitario,
        costo_promedio_actual: form.costo_promedio_actual || null,
        precio_venta: form.precio_venta,
        stock_minimo: form.stock_minimo,
        stock_maximo: form.stock_maximo,
        ubicacion_texto: form.ubicacion_texto || null,
        proveedor_principal_id: form.proveedor_principal_id || null,
        lead_time_dias: Number(form.lead_time_dias || 0),
        codigo_barras: form.codigo_barras || null,
        imagen_url: form.imagen_url || null,
        imagenes_extra: parseExtraImages(form.imagenes_extra_text),
        activo: form.activo,
      };

      if (form.id) {
        await updateMaterial({ materialId: form.id, token, empresaId, payload });
        setSuccess("Material actualizado correctamente.");
      } else {
        await createMaterial({ token, empresaId, payload });
        setSuccess("Material creado correctamente. El stock inicial se registra desde Movimientos.");
      }

      setModalOpen(false);
      resetForm();
      await loadMaterialsPage(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el material.");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleMaterialStatus(material) {
    setError("");
    setSuccess("");
    try {
      await updateMaterial({
        materialId: material.id,
        token,
        empresaId,
        payload: { activo: !material.activo },
      });
      setSuccess(material.activo ? "Material desactivado." : "Material activado.");
      await loadMaterialsPage(filters);
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el estado del material.");
    }
  }

  function exportCurrentView() {
    if (materials.length === 0) {
      setError("No hay materiales para exportar.");
      return;
    }

    downloadCsv(
      "inventario_materiales.csv",
      [
        [
          "SKU",
          "Nombre",
          "Categoría",
          "Subcategoría",
          "Código de barras",
          "Unidad",
          "Stock actual",
          "Stock mínimo",
          "Stock máximo",
          "Costo promedio",
          "Valor inventario",
          "Proveedor principal",
          "Estado",
        ],
        ...materials.map((material) => [
          material.sku,
          material.nombre,
          material.categoria || "",
          material.subcategoria || "",
          material.codigo_barras || "",
          material.unidad,
          material.stock_total,
          material.stock_minimo,
          material.stock_maximo,
          material.costo_promedio_actual ?? material.costo_unitario,
          material.valor_inventario,
          material.proveedor_principal_nombre || "",
          material.activo ? "Activo" : "Inactivo",
        ]),
      ],
    );
    setSuccess("Exportación CSV generada con la vista actual.");
  }

  function handleScanPlaceholder(field) {
    setNotice(
      field === "sku"
        ? "Escaneo con cámara pendiente. Puedes pegar o escribir el SKU manualmente."
        : "Escaneo con cámara pendiente. Puedes pegar o escribir el código manualmente.",
    );
  }

  if (loading) {
    return <div className="screen-center">Cargando materiales...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        actions={
          <>
            <ActionButton
              onClick={() => setNotice("Importación backend Excel/CSV pendiente.")}
              size="sm"
              type="button"
            >
              Importar Excel/CSV
            </ActionButton>
            <ActionButton onClick={exportCurrentView} size="sm" type="button">
              Exportar CSV
            </ActionButton>
            <ActionButton onClick={openCreateModal} size="sm" tone="primary" type="button">
              Agregar Material
            </ActionButton>
          </>
        }
        eyebrow="Inventario"
        meta={
          <>
            <StatusBadge tone="info">{planLabel}</StatusBadge>
            <span className="table-note">{skuMeta}</span>
            {selectedCount > 0 ? <span className="table-note">{selectedCount} seleccionados</span> : null}
          </>
        }
        subtitle="Gestión y control de stock"
        title="Inventario de Materiales"
      />

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}
      {notice ? <p className="feature-note">{notice}</p> : null}

      <FilterCard>
        <div className="inventory-filter-toolbar">
          <SearchInput
            action={
              <div className="inventory-actions">
                <ActionButton onClick={() => handleScanPlaceholder("barcode")} size="sm" type="button">
                  Escanear
                </ActionButton>
                <ActionButton
                  onClick={async () => {
                    const nextFilters = { ...filters, offset: 0 };
                    try {
                      await applyFilters(nextFilters);
                    } catch {
                      setError(MATERIALS_LOAD_ERROR);
                    }
                  }}
                  size="sm"
                  tone="primary"
                  type="button"
                >
                  Buscar
                </ActionButton>
              </div>
            }
            hint="Admite lectura manual o lector USB de código de barras."
            label="Buscar material"
            onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
            onKeyDown={async (event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                const nextFilters = { ...filters, offset: 0 };
                try {
                  await applyFilters(nextFilters);
                } catch {
                  setError(MATERIALS_LOAD_ERROR);
                }
              }
            }}
            placeholder="Filtrar por nombre, SKU, categoría o código de barras..."
            value={filters.q}
          />

          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton
              active={filters.stock_bajo === "true"}
              onClick={() =>
                setFilters((current) => ({
                  ...current,
                  stock_bajo: current.stock_bajo === "true" ? "" : "true",
                }))
              }
              size="sm"
              type="button"
            >
              Mostrar Bajo Stock
            </ActionButton>
            <ActionButton onClick={() => setShowAdvancedFilters((current) => !current)} size="sm" type="button">
              {showAdvancedFilters ? "Ocultar filtros" : "Filtros avanzados"}
            </ActionButton>
            <ActionButton
              onClick={async () => {
                try {
                  await loadMaterialsPage(filters);
                } catch {
                  setError(MATERIALS_LOAD_ERROR);
                }
              }}
              size="sm"
              type="button"
            >
              Actualizar
            </ActionButton>
          </div>
        </div>

        {showAdvancedFilters ? (
          <FormGrid className="inventory-filter-grid-wide">
            <Field label="Categoría">
              <input
                onChange={(event) => setFilters((current) => ({ ...current, categoria: event.target.value }))}
                placeholder="Filtrar por categoría"
                type="text"
                value={filters.categoria}
              />
            </Field>

            <Field label="Proveedor">
              <select
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    proveedor_principal_id: event.target.value,
                  }))
                }
                value={filters.proveedor_principal_id}
              >
                <option value="">Todos</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.nombre}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Estado">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, activo: event.target.value }))}
                value={filters.activo}
              >
                <option value="">Todos</option>
                <option value="true">Activos</option>
                <option value="false">Inactivos</option>
              </select>
            </Field>

            <Field label="Stock bajo">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, stock_bajo: event.target.value }))}
                value={filters.stock_bajo}
              >
                <option value="">Todos</option>
                <option value="true">Solo bajo stock</option>
                <option value="false">Excluir bajo stock</option>
              </select>
            </Field>
          </FormGrid>
        ) : null}

        {showAdvancedFilters ? (
          <div className="inventory-actions">
            <ActionButton
              onClick={async () => {
                const nextFilters = { ...filters, offset: 0 };
                try {
                  await applyFilters(nextFilters);
                } catch {
                  setError(MATERIALS_LOAD_ERROR);
                }
              }}
              size="sm"
              tone="primary"
              type="button"
            >
              Aplicar filtros
            </ActionButton>
            <ActionButton
              onClick={async () => {
                const nextFilters = { ...baseFilters };
                setNotice("");
                try {
                  await applyFilters(nextFilters);
                } catch {
                  setError(MATERIALS_LOAD_ERROR);
                }
              }}
              size="sm"
              type="button"
            >
              Limpiar
            </ActionButton>
          </div>
        ) : null}
      </FilterCard>

      <DataCard
        actions={<ResultMeta label="materiales" loaded={materials.length} total={meta.total} />}
        subtitle="Catálogo conectado al stock real calculado desde existencias"
        title="Materiales registrados"
      >
        {materials.length === 0 ? (
          <EmptyState
            note="Agrega el primer material para comenzar a operar compras, inventario y POS."
            title="No hay materiales"
          />
        ) : (
          <>
            <DataTable
              columns={[
                { key: "selected", label: "" },
                { key: "imagen", label: "Imagen" },
                { key: "sku", label: "SKU" },
                { key: "nombre", label: "Nombre" },
                { key: "categoria", label: "Categoría" },
                { key: "stock", label: "Stock actual" },
                { key: "minimo", label: "Stock mínimo" },
                { key: "unidad", label: "Unidad" },
                { key: "costo", label: "Costo promedio" },
                { key: "valor", label: "Valor inventario" },
                { key: "estado", label: "Estado" },
                { key: "acciones", label: "Acciones" },
              ]}
            >
              <tbody>
                {materials.map((material) => {
                  const selected = selectedIds.includes(material.id);
                  return (
                    <tr key={material.id}>
                      <td>
                        <input
                          checked={selected}
                          onChange={() =>
                            setSelectedIds((current) =>
                              current.includes(material.id)
                                ? current.filter((item) => item !== material.id)
                                : [...current, material.id],
                            )
                          }
                          type="checkbox"
                        />
                      </td>
                      <td>
                        <MaterialImage alt={material.nombre} size="sm" src={material.imagen_url} />
                      </td>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(material.sku)}</div>
                        <div className="inventory-cell-sub">{material.codigo_barras || "Sin código"}</div>
                      </td>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(material.nombre)}</div>
                        <div className="inventory-cell-sub">{material.subcategoria || material.descripcion || "Sin descripción"}</div>
                      </td>
                      <td>
                        <div className="inventory-cell-main">{safeDisplayText(material.categoria)}</div>
                        <div className="inventory-cell-sub">
                          {safeDisplayText(material.proveedor_principal_nombre, "Sin proveedor")}
                        </div>
                      </td>
                      <td>{formatNumber(material.stock_total)}</td>
                      <td>{formatNumber(material.stock_minimo)}</td>
                      <td>{safeDisplayText(material.unidad)}</td>
                      <td>{formatMoney(material.costo_promedio_actual ?? material.costo_unitario)}</td>
                      <td>{formatMoney(material.valor_inventario)}</td>
                      <td>
                        <div className="inventory-badge-stack">
                          <StockBadge minimo={material.stock_minimo} stock={material.stock_total} />
                          <StatusBadge tone={material.activo ? "success" : "neutral"}>
                            {material.activo ? "Activo" : "Inactivo"}
                          </StatusBadge>
                        </div>
                      </td>
                      <td className="inventory-row-actions">
                        <button className="link-button" onClick={() => openEditModal(material)} type="button">
                          Editar
                        </button>
                        <button className="link-button" onClick={() => toggleMaterialStatus(material)} type="button">
                          {material.activo ? "Desactivar" : "Activar"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </DataTable>

            <div className="inventory-list-footer">
              <label className="inventory-inline-checkbox">
                <input
                  checked={allSelected}
                  onChange={() => setSelectedIds(allSelected ? [] : materials.map((material) => material.id))}
                  type="checkbox"
                />
                Seleccionar todo en esta página
              </label>
              <PaginationControls
                meta={meta}
                onNext={async () => {
                  const nextFilters = { ...filters, offset: meta.offset + meta.limit };
                  setFilters(nextFilters);
                  try {
                    await loadMaterialsPage(nextFilters);
                  } catch {
                    setError(MATERIALS_LOAD_ERROR);
                  }
                }}
                onPrevious={async () => {
                  const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                  setFilters(nextFilters);
                  try {
                    await loadMaterialsPage(nextFilters);
                  } catch {
                    setError(MATERIALS_LOAD_ERROR);
                  }
                }}
              />
            </div>
          </>
        )}
      </DataCard>

      <ModalShell
        onClose={() => setModalOpen(false)}
        open={modalOpen}
        size="xl"
        subtitle="El stock inicial y los ajustes se registran desde Movimientos."
        title={form.id ? "Editar Material" : "Nuevo Material"}
      >
        <form className="inventory-modal-form" onSubmit={handleSubmit}>
          <div className="inventory-form-note">
            No se modifica stock directo desde Materiales. Usa Movimientos para entradas, salidas y ajustes.
          </div>

          <section className="inventory-form-section">
            <SectionTitle subtitle="SKU, nombre y código de barras" title="Identificación" />
            <FormGrid>
              <Field label="SKU" required>
                <div className="inventory-inline-field">
                  <input
                    onChange={(event) => setForm((current) => ({ ...current, sku: event.target.value }))}
                    required
                    type="text"
                    value={form.sku}
                  />
                  <ActionButton onClick={() => handleScanPlaceholder("sku")} size="sm" type="button">
                    Escanear
                  </ActionButton>
                </div>
              </Field>

              <Field label="Código de barras / QR">
                <div className="inventory-inline-field">
                  <input
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        codigo_barras: event.target.value,
                      }))
                    }
                    type="text"
                    value={form.codigo_barras}
                  />
                  <ActionButton onClick={() => handleScanPlaceholder("barcode")} size="sm" type="button">
                    Escanear
                  </ActionButton>
                </div>
              </Field>

              <Field label="Nombre">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))}
                  required
                  type="text"
                  value={form.nombre}
                />
              </Field>

              <Field hint="Opcional" label="Descripción">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, descripcion: event.target.value }))}
                  type="text"
                  value={form.descripcion}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Categoría, subcategoría y unidad" title="Clasificación" />
            <FormGrid>
              <Field label="Categoría">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, categoria: event.target.value }))}
                  required
                  type="text"
                  value={form.categoria}
                />
              </Field>

              <Field hint="Opcional" label="Subcategoría">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, subcategoria: event.target.value }))}
                  type="text"
                  value={form.subcategoria}
                />
              </Field>

              <Field label="Unidad">
                <input
                  onChange={(event) => setForm((current) => ({ ...current, unidad: event.target.value }))}
                  required
                  type="text"
                  value={form.unidad}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Mínimos, máximos y costos visibles" title="Stock y costos" />
            <FormGrid>
              <Field label="Stock mínimo">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      stock_minimo: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  required
                  step="0.0001"
                  type="number"
                  value={form.stock_minimo}
                />
              </Field>

              <Field label="Stock máximo">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      stock_maximo: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  step="0.0001"
                  type="number"
                  value={form.stock_maximo}
                />
              </Field>

              <Field label="Costo unitario">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      costo_unitario: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  required
                  step="0.0001"
                  type="number"
                  value={form.costo_unitario}
                />
              </Field>

              <Field hint="Opcional" label="Costo promedio actual">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      costo_promedio_actual: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  step="0.0001"
                  type="number"
                  value={form.costo_promedio_actual}
                />
              </Field>

              <Field label="Precio de venta">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      precio_venta: normalizeDecimalInput(event.target.value),
                    }))
                  }
                  required
                  step="0.0001"
                  type="number"
                  value={form.precio_venta}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Ubicación física y abastecimiento" title="Ubicación y proveedor" />
            <FormGrid>
              <Field hint="Opcional" label="Ubicación física">
                <input
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      ubicacion_texto: event.target.value,
                    }))
                  }
                  type="text"
                  value={form.ubicacion_texto}
                />
              </Field>

              <Field hint="Opcional" label="Proveedor principal">
                <select
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      proveedor_principal_id: event.target.value,
                    }))
                  }
                  value={form.proveedor_principal_id}
                >
                  <option value="">Sin proveedor</option>
                  {suppliers.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>
                      {supplier.nombre}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Lead time (días)">
                <input
                  min="0"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      lead_time_dias: event.target.value.replace(/[^\d]/g, ""),
                    }))
                  }
                  type="number"
                  value={form.lead_time_dias}
                />
              </Field>
            </FormGrid>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Solo URLs en esta fase, sin binarios en SQL" title="Imágenes" />
            <div className="inventory-image-preview-panel">
              <div className="inventory-image-preview">
                <MaterialImage alt={form.nombre || "Preview de material"} size="lg" src={form.imagen_url} />
              </div>

              <div className="inventory-image-fields">
                <FormGrid columns={1}>
                  <Field hint="Opcional" label="Imagen principal URL">
                    <input
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          imagen_url: event.target.value,
                        }))
                      }
                      placeholder="https://..."
                      type="url"
                      value={form.imagen_url}
                    />
                  </Field>

                  <Field hint="Una URL por línea" label="Imágenes adicionales">
                    <textarea
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          imagenes_extra_text: event.target.value,
                        }))
                      }
                      rows={4}
                      value={form.imagenes_extra_text}
                    />
                  </Field>
                </FormGrid>
              </div>
            </div>
          </section>

          <section className="inventory-form-section">
            <SectionTitle subtitle="Visibilidad del material en la operación diaria" title="Estado" />
            <FormGrid columns={1}>
              <Field span={2}>
                <label className="inventory-inline-checkbox">
                  <input
                    checked={form.activo}
                    onChange={(event) => setForm((current) => ({ ...current, activo: event.target.checked }))}
                    type="checkbox"
                  />
                  Material activo
                </label>
              </Field>
            </FormGrid>
          </section>

          <div className="inventory-actions inventory-actions-end">
            <ActionButton disabled={submitting} tone="primary" type="submit">
              {submitting ? "Guardando..." : form.id ? "Guardar cambios" : "Crear material"}
            </ActionButton>
            <ActionButton
              onClick={() => {
                resetForm();
                setModalOpen(false);
              }}
              type="button"
            >
              Cancelar
            </ActionButton>
          </div>
        </form>
      </ModalShell>
    </div>
  );
}
