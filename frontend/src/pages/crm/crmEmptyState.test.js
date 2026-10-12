import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import * as contextHelpers from './crmListContext.js';

const require = createRequire(new URL('../../../package.json', import.meta.url));
const parser = require('@babel/parser');
const helperUrl = new URL('./crmEmptyState.js', import.meta.url);
const helpers = existsSync(helperUrl) ? await import(helperUrl.href) : {};
const classify = helpers.classifyCrmEmptyState || ((kind, page) => ({ mode: page.items.length ? 'data' : 'truly-empty' }));
const page = (filters, patch = {}) => ({ applied: { clientId: 'A', filters }, status: 'ready', error: '',
  items: [], meta: { total: 0, limit: 25, offset: 0 }, ...patch });

test('F06 unfiltered zero total is first use; all five filtered datasets are not', () => {
  for (const [kind, filters] of [['clients', { q: 'no-match' }], ['clients', { estatus: 'inactivo' }],
    ['contacts', { activo: 'true' }], ['opportunities', { q: 'no-match' }],
    ['activities', { completada: 'false', activo: 'true' }], ['quotes', { search: 'no-match' }]]) {
    assert.equal(classify(kind, page(filters)).mode, 'filtered-empty', kind);
    assert.equal(classify(kind, page({})).mode, 'truly-empty', kind);
  }
});

test('F06 read errors, loading and nonempty data never masquerade as first use', () => {
  for (const kind of ['clients', 'contacts', 'opportunities', 'activities', 'quotes']) {
    assert.equal(classify(kind, page({}, { status: 'error', error: 'Synthetic failure' })).mode, 'error');
    assert.equal(classify(kind, page({}, { status: 'loading' })).mode, 'loading');
    assert.equal(classify(kind, page({}, { items: [{ id: 'Synthetic' }], meta: { total: 1, limit: 25, offset: 0 } })).mode, 'data');
  }
});

test('F06 contacts require their existing client context and clear never removes it', () => {
  assert.equal(classify('contacts', { ...page({}), applied: { clientId: '', filters: {} } }).mode, 'selection');
  const cleared = helpers.clearCrmFilters?.('contacts', { q: 'name', activo: 'true', client_id: 'A', limit: 25, offset: 50 });
  assert.equal(cleared?.client_id, 'A');
  assert.equal(cleared?.activo, '');
  assert.equal(cleared?.q, '');
  assert.equal(cleared?.offset, 0);
});

test('F06 clear can recover inactive clients, completed activities and draft quotes', () => {
  const cases = [['clients', { q: 'none', estatus: 'activo', tipo: 'cliente' }],
    ['activities', { q: '', tipo: '', activo: 'true', completada: 'false', vencidas: 'true' }],
    ['quotes', { search: 'none', estatus: 'aceptada', cliente_id: 'A', oportunidad_id: 'O' }]];
  for (const [kind, filters] of cases) {
    const cleared = helpers.clearCrmFilters?.(kind, { ...filters, limit: 25, offset: 0 });
    assert.equal(helpers.activeCrmFilters?.(kind, cleared)?.length, 0, kind);
  }
});

test('F06 only applied filters classify empty state; pagination is not proof of an empty database', () => {
  const applied = page({ q: 'OLD' });
  assert.equal(classify('clients', applied).mode, 'filtered-empty');
  assert.match(helpers.activeCrmFilters?.('clients', applied.applied.filters)?.join(' ') || '', /OLD/);
  assert.equal(classify('clients', page({}, { meta: { total: 10, limit: 25, offset: 25 } })).mode, 'filtered-empty');
});

test('F06 search text is displayed verbatim, including underscores', () => {
  assert.deepEqual(helpers.activeCrmFilters('clients', { q: 'QA_NO_EXISTE' }), ['Busqueda: QA_NO_EXISTE']);
  assert.deepEqual(helpers.activeCrmFilters('quotes', { search: 'COT_0001' }), ['Busqueda: COT_0001']);
});

test('F06 real screens use the same state renderer with a clear action, without changing Pipeline', () => {
  const crm = readFileSync(new URL('../CrmPage.jsx', import.meta.url), 'utf8');
  const quotes = readFileSync(new URL('./CrmQuotesView.jsx', import.meta.url), 'utf8');
  for (const kind of ['clients', 'contacts', 'opportunities', 'activities']) {
    assert.ok(crm.includes(`kind="${kind}"`), kind);
  }
  assert.ok(quotes.includes('kind="quotes"'));
  assert.ok(crm.includes('onClear={clearContactFilters}'));
  assert.ok(crm.includes('hasOpportunityFilters(opportunityAppliedFilters)'));
});

test('F06 real clients/activity/quote reads record failures as errors, not empty success', async () => {
  for (const [file, name, setter, request, ref] of [['../CrmPage.jsx', 'loadClientsPage', 'setClientPage', 'listCrmClients', 'clientRequestRef'],
    ['../CrmPage.jsx', 'loadActivitiesPage', 'setActivityPage', 'listCrmActivities', 'activityRequestRef'],
    ['./CrmQuotesView.jsx', 'loadQuotesPage', 'setQuotePage', 'listCrmQuotes', 'quoteRequestRef']]) {
    const source = readFileSync(new URL(file, import.meta.url), 'utf8');
    const tree = parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });
    const component = tree.program.body.find(node => node.type === 'ExportDefaultDeclaration').declaration;
    const fn = component.body.body.find(node => node.type === 'FunctionDeclaration' && node.id.name === name);
    let snapshot = page({});
    const context = { ...contextHelpers, token: 'fixture', empresaId: 'T', clientFilters: {}, activityFilters: {}, quoteFilters: {},
      [ref]: { current: 0 }, crmReadScopeRef: { current: { token: 'fixture', empresaId: 'T' } },
      quoteReadScopeRef: { current: { token: 'fixture', empresaId: 'T' } },
      [setter]: value => { snapshot = value; }, [request]: async () => { throw new Error('Synthetic read failure'); },
      parseBooleanFilter: () => undefined, setClients() {}, setClientMeta() {}, setActivities() {}, setActivityMeta() {}, setQuotes() {}, setQuoteMeta() {} };
    await runInNewContext(`(${source.slice(fn.start, fn.end)})`, context)({ limit: 25, offset: 0 }).catch(() => {});
    assert.equal(snapshot.status, 'error', name);
    assert.equal(classify('clients', snapshot).mode, 'error');
  }
});
