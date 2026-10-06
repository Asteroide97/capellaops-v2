import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { getMaterialStockRangeError, MATERIAL_STOCK_RANGE_ERROR } from './materialStockRange.js';

const source = () => readFileSync(new URL('./MaterialsPage.jsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const duplicate = () => Object.assign(new Error('El SKU ya existe en esta empresa.'), {status: 409});

async function submitFixture(form, responses) {
  const page = source();
  const code = page.slice(page.indexOf('async function handleSubmit'), page.indexOf('async function toggleMaterialStatus')).trim();
  const helpers = code.includes('isDuplicateMaterialSkuError') ? await import('./materialsFeedback.js') : {};
  const state = {error: '', success: '', skuError: false, closed: false, reset: false, calls: 0, focus: 0};
  const api = async () => {
    const response = responses[state.calls++];
    if (response instanceof Error) throw response;
  };
  const submit = runInNewContext(`(${code})`, {
    ...helpers, form, selectedImageFile: null, imageRemoved: false, token: 'fixture', empresaId: 'T', filters: {},
    getMaterialStockRangeError, MATERIAL_STOCK_RANGE_ERROR,
    setError: (value) => { state.error = value; }, setSuccess: (value) => { state.success = value; },
    setSkuError: (value) => { state.skuError = value; }, setStockRangeError: () => {}, setSubmitting: () => {},
    skuInputRef: {current: {focus: () => { state.focus++; }}},
    createMaterial: api, updateMaterial: api, loadMaterialsPage: async () => {},
    setModalOpen: (value) => { state.closed = !value; }, resetForm: () => { state.reset = true; },
  });
  return {submit, state};
}

test('F05 unique SKU create/edit retains the successful flow', async () => {
  for (const id of ['', 'existing']) {
    const {submit, state} = await submitFixture({id, sku: 'UNIQUE', stock_minimo: '', stock_maximo: ''}, [null]);
    await submit({preventDefault() {}});
    assert.equal(state.calls, 1);
    assert.equal(state.closed, true);
    assert.match(state.success, /Material/);
  }
});

test('F05 duplicate create/edit stays open, retains values, marks SKU and has no success', async () => {
  for (const id of ['', 'existing']) {
    const form = {id, sku: 'DUPLICATE', nombre: 'Keep name', stock_minimo: '2', stock_maximo: '100'};
    const before = {...form};
    const {submit, state} = await submitFixture(form, [duplicate()]);
    await submit({preventDefault() {}});
    assert.deepEqual(form, before);
    assert.equal(state.closed, false);
    assert.equal(state.reset, false);
    assert.equal(state.success, '');
    assert.match(state.error, /El SKU ya existe en esta empresa/);
    assert.equal(state.skuError, true);
    assert.equal(state.focus, 1);
  }
});

test('F05 correcting SKU allows retry and clears its previous error', async () => {
  const form = {id: '', sku: 'DUPLICATE', stock_minimo: '0', stock_maximo: '0'};
  const {submit, state} = await submitFixture(form, [duplicate(), null]);
  await submit({preventDefault() {}});
  form.sku = 'CORRECTED';
  await submit({preventDefault() {}});
  assert.equal(state.calls, 2);
  assert.equal(state.error, '');
  assert.equal(state.skuError, false);
  assert.equal(state.closed, true);
  assert.match(state.success, /Material creado/);
});

test('F05 other backend errors stay in the form without marking SKU', async () => {
  const error = Object.assign(new Error('El código de barras ya está asignado a otro material.'), {status: 409});
  const {submit, state} = await submitFixture({id: '', stock_minimo: '', stock_maximo: ''}, [error]);
  await submit({preventDefault() {}});
  assert.equal(state.closed, false);
  assert.equal(state.skuError, false);
  assert.match(state.error, /código de barras/);
  const modal = source().slice(source().indexOf('<ModalShell'));
  assert.match(modal, /id="material-form-error" role="alert"/);
});

test('F05 reset/edit reopening clears field error and the error is inside the modal', () => {
  const page = source();
  const reset = page.slice(page.indexOf('function resetForm'), page.indexOf('function openCreateModal'));
  assert.match(reset, /setError\(""\)/);
  assert.match(reset, /setSkuError\(false\)/);
  const edit = page.slice(page.indexOf('function openEditModal'), page.indexOf('async function handleSubmit'));
  assert.match(edit, /setSkuError\(false\)/);
  assert.match(page, /aria-describedby=\{skuError \? "material-form-error" : undefined\}/);
  assert.match(page, /error && !modalOpen/);
  const state = {error: 'El SKU ya existe en esta empresa.', skuError: true, form: {sku: 'OLD'}};
  const clear = runInNewContext(`(${reset.trim()})`, {
    resetImageState: () => {}, defaultForm: {sku: ''}, setStockRangeError: () => {},
    setForm: (value) => { state.form = value; }, setError: (value) => { state.error = value; },
    setSkuError: (value) => { state.skuError = value; },
  });
  clear();
  assert.equal(state.error, '');
  assert.equal(state.skuError, false);
  assert.equal(state.form.sku, '');
});

test('F06 missing metadata never uses filtered totals, and count labels are tenant scoped', async () => {
  const {getRegisteredMaterialTotal, formatRegisteredMaterialTotal} = await import('./materialsFeedback.js');
  for (const registered_total of [undefined, null, -1, '5']) {
    assert.equal(getRegisteredMaterialTotal({registered_total, total: 2}), null);
  }
  assert.equal(getRegisteredMaterialTotal({registered_total: 0}), 0);
  assert.equal(formatRegisteredMaterialTotal({empresaId: 'T', total: 5}, 'T'), 'SKUs registrados: 5');
  assert.equal(formatRegisteredMaterialTotal({empresaId: 'OTHER', total: 5}, 'T'), 'SKUs registrados: No disponible');
  assert.equal(formatRegisteredMaterialTotal(null, undefined), 'SKUs registrados: No disponible');
  assert.equal(formatRegisteredMaterialTotal({total: 5}, undefined), 'SKUs registrados: No disponible');
  assert.match(source(), /Resultados: \{meta.total\}/);
  assert.match(source(), /title=\{hasRegisteredMaterials \? "Sin resultados" : "No hay materiales"\}/);
});

test('F06 exact SKU lookup does not overwrite the registered tenant count', async () => {
  const page = source();
  const code = page.slice(page.indexOf('function applyLookupResult'), page.indexOf('async function lookupExactMaterial')).trim();
  const state = {registered: 5, meta: null};
  const lookup = runInNewContext(`(${code})`, {
    filters: {}, meta: {limit: 25}, DEFAULT_PAGE_SIZE: 25,
    setFilters: () => {}, syncQuery: () => {}, setMaterials: () => {}, setSelectedIds: () => {}, setNotice: () => {},
    setMeta: (value) => { state.meta = value; },
    setRegisteredSkuCount: () => assert.fail('Lookup must not replace the registered count'),
  });
  lookup({sku: 'ONE'}, 'ONE');
  assert.equal(state.registered, 5);
  assert.equal(state.meta.total, 1);
});

for (const [name, total, offset, items] of [['all', 5, 0, [{id: '1'}, {id: '2'}]],
  ['filtered', 2, 0, [{id: '1'}, {id: '2'}]], ['empty', 0, 0, []],
  ['page', 5, 2, [{id: '3'}]], ['inactive', 2, 0, [{id: '4'}]]]) {
  test(`F06 ${name}: registered 5 stays independent of results ${total}`, async () => {
    const page = source();
    const code = page.slice(page.indexOf('async function loadMaterialsPage'), page.indexOf('function revokePreviewUrl')).trim();
    const helpers = code.includes('getRegisteredMaterialTotal') ? await import('./materialsFeedback.js') : {};
    const state = {meta: {}, registered: null};
    let reads = 0;
    const load = runInNewContext(`(${code})`, {
      ...helpers, token: 'fixture', empresaId: 'T', filters: {}, parseBooleanFilter: () => undefined,
      getMaterials: async () => {
        reads++;
        return {items, total, limit: 2, offset, registered_total: 5};
      },
      setMaterials: () => {}, setSelectedIds: () => {}, setMeta: (value) => { state.meta = value; },
      setRegisteredSkuCount: (value) => { state.registered = value; },
    });
    await load();
    assert.equal(state.registered?.total, 5);
    assert.equal(state.registered?.empresaId, 'T');
    assert.equal(state.meta.total, total);
    assert.equal(reads, 1);
  });
}
