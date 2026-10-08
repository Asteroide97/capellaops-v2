import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = (name) => readFileSync(new URL(name, import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const supplierPage = () => source('./SuppliersPage.jsx');
const movementPage = () => source('./MovementsPage.jsx');
const transferPage = () => source('../../components/inventory/TransfersSection.jsx');
function code(page, start, end) { return page.slice(page.indexOf(start), page.indexOf(end, page.indexOf(start))).trim(); }

function supplierFixture(summary, error = null, cached = null) {
  const state = {summary: cached, error: '', detailError: '', open: false, orders: []};
  const context = {
    token: 'fixture', empresaId: 'T', supplierSummaries: cached ? {S: cached} : {},
    setDetailSupplierId() {}, setDetailSummary: v => {state.summary = v;},
    setDetailOrders: v => {state.orders = v;}, setDetailReceipts() {}, setDetailMaterials() {},
    setDetailOpen: v => {state.open = v;}, setDetailLoading() {},
    setError: v => {state.error = v;}, setDetailError: v => {state.detailError = v;},
    setSupplierSummaries() {},
    getSupplierSummary: async () => {if (error) throw error; return summary;},
    getSupplierPurchaseOrders: async () => ({items: summary?.ordenes_recientes || []}),
    getSupplierReceipts: async () => ({items: []}), getSupplierMaterials: async () => ({items: []}),
  };
  context.loadSupplierDetailBundle = runInNewContext(`(${code(supplierPage(), 'async function loadSupplierDetailBundle', '\n  useEffect')})`, context);
  const open = runInNewContext(`(${code(supplierPage(), 'async function openDetailModal', '\n  async function handleSubmit')})`, context);
  return {state, open};
}

test('N1 legitimate zero, one draft and multiple orders are displayed from the response', async () => {
  for (const count of [0, 1, 3]) {
    const summary = {ordenes_totales: count, ordenes_recientes: count ? [{folio: 'QA-DRAFT'}] : []};
    const {state, open} = supplierFixture(summary);
    await open('S');
    assert.equal(state.summary.ordenes_totales, count);
    assert.equal(state.orders.length, count ? 1 : 0);
    assert.equal(state.detailError, '');
  }
});

test('N1 query errors remain visible inside detail and never become cached zero metrics', async () => {
  const {state, open} = supplierFixture(null, new Error('synthetic query error'), {ordenes_totales: 0});
  await open('S');
  assert.equal(state.open, true);
  assert.equal(state.summary, null);
  assert.match(state.detailError, /No se pudo cargar el resumen/);
  const modal = supplierPage().slice(supplierPage().lastIndexOf('<ModalShell'));
  assert.match(modal, /detailError[^\n]*role="alert"/);
  assert.match(modal, /detailSummary \? \(/);
});

test('N1 partial list summary failures cannot appear as zero KPI totals', async () => {
  const page = supplierPage();
  const state = {error: '', summaries: null};
  const load = runInNewContext(`(${code(page, 'async function loadSupplierSummarySnapshot', '\n  async function loadSuppliersPage')})`, {
    token: 'fixture', empresaId: 'T',
    getSupplierSummary: async () => {throw new Error('fixture');},
    setSupplierSummaries: v => {state.summaries = v;}, setError: v => {state.error = v;},
  });
  await load([{id: 'S'}]);
  assert.match(state.error, /resumen/);
  assert.match(page, /summariesReady \? formatNumber\(kpis.conOrdenesAbiertas\) : "No disponible"/);
});

function movementFixture(responses) {
  const page = movementPage();
  const draft = {items: [{material_id: 'M', cantidad: '11', notas: ''}], notas: '', almacen_id: 'A'};
  const state = {error: '', success: '', closed: false, calls: 0};
  const context = {
    draft, modalState: {open: true, tipo: 'salida'}, token: 'fixture', empresaId: 'T', filters: {},
    setSubmitting() {}, setError: v => {state.error = v;}, setSuccess: v => {state.success = v;},
    createInventoryMovementBulk: async () => {const r=responses[state.calls++]; if (r instanceof Error) throw r;},
    closeMovementModal: () => {state.closed = true;}, loadMovementsPage: async () => {}, loadOptions: async () => {},
  };
  return {state, draft, submit: runInNewContext(`(${code(page, 'async function handleSubmit', '\n  if (loading)')})`, context)};
}

test('N2 stock and other request errors preserve lines, keep modal open and show no success', async () => {
  for (const message of ['Stock insuficiente.', 'No se pudo registrar el movimiento.']) {
    const {state, draft, submit} = movementFixture([new Error(message)]);
    const before = JSON.stringify(draft);
    await submit({preventDefault() {}});
    assert.equal(state.error, message);
    assert.equal(state.closed, false);
    assert.equal(state.success, '');
    assert.equal(JSON.stringify(draft), before);
  }
  const page = movementPage();
  assert.match(page, /error && !modalState.open/);
  assert.match(page.slice(page.indexOf('<ModalShell')), /id="movement-form-error" role="alert"/);
});

test('N2 correcting quantity permits retry and close/reopen clears previous error', async () => {
  const {state, draft, submit} = movementFixture([new Error('Stock insuficiente.'), null]);
  await submit({preventDefault() {}});
  draft.items[0].cantidad = '1';
  await submit({preventDefault() {}});
  assert.equal(state.error, '');
  assert.equal(state.closed, true);
  assert.match(state.success, /registrado correctamente/);
  const page = movementPage();
  assert.match(code(page, 'function closeMovementModal', '\n  function addDraftLine'), /setError\(""\)/);
  assert.match(code(page, 'function openMovementModal', '\n  function closeMovementModal'), /setError\(""\)/);
});

test('N3 documentary reference is labeled separately from applied cost, including legacy', () => {
  const page = transferPage();
  assert.match(page, /<th>Costo documental<\/th>/);
  assert.match(page, /no es el costo aplicado/);
  assert.match(page, /Kardex/);
  assert.doesNotMatch(page, /<th>Costo snapshot<\/th>/);
});

test('N3 empty cost, numeric/string zero and explicit/legacy reference render without truthy fallback', () => {
  const page = transferPage();
  const expression = page.split('<td>{formatNumber(detail.cantidad)}</td>')[1].match(/<td>\{(.+?)\}<\/td>/)[1];
  const formatMoney = v => `$${Number(v).toFixed(2)}`;
  const helpers = {formatMoney};
  if (page.includes('function formatDocumentCost')) {
    helpers.formatDocumentCost = runInNewContext(`(${code(page, 'function formatDocumentCost', '\n\nfunction')})`, helpers);
  }
  for (const [value, expected] of [[null, 'Sin referencia'], ['', 'Sin referencia'], [0, '$0.00'], ['0.0000', '$0.00'], [20, '$20.00'], ['7.0000', '$7.00']]) {
    assert.equal(runInNewContext(`(${expression})`, {...helpers, detail: {costo_unitario_snapshot: value}}), expected);
  }
  assert.match(page, /String\(detail.costo_unitario_snapshot \?\? ""\)/);
});
