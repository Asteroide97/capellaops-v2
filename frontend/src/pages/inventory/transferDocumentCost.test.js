import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const page = readFileSync(new URL('../../components/inventory/TransfersSection.jsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
function code(start, end) { return page.slice(page.indexOf(start), page.indexOf(end, page.indexOf(start))).trim(); }

function fixture(input, editing = false) {
  const state = {payload: null, document: null, error: ''};
  const context = {
    detailForm: {id: editing ? 'LINE' : '', material_id: 'M', cantidad: '1', costo_unitario_snapshot: input},
    selectedTransfer: {id: 'DOC'}, token: 'fixture', empresaId: 'T', transferFilters: {},
    setSubmitting() {}, setError: v => {state.error = v;}, setSuccess() {}, resetDetailForm() {},
    setSelectedTransfer: v => {state.document = v;}, loadTransferList: async () => {},
    addTransferDetail: async ({payload}) => {state.payload = payload; return {id: 'DOC', details: [payload]};},
    updateTransferDetail: async ({payload}) => {state.payload = payload; return {id: 'DOC', details: [payload]};},
  };
  const submit = runInNewContext(`(${code('async function handleDetailSubmit', '\n  async function handleDeleteDetail')})`, context);
  return {state, submit};
}

test('N3 create/update sends null for empty, numeric zero for explicit zero, and numeric value', async () => {
  for (const editing of [false, true]) {
    for (const [input, expected] of [['', null], ['0', 0], ['20', 20]]) {
      const {state, submit} = fixture(input, editing);
      await submit({preventDefault() {}});
      assert.equal(state.payload.costo_unitario_snapshot, expected);
      assert.equal(state.error, '');
    }
  }
});

test('N3 reopened detail keeps empty, zero and value distinct', async () => {
  const display = runInNewContext(`(${code('function formatDocumentCost', '\n\nfunction')})`, {
    formatMoney: v => `$${Number(v).toFixed(2)}`,
  });
  const loadCode = code('async function loadTransferDocument', '\n  function resetTransferForm');
  for (const [input, expected] of [['', 'Sin referencia'], ['0', '$0.00'], ['20', '$20.00']]) {
    const {state, submit} = fixture(input);
    await submit({preventDefault() {}});
    let reopened;
    const load = runInNewContext(`(${loadCode})`, {
      token: 'fixture', empresaId: 'T',
      getTransferDetail: async () => JSON.parse(JSON.stringify(state.document)),
      setSelectedTransfer: v => {reopened = v;}, setTransferForm() {},
    });
    await load('DOC');
    assert.equal(display(reopened.details[0].costo_unitario_snapshot), expected);
  }
  assert.match(page, /String\(detail.costo_unitario_snapshot \?\? ""\)/);
});

test('N3 optional cost input states that empty means no documentary reference', () => {
  assert.match(page, /placeholder="Sin referencia"/);
  assert.doesNotMatch(page, /Vacio: costo de referencia del material/);
});
