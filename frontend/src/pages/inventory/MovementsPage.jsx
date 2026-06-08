import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../../auth/AuthContext";
import BarcodeScannerModal from "../../components/BarcodeScannerModal";
import {
  createInventoryMovementBulk,
  getInventoryMovements,
  getMaterials,
  getWarehouses,
  inventoryLookupMaterial,
  listPmProjects,
} from "../../api/client";
import {
  ActionButton,
  DEFAULT_PAGE_SIZE,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FilterCard,
  FormGrid,
  ModalShell,
  PageHeader,
  PaginationControls,
  ResultMeta,
  SearchInput,
  SectionTitle,
  StatusBadge,
  formatDateTime,
  formatMoney,
  formatNumber,
  handleScannerEnter,
  normalizeDecimalInput,
  safeDisplayText,
} from "./shared";


const movementTypes = [
  { value: "entrada", label: "Entrada" },
  { value: "salida", label: "Salida" },
  { value: "ajuste", label: "Ajuste" },
];

const movementMetaMap = {
  entrada: {
    helper: "Aumenta stock",
    tone: "success",
  },
  salida: {
    helper: "Descuenta stock",
    tone: "danger",
  },
  ajuste: {
    helper: "Requiere justificación",
    tone: "warning",
  },
};

const defaultFilters = {
  q: "",
  almacen_id: "",
  material_id: "",
  tipo: "",
  fecha_desde: "",
  fecha_hasta: "",
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};

const defaultModalState = {
  open: false,
  tipo: "entrada",
};

const defaultDraft = {
  almacen_id: "",
  motivo: "",
  entregado_por: "",
  recibido_por: "",
  documento_referencia: "",
  evidencia_url: "",
  referencia_id: "",
  notas: "",
  es_proyecto: false,
  proyecto_id: "",
  proyecto_nombre_snapshot: "",
  material_search: "",
  material_candidate_id: "",
  items: [],
};


function buildDefaultLine(tipo, materialId = "") {
  return {
    local_id: `${tipo}-${crypto.randomUUID()}`,
    material_id: materialId,
    cantidad: "",
    cantidad_nueva: "",
    costo_unitario: "",
    notas: "",
  };
}


function movementTone(tipo) {
  return movementMetaMap[tipo]?.tone ?? "neutral";
}


export default function MovementsPage() {
  const { token, empresaId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [notice, setNotice] = useState("");
  const [warehouses, setWarehouses] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [movements, setMovements] = useState([]);
  const [meta, setMeta] = useState({ total: 0, limit: DEFAULT_PAGE_SIZE, offset: 0 });
  const [filters, setFilters] = useState(defaultFilters);
  const [modalState, setModalState] = useState(defaultModalState);
  const [draft, setDraft] = useState(defaultDraft);
  const [projects, setProjects] = useState([]);
  const [projectLookupAvailable, setProjectLookupAvailable] = useState(false);
  const [detailMovement, setDetailMovement] = useState(null);
  const [scannerOpen, setScannerOpen] = useState(false);

  const filteredMaterials = useMemo(() => {
    const q = draft.material_search.trim().toLowerCase();
    if (!q) {
      return materials.slice(0, 60);
    }

    return materials.filter((material) =>
      [material.sku, material.nombre, material.codigo_barras]
        .filter(Boolean)
        .some((value) => safeDisplayText(value, "").toLowerCase().includes(q)),
    );
  }, [draft.material_search, materials]);

  const selectedWarehouse = warehouses.find((warehouse) => warehouse.id === draft.almacen_id);
  const currentMovementMeta = movementMetaMap[modalState.tipo] ?? movementMetaMap.entrada;

  function upsertMaterialOption(material) {
    setMaterials((current) => {
      if (current.some((item) => item.id === material.id)) {
        return current;
      }
      return [...current, material].sort((left, right) =>
        `${left.nombre} ${left.sku}`.localeCompare(`${right.nombre} ${right.sku}`, "es"),
      );
    });
  }

  function addResolvedMaterialToDraft(material) {
    upsertMaterialOption(material);
    let nextNotice = `Código detectado: ${material.codigo_barras || material.sku}`;

    setDraft((current) => {
      const existingIndex = current.items.findIndex((item) => item.material_id === material.id);
      if (existingIndex >= 0) {
        if (modalState.tipo === "ajuste") {
          nextNotice = "Ese material ya existe en el carrito del ajuste.";
          return current;
        }

        const nextItems = current.items.map((item, index) => {
          if (index !== existingIndex) {
            return item;
          }

          const nextQuantity = Number(item.cantidad || 0) + 1;
          return {
            ...item,
            cantidad: String(nextQuantity),
          };
        });
        return {
          ...current,
          material_candidate_id: "",
          material_search: "",
          items: nextItems,
        };
      }

      const nextLine = buildDefaultLine(modalState.tipo, material.id);
      if (modalState.tipo === "entrada" || modalState.tipo === "salida") {
        nextLine.cantidad = "1";
      }

      return {
        ...current,
        material_candidate_id: "",
        material_search: "",
        items: [...current.items, nextLine],
      };
    });

    setNotice(nextNotice);
  }

  async function lookupMaterialForMovement(code) {
    const normalized = String(code || "").trim();
    if (!normalized) {
      setError("Escribe o escanea un código antes de agregar el material.");
      return;
    }

    setError("");
    try {
      const response = await inventoryLookupMaterial({ code: normalized, token, empresaId });
      addResolvedMaterialToDraft(response.material);
    } catch (requestError) {
      setError(requestError.message || "No se encontró material con ese código.");
    }
  }

  async function loadOptions() {
    const [warehouseResponse, materialResponse] = await Promise.all([
      getWarehouses({ token, empresaId, filters: { activo: true, limit: 200, offset: 0 } }),
      getMaterials({ token, empresaId, filters: { activo: true, limit: 500, offset: 0 } }),
    ]);
    setWarehouses(warehouseResponse.items);
    setMaterials(materialResponse.items);
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
    return {
      warehouseItems: warehouseResponse.items,
      materialItems: materialResponse.items,
    };
  }

  async function loadMovementsPage(nextFilters = filters) {
    const response = await getInventoryMovements({ token, empresaId, filters: nextFilters });
    setMovements(response.items);
    setMeta({
      total: response.total,
      limit: response.limit,
      offset: response.offset,
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
        setDraft((current) => ({
          ...current,
          almacen_id: current.almacen_id || options.warehouseItems[0]?.id || "",
        }));
        await loadMovementsPage(defaultFilters);
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los movimientos.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId]);

  function openMovementModal(tipo) {
    setModalState({ open: true, tipo });
    setDraft((current) => ({
      ...defaultDraft,
      almacen_id: current.almacen_id || warehouses[0]?.id || "",
      items: [],
    }));
    setError("");
    setSuccess("");
    setNotice("");
  }

  function closeMovementModal() {
    setModalState(defaultModalState);
    setDraft(defaultDraft);
  }

  function addDraftLine(materialId = draft.material_candidate_id) {
    if (!materialId) {
      setError("Selecciona un material para agregarlo.");
      return;
    }

    setDraft((current) => ({
      ...current,
      material_candidate_id: "",
      material_search: "",
      items: [...current.items, buildDefaultLine(modalState.tipo, materialId)],
    }));
  }

  function updateDraftLine(localId, key, value) {
    setDraft((current) => ({
      ...current,
      items: current.items.map((item) => (item.local_id === localId ? { ...item, [key]: value } : item)),
    }));
  }

  function removeDraftLine(localId) {
    setDraft((current) => ({
      ...current,
      items: current.items.filter((item) => item.local_id !== localId),
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      if (draft.items.length === 0) {
        throw new Error("Debes agregar al menos un material.");
      }

      if (modalState.tipo === "ajuste" && !draft.notas.trim()) {
        throw new Error("La justificación detallada es obligatoria para ajustes.");
      }

      const payload = {
        almacen_id: draft.almacen_id,
        tipo: modalState.tipo,
        referencia_tipo: "manual_bulk",
        referencia_id: draft.referencia_id || null,
        motivo: draft.motivo || null,
        entregado_por: draft.entregado_por || null,
        recibido_por: draft.recibido_por || null,
        documento_referencia: draft.documento_referencia || null,
        evidencia_url: draft.evidencia_url || null,
        es_proyecto: modalState.tipo === "salida" ? draft.es_proyecto : false,
        proyecto_id: modalState.tipo === "salida" && draft.es_proyecto ? draft.proyecto_id || null : null,
        proyecto_nombre_snapshot:
          modalState.tipo === "salida" && draft.es_proyecto ? draft.proyecto_nombre_snapshot || null : null,
        notas: draft.notas || null,
        items: draft.items.map((item) => ({
          material_id: item.material_id,
          cantidad: modalState.tipo === "ajuste" ? null : item.cantidad,
          cantidad_nueva: modalState.tipo === "ajuste" ? item.cantidad_nueva : null,
          costo_unitario:
            modalState.tipo === "entrada" || modalState.tipo === "ajuste" ? item.costo_unitario || null : null,
          notas: item.notas || null,
        })),
      };

      await createInventoryMovementBulk({ token, empresaId, payload });
      setSuccess("Movimiento multi-artículo registrado correctamente.");
      closeMovementModal();
      await loadMovementsPage(filters);
      await loadOptions();
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar el movimiento.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando movimientos...</div>;
  }

  return (
    <div className="dashboard-stack inventory-screen">
      <PageHeader
        actions={
          <>
            {movementTypes.map((item) => (
              <ActionButton
                key={item.value}
                onClick={() => openMovementModal(item.value)}
                size="sm"
                tone={item.value === "entrada" ? "primary" : "ghost"}
                type="button"
              >
                {item.label}
              </ActionButton>
            ))}
          </>
        }
        eyebrow="Inventario"
        subtitle="Entradas, salidas y ajustes de inventario"
        title="Movimientos"
      />

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}
      {notice ? <p className="feature-note">{notice}</p> : null}

      <FilterCard>
        <div className="inventory-filter-toolbar inventory-filter-toolbar-stack">
          <SearchInput
            hint="Busca por material, SKU, código de barras o motivo."
            label="Buscar movimientos"
            onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))}
            onKeyDown={(event) =>
              handleScannerEnter(event, async () => {
                const nextFilters = { ...filters, offset: 0 };
                setFilters(nextFilters);
                try {
                  await loadMovementsPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron aplicar los filtros.");
                }
              })
            }
            placeholder="Material, SKU, código de barras o motivo"
            value={filters.q}
          />

          <FormGrid className="inventory-filter-grid-wide">
            <Field label="Almacén">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, almacen_id: event.target.value }))}
                value={filters.almacen_id}
              >
                <option value="">Todos</option>
                {warehouses.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>
                    {safeDisplayText(warehouse.nombre)} ({safeDisplayText(warehouse.codigo)})
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Material">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, material_id: event.target.value }))}
                value={filters.material_id}
              >
                <option value="">Todos</option>
                {materials.map((material) => (
                  <option key={material.id} value={material.id}>
                    {safeDisplayText(material.sku)} - {safeDisplayText(material.nombre)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Tipo">
              <select
                onChange={(event) => setFilters((current) => ({ ...current, tipo: event.target.value }))}
                value={filters.tipo}
              >
                <option value="">Todos</option>
                {movementTypes.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Fecha desde">
              <input
                onChange={(event) => setFilters((current) => ({ ...current, fecha_desde: event.target.value }))}
                type="datetime-local"
                value={filters.fecha_desde}
              />
            </Field>

            <Field label="Fecha hasta">
              <input
                onChange={(event) => setFilters((current) => ({ ...current, fecha_hasta: event.target.value }))}
                type="datetime-local"
                value={filters.fecha_hasta}
              />
            </Field>
          </FormGrid>

          <div className="inventory-actions">
            <ActionButton
              onClick={async () => {
                const nextFilters = { ...filters, offset: 0 };
                setFilters(nextFilters);
                try {
                  await loadMovementsPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron aplicar los filtros.");
                }
              }}
              size="sm"
              tone="primary"
              type="button"
            >
              Filtrar
            </ActionButton>
            <ActionButton
              onClick={async () => {
                setFilters(defaultFilters);
                try {
                  await loadMovementsPage(defaultFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudieron reiniciar los filtros.");
                }
              }}
              size="sm"
              type="button"
            >
              Limpiar
            </ActionButton>
            <ActionButton
              onClick={async () => {
                try {
                  await loadMovementsPage(filters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo actualizar el listado.");
                }
              }}
              size="sm"
              type="button"
            >
              Actualizar
            </ActionButton>
          </div>
        </div>
      </FilterCard>

      <DataCard
        actions={<ResultMeta label="movimientos" loaded={movements.length} total={meta.total} />}
        subtitle="Registro auditable conectado al stock real"
        title="Movimientos recientes"
      >
        {movements.length === 0 ? (
          <EmptyState note="Cuando registres entradas, salidas o ajustes aparecerán aquí." title="No hay movimientos todavía" />
        ) : (
          <>
            <DataTable
              columns={[
                { key: "fecha", label: "Fecha" },
                { key: "tipo", label: "Tipo" },
                { key: "material", label: "Material" },
                { key: "cantidad", label: "Cantidad" },
                { key: "motivo", label: "Motivo" },
                { key: "entregado", label: "Entregado por" },
                { key: "recibido", label: "Recibido / Retirado" },
                { key: "evidencia", label: "Evidencia" },
                { key: "estatus", label: "Estatus" },
                { key: "proyecto", label: "Proyecto / contexto" },
                { key: "acciones", label: "Acciones" },
              ]}
            >
              <tbody>
                {movements.map((movement) => (
                  <tr key={movement.id}>
                    <td>{formatDateTime(movement.created_at)}</td>
                    <td>
                      <StatusBadge tone={movementTone(movement.tipo)}>{movement.tipo}</StatusBadge>
                    </td>
                    <td>
                      <div className="inventory-cell-main">
                        {safeDisplayText(
                          movement.material_nombre ||
                            movement.material?.nombre ||
                            movement.material?.sku ||
                            movement.material_id,
                        )}
                      </div>
                      <div className="inventory-cell-sub">
                        {safeDisplayText(
                          movement.material_sku || movement.material?.sku || movement.material_id,
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="inventory-cell-main">{formatNumber(movement.cantidad)}</div>
                      <div className="inventory-cell-sub">Balance {formatNumber(movement.cantidad_nueva)}</div>
                    </td>
                    <td>{safeDisplayText(movement.motivo || movement.notas, "Manual")}</td>
                    <td>{safeDisplayText(movement.entregado_por)}</td>
                    <td>{safeDisplayText(movement.recibido_por)}</td>
                    <td>
                      {movement.evidencia_url ? (
                        <a className="link-button" href={movement.evidencia_url} rel="noreferrer" target="_blank">
                          Ver evidencia
                        </a>
                      ) : (
                        <span className="table-note">Sin evidencia</span>
                      )}
                    </td>
                    <td>
                      <StatusBadge tone={movement.estatus === "confirmado" ? "success" : movement.estatus === "cancelado" ? "danger" : "neutral"}>
                        {movement.estatus}
                      </StatusBadge>
                    </td>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(movement.proyecto_nombre_snapshot || movement.proyecto_id, "—")}</div>
                      <div className="inventory-cell-sub">
                        {safeDisplayText(movement.pm_tarea_nombre_snapshot, "Proyecto general")} · {safeDisplayText(movement.pm_partida_nombre_snapshot, "Sin partida")}
                      </div>
                    </td>
                    <td className="inventory-row-actions">
                      <button className="link-button" onClick={() => setDetailMovement(movement)} type="button">
                        Ver
                      </button>
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
                  await loadMovementsPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
              onPrevious={async () => {
                const nextFilters = { ...filters, offset: Math.max(0, meta.offset - meta.limit) };
                setFilters(nextFilters);
                try {
                  await loadMovementsPage(nextFilters);
                } catch (requestError) {
                  setError(requestError.message || "No se pudo cambiar la página.");
                }
              }}
            />
          </>
        )}
      </DataCard>

      <ModalShell
        onClose={closeMovementModal}
        open={modalState.open}
        size="xl"
        subtitle="Los movimientos manuales se guardan confirmados. Borrador y cancelación formal quedan pendientes para una fase posterior."
        title="Nuevo Movimiento - Multi-Artículo"
      >
        {warehouses.length === 0 || materials.length === 0 ? (
          <EmptyState
            note="Necesitas al menos un almacén y un material activo antes de mover inventario."
            title="Faltan datos base"
          />
        ) : (
          <form className="inventory-modal-form" onSubmit={handleSubmit}>
            <div className={`inventory-form-note inventory-form-note-${currentMovementMeta.tone}`}>
              <strong>{movementTypes.find((item) => item.value === modalState.tipo)?.label}</strong>: {currentMovementMeta.helper}
            </div>

            <section className="inventory-form-section">
              <SectionTitle subtitle="Datos generales del movimiento" title="Encabezado" />
              <FormGrid>
                <Field label="Tipo de movimiento">
                  <select
                    onChange={(event) => setModalState((current) => ({ ...current, tipo: event.target.value }))}
                    value={modalState.tipo}
                  >
                    {movementTypes.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Almacén">
                  <select
                    onChange={(event) => setDraft((current) => ({ ...current, almacen_id: event.target.value }))}
                    required
                    value={draft.almacen_id}
                  >
                    {warehouses.map((warehouse) => (
                      <option key={warehouse.id} value={warehouse.id}>
                        {warehouse.nombre} ({warehouse.codigo})
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label="Motivo">
                  <input
                    onChange={(event) => setDraft((current) => ({ ...current, motivo: event.target.value }))}
                    placeholder="Recepción, consumo, ajuste, devolución..."
                    type="text"
                    value={draft.motivo}
                  />
                </Field>

                <Field hint={modalState.tipo === "ajuste" ? "Obligatoria para ajustes" : "Opcional"} label="Justificación / notas">
                  <textarea
                    onChange={(event) => setDraft((current) => ({ ...current, notas: event.target.value }))}
                    rows={3}
                    value={draft.notas}
                  />
                </Field>

                <Field label={modalState.tipo === "entrada" ? "Entregado por / proveedor" : "Entregado por"}>
                  <input
                    onChange={(event) => setDraft((current) => ({ ...current, entregado_por: event.target.value }))}
                    type="text"
                    value={draft.entregado_por}
                  />
                </Field>

                <Field label={modalState.tipo === "salida" ? "Recibido / persona que retira" : "Recibido por"}>
                  <input
                    onChange={(event) => setDraft((current) => ({ ...current, recibido_por: event.target.value }))}
                    type="text"
                    value={draft.recibido_por}
                  />
                </Field>

                <Field hint="Opcional" label="Documento / factura">
                  <input
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        documento_referencia: event.target.value,
                      }))
                    }
                    type="text"
                    value={draft.documento_referencia}
                  />
                </Field>

                <Field hint="Opcional" label="Referencia interna">
                  <input
                    onChange={(event) => setDraft((current) => ({ ...current, referencia_id: event.target.value }))}
                    type="text"
                    value={draft.referencia_id}
                  />
                </Field>

                <Field hint="Solo URL en esta fase" label="Evidencia fotográfica URL" span={2}>
                  <input
                    onChange={(event) => setDraft((current) => ({ ...current, evidencia_url: event.target.value }))}
                    placeholder="https://..."
                    type="url"
                    value={draft.evidencia_url}
                  />
                </Field>
              </FormGrid>
            </section>

            {modalState.tipo === "salida" ? (
              <section className="inventory-form-section">
                <SectionTitle subtitle="Preparación para la integración futura con PM" title="Proyecto" />
                <FormGrid>
                  <Field span={2}>
                    <label className="inventory-inline-checkbox">
                      <input
                        checked={draft.es_proyecto}
                        onChange={(event) =>
                          setDraft((current) => ({
                            ...current,
                            es_proyecto: event.target.checked,
                          }))
                        }
                        type="checkbox"
                      />
                      Vincular salida a proyecto
                    </label>
                  </Field>

                  {draft.es_proyecto ? (
                    <>
                      {projectLookupAvailable ? (
                        <>
                          <Field label="Proyecto">
                            <select
                              onChange={(event) => {
                                const project = projects.find((item) => item.id === event.target.value);
                                setDraft((current) => ({
                                  ...current,
                                  proyecto_id: event.target.value,
                                  proyecto_nombre_snapshot: project?.nombre ?? "",
                                }));
                              }}
                              value={draft.proyecto_id}
                            >
                              <option value="">Selecciona un proyecto</option>
                              {projects.map((project) => (
                                <option key={project.id} value={project.id}>
                                  {safeDisplayText(project.codigo, "PM")} · {safeDisplayText(project.nombre)}
                                </option>
                              ))}
                            </select>
                          </Field>

                          <Field label="Nombre del proyecto">
                            <input readOnly type="text" value={draft.proyecto_nombre_snapshot} />
                          </Field>
                        </>
                      ) : (
                        <>
                          <Field label="ID / referencia de proyecto">
                            <input
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  proyecto_id: event.target.value,
                                }))
                              }
                              type="text"
                              value={draft.proyecto_id}
                            />
                          </Field>

                          <Field label="Nombre del proyecto">
                            <input
                              onChange={(event) =>
                                setDraft((current) => ({
                                  ...current,
                                  proyecto_nombre_snapshot: event.target.value,
                                }))
                              }
                              type="text"
                              value={draft.proyecto_nombre_snapshot}
                            />
                          </Field>
                        </>
                      )}
                    </>
                  ) : null}
                </FormGrid>
                <p className="feature-note">
                  La integración completa con PM se conectará cuando el módulo PM esté activo.
                </p>
              </section>
            ) : null}

            <section className="inventory-form-section">
              <SectionTitle
                subtitle={
                  selectedWarehouse
                    ? `Los renglones se aplicarán en ${selectedWarehouse.nombre} (${selectedWarehouse.codigo}).`
                    : "Selecciona un almacén antes de registrar el movimiento."
                }
                title="Agregar Materiales"
              />

              <div className="inventory-material-picker">
                <SearchInput
                  action={
                    <div className="inventory-actions">
                      <ActionButton onClick={() => setScannerOpen(true)} size="sm" type="button">
                        Escanear SKU
                      </ActionButton>
                    </div>
                  }
                  hint="Escribe o escanea SKU / código de barras y presiona Enter para agregar."
                  label="Buscar material"
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      material_search: event.target.value,
                    }))
                  }
                  onKeyDown={(event) =>
                    handleScannerEnter(event, async (code) => {
                      if (!code && draft.material_candidate_id) {
                        addDraftLine();
                        return;
                      }
                      await lookupMaterialForMovement(code);
                    })
                  }
                  placeholder="Nombre, SKU o código de barras"
                  value={draft.material_search}
                />

                <FormGrid>
                  <Field label="Material">
                    <select
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          material_candidate_id: event.target.value,
                        }))
                      }
                      value={draft.material_candidate_id}
                    >
                      <option value="">Selecciona un material</option>
                      {filteredMaterials.map((material) => (
                        <option key={material.id} value={material.id}>
                          {safeDisplayText(material.sku)} - {safeDisplayText(material.nombre)}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Acción">
                    <ActionButton onClick={() => addDraftLine()} size="sm" tone="primary" type="button">
                      Agregar al carrito
                    </ActionButton>
                  </Field>
                </FormGrid>
              </div>

              {draft.items.length === 0 ? (
                <EmptyState compact note="Agrega al menos un material para continuar." title="Sin renglones" />
              ) : (
                <DataTable
                  columns={[
                    { key: "material", label: "Material" },
                    { key: "cantidad", label: modalState.tipo === "ajuste" ? "Cantidad nueva" : "Cantidad" },
                    ...(modalState.tipo === "entrada" || modalState.tipo === "ajuste"
                      ? [{ key: "costo", label: "Costo unitario" }]
                      : []),
                    { key: "notas", label: "Notas" },
                    { key: "accion", label: "Acción" },
                  ]}
                >
                  <tbody>
                    {draft.items.map((line) => {
                      const material = materials.find((item) => item.id === line.material_id);
                      return (
                        <tr key={line.local_id}>
                          <td>
                            <select
                              onChange={(event) => updateDraftLine(line.local_id, "material_id", event.target.value)}
                              required
                              value={line.material_id}
                            >
                              <option value="">Selecciona un material</option>
                              {materials.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {safeDisplayText(item.sku)} - {safeDisplayText(item.nombre)}
                                </option>
                              ))}
                            </select>
                            {material ? (
                              <div className="inventory-cell-sub">
                                {material.codigo_barras || "Sin código"} · Stock {formatNumber(material.stock_total)}
                              </div>
                            ) : null}
                          </td>
                          <td>
                            <input
                              min={modalState.tipo === "ajuste" ? "0" : "0.0001"}
                              onChange={(event) =>
                                updateDraftLine(
                                  line.local_id,
                                  modalState.tipo === "ajuste" ? "cantidad_nueva" : "cantidad",
                                  normalizeDecimalInput(event.target.value),
                                )
                              }
                              required
                              step="0.0001"
                              type="number"
                              value={modalState.tipo === "ajuste" ? line.cantidad_nueva : line.cantidad}
                            />
                          </td>
                          {modalState.tipo === "entrada" || modalState.tipo === "ajuste" ? (
                            <td>
                              <input
                                min="0"
                                onChange={(event) =>
                                  updateDraftLine(
                                    line.local_id,
                                    "costo_unitario",
                                    normalizeDecimalInput(event.target.value),
                                  )
                                }
                                step="0.0001"
                                type="number"
                                value={line.costo_unitario}
                              />
                            </td>
                          ) : null}
                          <td>
                            <input
                              onChange={(event) => updateDraftLine(line.local_id, "notas", event.target.value)}
                              type="text"
                              value={line.notas}
                            />
                          </td>
                          <td>
                            <button className="link-button" onClick={() => removeDraftLine(line.local_id)} type="button">
                              Quitar
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </DataTable>
              )}

              <div className="table-note">Total de líneas: {draft.items.length}</div>
            </section>

            <div className="inventory-actions inventory-actions-end">
              <ActionButton disabled={submitting} tone="primary" type="submit">
                {submitting ? "Registrando..." : `Confirmar ${modalState.tipo}`}
              </ActionButton>
              <ActionButton onClick={closeMovementModal} type="button">
                Cancelar
              </ActionButton>
            </div>
          </form>
        )}
      </ModalShell>

      <ModalShell
        onClose={() => setDetailMovement(null)}
        open={Boolean(detailMovement)}
        size="medium"
        subtitle="Detalle del movimiento aplicado"
        title="Movimiento"
      >
        {detailMovement ? (
          <div className="inventory-detail-stack">
            <div className="inventory-detail-grid">
              <div>
                <strong>Material</strong>
                <p>
                  {safeDisplayText(
                    detailMovement.material_sku || detailMovement.material?.sku || detailMovement.material_id,
                  )}{" "}
                  -{" "}
                  {safeDisplayText(
                    detailMovement.material_nombre ||
                      detailMovement.material?.nombre ||
                      detailMovement.material?.sku ||
                      detailMovement.material_id,
                  )}
                </p>
              </div>
              <div>
                <strong>Fecha</strong>
                <p>{formatDateTime(detailMovement.created_at)}</p>
              </div>
              <div>
                <strong>Tipo</strong>
                <p>{safeDisplayText(detailMovement.tipo)}</p>
              </div>
              <div>
                <strong>Estatus</strong>
                <p>{safeDisplayText(detailMovement.estatus)}</p>
              </div>
              <div>
                <strong>Cantidad</strong>
                <p>{formatNumber(detailMovement.cantidad)}</p>
              </div>
              <div>
                <strong>Balance</strong>
                <p>{formatNumber(detailMovement.cantidad_nueva)}</p>
              </div>
              <div>
                <strong>Costo snapshot</strong>
                <p>
                  {detailMovement.costo_unitario_snapshot != null
                    ? formatMoney(detailMovement.costo_unitario_snapshot)
                    : "—"}
                </p>
              </div>
              <div>
                <strong>Proyecto</strong>
                <p>{safeDisplayText(detailMovement.proyecto_nombre_snapshot || detailMovement.proyecto_id)}</p>
              </div>
              <div>
                <strong>Tarea</strong>
                <p>{safeDisplayText(detailMovement.pm_tarea_nombre_snapshot, "Proyecto general")}</p>
              </div>
              <div>
                <strong>Partida</strong>
                <p>{safeDisplayText(detailMovement.pm_partida_nombre_snapshot, "Sin partida")}</p>
              </div>
            </div>
            <div className="table-note">{safeDisplayText(detailMovement.notas, "Sin notas adicionales.")}</div>
          </div>
        ) : null}
      </ModalShell>

      <BarcodeScannerModal
        helperText="Apunta la cámara al código de barras o QR para agregar el material al carrito."
        onClose={() => setScannerOpen(false)}
        onDetected={(code) => {
          lookupMaterialForMovement(code).finally(() => setScannerOpen(false));
        }}
        open={scannerOpen}
        title="Escanear SKU o código"
      />
    </div>
  );
}
