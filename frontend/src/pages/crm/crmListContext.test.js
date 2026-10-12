import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { mapCrmFormFeedback } from './useCrmFormFeedback.js';

const require = createRequire(new URL('../../../package.json', import.meta.url));
const parser = require('@babel/parser');
const source = readFileSync(new URL('../CrmPage.jsx', import.meta.url), 'utf8');
const tree = parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });
const component = tree.program.body.find(node => node.type === 'ExportDefaultDeclaration').declaration;
const helperUrl = new URL('./crmListContext.js', import.meta.url);
const helpers = existsSync(helperUrl) ? await import(helperUrl.href) : {};
function code(name) {
  const node = [...tree.program.body, ...component.body.body].find(node => node.type === 'FunctionDeclaration' && node.id.name === name);
  assert.ok(node, name);
  return source.slice(node.start, node.end);
}
const actual = (name, context) => runInNewContext(`(${code(name)})`, context);
const filters = { q: '', activo: 'true', limit: 25, offset: 0 };
const opportunityFilters = { q: '', etapa: '', activa: '', limit: 25, offset: 0 };
const response = client => ({ items: [{ id: client + '-contact', cliente_id: client, empresa_id: 'T' }], total: 1, limit: 25, offset: 0 });
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function listFixture() {
  const state = { contact: { applied: { clientId: 'A', filters }, items: response('A').items, meta: response('A'), status: 'ready', error: '' },
    opportunity: { applied: { filters: opportunityFilters }, items: [], meta: { total: 0, limit: 25, offset: 0 }, status: 'ready', error: '' }, draft: 'A', draftFilters: filters, calls: [] };
  const context = { ...helpers, token: 'fixture', empresaId: 'T', defaultContactFilters: filters, defaultOpportunityFilters: opportunityFilters,
    EMPTY_META: { total: 0, limit: 25, offset: 0 }, contactRequestRef: { current: 0 }, opportunityRequestRef: { current: 0 },
    crmReadScopeRef: { current: { token: 'fixture', empresaId: 'T' } },
    contactAppliedRef: { get current() { return state.contact.applied; }, set current(value) { state.contact.applied = value; } },
    opportunityAppliedFiltersRef: { get current() { return state.opportunity.applied.filters; }, set current(value) { state.opportunity.applied.filters = value; } },
    parseBooleanFilter: value => value === 'true' ? true : value === 'false' ? false : undefined,
    get contactClientId() { return state.draft; }, get contactFilters() { return state.draftFilters; },
    get contactApplied() { return state.contact.applied; }, get opportunityAppliedFilters() { return state.opportunity.applied.filters; },
    opportunityFilters, setContactPage: value => { state.contact = value; }, setOpportunityPage: value => { state.opportunity = value; },
    setContacts: value => { state.contact.items = value; }, setContactMeta: value => { state.contact.meta = value; },
    setOpportunities: value => { state.opportunity.items = value; }, setOpportunityMeta: value => { state.opportunity.meta = value; },
    setContactClientId: value => { state.draft = value; }, setContactFilters: value => { state.draftFilters = value; },
    setOpportunityFilters() {}, setError() {}, loadClientContactOptions: async () => [],
    listCrmClientContacts: async request => { state.calls.push(request); return response(request.clientId); },
    listCrmOpportunities: async () => ({ items: [], total: 0, limit: 25, offset: 0 }),
  };
  context.loadContactsPage = actual('loadContactsPage', context);
  context.loadOpportunitiesPage = actual('loadOpportunitiesPage', context);
  return { state, context };
}

test('F01 applied client and rows change together; edited draft does not affect refresh', async () => {
  const { state, context } = listFixture();
  state.draft = 'B';
  await context.loadContactsPage();
  assert.equal(state.calls[0].clientId, 'A');
  assert.equal(state.contact.applied.clientId, 'A');
  assert.equal(state.contact.items[0].cliente_id, 'A');
  await actual('applyContactFilters', context)(filters, 'B');
  assert.equal(state.contact.applied.clientId, 'B');
  assert.equal(state.contact.items[0].cliente_id, 'B');
});

test('F01 stale A after B, stale failures and reads from a previous tenant cannot replace B', async () => {
  for (const oldFails of [false, true]) {
    const { state, context } = listFixture(), a = deferred(), b = deferred();
    context.listCrmClientContacts = request => request.clientId === 'A' ? a.promise : b.promise;
    const first = context.loadContactsPage('A', filters), second = context.loadContactsPage('B', filters);
    b.resolve(response('B')); await second;
    if (oldFails) a.reject(new Error('Old read failed')); else a.resolve(response('A'));
    await first.catch(() => {});
    assert.equal(state.contact.items[0].cliente_id, 'B');
    assert.equal(state.contact.applied.clientId, 'B');
  }
  const { state, context } = listFixture(), pending = deferred();
  context.listCrmClientContacts = () => pending.promise;
  const read = context.loadContactsPage('A', filters);
  context.crmReadScopeRef.current = { token: 'other', empresaId: 'Other' };
  pending.resolve(response('A')); await read;
  assert.equal(state.contact.items.length, 0);
});

test('F01 loading/error remove old rows, wrong client responses are rejected, no client requires selection', async () => {
  const { state, context } = listFixture(), pending = deferred();
  context.listCrmClientContacts = () => pending.promise;
  const read = context.loadContactsPage('B', filters);
  assert.equal(state.contact.status, 'loading');
  assert.equal(state.contact.items.length, 0);
  pending.reject(new Error('Read failed')); await read.catch(() => {});
  assert.equal(state.contact.status, 'error');
  assert.ok(state.contact.error);
  assert.equal(state.contact.items.length, 0);
  context.listCrmClientContacts = async () => response('A');
  await context.loadContactsPage('B', filters);
  assert.equal(state.contact.status, 'error');
  await context.loadContactsPage('', filters);
  assert.equal(state.contact.applied.clientId, '');
  assert.equal(state.contact.items.length, 0);
});

test('F01 creating contact from detail B refreshes applied agenda A without changing draft', async () => {
  const { state, context } = listFixture();
  Object.assign(context, { contactForm: { id: '', client_id: 'B' }, validateContactForm: () => '', buildContactPayload: value => value,
    createCrmContact: async () => ({}), setSubmitting() {}, setSuccess() {}, setContactFormOpen() {}, resetContactForm() {},
    clientDetailOpen: true, clientDetail: { id: 'B' }, loadClientDetailBundle: async () => {} });
  await actual('handleContactSubmit', context)({ preventDefault() {} });
  assert.equal(state.draft, 'A');
  assert.equal(state.contact.applied.clientId, 'A');
  assert.equal(state.contact.items[0].cliente_id, 'A');
});

test('F01 clear search/status keeps applied client, not a pending draft client', async () => {
  const { state, context } = listFixture();
  state.draft = 'B'; state.draftFilters = { ...filters, q: 'no-match', activo: 'false' };
  await actual('clearContactFilters', context)();
  assert.equal(state.draft, 'A');
  assert.equal(state.contact.applied.clientId, 'A');
  assert.equal(state.contact.applied.filters.q, '');
  assert.equal(state.contact.applied.filters.activo, '');
});

test('F07 Pipeline shows applied filters, clear, filtered empty and explicit global KPI scope', () => {
  const pipeline = source.slice(source.indexOf('{activeView === "pipeline" ?'), source.indexOf('{activeView === "quotes" ?'));
  assert.ok(pipeline.includes('describeOpportunityFilters(opportunityAppliedFilters)'));
  assert.ok(pipeline.includes('Limpiar'));
  assert.ok(pipeline.includes('Sin resultados'));
  assert.ok(pipeline.includes('global'));
  assert.ok(source.includes('nextFilters = opportunityAppliedFiltersRef.current'));
  const description = helpers.describeOpportunityFilters?.({ ...opportunityFilters, q: 'QA_NO_EXISTE', etapa: 'nueva', activa: 'true' });
  assert.match(description || '', /QA_NO_EXISTE/);
  assert.equal(helpers.hasOpportunityFilters?.(opportunityFilters), false);
});

test('F07 opportunity applied filters and rows are latest-only and remain separate from drafts', async () => {
  const { state, context } = listFixture(), a = deferred(), b = deferred();
  context.listCrmOpportunities = request => request.filters.q === 'A' ? a.promise : b.promise;
  const first = context.loadOpportunitiesPage({ ...opportunityFilters, q: 'A' });
  const second = context.loadOpportunitiesPage({ ...opportunityFilters, q: 'B' });
  b.resolve({ items: [{ id: 'B', empresa_id: 'T' }], total: 1, limit: 25, offset: 0 }); await second;
  a.resolve({ items: [{ id: 'A', empresa_id: 'T' }], total: 1, limit: 25, offset: 0 }); await first;
  assert.equal(state.opportunity.applied.filters.q, 'B');
  assert.equal(state.opportunity.items[0].id, 'B');
});

test('F08 actual amount input preserves sign/text; validation blocks API and localizes amount', () => {
  const controls = [];
  const walk = node => {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'JSXOpeningElement' && node.name.name === 'input') controls.push(node);
    for (const value of Object.values(node)) if (Array.isArray(value)) value.forEach(walk); else if (value && typeof value === 'object') walk(value);
  };
  walk(tree);
  const input = controls.find(node => node.attributes.some(attr => attr.name?.name === 'value' && attr.value?.expression?.property?.name === 'monto_estimado'));
  const handler = input.attributes.find(attr => attr.name?.name === 'onChange').value.expression;
  for (const value of ['-1', '-0.01', 'invalid', 'Infinity']) {
    let form = { cliente_id: 'C', titulo: 'Synthetic', monto_estimado: '0', probabilidad: '50' };
    const context = { ...helpers, normalizeDecimalInput: v => v.replace(',', '.').replace(/[^\d.]/g, ''),
      setOpportunityForm: updater => { form = updater(form); } };
    runInNewContext(`(${source.slice(handler.start, handler.end)})`, context)({ target: { value } });
    assert.equal(form.monto_estimado, value);
    const message = actual('validateOpportunityForm', context)(form);
    assert.ok(message);
    const feedback = mapCrmFormFeedback(message, 'opportunity', form);
    assert.ok(feedback.fields.monto_estimado);
  }
});

test('F08 zero/positive/empty/comma keep contract and correcting negative can save', () => {
  const context = { ...helpers, normalizeOptionalText: value => value || null };
  for (const [input, expected] of [['0', 0], ['1234.56', 1234.56], ['', 0], ['1234,56', 1234.56]]) {
    const form = { cliente_id: 'C', titulo: 'Synthetic', monto_estimado: input, probabilidad: '50' };
    assert.equal(actual('validateOpportunityForm', context)(form), '');
    assert.equal(actual('buildOpportunityPayload', context)(form).monto_estimado, expected);
  }
});

test('F08 actual submit blocks invalid amount, preserves values, and correction saves once', async () => {
  const state = { calls: [], error: '', fields: {}, closed: false, success: '', reset: false };
  let form = { id: 'O', cliente_id: 'C', titulo: 'Synthetic', monto_estimado: '-1', probabilidad: '50' };
  const context = { ...helpers, normalizeOptionalText: value => value || null, opportunityAppliedFilters: opportunityFilters,
    token: 'fixture', empresaId: 'T', opportunityFilters, clientDetailOpen: false,
    get opportunityForm() { return form; }, setSubmitting() {}, setError() {}, setSuccess: value => { state.success = value; },
    opportunityFeedback: { clear: () => { state.error = ''; state.fields = {}; },
      show: message => Object.assign(state, { error: message, fields: mapCrmFormFeedback(message, 'opportunity', form).fields }) },
    updateCrmOpportunity: async ({ payload }) => { state.calls.push(payload); },
    closeOpportunityFormModal: () => { state.closed = true; }, loadSummaryData: async () => {},
    loadOpportunitiesPage: async () => {}, loadOpportunityOptions: async () => {} };
  context.validateOpportunityForm = actual('validateOpportunityForm', context);
  context.buildOpportunityPayload = actual('buildOpportunityPayload', context);
  const submit = actual('handleOpportunitySubmit', context);
  for (const value of ['-1', '-0.01', 'invalid', 'Infinity']) {
    form = { ...form, monto_estimado: value };
    await submit({ preventDefault() {} });
    assert.equal(state.calls.length, 0);
    assert.ok(state.fields.monto_estimado);
    assert.equal(form.monto_estimado, value);
    assert.equal(state.closed, false);
    assert.equal(state.success, '');
    assert.throws(() => context.buildOpportunityPayload(form));
  }
  form = { ...form, monto_estimado: '1234.56' };
  await submit({ preventDefault() {} });
  assert.equal(state.calls.length, 1);
  assert.equal(state.calls[0].monto_estimado, 1234.56);
  assert.equal(state.calls[0].probabilidad, 50);
  assert.equal(state.closed, true);
  assert.ok(state.success);
});

test('F01 real client selector only edits draft; table header/pagination use applied context', async () => {
  const nodes = [];
  function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'JSXOpeningElement' && node.name.name === 'select') nodes.push(node);
    Object.values(node).forEach(value => Array.isArray(value) ? value.forEach(walk) : value && typeof value === 'object' ? walk(value) : null);
  }
  walk(tree);
  const select = nodes.find(node => node.attributes.some(attr => attr.name?.name === 'value' && attr.value?.expression?.name === 'contactClientId'));
  const handler = select.attributes.find(attr => attr.name?.name === 'onChange').value.expression;
  let client = 'A';
  await runInNewContext(`(${source.slice(handler.start, handler.end)})`, {
    setContactClientId: value => { client = value; },
    loadClientContactOptions: () => assert.fail('Draft must not fetch'), applyContactFilters: () => assert.fail('Draft must not apply'),
  })({ target: { value: 'B' } });
  assert.equal(client, 'B');
  assert.ok(source.includes('item.id === contactApplied.clientId'));
  const section = source.slice(source.indexOf('{activeView === "contacts" ?'), source.indexOf('{activeView === "opportunities" ?'));
  assert.ok(section.includes('Cliente aplicado:'));
  assert.ok(section.includes('loadContactsPage(contactApplied.clientId, { ...contactApplied.filters'));
  assert.ok(section.includes('contactPage.status === "error"'));
});

test('F07 tabs preserve shared applied filters and clear restores unfiltered results', async () => {
  const { state, context } = listFixture();
  context.listCrmOpportunities = async request => request.filters.q
    ? { items: [], total: 0, limit: 25, offset: 0 }
    : { items: [{ id: 'O', empresa_id: 'T' }], total: 1, limit: 25, offset: 0 };
  await actual('applyOpportunityFilters', context)({ ...opportunityFilters, q: 'QA_NO_EXISTE' });
  assert.equal(state.opportunity.applied.filters.q, 'QA_NO_EXISTE');
  assert.equal(state.opportunity.items.length, 0);
  assert.ok(helpers.hasOpportunityFilters(state.opportunity.applied.filters));
  assert.ok(!code('setCrmView').includes('setOpportunityFilters'));
  assert.ok(!code('setCrmView').includes('loadOpportunitiesPage'));
  await actual('applyOpportunityFilters', context)(opportunityFilters);
  assert.equal(helpers.hasOpportunityFilters(state.opportunity.applied.filters), false);
  assert.equal(state.opportunity.items[0].id, 'O');
});

test('F01/F07 passive refresh from an old render uses current applied context, not its captured filter', async () => {
  const { state, context } = listFixture();
  const captured = { ...context };
  const oldContactRefresh = actual('loadContactsPage', captured);
  const oldOpportunityRefresh = actual('loadOpportunitiesPage', captured);
  await context.loadContactsPage('B', filters);
  await oldContactRefresh();
  assert.equal(state.calls.at(-1).clientId, 'B');
  assert.equal(state.contact.applied.clientId, 'B');
  context.listCrmOpportunities = async request => ({ items: [], total: 0, limit: 25, offset: 0, q: request.filters.q });
  captured.listCrmOpportunities = context.listCrmOpportunities;
  await context.loadOpportunitiesPage({ ...opportunityFilters, q: 'LATEST' });
  await oldOpportunityRefresh();
  assert.equal(state.opportunity.applied.filters.q, 'LATEST');
});

test('F01 applied client outside the options page is still identified from the current client rows', () => {
  const node = component.body.body.filter(item => item.type === 'VariableDeclaration').flatMap(item => item.declarations)
    .find(item => item.id.name === 'selectedContactClient').init.arguments[0];
  const resolve = runInNewContext(`(${source.slice(node.start, node.end)})`, {
    clientOptions: [{ id: 'A', nombre_comercial: 'Synthetic A' }],
    clients: [{ id: 'B', nombre_comercial: 'Synthetic B' }],
    contacts: [], contactApplied: { clientId: 'B' },
  });
  assert.equal(resolve()?.id, 'B');
  assert.equal(resolve()?.nombre_comercial, 'Synthetic B');
});
