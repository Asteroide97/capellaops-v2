import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const readPage = (name) => readFileSync(new URL(`./${name}.jsx`, import.meta.url), 'utf8').replace(/\r\n/g, '\n');

for (const [warehouseId, quantity, expected] of [['', 5, 50], ['A', 4, 40], ['B', 1, 10], ['C', 0, 0]]) {
  test(`F04 actual Kardex card value for ${warehouseId || 'all warehouses'}`, async () => {
    const source = readPage('KardexPage');
    const cards = source.slice(source.indexOf('className="inventory-metric-grid'), source.indexOf('className="inventory-content-grid'));
    const calls = [...cards.matchAll(/\{formatMoney\(([^)]+)\)\}/g)];
    assert.equal(calls.length, 2);
    const expression = calls.at(-1)[1];
    const kardex = {existencia_total: quantity, stock_por_almacen: [],
      material: {stock_total: 5, costo_promedio_actual: 10, costo_unitario: 7, valor_inventario: 50}};
    let scopeMetrics;
    if (expression.includes('scopeMetrics')) {
      const {getKardexScopeMetrics} = await import('./inventoryStockScope.js');
      scopeMetrics = getKardexScopeMetrics(kardex, warehouseId);
    }
    assert.equal(runInNewContext(expression, {kardex, scopeMetrics}), expected);
  });
}

test('F04 null selection, cost fallback, zero cost and existing global value are preserved', async () => {
  const {getKardexScopeMetrics} = await import('./inventoryStockScope.js');
  assert.equal(getKardexScopeMetrics(null), null);
  const material = {costo_promedio_actual: null, costo_unitario: 10, valor_inventario: 50};
  assert.deepEqual(getKardexScopeMetrics({existencia_total: 4, material}, 'A'), {quantity: 4, cost: 10, value: 40, valueScope: 'local'});
  const zeroCost = {...material, costo_promedio_actual: 0};
  assert.deepEqual(getKardexScopeMetrics({existencia_total: 4, material: zeroCost}, 'A'), {quantity: 4, cost: 0, value: 50, valueScope: 'global'});
  assert.equal(getKardexScopeMetrics({existencia_total: 5, material: zeroCost}).value, 50);
  assert.equal(material.valor_inventario, 50);
  assert.match(readPage('KardexPage'), /Valor global — todos los almacenes/);
});

test('F04 zero local stock is zero value even when the displayed cost is ambiguous', async () => {
  const {getKardexScopeMetrics} = await import('./inventoryStockScope.js');
  const material = {stock_total: 5, costo_promedio_actual: 0, costo_unitario: 10, valor_inventario: 50};
  const metrics = getKardexScopeMetrics({existencia_total: 0, material}, 'EMPTY');
  assert.equal(metrics.value, 0);
  assert.equal(metrics.valueScope, 'local');
  assert.equal(material.valor_inventario, 50);
});

test('F07 loading/error/tenant changes never masquerade as zero or global stock', async () => {
  const {getWarehouseAvailability} = await import('./inventoryStockScope.js');
  const snapshot = {empresaId: 'T', warehouseId: 'A', status: 'ready', items: [{material_id: 'M', cantidad: 9}]};
  for (const [snapshotValue, tenant, warehouse, status] of [
    [null, 'T', 'A', 'loading'], [snapshot, 'T', 'B', 'loading'],
    [snapshot, 'OTHER', 'A', 'loading'], [{...snapshot, status: 'error'}, 'T', 'A', 'error'],
    [snapshot, 'T', '', 'select_warehouse'],
  ]) {
    assert.deepEqual(getWarehouseAvailability(snapshotValue, tenant, warehouse, 'M'), {status, quantity: null});
  }
  assert.deepEqual(getWarehouseAvailability(snapshot, 'T', 'A', 'OTHER-MATERIAL'), {status: 'ready', quantity: 0});
});

test('F07 existing stock endpoint is read through all pages before absent material means zero', async () => {
  const {readWarehouseStock, getWarehouseAvailability} = await import('./inventoryStockScope.js');
  const calls = [];
  const first = Array.from({length: 100}, (_, index) => ({almacen_id: 'A', material_id: `M${index}`, cantidad: '9'}));
  const items = await readWarehouseStock(async (page) => {
    calls.push(page);
    return {items: page.offset === 0 ? first : [{almacen_id: 'A', material_id: 'LAST', cantidad: '3'}], total: 101, offset: page.offset};
  }, 'A');
  assert.deepEqual(calls, [{limit: 100, offset: 0}, {limit: 100, offset: 100}]);
  assert.equal(items.length, 101);
  assert.equal(getWarehouseAvailability({empresaId: 'T', warehouseId: 'A', status: 'ready', items}, 'T', 'A', 'LAST').quantity, 3);
});

test('F07 failed/incomplete/wrong-scope stock reads are errors, not empty successes', async () => {
  const {readWarehouseStock} = await import('./inventoryStockScope.js');
  await assert.rejects(readWarehouseStock(async () => { throw new Error('read failed'); }, 'A'));
  for (const response of [null, {items: [], total: 1, offset: 0},
    {items: [{almacen_id: 'B', material_id: 'M', cantidad: 1}], total: 1, offset: 0},
    {items: [{almacen_id: 'A', material_id: 'M', cantidad: null}], total: 1, offset: 0}]) {
    await assert.rejects(readWarehouseStock(async () => response, 'A'));
  }
  assert.deepEqual(await readWarehouseStock(async () => ({items: [], total: 0, offset: 0}), 'A'), []);
});

test('F07 actual effect ignores old warehouse responses after selection changes', async () => {
  const {readWarehouseStock} = await import('./inventoryStockScope.js');
  const source = readPage('MovementsPage');
  const start = source.indexOf('useEffect(() => {\n    if (!modalState.open');
  const end = source.indexOf('  }, [modalState.open', start);
  assert.ok(start >= 0 && end > start);
  const effect = source.slice(start, end) + '});';
  const snapshots = [];
  let cleanup;
  let finish;
  runInNewContext(effect, {
    modalState: {open: true}, draft: {almacen_id: 'A'}, token: 'fixture', empresaId: 'T', readWarehouseStock,
    useEffect: (callback) => { cleanup = callback(); },
    setWarehouseStock: (snapshot) => snapshots.push(snapshot),
    getStock: () => new Promise((resolve) => { finish = resolve; }),
  });
  cleanup();
  finish({items: [{almacen_id: 'A', material_id: 'M', cantidad: 9}], total: 1, offset: 0});
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(snapshots.map((snapshot) => snapshot.status), ['loading']);
});

test('F04 actual loading keeps metrics tied to applied filter and clearing selection discards pending reads', async () => {
  const source = readPage('KardexPage');
  const start = source.indexOf('async function loadKardex');
  const end = source.indexOf('  useEffect(', start);
  const responses = [];
  const state = {kardex: null, warehouseId: ''};
  const load = runInNewContext(`(${source.slice(start, end).trim()})`, {
    filters: {}, token: 'fixture', empresaId: 'T', kardexRequestId: {current: 0},
    getMaterialKardex: () => new Promise((resolve) => responses.push(resolve)),
    setKardex: (value) => { state.kardex = value; },
    setAppliedWarehouseId: (value) => { state.warehouseId = value; },
  });
  const first = load('M', 'A');
  const second = load('M', 'B');
  responses[1]({existencia_total: 1});
  await second;
  responses[0]({existencia_total: 4});
  await first;
  assert.equal(state.warehouseId, 'B');
  assert.equal(state.kardex.existencia_total, 1);
  const pending = load('M', 'A');
  await load('', '');
  responses[2]({existencia_total: 4});
  await pending;
  assert.equal(state.kardex, null);
  assert.equal(state.warehouseId, '');
});

for (const [warehouseId, materialId, expected] of [['A', 'M', 9], ['B', 'M', 1],
  ['A', 'M', 9], ['C', 'M', 0], ['A', 'ONLY-B', 0]]) {
  test(`F07 local availability ${warehouseId}/${materialId} = ${expected}`, async () => {
    const source = readPage('MovementsPage');
    const oldStock = source.match(/ · Stock \{formatNumber\(([^)]+)\)\}/);
    if (oldStock) {
      assert.equal(runInNewContext(oldStock[1], {material: {stock_total: 10}}), expected);
    } else {
      const {getWarehouseAvailability} = await import('./inventoryStockScope.js');
      const snapshot = {empresaId: 'T', warehouseId, status: 'ready', items: warehouseId === 'A'
        ? [{material_id: 'M', cantidad: 9}] : warehouseId === 'B'
          ? [{material_id: 'M', cantidad: 1}, {material_id: 'ONLY-B', cantidad: 7}] : []};
      assert.equal(getWarehouseAvailability(snapshot, 'T', warehouseId, materialId).quantity, expected);
      assert.match(source, /Disponible en/);
      assert.match(source, /Stock global:/);
    }
  });
}
