import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../../package.json', import.meta.url));
const parser = require('@babel/parser');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const feedbackUrl = new URL('./useCrmFormFeedback.js', import.meta.url);
const feedbackModule = existsSync(feedbackUrl) ? await import(feedbackUrl.href) : {};
function page(path) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const tree = parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });
  const component = tree.program.body.find(node => node.type === 'ExportDefaultDeclaration').declaration;
  function functionCode(name) {
    const node = [...tree.program.body, ...component.body.body]
      .find(node => node.type === 'FunctionDeclaration' && node.id.name === name);
    assert.ok(node, name);
    return source.slice(node.start, node.end);
  }
  return { source, tree, functionCode, actual: (name, context) => runInNewContext(`(${functionCode(name)})`, context) };
}
const quotes = page('./CrmQuotesView.jsx');
const opportunities = page('../CrmPage.jsx');
function feedback(kind, form) {
  const state = { message: '', fields: {}, clears: 0 };
  state.clear = () => { state.message = ''; state.fields = {}; state.clears++; };
  state.show = (error, current = form, override) => {
    const mapped = feedbackModule.mapCrmFormFeedback?.(error, kind, current, override)
      || { message: typeof error === 'string' ? error : error.message, fields: {} };
    Object.assign(state, mapped);
  };
  return state;
}
const quoteForm = () => ({ id: 'Q', cliente_id: 'C', titulo: 'Synthetic quote', items: [
  { local_id: 'L', descripcion: 'Synthetic service', cantidad: '2', precio_unitario: '100', descuento: '10', impuesto_porcentaje: '16' },
] });

test('F03 detail -> edit keeps one modal, closes detail and closing editor returns to list', async () => {
  const state = { detail: true, editor: false, quote: null };
  const quoteFeedback = feedback('quote', quoteForm());
  const context = {
    token: 'fixture', empresaId: 'fixture', setSubmitting() {}, setError() {}, setSuccess() {}, quoteFeedback,
    getCrmQuote: async () => ({ ...quoteForm(), fecha_emision: '2026-10-05' }), loadClientContactOptions: async () => {},
    mapQuoteResponseToForm: value => value, setQuoteForm: value => { state.quote = value; },
    setQuoteFormOpen: value => { state.editor = value; }, setQuoteDetailOpen: value => { state.detail = value; },
    setQuoteDetail() {}, resetQuoteForm() {},
  };
  context.closeQuoteDetailModal = quotes.actual('closeQuoteDetailModal', context);
  assert.equal(Number(state.detail) + Number(state.editor), 1);
  await quotes.actual('openQuoteEditModal', context)('Q');
  assert.equal(state.editor, true);
  assert.equal(state.detail, false);
  assert.equal(Number(state.detail) + Number(state.editor), 1);
  assert.equal(state.quote.id, 'Q');
  quotes.actual('closeQuoteFormModal', context)();
  assert.equal(state.editor, false);
  assert.equal(state.detail, false);
});

test('F03/F04 editor focus and feedback are scoped inside the real forms, not global modals', () => {
  for (const [view, id, state] of [[quotes, 'crm-quote-form', 'quoteFeedback'], [opportunities, 'crm-opportunity-form', 'opportunityFeedback']]) {
    const formStart = view.source.indexOf(`id="${id}"`);
    const formEnd = view.source.indexOf('</form>', formStart);
    const markup = view.source.slice(formStart, formEnd);
    assert.ok(markup.includes(`feedback={${state}}`));
    assert.ok(markup.includes(`onChangeCapture={${state}.clear}`));
    assert.ok(view.source.includes('useCrmFormFeedback('));
    assert.ok(view.source.includes(`${state}.fieldProps(`));
  }
});

function submitFixture(kind, { form, failure = null, validation = '', refreshFailure = false }) {
  const state = { calls: 0, global: '', success: 'Old success', closed: false, reset: false };
  const modal = feedback(kind, form);
  const common = {
    token: 'fixture', empresaId: 'fixture', setSubmitting() {}, setError: value => { state.global = value; },
    setSuccess: value => { state.success = value; },
  };
  const api = async () => { state.calls++; if (failure) throw failure; return { cliente_id: 'C' }; };
  const refresh = async () => { if (refreshFailure) throw new Error('Synthetic read failure'); };
  const context = kind === 'quote' ? {
    ...common, quoteForm: form, quoteFeedback: modal, validateQuoteForm: () => validation,
    buildQuotePayload: value => value, translateQuoteEditError: message => message,
    createCrmQuote: api, updateCrmQuote: api, quoteFilters: {}, quoteDetailOpen: false,
    setQuoteFormOpen: value => { state.closed = !value; }, resetQuoteForm: () => { state.reset = true; },
    loadQuotesPage: refresh, closeQuoteFormModal: () => { state.closed = true; },
  } : {
    ...common, opportunityForm: form, opportunityFeedback: modal, validateOpportunityForm: () => validation,
    buildOpportunityPayload: value => value, createCrmOpportunity: api, updateCrmOpportunity: api,
    setOpportunityFormOpen: value => { state.closed = !value; }, resetOpportunityForm: () => { state.reset = true; },
    loadSummaryData: refresh, loadOpportunitiesPage: async () => {}, loadOpportunityOptions: async () => {},
    opportunityFilters: {}, clientDetailOpen: false, closeOpportunityFormModal: () => { state.closed = true; },
  };
  const submit = (kind === 'quote' ? quotes : opportunities).actual(
    kind === 'quote' ? 'handleQuoteSubmit' : 'handleOpportunitySubmit', context);
  return { state, modal, submit };
}

test('F04 probability 101 stays in modal, marks probability, and corrected 100 can retry', async () => {
  const form = { id: 'O', cliente_id: 'C', titulo: 'Synthetic', probabilidad: '101' };
  const invalid = submitFixture('opportunity', { form, validation: 'La probabilidad debe estar entre 0 y 100.' });
  await invalid.submit({ preventDefault() {} });
  assert.equal(invalid.state.calls, 0);
  assert.ok(invalid.modal.message);
  assert.ok(invalid.modal.fields.probabilidad);
  assert.equal(invalid.state.global, '');
  assert.equal(invalid.state.success, '');
  assert.equal(invalid.state.closed, false);
  assert.equal(form.probabilidad, '101');
  invalid.modal.clear();
  assert.equal(invalid.modal.message, '');
  const valid = submitFixture('opportunity', { form: { ...form, probabilidad: '100' } });
  await valid.submit({ preventDefault() {} });
  assert.equal(valid.state.calls, 1);
  assert.equal(valid.state.closed, true);
  assert.ok(valid.state.success);
});

test('F04 quote discount rejection and quantity zero remain inside, without clearing values or success', async () => {
  for (const scenario of ['discount', 'quantity']) {
    const form = quoteForm();
    form.items[0][scenario === 'discount' ? 'descuento' : 'cantidad'] = scenario === 'discount' ? '201' : '0';
    const fixture = submitFixture('quote', {
      form, failure: scenario === 'discount' ? { status: 400, message: 'El descuento no puede superar el subtotal de la partida.' } : null,
      validation: scenario === 'quantity' ? 'La cantidad de cada partida debe ser mayor a cero.' : '',
    });
    await fixture.submit({ preventDefault() {} });
    assert.ok(fixture.modal.message);
    assert.ok(fixture.modal.fields[`items.0.${scenario === 'discount' ? 'descuento' : 'cantidad'}`]);
    assert.equal(fixture.state.closed, false);
    assert.equal(fixture.state.reset, false);
    assert.equal(fixture.state.success, '');
    assert.equal(fixture.state.global, '');
  }
});

test('F04 structured field locations are preferred; unknown backend errors never mark a wrong field', async () => {
  const structured = submitFixture('opportunity', { form: { probabilidad: '101' }, failure: {
    status: 422, message: 'Input should be less than or equal to 100',
    detail: [{ loc: ['body', 'probabilidad'], type: 'less_than_equal', msg: 'Input should be less than or equal to 100' }],
  } });
  await structured.submit({ preventDefault() {} });
  assert.ok(structured.modal.fields.probabilidad);
  for (const kind of ['quote', 'opportunity']) {
    const other = submitFixture(kind, { form: kind === 'quote' ? quoteForm() : { probabilidad: '100' },
      failure: { status: 500, message: 'SQLAlchemy Traceback SELECT secret' } });
    await other.submit({ preventDefault() {} });
    assert.ok(other.modal.message);
    assert.deepEqual(Object.keys(other.modal.fields), []);
    assert.doesNotMatch(other.modal.message, /SQL|Traceback|SELECT/);
    assert.equal(other.state.closed, false);
    assert.equal(other.state.success, '');
  }
});

test('F04 closing/reopening either editor clears old feedback', () => {
  for (const [view, name, key, form] of [[quotes, 'closeQuoteFormModal', 'quoteFeedback', quoteForm()],
    [opportunities, 'closeOpportunityFormModal', 'opportunityFeedback', { probabilidad: '101' }]]) {
    const modal = feedback(key === 'quoteFeedback' ? 'quote' : 'opportunity', form);
    modal.show('Old validation error');
    view.actual(name, { [key]: modal, setQuoteFormOpen() {}, resetQuoteForm() {},
      setOpportunityFormOpen() {}, resetOpportunityForm() {} })();
    assert.equal(modal.message, '');
    assert.deepEqual(Object.keys(modal.fields), []);
  }
});

test('F04 successful save followed by failed refresh remains visible outside the now-closed editor', async () => {
  for (const kind of ['quote', 'opportunity']) {
    const fixture = submitFixture(kind, { form: kind === 'quote' ? quoteForm() : { cliente_id: 'C', probabilidad: '100' }, refreshFailure: true });
    await fixture.submit({ preventDefault() {} });
    assert.equal(fixture.state.calls, 1);
    assert.equal(fixture.state.closed, true);
    assert.match(fixture.state.global, /se guardo.*actualizar/);
    assert.equal(fixture.modal.message, '');
  }
});

test('F03 reopening detail clears editor state and reloads the selected record', async () => {
  const state = { editor: true, detail: false, selected: 'old', loading: false };
  const quoteFeedback = feedback('quote', quoteForm());
  const context = { quoteFeedback, setQuoteFormOpen: value => { state.editor = value; }, resetQuoteForm() {},
    setQuoteDetailOpen: value => { state.detail = value; }, setQuoteDetail: value => { state.selected = value; },
    setDetailLoading: value => { state.loading = value; }, setError() {},
    loadQuoteDetail: async id => { assert.equal(state.selected, null); state.selected = id; } };
  context.closeQuoteFormModal = quotes.actual('closeQuoteFormModal', context);
  await quotes.actual('openQuoteDetailModal', context)('Q');
  assert.equal(state.editor, false);
  assert.equal(state.detail, true);
  assert.equal(state.selected, 'Q');
  assert.equal(state.loading, false);
});

test('F04 malformed/unknown structured details never assign an unrelated field', () => {
  for (const detail of [[null], [{ loc: ['body', 'unknown'], msg: 'Technical' }], [{ loc: ['body', 'items', 99, 'descuento'] }]]) {
    const result = feedbackModule.mapCrmFormFeedback({ status: 422, detail }, 'quote', quoteForm());
    assert.ok(result.message);
    assert.deepEqual(result.fields, {});
  }
});

test('F03 local editor focuses form, disables background, traps Tab and restores prior attributes', () => {
  const attributes = () => {
    const values = new Map();
    return { getAttribute: name => values.get(name) ?? null, setAttribute: (name, value) => values.set(name, value),
      removeAttribute: name => values.delete(name), closest: () => null };
  };
  const document = { activeElement: null };
  const first = { ...attributes(), focus: () => { document.activeElement = first; }, getClientRects: () => [{}] };
  const last = { ...attributes(), focus: () => { document.activeElement = last; }, getClientRects: () => [{}] };
  const previous = { ...attributes(), isConnected: true, focus: () => { document.activeElement = previous; } };
  document.activeElement = previous;
  const list = attributes(), header = attributes();
  header.setAttribute('inert', 'previous'); header.setAttribute('aria-hidden', 'previous');
  let onKey;
  const dialog = { ...attributes(), querySelectorAll: () => [first, last], contains: value => [first, last].includes(value),
    addEventListener: (name, fn) => { assert.equal(name, 'keydown'); onKey = fn; },
    removeEventListener: (name, fn) => { assert.equal(onKey, fn); onKey = null; } };
  const backdrop = {}, parent = { children: [list, backdrop] }, body = { children: [header, parent] };
  backdrop.parentElement = parent; parent.parentElement = body; document.body = body;
  const form = { ownerDocument: document, closest: selector => selector.includes('dialog') ? dialog : backdrop,
    querySelector: () => first };
  const clean = feedbackModule.activateCrmEditor(form);
  assert.equal(document.activeElement, first);
  assert.equal(dialog.getAttribute('aria-modal'), 'true');
  assert.equal(list.getAttribute('inert'), '');
  assert.equal(list.getAttribute('aria-hidden'), 'true');
  last.focus(); let prevented = false;
  onKey({ key: 'Tab', shiftKey: false, preventDefault: () => { prevented = true; } });
  assert.equal(prevented, true); assert.equal(document.activeElement, first);
  onKey({ key: 'Tab', shiftKey: true, preventDefault() {} });
  assert.equal(document.activeElement, last);
  onKey({ key: 'Escape', preventDefault: () => assert.fail('No global Escape changes') });
  clean();
  assert.equal(list.getAttribute('inert'), null);
  assert.equal(header.getAttribute('inert'), 'previous');
  assert.equal(header.getAttribute('aria-hidden'), 'previous');
  assert.equal(dialog.getAttribute('aria-modal'), null);
  assert.equal(document.activeElement, previous);
});

test('F04 focus goes to first invalid field or general summary without moving focus on correction', () => {
  const calls = [];
  const invalid = { focus: () => calls.push('field') }, summary = { focus: () => calls.push('summary') };
  feedbackModule.focusCrmFormError({ querySelector: selector => selector.includes('invalid') ? invalid : summary });
  feedbackModule.focusCrmFormError({ querySelector: selector => selector.includes('invalid') ? null : summary });
  assert.deepEqual(calls, ['field', 'summary']);
});

test('F03 real shared ModalShell renders one dialog/overlay and F04 summary is inside its form', () => {
  const source = readFileSync(new URL('../inventory/shared.jsx', import.meta.url), 'utf8');
  const tree = parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });
  const shell = tree.program.body.find(node => node.type === 'ExportNamedDeclaration' && node.declaration?.id?.name === 'ModalShell').declaration;
  const compiled = require('esbuild').transformSync(source.slice(shell.start, shell.end), {
    loader: 'jsx', jsxFactory: 'React.createElement', jsxFragment: 'React.Fragment',
  }).code;
  const ModalShell = runInNewContext(`${compiled}; ModalShell`, {
    React, safeDisplayText: value => value, ActionButton: props => React.createElement('button', { onClick: props.onClick }, props.children),
  });
  for (const editor of [false, true]) {
    const html = renderToStaticMarkup(React.createElement(React.Fragment, null,
      React.createElement(ModalShell, { open: !editor, title: 'Detail' }, 'Synthetic detail'),
      React.createElement(ModalShell, { open: editor, title: 'Editor' },
        React.createElement('form', { id: 'crm-quote-form' },
          React.createElement(feedbackModule.CrmFormError, { feedback: { message: 'Synthetic validation' } }),
          React.createElement('input', { name: 'items.0.descuento', 'aria-invalid': true }))),
    ));
    assert.equal((html.match(/role="dialog"/g) || []).length, 1);
    assert.equal((html.match(/class="inventory-modal-backdrop"/g) || []).length, 1);
    if (editor) {
      assert.match(html, /<form[^>]*>[\s\S]*role="alert"[\s\S]*Synthetic validation[\s\S]*<\/form>/);
      assert.match(html, /name="items\.0\.descuento" aria-invalid="true"/);
      assert.ok(!html.includes('Synthetic detail'));
    }
  }
});
