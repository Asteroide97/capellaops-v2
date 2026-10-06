import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { getMaterialStockRangeError, MATERIAL_STOCK_RANGE_ERROR } from './materialStockRange.js';

test('valid and equal ranges are allowed', () => {
  for (const [minimum, maximum] of [['2', '100'], ['100', '100'], ['0', '0'], ['', '100'], ['', ''], ['02.0000', '2'], ['.1', '0.1000']]) {
    assert.equal(getMaterialStockRangeError(minimum, maximum), '');
  }
});
test('invalid range blocks submit including blank maximum sent as zero', () => {
  for (const [minimum, maximum] of [['101', '100'], ['2', ''], ['0.1001', '0.1'], ['99999999999999.0002', '99999999999999.0001']]) {
    assert.equal(getMaterialStockRangeError(minimum, maximum), 'El stock mínimo no puede ser mayor que el stock máximo.');
  }
});

function submitFixture(form, apiError = null) {
  const source = readFileSync(new URL('./MaterialsPage.jsx', import.meta.url), 'utf8');
  const code = source.slice(source.indexOf('async function handleSubmit'), source.indexOf('async function toggleMaterialStatus')).trim();
  const result = {calls: [], stockRangeError: '', success: '', error: '', reset: false, closed: false};
  const api = async (request) => {
    result.calls.push(request);
    if (apiError) throw new Error(apiError);
  };
  const submit = runInNewContext(`(${code})`, {
    form, selectedImageFile: null, imageRemoved: false, token: 'fixture', empresaId: 'fixture', filters: {},
    getMaterialStockRangeError, MATERIAL_STOCK_RANGE_ERROR,
    setStockRangeError: (value) => { result.stockRangeError = value; },
    setSkuError: () => {},
    setError: (value) => { result.error = value; },
    setSuccess: (value) => { result.success = value; },
    setSubmitting: () => {},
    setModalOpen: (value) => { result.closed = !value; },
    resetForm: () => { result.reset = true; },
    loadMaterialsPage: async () => {}, createMaterial: api, updateMaterial: api,
    uploadMaterialImage: async () => { throw new Error('Unexpected upload'); },
  });
  return {submit, result};
}

test('actual submit handler rejects invalid create/edit without clearing values or sending requests', async () => {
  for (const id of ['', 'existing']) {
    const form = {id, stock_minimo: '101', stock_maximo: '100', nombre: 'Keep this value'};
    const before = {...form};
    const {submit, result} = submitFixture(form);
    await submit({preventDefault() {}});
    assert.deepEqual(form, before);
    assert.deepEqual(result.calls, []);
    assert.equal(result.stockRangeError, MATERIAL_STOCK_RANGE_ERROR);
    assert.equal(result.success, '');
    assert.equal(result.reset, false);
    assert.equal(result.closed, false);
  }
});

test('actual submit handler sends valid create/edit and displays backend range rejection inside form', async () => {
  for (const id of ['', 'existing']) {
    const form = {id, stock_minimo: '2', stock_maximo: '100'};
    const valid = submitFixture(form);
    await valid.submit({preventDefault() {}});
    assert.equal(valid.result.calls.length, 1);
    assert.equal(valid.result.calls[0].payload.stock_minimo, '2');
    assert.match(valid.result.success, /Material/);
    const rejected = submitFixture(form, MATERIAL_STOCK_RANGE_ERROR);
    await rejected.submit({preventDefault() {}});
    assert.equal(rejected.result.stockRangeError, MATERIAL_STOCK_RANGE_ERROR);
    assert.equal(rejected.result.error, '');
    assert.equal(rejected.result.success, '');
    assert.equal(rejected.result.closed, false);
  }
});

test('existing CSV action still exports the current materials and stock limits', () => {
  const source = readFileSync(new URL('./MaterialsPage.jsx', import.meta.url), 'utf8');
  const code = source.slice(source.indexOf('function exportCurrentView'), source.indexOf('function handleScannerDetected')).trim();
  let exported;
  let success = '';
  const action = runInNewContext(`(${code})`, {
    materials: [{sku: 'TEST', nombre: 'Test', unidad: 'pieza', stock_total: 5, stock_minimo: 2, stock_maximo: 100,
      costo_unitario: 10, valor_inventario: 50, activo: true}],
    downloadCsv: (filename, rows) => { exported = {filename, rows}; },
    setError: () => assert.fail('Unexpected CSV error'),
    setSuccess: (value) => { success = value; },
  });
  action();
  assert.equal(exported.filename, 'inventario_materiales.csv');
  assert.equal(exported.rows.length, 2);
  assert.deepEqual(Array.from(exported.rows[1]).slice(6, 11), [5, 2, 100, 10, 50]);
  assert.match(success, /CSV/);
});
test('negative and nonfinite values are not submitted', () => {
  for (const [minimum, maximum] of [['-1', '100'], ['0', '-1'], ['NaN', '100'], ['1', 'Infinity']]) {
    assert.notEqual(getMaterialStockRangeError(minimum, maximum), '');
  }
});
test('modal submit checks range before uploads or API calls and preserves the form', () => {
  const source = readFileSync(new URL('./MaterialsPage.jsx', import.meta.url), 'utf8');
  const submit = source.slice(source.indexOf('async function handleSubmit'), source.indexOf('async function toggleMaterialStatus'));
  assert.match(submit, /getMaterialStockRangeError\(form.stock_minimo, form.stock_maximo\)/);
  assert.ok(submit.indexOf('if (rangeError)') < submit.indexOf('uploadMaterialImage('));
  assert.match(submit, /if \(rangeError\)\s*\{\s*setStockRangeError\(rangeError\);\s*return;/);
  assert.match(source, /id="material-stock-range-error" role="alert"/);
  assert.match(source, /aria-describedby=\{stockRangeError \? "material-stock-range-error" : undefined\}/);
  assert.match(source, /aria-invalid=\{Boolean\(stockRangeError\)\}/);
});
