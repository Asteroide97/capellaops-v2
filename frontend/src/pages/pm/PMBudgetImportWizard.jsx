import { Fragment, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, FileDown, FileSpreadsheet, ImagePlus, RotateCw, Upload, X } from "lucide-react";

import {
  addPmBudgetImportRow,
  cancelPmBudgetImport,
  confirmPmBudgetImport,
  createPmBudgetImport,
  downloadPmBudgetImportSource,
  getPmBudgetImport,
  deletePmEstimationEvidence,
  listPmBudgetImports,
  updatePmBudgetImportDetails,
  updatePmBudgetImportEvidence,
  updatePmBudgetImportMapping,
  updatePmBudgetImportRow,
  uploadPmBudgetImportEvidence,
} from "../../api/client";
import { ActionButton, ModalShell, StatusBadge, formatMoney, formatNumber } from "../inventory/shared";
import PMEvidencePreview from "./PMEvidencePreview";
import { formatPmCalendarDate, toPmDateInputValue } from "./dateOnly";

const MAPPING_FIELDS = [
  ["codigo", "Código"], ["capitulo", "Capítulo"], ["concepto", "Concepto"], ["unidad", "Unidad"],
  ["cantidad", "Cantidad"], ["precio_unitario", "Precio unitario"], ["importe", "Importe"],
  ["cantidad_contratada", "Cantidad contratada"], ["avance_anterior", "Avance anterior"],
  ["esta_estimacion", "Esta estimación"], ["acumulado", "Acumulado"], ["por_ejecutar", "Por ejecutar"],
];

const FIELD_TO_VALUE = {
  codigo: "code", capitulo: "chapter", concepto: "concept", unidad: "unit", cantidad: "quantity",
  precio_unitario: "unit_price", importe: "amount_excel", cantidad_contratada: "contracted_quantity",
  avance_anterior: "previous_progress", esta_estimacion: "this_estimate", acumulado: "accumulated", por_ejecutar: "remaining",
};

function excelColumnName(index) {
  let number = Number(index) + 1;
  let label = "";
  while (number > 0) {
    const remainder = (number - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    number = Math.floor((number - 1) / 26);
  }
  return label;
}

const ROW_ERROR_CODES = new Set([
  "missing_description", "invalid_quantity", "missing_unit", "invalid_unit_price",
  "duplicate_code", "duplicate_row", "accumulated_exceeds_contracted", "negative_remaining",
]);
const WARNING_LABELS = {
  missing_description: "Falta concepto",
  invalid_quantity: "Cantidad inválida",
  missing_unit: "Falta unidad",
  invalid_unit_price: "Precio unitario inválido",
  duplicate_code: "Código repetido",
  duplicate_row: "Partida repetida",
  accumulated_exceeds_contracted: "Esta partida supera la cantidad contratada",
  negative_remaining: "Saldo negativo",
  amount_mismatch: "El importe no coincide con cantidad por precio",
  estimate_exceeds_budget: "La estimación supera el importe contratado",
  formula_error: "El archivo contiene una fórmula inválida (#REF!). Capella no utiliza esa fórmula para calcular el presupuesto.",
  formula_without_cached_value: "La fórmula no tiene valor guardado en Excel",
  summary_row: "Ignorada como fila de resumen",
};

function cleanError(error, fallback) {
  const message = String(error?.message || "");
  if (!message || /not found|object object|sql|traceback|backend|payload/i.test(message)) return fallback;
  return message;
}

function displayStatus(row) {
  const warnings = row?.warnings ?? [];
  if (row?.row_type === "ignored" && warnings.includes("summary_row")) return { label: "Fila de resumen", tone: "success" };
  if (warnings.some((code) => ROW_ERROR_CODES.has(code))) return { label: "Corregir", tone: "danger" };
  if (warnings.length) return { label: "Revisar", tone: "warning" };
  return { label: "Detectado", tone: "success" };
}

export default function PMBudgetImportWizard({ empresaId, onClose, onContinuePlanning, onImported, open, projectId, token }) {
  const [sessions, setSessions] = useState([]);
  const [session, setSession] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warningsAcknowledged, setWarningsAcknowledged] = useState(false);
  const [draftRows, setDraftRows] = useState({});
  const [expandedRowId, setExpandedRowId] = useState(null);
  const [details, setDetails] = useState({});
  const [evidenceDraft, setEvidenceDraft] = useState({ source_row: "", descripcion: "", ubicacion: "", fecha_evidencia: "" });
  const [evidenceEdits, setEvidenceEdits] = useState({});

  async function reloadSessions() {
    setLoading(true);
    setError("");
    try {
      const result = await listPmBudgetImports({ projectId, token, empresaId });
      setSessions(Array.isArray(result) ? result : []);
    } catch (requestError) {
      setError(cleanError(requestError, "No se pudieron recuperar las revisiones guardadas."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open) {
      setSession(null);
      setDraftRows({});
      return undefined;
    }
    if (projectId) reloadSessions();
  // Load only the light session list; full rows are fetched when resumed.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, projectId, token, empresaId]);

  const rows = session?.rows ?? [];
  const sheets = session?.sheets ?? [];
  const headers = session?.headers ?? [];
  const summary = session?.summary ?? {};
  const selectedMapping = session?.mapping ?? {};
  const metadata = session?.metadata ?? {};
  const warningsCount = Number(summary.warnings_count ?? 0);
  const errorsCount = Number(summary.errors_count ?? 0);
  const canConfirm = session && ["review", "ready"].includes(session.status) && errorsCount === 0 && Number(summary.items_count ?? 0) > 0;
  const totalDetected = Number(summary.total_detected ?? 0);
  const totalCalculated = Number(summary.total_recalculated ?? 0);

  const mappingChoices = useMemo(() => headers.map((header, index) => ({ index, label: `${excelColumnName(index)} · ${String(header || `Columna ${index + 1}`)}` })), [headers]);

  async function applyMapping(nextSheet = session?.selected_sheet, nextMapping = selectedMapping) {
    if (!session?.id || !nextSheet) return;
    setSaving(true); setError(""); setSuccess("");
    try {
      const result = await updatePmBudgetImportMapping({ sessionId: session.id, token, empresaId, payload: { selected_sheet: nextSheet, mapping: nextMapping } });
      setSession(result);
      setDraftRows({});
      setWarningsAcknowledged(false);
    } catch (requestError) {
      setError(cleanError(requestError, "No se pudo actualizar la lectura de columnas."));
    } finally { setSaving(false); }
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!selectedFile) { setError("Selecciona un archivo .xlsx."); return; }
    setSaving(true); setError(""); setSuccess("");
    try {
      const created = await createPmBudgetImport({ projectId, file: selectedFile, token, empresaId });
      setSession(created);
      setSelectedFile(null);
      await reloadSessions();
    } catch (requestError) {
      setError(cleanError(requestError, "No se pudo analizar el archivo. Revisa que sea un XLSX válido."));
    } finally { setSaving(false); }
  }

  async function openSavedSession(sessionId) {
    setLoading(true); setError("");
    try {
      const result = await getPmBudgetImport({ projectId, sessionId, token, empresaId });
      setSession(result);
      setDraftRows({});
      setWarningsAcknowledged(false);
    } catch (requestError) {
      setError(cleanError(requestError, "No se pudo abrir la revisión guardada."));
    } finally { setLoading(false); }
  }

  function closeWizard() {
    setSession(null);
    setSelectedFile(null);
    setDraftRows({});
    onClose?.();
  }

  async function saveRow(row, overrides = {}) {
    const values = { ...(draftRows[row.id] ?? row.values), ...overrides };
    const includeWasExplicitlyChanged = Boolean(values._include_explicit || Object.hasOwn(overrides, "include"));
    const rowTypeWasExplicitlyChanged = Boolean(values._row_type_explicit || Object.hasOwn(overrides, "row_type"));
    delete values._include_explicit;
    delete values._row_type_explicit;
    setSaving(true); setError(""); setSuccess("");
    try {
      const updated = await updatePmBudgetImportRow({ sessionId: session.id, rowId: row.id, token, empresaId, payload: {
        ...values,
        ...(includeWasExplicitlyChanged ? { _include_explicit: true } : {}),
        ...(rowTypeWasExplicitlyChanged ? { _row_type_explicit: true } : {}),
      } });
      setSession(updated);
      setDraftRows((current) => { const next = { ...current }; delete next[row.id]; return next; });
      setSuccess("Renglón guardado en la revisión.");
    } catch (requestError) {
      setError(cleanError(requestError, "No se pudo guardar el renglón."));
    } finally { setSaving(false); }
  }

  async function addBlankRow(rowType = "item") {
    setSaving(true); setError("");
    try {
      const updated = await addPmBudgetImportRow({ sessionId: session.id, token, empresaId, payload: {
        row_type: rowType, include: true, code: "", chapter: "", concept: "", unit: "", quantity: "1", unit_price: "0", amount_excel: null,
      } });
      setSession(updated);
    } catch (requestError) { setError(cleanError(requestError, "No se pudo agregar el renglón.")); }
    finally { setSaving(false); }
  }

  async function saveDetails(event) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      const updated = await updatePmBudgetImportDetails({ sessionId: session.id, token, empresaId, payload: details });
      setSession(updated); setDetails({}); setSuccess("Datos generales guardados.");
    } catch (requestError) { setError(cleanError(requestError, "No se pudieron guardar los datos detectados.")); }
    finally { setSaving(false); }
  }

  async function uploadEvidence(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setSaving(true); setError("");
    try {
      const created = await uploadPmBudgetImportEvidence({
        projectId, sessionId: session.id, file, token, empresaId,
        sourceRow: evidenceDraft.source_row ? Number(evidenceDraft.source_row) : null,
        descripcion: evidenceDraft.descripcion,
        ubicacion: evidenceDraft.ubicacion,
        fechaEvidencia: toPmDateInputValue(evidenceDraft.fecha_evidencia),
      });
      setSession((current) => ({ ...current, evidences: [...(current?.evidences ?? []), created] }));
      setEvidenceDraft({ source_row: "", descripcion: "", ubicacion: "", fecha_evidencia: "" });
    } catch (requestError) { setError(cleanError(requestError, "No se pudo guardar la fotografía. Revisa el almacenamiento disponible.")); }
    finally { setSaving(false); }
  }

  async function removeEvidence(evidenceId) {
    setSaving(true); setError("");
    try {
      await deletePmEstimationEvidence({ evidenceId, token, empresaId });
      setSession((current) => ({ ...current, evidences: (current?.evidences ?? []).filter((item) => item.id !== evidenceId) }));
    } catch (requestError) { setError(cleanError(requestError, "No se pudo quitar la fotografía.")); }
    finally { setSaving(false); }
  }

  async function saveEvidence(evidence) {
    const draft = evidenceEdits[evidence.id] ?? evidence;
    setSaving(true); setError(""); setSuccess("");
    try {
      const updated = await updatePmBudgetImportEvidence({
        projectId, sessionId: session.id, evidenceId: evidence.id, token, empresaId,
        payload: { source_row: draft.source_row || null, descripcion: draft.descripcion || "", ubicacion: draft.ubicacion || "", fecha_evidencia: toPmDateInputValue(draft.fecha_evidencia) || null },
      });
      setSession((current) => ({ ...current, evidences: (current?.evidences ?? []).map((item) => item.id === updated.id ? updated : item) }));
      setEvidenceEdits((current) => { const next = { ...current }; delete next[evidence.id]; return next; });
      setSuccess("Fotografía actualizada.");
    } catch (requestError) { setError(cleanError(requestError, "No se pudo actualizar la fotografía.")); }
    finally { setSaving(false); }
  }

  async function handleConfirm() {
    if (!canConfirm) return;
    setSaving(true); setError(""); setSuccess("");
    try {
      const result = await confirmPmBudgetImport({ sessionId: session.id, token, empresaId, warnings_acknowledged: warningsAcknowledged });
      setSuccess("Presupuesto importado.");
      setSession((current) => ({ ...current, status: "imported", summary: { ...current?.summary, ...result } }));
      await reloadSessions();
      await onImported?.(result);
    } catch (requestError) { setError(cleanError(requestError, "No se pudo confirmar la importación. Revisa los datos y vuelve a intentar.")); }
    finally { setSaving(false); }
  }

  async function handleCancel() {
    if (!session?.id || !window.confirm("¿Cancelar esta revisión? El archivo analizado no se importará.")) return;
    setSaving(true); setError("");
    try {
      const updated = await cancelPmBudgetImport({ sessionId: session.id, token, empresaId });
      setSession(updated); await reloadSessions();
    } catch (requestError) { setError(cleanError(requestError, "No se pudo cancelar la revisión.")); }
    finally { setSaving(false); }
  }

  async function cancelSavedSession(sessionId) {
    if (!sessionId || !window.confirm("¿Cancelar esta revisión? El archivo analizado no se importará.")) return;
    setSaving(true); setError("");
    try {
      await cancelPmBudgetImport({ sessionId, token, empresaId });
      await reloadSessions();
      setSuccess("Importación pendiente cancelada.");
    } catch (requestError) {
      setError(cleanError(requestError, "No se pudo cancelar la importación pendiente."));
    } finally { setSaving(false); }
  }

  function focusRowField(rowId, field) {
    setExpandedRowId(rowId);
    requestAnimationFrame(() => {
      const target = document.getElementById(`pm-import-${field}-${rowId}`);
      target?.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
      target?.focus();
    });
  }

  async function downloadSourceFile() {
    if (!session?.id || !session?.source_file?.available) return;
    setSaving(true); setError("");
    try {
      await downloadPmBudgetImportSource({ projectId, sessionId: session.id, token, empresaId, filename: session.filename });
    } catch (requestError) {
      setError(cleanError(requestError, "No se pudo descargar el documento de origen."));
    } finally { setSaving(false); }
  }

  if (!open) return null;

  return (
    <ModalShell
      onClose={saving ? undefined : closeWizard}
      open={open}
      size="large"
      subtitle="Capella conserva los valores originales y la lectura de cada renglón. Nada se escribe en el presupuesto hasta confirmar."
      title="Importar presupuesto desde Excel"
      footer={session && ["review", "ready"].includes(session.status) ? (
        <div className="pm-excel-import-footer">
          <ActionButton disabled={saving} onClick={handleCancel} type="button">Cancelar revisión</ActionButton>
          <span className="pm-excel-import-footer-spacer" />
          <ActionButton disabled={saving || !canConfirm || (warningsCount > 0 && !warningsAcknowledged)} icon={<Check size={15} />} onClick={handleConfirm} tone="primary" type="button">
            Confirmar y crear presupuesto
          </ActionButton>
        </div>
      ) : null}
    >
      {error ? <div className="inventory-form-note inventory-form-note-danger"><strong>No se pudo completar</strong><p>{error}</p></div> : null}
      {success ? <div className="inventory-form-note inventory-form-note-success"><strong>{success}</strong></div> : null}

      {!session ? (
        <div className="pm-excel-import-start">
          <div className="pm-excel-import-upload-card">
            <span className="pm-excel-import-icon"><FileSpreadsheet size={22} /></span>
            <div><strong>Selecciona el archivo de presupuesto</strong><p>Solo XLSX, hasta 15 MB. No se ejecutan fórmulas ni macros.</p></div>
            <form className="pm-excel-import-upload-form" onSubmit={handleUpload}>
              <input accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} type="file" />
              <ActionButton disabled={saving || !selectedFile} icon={<Upload size={15} />} tone="primary" type="submit">Analizar archivo</ActionButton>
            </form>
          </div>
          {loading ? <p>Buscando revisiones guardadas…</p> : null}
          {sessions.length ? <section className="pm-excel-import-resumable"><h3>Revisiones guardadas</h3>{sessions.filter((item) => item.status !== "cancelled").map((item) => (
            <div className="pm-excel-import-resume-row" key={item.id}>
              <button onClick={() => openSavedSession(item.id)} type="button">
                <span><strong>{item.filename}</strong><small>{item.status === "imported" ? "Importación completada" : "Importación pendiente de revisión"} · {item.selected_sheet || "Selecciona una hoja"} · {new Date(item.updated_at).toLocaleString()}</small></span>
                <StatusBadge tone={item.status === "imported" ? "success" : "warning"}>{item.status === "imported" ? "Importado" : "Continuar revisión"}</StatusBadge>
              </button>
              {item.status !== "imported" ? <ActionButton disabled={saving} onClick={() => cancelSavedSession(item.id)} size="sm" type="button">Cancelar importación</ActionButton> : null}
            </div>
          ))}</section> : null}
        </div>
      ) : session.status === "cancelled" ? (
        <section className="pm-excel-import-result">
          <span className="pm-excel-import-icon"><X size={22} /></span>
          <h3>Revisión cancelada</h3>
          <p>Se eliminaron los renglones temporales y el documento de origen. El registro de auditoría mínimo se conserva.</p>
          <ActionButton onClick={closeWizard} type="button">Cerrar</ActionButton>
        </section>
      ) : session.status === "imported" ? (
        <section className="pm-excel-import-result">
          <span className="pm-excel-import-success-icon"><Check size={24} /></span>
          <h3>Presupuesto importado</h3>
          <p>{summary.chapters_count ?? 0} capítulos · {summary.items_count ?? 0} partidas · 1 estimación en borrador</p>
          <strong>{formatMoney(summary.budget_total ?? totalCalculated)}</strong>
          <p>No se crearon tareas ni línea base.</p>
          {session.source_file?.available ? <ActionButton disabled={saving} icon={<FileDown size={15} />} onClick={downloadSourceFile} type="button">Descargar documento de origen</ActionButton> : null}
          <div className="inventory-actions inventory-actions-wrap">
          <ActionButton onClick={closeWizard} type="button">Ver presupuesto</ActionButton>
          <ActionButton onClick={() => { closeWizard(); onContinuePlanning?.(); }} tone="primary" type="button">Continuar con planificación</ActionButton>
          </div>
        </section>
      ) : (
        <div className="pm-excel-import-review">
          <ol aria-label="Pasos de importación" className="pm-excel-import-steps">
            {["Archivo", "Hoja y mapping", "Vista previa", "Datos de estimación", "Evidencias", "Revisión final", "Confirmación"].map((step, index) => (
              <li className={index < 5 ? "is-reviewed" : index === 5 ? "is-current" : ""} key={step}><span>{index + 1}</span>{step}</li>
            ))}
          </ol>
          <div className="pm-excel-import-review-head">
            <div><span className="pm-project-setup-eyebrow">Revisa lo que Capella entendió · {session.format_type === "frts" ? "Formato FRTS" : "Formato general"}</span><h3>{session.filename}</h3><p>El presupuesto confirmado será la fuente operativa. El Excel se conserva como documento de origen y no se vuelve a procesar automáticamente.</p>
              {session.source_file?.available ? <ActionButton disabled={saving} icon={<FileDown size={15} />} onClick={downloadSourceFile} size="sm" type="button">Descargar documento de origen</ActionButton> : null}
            </div>
            <StatusBadge tone={session.status === "ready" ? "success" : "warning"}>{session.status === "ready" ? "Listo para confirmar" : "En revisión"}</StatusBadge>
          </div>

          <div className="pm-excel-import-summary">
            <span><strong>{summary.chapters_count ?? 0}</strong> capítulos</span><span><strong>{summary.items_count ?? 0}</strong> partidas</span>
            <span><strong>{warningsCount}</strong> advertencias</span><span><strong>{errorsCount}</strong> por corregir</span>
          </div>

          <div className="pm-excel-import-section">
            <div className="pm-excel-import-section-title"><div><h3>Hoja y columnas</h3><p>Verifica la hoja seleccionada y confirma cada relación.</p></div>
              <label className="pm-excel-import-sheet-select">Hoja
                <select onChange={(event) => {
                  const sheet = sheets.find((item) => item.name === event.target.value);
                  const mapping = sheet?.suggested_mapping ?? {};
                  setSession((current) => ({ ...current, selected_sheet: event.target.value, mapping, headers: sheet?.headers ?? [] }));
                  applyMapping(event.target.value, mapping);
                }} value={session.selected_sheet || ""}>{sheets.map((sheet) => <option key={sheet.name} value={sheet.name}>{sheet.name}{sheet.mapping_required ? " · requiere mapping" : ""}</option>)}</select>
              </label>
            </div>
            <div className="pm-excel-import-mapping-grid">{MAPPING_FIELDS.map(([field, label]) => (
              <label key={field}>{label}<select value={selectedMapping[field] ?? ""} onChange={(event) => {
                const next = { ...selectedMapping };
                if (event.target.value === "") delete next[field]; else next[field] = Number(event.target.value);
                setSession((current) => ({ ...current, mapping: next }));
              }}><option value="">Ignorar</option>{mappingChoices.map((option) => <option key={option.index} value={option.index}>{option.label}</option>)}</select></label>
            ))}</div>
            <ActionButton disabled={saving} onClick={() => applyMapping()} type="button">Aplicar mapping</ActionButton>
          </div>

          <details className="pm-excel-import-details" open>
            <summary>Datos generales y estimación</summary>
            <form className="pm-excel-import-details-grid" onSubmit={saveDetails}>
              {[["project_name", "Proyecto"], ["client_name", "Cliente"], ["contract_reference", "Contrato"], ["contractor", "Contratista"], ["supervisor", "Supervisor"], ["currency", "Moneda"], ["estimation_name", "Nombre de la estimación"], ["estimation_period", "Periodo"], ["estimation_notes", "Notas de estimación"]].map(([key, label]) => (
                <label key={key}>{label}<input defaultValue={metadata[key] ?? ""} onChange={(event) => setDetails((current) => ({ ...current, [key]: event.target.value }))} /></label>
              ))}
              <ActionButton disabled={saving} type="submit">Guardar datos</ActionButton>
            </form>
          </details>

          <div className="pm-excel-import-section">
            <div className="pm-excel-import-section-title"><div><h3>Vista previa editable</h3><p>El precio unitario se guarda como precio de venta; no se inventa un costo.</p></div>
              <div className="inventory-actions"><ActionButton disabled={saving} onClick={() => addBlankRow("chapter")} type="button">Nuevo capítulo</ActionButton><ActionButton disabled={saving} onClick={() => addBlankRow("item")} type="button">Nueva partida</ActionButton></div>
            </div>
            <div className="pm-excel-import-table-wrap"><table className="pm-excel-import-table"><thead><tr><th>Incluir</th><th>Código</th><th>Tipo</th><th>Capítulo</th><th>Concepto</th><th>Unidad</th><th>Cantidad</th><th>P.U.</th><th>Importe</th><th>Estado</th><th /></tr></thead><tbody>
              {rows.map((row) => {
                const values = draftRows[row.id] ?? { ...row.values, include: row.include };
                const rowStatus = displayStatus(row);
                const rowWarnings = row.warnings ?? [];
                const code = String(row.values.code ?? "").trim();
                const duplicateRows = rowWarnings.includes("duplicate_code") && code
                  ? rows.filter((candidate) => candidate.id !== row.id && candidate.row_type === "item" && candidate.include && String(candidate.values.code ?? "").trim().toLocaleLowerCase() === code.toLocaleLowerCase())
                  : [];
                const contractedAmount = Number(values.quantity || 0) * Number(values.unit_price || 0);
                const accumulatedAmount = Number(values.accumulated || 0);
                const overrunAmount = Math.max(0, accumulatedAmount - contractedAmount);
                const overrunQuantity = Number(values.unit_price) > 0 ? overrunAmount / Number(values.unit_price) : 0;
                const setField = (field, value, includeExplicit = false, rowTypeExplicit = false) => setDraftRows((current) => ({ ...current, [row.id]: {
                  ...(current[row.id] ?? { ...row.values, include: row.include }),
                  [field]: value,
                  ...(includeExplicit ? { _include_explicit: true } : {}),
                  ...(rowTypeExplicit ? { _row_type_explicit: true } : {}),
                } }));
                return <Fragment key={row.id}>
                  <tr className={!values.include ? "is-excluded" : ""} id={`pm-import-row-${row.id}`}>
                    <td><input aria-label="Incluir renglón" checked={values.include !== false} onChange={(event) => setField("include", event.target.checked, true)} type="checkbox" /></td>
                    <td><input id={`pm-import-code-${row.id}`} value={values.code ?? ""} onChange={(event) => setField("code", event.target.value)} /></td>
                    <td><select value={values.row_type ?? row.row_type} onChange={(event) => setField("row_type", event.target.value, false, true)}><option value="chapter">Capítulo</option><option value="item">Partida</option><option value="ignored">Excluir</option></select></td>
                    <td><input value={values.chapter ?? ""} onChange={(event) => setField("chapter", event.target.value)} /></td>
                    <td><input value={values.concept ?? ""} onChange={(event) => setField("concept", event.target.value)} /></td>
                    <td><input value={values.unit ?? ""} onChange={(event) => setField("unit", event.target.value)} /></td>
                    <td><input id={`pm-import-quantity-${row.id}`} inputMode="decimal" value={values.quantity ?? ""} onChange={(event) => setField("quantity", event.target.value)} /></td>
                    <td><input inputMode="decimal" value={values.unit_price ?? ""} onChange={(event) => setField("unit_price", event.target.value)} /></td>
                    <td>{formatMoney(values.amount_calculated ?? 0)}</td>
                    <td><StatusBadge title={(row.warnings ?? []).map((code) => WARNING_LABELS[code] ?? "Revisar dato").join(" · ")} tone={rowStatus.tone}>{rowStatus.label}</StatusBadge></td>
                    <td><div className="pm-excel-import-row-actions"><ActionButton disabled={saving} onClick={() => saveRow(row)} size="sm" type="button">Guardar</ActionButton><ActionButton onClick={() => setExpandedRowId((current) => current === row.id ? null : row.id)} size="sm" type="button">Avance</ActionButton></div></td>
                  </tr>
                  {expandedRowId === row.id ? <tr className="pm-excel-import-row-extra"><td colSpan="11"><div className="pm-excel-import-row-extra-grid">{[
                    ["contracted_quantity", "Cantidad contratada"], ["previous_progress", "Avance anterior"], ["this_estimate", "Esta estimación"], ["accumulated", "Acumulado"], ["remaining", "Por ejecutar"],
                  ].map(([field, label]) => <label key={field}>{label}<input id={`pm-import-${field}-${row.id}`} inputMode="decimal" value={values[field] ?? ""} onChange={(event) => setField(field, event.target.value)} /></label>)}</div></td></tr> : null}
                  {row.row_type === "ignored" && rowWarnings.includes("summary_row") ? <tr className="pm-excel-import-row-extra"><td colSpan="11"><div className="inventory-form-note"><strong>Ignorada como fila de resumen</strong><p>Este renglón no se agregará al presupuesto. Para incluirlo manualmente, cambia su tipo a capítulo o partida y marca “Incluir”.</p></div></td></tr> : null}
                  {duplicateRows.length ? <tr className="pm-excel-import-row-extra"><td colSpan="11"><div className="inventory-form-note inventory-form-note-danger"><strong>Hay más de una partida con el código {code}.</strong><p>No corregimos códigos automáticamente porque podrían corresponder a conceptos distintos. Revisa la fila {row.source_row} y las filas {duplicateRows.map((candidate) => candidate.source_row).join(", ")}.</p><div className="inventory-actions inventory-actions-wrap"><ActionButton disabled={saving} onClick={() => focusRowField(row.id, "code")} size="sm" type="button">Editar código</ActionButton><ActionButton disabled={saving} onClick={() => saveRow(row, { include: false })} size="sm" type="button">Excluir fila {row.source_row}</ActionButton><ActionButton disabled={saving} onClick={() => { setExpandedRowId(null); focusRowField(duplicateRows[0].id, "code"); }} size="sm" type="button">Revisar ambas filas</ActionButton></div></div></td></tr> : null}
                  {rowWarnings.includes("accumulated_exceeds_contracted") || rowWarnings.includes("negative_remaining") ? <tr className="pm-excel-import-row-extra"><td colSpan="11"><div className="inventory-form-note inventory-form-note-danger"><strong>Esta partida supera la cantidad contratada.</strong><p>Revisa cantidades y montos. No se convertirá automáticamente en una aditiva.</p><div className="pm-excel-import-summary"><span>Cantidad contratada · {formatNumber(values.contracted_quantity ?? values.quantity ?? 0)} {values.unit || ""}</span><span>Importe contratado · {formatMoney(contractedAmount)}</span><span>Acumulado · {formatMoney(accumulatedAmount)}</span><span>Exceso · {formatNumber(overrunQuantity)} {values.unit || ""}</span><span>Importe del exceso · {formatMoney(overrunAmount)}</span></div><div className="inventory-actions inventory-actions-wrap"><ActionButton disabled={saving} onClick={() => focusRowField(row.id, "quantity")} size="sm" type="button">Editar contratado</ActionButton><ActionButton disabled={saving} onClick={() => focusRowField(row.id, "accumulated")} size="sm" type="button">Editar acumulado</ActionButton><ActionButton disabled={saving} onClick={() => saveRow(row, { include: false })} size="sm" type="button">Excluir fila</ActionButton></div></div></td></tr> : null}
                  {rowWarnings.includes("formula_error") ? <tr className="pm-excel-import-row-extra"><td colSpan="11"><div className="inventory-form-note inventory-form-note-warning"><strong>{WARNING_LABELS.formula_error}</strong><p>Si el renglón es un capítulo o resumen, puedes cambiar su tipo. Los importes se recalculan desde las partidas base.</p></div></td></tr> : null}
                </Fragment>;
              })}
              {!rows.length ? <tr><td colSpan="11">No se detectaron renglones en esta hoja. Ajusta el mapping o selecciona otra hoja.</td></tr> : null}
            </tbody></table></div>
          </div>

          <div className="pm-excel-import-reconciliation">
            <div><span>Total reportado por Excel</span><strong>{formatMoney(totalDetected)}</strong></div>
            <div><span>Total calculado por Capella</span><strong>{formatMoney(totalCalculated)}</strong></div>
            <div><span>{summary.reconciliation_status === "redondeo" ? "Diferencia de redondeo" : "Diferencia"}</span><strong>{Number(summary.difference) > 0 ? "+" : ""}{formatMoney(summary.difference ?? 0)}</strong></div>
            <StatusBadge tone={summary.reconciliation_status === "conciliado" ? "success" : ["diferencia", "redondeo"].includes(summary.reconciliation_status) ? "warning" : "neutral"}>{summary.reconciliation_status === "conciliado" ? "Conciliado" : summary.reconciliation_status === "redondeo" ? "Redondeo · Informativa" : summary.reconciliation_status === "diferencia" ? "Revisar diferencia" : "Sin importe detectado"}</StatusBadge>
          </div>
          {summary.reconciliation_status === "redondeo" ? <p className="table-note">El archivo y Capella usan criterios de redondeo distintos. Capella redondea cada partida a centavos antes de calcular el total.</p> : null}
          <div className="pm-excel-import-reconciliation is-secondary">
            <div><span>Estimación detectada</span><strong>{formatMoney(summary.estimate_total_detected ?? 0)}</strong></div>
            <div><span>Estimación recalculada</span><strong>{formatMoney(summary.estimate_total_recalculated ?? 0)}</strong></div>
            <div><span>Diferencia de estimación</span><strong>{formatMoney(summary.estimate_difference ?? 0)}</strong></div>
          </div>
          <p className="table-note">Contratado: {formatNumber(summary.contracted_total ?? 0)} · Acumulado: {formatNumber(summary.accumulated_total ?? 0)} · Saldo: {formatNumber(summary.remaining_total ?? 0)}</p>

          <section className="pm-excel-import-section"><div className="pm-excel-import-section-title"><div><h3>Evidencias</h3><p>Fotografías opcionales; puedes asociarlas con una partida importada.</p></div></div>
            <div className="pm-excel-import-evidence-fields">
              <label>Partida relacionada<select onChange={(event) => setEvidenceDraft((current) => ({ ...current, source_row: event.target.value }))} value={evidenceDraft.source_row}><option value="">Estimación general</option>{rows.filter((row) => row.include && row.row_type === "item").map((row) => <option key={row.id} value={row.source_row}>Fila {row.source_row} · {row.values.concept || "Partida"}</option>)}</select></label>
              <label>Descripción<input maxLength={500} onChange={(event) => setEvidenceDraft((current) => ({ ...current, descripcion: event.target.value }))} value={evidenceDraft.descripcion} /></label>
              <label>Ubicación / frente<input maxLength={255} onChange={(event) => setEvidenceDraft((current) => ({ ...current, ubicacion: event.target.value }))} value={evidenceDraft.ubicacion} /></label>
              <label>Fecha<input onChange={(event) => setEvidenceDraft((current) => ({ ...current, fecha_evidencia: event.target.value }))} type="date" value={toPmDateInputValue(evidenceDraft.fecha_evidencia)} /></label>
              <label className="pm-excel-evidence-add"><ImagePlus size={16} /> Agregar fotografía<input accept="image/jpeg,image/png" onChange={uploadEvidence} type="file" /></label>
            </div>
            <div className="pm-excel-evidence-grid">{(session.evidences ?? []).map((evidence) => {
              const draft = evidenceEdits[evidence.id] ?? evidence;
              return <article className="pm-excel-evidence-card" key={evidence.id}>
                <PMEvidencePreview alt={draft.descripcion || evidence.nombre_archivo} empresaId={empresaId} evidenceId={evidence.id} token={token} />
                <div className="pm-excel-evidence-edit">
                  <strong>{evidence.nombre_archivo}</strong>
                  <span className="table-note">Fecha: {formatPmCalendarDate(evidence.fecha_evidencia)}</span>
                  <label>Partida relacionada<select disabled={saving} onChange={(event) => setEvidenceEdits((current) => ({ ...current, [evidence.id]: { ...draft, source_row: event.target.value } }))} value={draft.source_row ?? ""}><option value="">Estimación general</option>{rows.filter((row) => row.include && row.row_type === "item").map((row) => <option key={row.id} value={row.source_row}>Fila {row.source_row} · {row.values.concept || "Partida"}</option>)}</select></label>
                  <label>Descripción<input disabled={saving} maxLength={500} onChange={(event) => setEvidenceEdits((current) => ({ ...current, [evidence.id]: { ...draft, descripcion: event.target.value } }))} value={draft.descripcion ?? ""} /></label>
                  <label>Ubicación / frente<input disabled={saving} maxLength={255} onChange={(event) => setEvidenceEdits((current) => ({ ...current, [evidence.id]: { ...draft, ubicacion: event.target.value } }))} value={draft.ubicacion ?? ""} /></label>
                  <label>Fecha<input disabled={saving} onChange={(event) => setEvidenceEdits((current) => ({ ...current, [evidence.id]: { ...draft, fecha_evidencia: event.target.value } }))} type="date" value={toPmDateInputValue(draft.fecha_evidencia)} /></label>
                  <div className="inventory-actions inventory-actions-wrap"><ActionButton disabled={saving} onClick={() => saveEvidence(evidence)} size="sm" type="button">Guardar cambios</ActionButton><ActionButton disabled={saving} onClick={() => removeEvidence(evidence.id)} size="sm" type="button">Quitar</ActionButton></div>
                </div>
              </article>;
            })}{!(session.evidences ?? []).length ? <p className="table-note">Sin fotografías agregadas.</p> : null}</div>
          </section>

          {warningsCount > 0 ? <label className="pm-excel-warning-ack"><input checked={warningsAcknowledged} onChange={(event) => setWarningsAcknowledged(event.target.checked)} type="checkbox" /><span><AlertTriangle size={16} /> He revisado las advertencias antes de confirmar.</span></label> : null}
          <div className="pm-excel-import-footnote"><RotateCw size={14} /> Puedes cerrar esta ventana y continuar después; la revisión queda guardada.</div>
        </div>
      )}
    </ModalShell>
  );
}
