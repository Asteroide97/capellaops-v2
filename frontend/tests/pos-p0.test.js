import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const page = readFileSync(new URL('../src/pages/PosPage.jsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
function code(start, end) { return page.slice(page.indexOf(start), page.indexOf(end, page.indexOf(start))).trim(); }

test('F01 report CSV uses the same cents as UI and distinguishes unknown profit', () => {
  let rows;
  const context = {
    reportData: {kpis: {total_neto: '22.1768', ventas_pagadas_count: 1, ventas_canceladas_count: 0,
      ticket_promedio: '22.1768', total_descuentos: '1.04', utilidad_estimada: null},
      ventas_por_dia: [{fecha: '2026-10-08', ventas_count: 1, total_neto: '22.1768', cancelado: '0'}]},
    downloadCsvFile: (_, result) => {rows = result;},
  };
  if (page.includes('function formatReportCsvMoney')) {
    context.formatReportCsvMoney = runInNewContext(`(${code('function formatReportCsvMoney', '\n\nfunction')})`);
  }
  const exportCsv = runInNewContext(`(${code('function handleExportReportCsv', '\n  async function handleCatalogPageChange')})`, context);
  exportCsv();
  assert.equal(rows.find(row => row[1] === 'Ventas netas')[2], '22.18');
  assert.equal(rows.find(row => row[1] === 'Utilidad estimada')[2], 'No disponible');
});

test('F01 cancelled-only report CSV net stays zero', () => {
  let rows;
  const context = {reportData: {kpis: {total_neto: '0.0000', utilidad_estimada: '0.0000'},
    ventas_por_dia: [{fecha: '2026-10-08', ventas_count: 0, total_neto: '0', cancelado: '22.1768'}],
    metodos_pago: [{metodo: 'efectivo', ventas_count: 0, total: '0'}],
    ventas_por_cajero: [{nombre: 'Synthetic cashier', ventas_count: 0, total_neto: '0'}],
    ventas_por_almacen: [{nombre: 'Synthetic warehouse', ventas_count: 0, total_neto: '0'}]},
    downloadCsvFile: (_, result) => {rows = result;}};
  if (page.includes('function formatReportCsvMoney')) {
    context.formatReportCsvMoney = runInNewContext(`(${code('function formatReportCsvMoney', '\n\nfunction')})`);
  }
  runInNewContext(`(${code('function handleExportReportCsv', '\n  async function handleCatalogPageChange')})`, context)();
  assert.equal(rows.find(row => row[1] === 'Ventas netas')[2], '0.00');
  for (const name of ['efectivo', 'Synthetic cashier', 'Synthetic warehouse']) {
    assert.equal(rows.find(row => row[0] === name)[2], '0.00');
  }
});

function cashFixture(amount, fail = false) {
  const state = {calls: 0, error: '', success: '', open: 'retiro', cleared: false};
  const context = {
    selectedWarehouseId: 'A', activeShift: {almacen_id: 'A', efectivo_esperado: '11'}, expectedCash: 11,
    shiftMovementForm: {monto: amount, motivo: 'Synthetic reason'}, shiftMovementModalType: 'retiro',
    token: 'fixture', empresaId: 'T', shiftHistoryFilters: {}, defaultShiftMovementForm: {},
    setError: v => {state.error = v;}, setShiftMovementError: v => {state.error = v;},
    setShiftSubmitting() {}, clearFeedback: () => {state.error = ''; state.success = '';},
    setActiveShift() {}, setShiftMovementForm: () => {state.cleared = true;},
    setShiftMovementModalType: v => {state.open = v;}, loadShiftHistory: async () => {},
    setSuccess: v => {state.success = v;}, getPosUiError: (error, fallback) => error.message || fallback,
    createPosShiftManualWithdrawal: async () => {state.calls++; if (fail) throw new Error('El retiro supera el efectivo disponible.'); return {};},
  };
  return {state, submit: runInNewContext(`(${code('async function handleShiftMovementSubmit', '\n  async function handleCloseShiftSubmit')})`, context)};
}

test('F02 frontend blocks known excess before API and retains amount/reason', async () => {
  const {state, submit} = cashFixture('12');
  await submit({preventDefault() {}});
  assert.equal(state.calls, 0);
  assert.match(state.error, /efectivo disponible/);
  assert.equal(state.open, 'retiro');
  assert.equal(state.cleared, false);
  assert.equal(state.success, '');
});

test('F02 valid withdrawal submits and stale backend rejection stays inside modal', async () => {
  for (const amount of ['10', '11']) {
    const {state, submit} = cashFixture(amount);
    await submit({preventDefault() {}});
    assert.equal(state.calls, 1);
    assert.equal(state.open, '');
  }
  const {state, submit} = cashFixture('10', true);
  await submit({preventDefault() {}});
  assert.equal(state.open, 'retiro');
  assert.equal(state.cleared, false);
  assert.equal(state.success, '');
  assert.match(state.error, /efectivo disponible/);
  assert.match(page, /id="pos-shift-movement-error" role="alert"/);
});

test('F03 six POS direct URLs survive SPA resolution and retain view query', () => {
  const config = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url)));
  assert.equal(config.routes[0].handle, 'filesystem');
  const fallback = config.routes.filter(route => route.dest === '/index.html');
  const allowed = JSON.parse(page.match(/const POS_VIEWS = (\[.*\]);/)[1]);
  const expression = page.match(/const activeView = (.*);/)[1];
  for (const view of ['sell', 'history', 'tickets', 'cash', 'reports', 'billing']) {
    const url = new URL(`/pos?view=${view}`, 'https://fixture.invalid');
    assert.ok(fallback.some(route => new RegExp(`^${route.src}$`).test(url.pathname)));
    const resolved = runInNewContext(expression, {POS_VIEWS: allowed, searchParams: url.searchParams});
    assert.equal(resolved, view === 'billing' ? 'invoicing' : view);
    assert.equal(url.searchParams.get('view'), view);
  }
  for (const path of ['/api/pos/sales', '/assets/app.js', '/pos/missing.css']) {
    assert.equal(fallback.some(route => new RegExp(`^${route.src}$`).test(path)), false);
  }
});

test('F03 reload uses persisted session and menu navigation retains unrelated query parameters', () => {
  const auth = readFileSync(new URL('../src/auth/AuthContext.jsx', import.meta.url), 'utf8');
  assert.match(auth, /useState\(\(\) => window.localStorage.getItem\(TOKEN_KEY\)\)/);
  assert.match(auth, /useState\(\(\) => window.localStorage.getItem\(EMPRESA_KEY\)\)/);
  assert.match(auth, /const TOKEN_KEY = "capella_ops_token"/);
  const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.match(app, /path="\/pos"/);
  assert.match(app, /if \(!ready\)/);
  let result;
  const original = new URLSearchParams('view=sell&qa=fixture');
  const navigate = runInNewContext(`(${code('function updateView', '\n  function clearFeedback')})`, {
    searchParams: original, URLSearchParams, setSearchParams: v => {result = v;},
  });
  for (const view of ['sell', 'history', 'tickets', 'cash', 'reports', 'billing']) {
    navigate(view);
    assert.equal(result.get('view'), view);
    assert.equal(result.get('qa'), 'fixture');
  }
  assert.equal(original.get('view'), 'sell');
});

test('F03b billing and existing invoicing both resolve to invoicing; unknown retains sell fallback', () => {
  const allowed = JSON.parse(page.match(/const POS_VIEWS = (\[.*\]);/)[1]);
  const expression = page.match(/const activeView = (.*);/)[1];
  for (const [view, expected] of [['billing', 'invoicing'], ['invoicing', 'invoicing'],
    ['unknown', 'sell'], ['', 'sell']]) {
    const searchParams = new URLSearchParams(view ? {view} : {});
    assert.equal(runInNewContext(expression, {POS_VIEWS: allowed, searchParams}), expected);
    assert.equal(searchParams.get('view'), view || null);
  }
});

test('F03b logical URL reload retains billing/invoicing and the other public views', () => {
  const allowed = JSON.parse(page.match(/const POS_VIEWS = (\[.*\]);/)[1]);
  const expression = page.match(/const activeView = (.*);/)[1];
  for (const view of ['sell', 'history', 'tickets', 'cash', 'reports', 'billing', 'invoicing']) {
    const initial = new URL(`/pos?view=${view}&qa=fixture`, 'https://fixture.invalid');
    const reloaded = new URL(initial.href);
    const searchParams = reloaded.searchParams;
    assert.equal(runInNewContext(expression, {POS_VIEWS: allowed, searchParams}), view === 'billing' ? 'invoicing' : view);
    assert.equal(searchParams.get('view'), view);
    assert.equal(searchParams.get('qa'), 'fixture');
    assert.equal(reloaded.pathname, '/pos');
  }
});
