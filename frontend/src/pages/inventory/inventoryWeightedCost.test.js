import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { getKardexScopeMetrics } from './inventoryStockScope.js';
import { getMaterialStockRangeError, MATERIAL_STOCK_RANGE_ERROR } from './materialStockRange.js';

test('C01 weighted cost preserves F04 local/global values and zero average', () => {
  const material = {costo_promedio_actual: 20, costo_unitario: 7, valor_inventario: 100};
  for (const [warehouse, qty, value] of [['', 5, 100], ['A', 4, 80], ['B', 1, 20]]) {
    assert.equal(getKardexScopeMetrics({material, existencia_total: qty}, warehouse).value, value);
  }
  assert.equal(getKardexScopeMetrics({material: {...material, costo_promedio_actual: 0, valor_inventario: 0}, existencia_total: 5}).value, 0);
  const zero = getKardexScopeMetrics({material: {...material, costo_promedio_actual: 0, valor_inventario: 0}, existencia_total: 4}, 'A');
  assert.equal(zero.valueScope, 'local');
  assert.equal(zero.value, 0);
});

test('C01 editing excludes average from request; creation accepts initial zero', async () => {
  const page = readFileSync(new URL('./MaterialsPage.jsx', import.meta.url), 'utf8');
  const code = page.slice(page.indexOf('async function handleSubmit'), page.indexOf('async function toggleMaterialStatus')).trim();
  for (const id of ['', 'material']) {
    let payload;
    const save = async (request) => { payload = request.payload; };
    const submit = runInNewContext(`(${code})`, {
      form: {id, costo_promedio_actual: '0', stock_minimo: '', stock_maximo: ''},
      selectedImageFile: null, imageRemoved: false, token: 'fixture', empresaId: 'T', filters: {},
      getMaterialStockRangeError, MATERIAL_STOCK_RANGE_ERROR,
      setError() {}, setSkuError() {}, setSuccess() {}, setStockRangeError() {}, setSubmitting() {},
      createMaterial: save, updateMaterial: save, setModalOpen() {}, resetForm() {}, loadMaterialsPage: async () => {},
    });
    await submit({preventDefault() {}});
    assert.equal(Object.hasOwn(payload, 'costo_promedio_actual'), !id);
    if (!id) assert.equal(payload.costo_promedio_actual, '0');
  }
  assert.match(page, /readOnly=\{Boolean\(form.id\)\}/);
});
