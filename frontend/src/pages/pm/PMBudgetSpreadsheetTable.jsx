import { useMemo, useRef, useState } from "react";
import { ClipboardPaste, Table2 } from "lucide-react";

import { ActionButton, ModalShell, formatMoney, formatNumber, safeDisplayText } from "../inventory/shared";

const COLUMNS = [
  ["code", "Código"], ["concept", "Concepto"], ["unit", "Unidad"],
  ["quantity", "Cantidad"], ["price", "P.U."],
];

function cleanRows(text) {
  return String(text || "").replace(/\r/g, "").split("\n").filter((line) => line.trim()).map((line) => line.split("\t").map((cell) => cell.trim()));
}

export default function PMBudgetSpreadsheetTable({ canEdit, chapters = [], items = [], onPasteRows, onSelectItem, onUpdateCell }) {
  const [editing, setEditing] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [savingCell, setSavingCell] = useState(null);
  const [cellError, setCellError] = useState("");
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [pasteMapping, setPasteMapping] = useState({ code: 0, concept: 1, unit: 2, quantity: 3, price: 4 });
  const [pasteBusy, setPasteBusy] = useState(false);
  const [pasteError, setPasteError] = useState("");
  const savingEdit = useRef(false);
  const skipBlurSave = useRef(false);
  const parsedRows = useMemo(() => cleanRows(pasteText), [pasteText]);
  const maxColumns = Math.max(0, ...parsedRows.map((row) => row.length));
  const flattened = useMemo(() => {
    const byId = new Map(items.map((item) => [item.id, item]));
    return [...chapters.map((chapter) => ({ ...chapter, indent: 0 })), ...items.filter((item) => item.tipo === "partida").map((item) => ({ ...item, indent: item.parent_id ? 1 : 0, chapter: byId.get(item.parent_id) }))]
      .sort((left, right) => (Number(left.orden || 0) - Number(right.orden || 0)) || String(left.codigo || "").localeCompare(String(right.codigo || ""), undefined, { numeric: true }));
  }, [chapters, items]);

  function startEdit(item, field, event) {
    if (!canEdit || item.tipo === "capitulo" && !["code", "concept"].includes(field)) return;
    event.stopPropagation();
    setEditing({ itemId: item.id, field });
    setCellError("");
    setEditValue(field === "concept" ? item.nombre ?? "" : field === "code" ? item.codigo ?? "" : field === "unit" ? item.unidad ?? "" : field === "quantity" ? String(item.cantidad ?? "") : String(item.precio_unitario_manual ?? item.precio_unitario ?? ""));
  }

  async function saveEdit(nextFocus = false) {
    if (!editing || savingEdit.current) return;
    const edit = editing;
    const target = flattened.find((item) => item.id === edit.itemId);
    const fieldMap = { code: "codigo", concept: "nombre", unit: "unidad", quantity: "cantidad", price: "precio_unitario_manual" };
    const field = fieldMap[edit.field];
    const value = ["quantity", "price"].includes(edit.field) ? Number(editValue) : editValue.trim() || null;
    if (["quantity", "price"].includes(edit.field) && (!Number.isFinite(value) || (edit.field === "quantity" && value <= 0) || (edit.field === "price" && value < 0))) {
      setCellError(edit.field === "quantity" ? "La cantidad debe ser mayor a cero." : "El precio unitario debe ser cero o mayor.");
      return;
    }
    setCellError("");
    savingEdit.current = true;
    setSavingCell(edit);
    try {
      await onUpdateCell?.(target, field, value);
      setEditing(null);
      if (nextFocus) {
        requestAnimationFrame(() => {
          const cells = Array.from(document.querySelectorAll(".pm-budget-sheet-table [data-editable-cell='true']:not(:disabled)"));
          const current = cells.findIndex((element) => element.dataset.itemId === edit.itemId && element.dataset.field === edit.field);
          if (current >= 0) cells[Math.min(cells.length - 1, current + 1)]?.click();
        });
      }
    } catch (error) {
      setCellError(error?.message || "No se pudo guardar esta celda.");
    } finally {
      savingEdit.current = false;
      setSavingCell(null);
    }
  }

  function handleCellKeyDown(event) {
    if (event.key === "Escape") { event.preventDefault(); skipBlurSave.current = true; setEditing(null); setCellError(""); window.setTimeout(() => { skipBlurSave.current = false; }, 0); return; }
    if (event.key === "Enter") {
      event.preventDefault();
      saveEdit(false);
    }
    if (event.key === "Tab") {
      event.preventDefault();
      saveEdit(true);
    }
  }

  async function confirmPaste() {
    const getColumn = (row, field) => {
      const index = Number(pasteMapping[field]);
      return index >= 0 ? row[index] ?? "" : "";
    };
    const data = parsedRows.map((row) => ({
      codigo: getColumn(row, "code"),
      nombre: getColumn(row, "concept"),
      unidad: getColumn(row, "unit"),
      cantidad: Number(String(getColumn(row, "quantity")).replace(/,/g, "")),
      precio_unitario_manual: Number(String(getColumn(row, "price")).replace(/[$,]/g, "")),
    })).filter((row) => row.nombre || row.codigo);
    const invalid = data.find((row) => !row.nombre || !Number.isFinite(row.cantidad) || row.cantidad <= 0 || !Number.isFinite(row.precio_unitario_manual) || row.precio_unitario_manual < 0);
    if (invalid) { setPasteError("Corrige concepto, cantidad y precio unitario antes de agregar las filas."); return; }
    setPasteBusy(true); setPasteError("");
    try {
      await onPasteRows?.(data);
      setPasteOpen(false); setPasteText("");
    } catch (error) {
      setPasteError(error?.message || "No se pudieron agregar las filas.");
    } finally { setPasteBusy(false); }
  }

  return (
    <section className="pm-budget-spreadsheet">
      <div className="pm-budget-spreadsheet-head"><div><span className="pm-project-setup-eyebrow"><Table2 size={14} /> Presupuesto</span><h3>Vista tipo hoja de cálculo</h3></div>
        <ActionButton disabled={!canEdit || !items.length} icon={<ClipboardPaste size={15} />} onClick={() => setPasteOpen(true)} type="button">Pegar desde Excel</ActionButton>
      </div>
      <div className="pm-budget-sheet-scroll"><table className="pm-budget-sheet-table"><thead><tr><th>Código</th><th>Concepto</th><th>Unidad</th><th>Cantidad</th><th>P.U.</th><th>Importe</th></tr></thead><tbody>
        {flattened.map((item) => {
          const isChapter = item.tipo === "capitulo";
          const isEditing = (field) => editing?.itemId === item.id && editing?.field === field;
          const cell = (field, value, className = "") => (
            <td className={className} key={field}>
              {isEditing(field) ? <><input aria-invalid={Boolean(cellError)} autoFocus disabled={Boolean(savingCell)} onBlur={() => { if (skipBlurSave.current) { skipBlurSave.current = false; return; } saveEdit(false); }} onChange={(event) => { setEditValue(event.target.value); setCellError(""); }} onKeyDown={handleCellKeyDown} type={["quantity", "price"].includes(field) ? "number" : "text"} value={editValue} />{savingCell?.itemId === item.id && savingCell?.field === field ? <small className="pm-budget-sheet-cell-status">Guardando…</small> : null}{cellError ? <small className="pm-budget-sheet-cell-error">{cellError}</small> : null}</> : (
                <button className={`pm-budget-sheet-cell ${field === "concept" ? "is-concept" : ""}`} data-editable-cell="true" data-field={field} data-item-id={item.id} disabled={!canEdit} onClick={(event) => startEdit(item, field, event)} title="Selecciona para editar" type="button">{value}</button>
              )}
            </td>
          );
          return <tr className={isChapter ? "is-chapter" : ""} key={item.id} onClick={() => onSelectItem?.(item.id)}>
            {cell("code", safeDisplayText(item.codigo, "—"))}
            {cell("concept", <span style={{ paddingLeft: item.indent * 14 }}>{safeDisplayText(item.nombre)}</span>)}
            {cell("unit", isChapter ? "—" : safeDisplayText(item.unidad, "—"))}
            {cell("quantity", isChapter ? "—" : formatNumber(item.cantidad ?? 0), "is-number")}
            {cell("price", isChapter ? "—" : formatMoney(item.precio_unitario ?? 0), "is-number")}
            <td className="is-number">{formatMoney(item.subtotal_venta ?? 0)}</td>
          </tr>;
        })}
        {!flattened.length ? <tr><td className="pm-budget-sheet-empty" colSpan="6">Agrega partidas o pega varias filas para comenzar.</td></tr> : null}
      </tbody></table></div>
      <p className="pm-budget-sheet-hint">Click para editar · Enter guarda · Tab guarda y avanza · Esc cancela. Los totales provienen del presupuesto calculado.</p>

      <ModalShell
        footer={<div className="inventory-actions inventory-actions-wrap"><ActionButton disabled={pasteBusy} onClick={() => setPasteOpen(false)} type="button">Cancelar</ActionButton><ActionButton disabled={pasteBusy || !parsedRows.length} onClick={confirmPaste} tone="primary" type="button">Agregar {parsedRows.length} filas temporales</ActionButton></div>}
        onClose={() => setPasteOpen(false)} open={pasteOpen} subtitle="Pega un bloque tabular; revisa cómo se interpreta y confirma para agregar las partidas." title="Pegar desde Excel"
      >
        <div className="pm-budget-paste-modal">
          <textarea onChange={(event) => setPasteText(event.target.value)} onPaste={() => setPasteError("")} placeholder="Copia filas y columnas desde Excel y pégalas aquí…" value={pasteText} />
          {maxColumns ? <div className="pm-budget-paste-mapping">{COLUMNS.map(([field, label], index) => <label key={field}>{label}<select onChange={(event) => setPasteMapping((current) => ({ ...current, [field]: Number(event.target.value) }))} value={pasteMapping[field]}><option value={-1}>Ignorar</option>{Array.from({ length: maxColumns }, (_, col) => <option key={col} value={col}>Columna {col + 1}</option>)}</select></label>)}</div> : null}
          {parsedRows.length ? <div className="pm-budget-paste-preview"><strong>Vista previa · {parsedRows.length} filas</strong><div className="pm-budget-sheet-scroll"><table className="pm-budget-sheet-table"><thead><tr>{COLUMNS.map(([, label]) => <th key={label}>{label}</th>)}</tr></thead><tbody>{parsedRows.slice(0, 8).map((row, index) => <tr key={index}>{COLUMNS.map(([field]) => <td key={field}>{safeDisplayText(row[pasteMapping[field]], "—")}</td>)}</tr>)}</tbody></table></div></div> : null}
          {pasteError ? <p className="inventory-form-note-danger">{pasteError}</p> : null}
          <p className="table-note">Las filas solo se agregan al guardar esta confirmación. El precio unitario representa precio de venta, no costo interno.</p>
        </div>
      </ModalShell>
    </section>
  );
}
