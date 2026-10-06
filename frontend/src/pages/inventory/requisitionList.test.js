import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { readRequisitionList, countRequisitionStates, refreshCommittedRequisitionList } from './requisitionList.js';

test('real empty response remains empty', async () => {
  const result = await readRequisitionList(async () => ({items: [], total: 0, limit: 25, offset: 0}));
  assert.equal(result.total, 0);
  assert.deepEqual(result.items, []);
});
test('failed or malformed read is never converted to empty success', async () => {
  await assert.rejects(readRequisitionList(async () => { throw new Error('read failed'); }));
  await assert.rejects(readRequisitionList(async () => ({})));
});
for (const state of ['borrador', 'enviada', 'aprobada', 'parcial', 'surtida', 'cancelada', 'rechazada']) {
  test(`list and counts reflect ${state}`, async () => {
    const result = await readRequisitionList(async () => ({items: [{id: 'r1', estatus: state}], total: 1, limit: 25, offset: 0}));
    assert.equal(result.items[0].estatus, state);
    assert.equal(countRequisitionStates(result.items)[state], 1);
  });
}
test('refresh failure after confirmed mutation is separate and preserves document', async () => {
  const saved = {id: 'r1', estatus: 'enviada'};
  let message = '';
  const result = await refreshCommittedRequisitionList(async () => { throw new Error('read failed'); }, (value) => { message = value; });
  assert.equal(result, false);
  assert.match(message, /registrada/);
  assert.match(message, /listado/);
  assert.equal(saved.estatus, 'enviada');
});

test('successful refresh replaces visible list and does not report a failure', async () => {
  let visible = [];
  const messages = [];
  const result = await refreshCommittedRequisitionList(async () => {
    const response = await readRequisitionList(async () => ({items: [{id: 'saved', estatus: 'aprobada'}], total: 1, limit: 25, offset: 0}));
    visible = response.items;
  }, (message) => messages.push(message));
  assert.equal(result, true);
  assert.equal(visible[0].estatus, 'aprobada');
  assert.deepEqual(messages, []);
});

test('retry performs another read after rejection', async () => {
  let attempts = 0;
  const fetchList = async () => {
    if (++attempts === 1) throw new Error('temporary read error');
    return {items: [], total: 0, limit: 25, offset: 0};
  };
  await assert.rejects(readRequisitionList(fetchList));
  const response = await readRequisitionList(fetchList);
  assert.equal(attempts, 2);
  assert.deepEqual(response.items, []);
});

test('page wiring clears read error and renders it before the empty state', () => {
  const source = readFileSync(new URL('./RequisitionsPage.jsx', import.meta.url), 'utf8');
  assert.match(source, /setListError\(""\);\s*setRequisitions\(response.items\)/);
  assert.match(source, /listError \? \([\s\S]*role="alert"[\s\S]*\) : requisitions.length === 0 \? \(/);
  assert.match(source, /refreshAfterMutation\(\);\s*setSuccess\(/);
  assert.match(source, /countRequisitionStates\(requisitions\)/);
});
