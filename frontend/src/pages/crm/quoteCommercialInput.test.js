import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { runInNewContext } from 'node:vm';

const require = createRequire(new URL('../../../package.json', import.meta.url));
const parser = require('@babel/parser');
const source = readFileSync(new URL('./CrmQuotesView.jsx', import.meta.url), 'utf8');
const shared = readFileSync(new URL('../inventory/shared.jsx', import.meta.url), 'utf8');
const helperUrl = new URL('./quoteCommercialInput.js', import.meta.url);
const helpers = existsSync(helperUrl) ? await import(helperUrl.href) : {};
const tree = parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });
function code(name) {
  const node = tree.program.body.find(item => item.type === 'FunctionDeclaration' && item.id.name === name);
  assert.ok(node, name);
  return source.slice(node.start, node.end);
}
const context = {
  normalizeDecimalInput: value => value.replace(',', '.').replace(/[^\d.]/g, ''),
  ...helpers,
};
for (const name of ['normalizeOptionalText', 'parseQuoteNumber', 'createLocalQuoteItem',
  'buildQuotePayload', 'validateQuoteForm', 'mapQuoteResponseToForm']) {
  context[name] = runInNewContext(`(${code(name)})`, context);
}
function form(percent) {
  return { cliente_id: 'synthetic-client', titulo: 'Synthetic quote', items: [{
    descripcion: 'Synthetic service', cantidad: '2', precio_unitario: '100', descuento: '10',
    impuesto_porcentaje: percent,
  }] };
}
function estimate(formValue) {
  const component = tree.program.body.find(item => item.type === 'ExportDefaultDeclaration').declaration;
  const node = component.body.body.filter(item => item.type === 'VariableDeclaration')
    .flatMap(item => item.declarations).find(item => item.id.name === 'quoteTotals');
  const calculate = node.init.arguments[0];
  return runInNewContext(`(${source.slice(calculate.start, calculate.end)})`, {
    ...context, quoteForm: formValue,
  })();
}

test('F02 civil emission/expiry retain the same day at UTC midnight and in -06', () => {
  const oldFunction = /export (function formatDate\(value\) \{[\s\S]*?\n\})/.exec(shared)[1];
  const formatter = helpers.formatQuoteCommercialDate
    || runInNewContext(`(${oldFunction})`);
  for (const zone of ['America/Mexico_City', 'UTC', 'Pacific/Honolulu']) {
    const result = spawnSync(process.execPath, ['-e',
      `const format=${formatter.toString()}; console.log(JSON.stringify(['2026-10-05','2026-01-01'].map(format)));`],
    { env: { ...process.env, TZ: zone }, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout), ['05/10/2026', '01/01/2026'], zone);
  }
});

test('F02 list/detail use civil formatting only; conversion timestamps keep existing formatter', () => {
  for (const field of ['quote.fecha_emision', 'quote.fecha_vencimiento',
    'quoteDetail.fecha_emision', 'quoteDetail.fecha_vencimiento']) {
    assert.ok(source.includes(`formatQuoteCommercialDate(${field})`), field);
  }
  assert.ok(source.includes('formatDate(quoteDetail.convertida_a_proyecto_at)'));
  assert.ok(source.includes('formatDate(quoteDetail.convertida_a_venta_at)'));
});

test('F02 civil formatter validates dates without interpreting instants or invalid calendar days', () => {
  const format = helpers.formatQuoteCommercialDate;
  assert.equal(format('2024-02-29'), '29/02/2024');
  for (const invalid of [null, '', '2026-02-29', '2026-13-01', '2026-10-32', '2026-10-05T00:00:00Z']) {
    assert.equal(format(invalid), '\u2014');
  }
});

test('F05 human percent is converted exactly once at the API boundary and in the estimate', () => {
  for (const [input, factor] of [['16', 0.16], ['16.00', 0.16], ['0', 0], ['100', 1], ['', 0], ['0.16', 0.0016]]) {
    const value = form(input);
    assert.equal(context.validateQuoteForm(value), '', input);
    assert.equal(Number(context.buildQuotePayload(value).items[0].impuesto_tasa), factor, input);
    const totals = estimate(value);
    assert.equal(totals.subtotal, 190);
    assert.ok(Math.abs(totals.impuesto - 190 * factor) < 1e-9);
    assert.ok(Math.abs(totals.total - (190 + 190 * factor)) < 1e-9);
  }
});

test('F05 invalid percentages block submit before either create or update API and retain form', async () => {
  const component = tree.program.body.find(item => item.type === 'ExportDefaultDeclaration').declaration;
  const node = component.body.body.find(item => item.type === 'FunctionDeclaration' && item.id.name === 'handleQuoteSubmit');
  for (const editing of [false, true]) {
    for (const input of ['101', '-1', 'invalid', 'Infinity', '16.001']) {
      let calls = 0, error = '', cleared = false, success = '';
      const quoteForm = { ...form(input), id: editing ? 'synthetic-quote' : '' };
      const submit = runInNewContext(`(${source.slice(node.start, node.end)})`, {
        ...context, quoteForm, token: 'fixture', empresaId: 'fixture', quoteFilters: {}, quoteDetailOpen: false,
        setError: value => { error = value; }, setSubmitting() {},
        setSuccess: value => { success = value; }, setQuoteFormOpen: () => { cleared = true; },
        resetQuoteForm: () => { cleared = true; }, translateQuoteEditError: message => message,
        createCrmQuote: async () => { calls++; return {}; }, updateCrmQuote: async () => { calls++; return {}; },
        loadQuotesPage: async () => {},
      });
      await submit({ preventDefault() {} });
      assert.equal(calls, 0, input);
      assert.ok(error, input);
      assert.equal(cleared, false);
      assert.equal(success, '');
      assert.equal(quoteForm.items[0].impuesto_porcentaje, input);
    }
  }
});

test('F05 edit maps legacy factors to percent without changing dates, totals or stored values', () => {
  for (const [factor, percent] of [['0.16', 16], ['0.0016', 0.16], ['0', 0], ['1', 100], ['16', 1600]]) {
    const quote = { id: 'synthetic-quote', cliente_id: 'synthetic-client', titulo: 'Synthetic',
      fecha_emision: '2026-10-05', fecha_vencimiento: '2026-10-15', total: '220.4000',
      items: [{ descripcion: 'Synthetic', cantidad: '2', precio_unitario: '100', descuento: '10', impuesto_tasa: factor }] };
    const mapped = context.mapQuoteResponseToForm(quote);
    assert.equal(Number(mapped.items[0].impuesto_porcentaje), percent);
    if (percent <= 100) assert.equal(Number(context.buildQuotePayload(mapped).items[0].impuesto_tasa), Number(factor));
    else assert.ok(context.validateQuoteForm(mapped));
    assert.equal(quote.fecha_emision, '2026-10-05');
    assert.equal(quote.total, '220.4000');
    assert.equal(quote.items[0].impuesto_tasa, factor);
  }
});

test('F05 UI states percent explicitly, preserves negative input and explains fractional percent', () => {
  assert.ok(source.includes('label="IVA (%)"'));
  assert.ok(source.includes('placeholder="16"'));
  assert.ok(source.includes('0.16 significa 0.16%'));
  assert.ok(!source.includes('"impuesto_porcentaje", normalizeDecimalInput(event.target.value)'));
});

test('quote PDF download still uses the existing ID/token/tenant and neutral failure message', async () => {
  const component = tree.program.body.find(item => item.type === 'ExportDefaultDeclaration').declaration;
  const node = component.body.body.find(item => item.type === 'FunctionDeclaration' && item.id.name === 'handleDownloadQuotePdf');
  for (const fail of [false, true]) {
    let payload, error = '', submitting;
    const download = runInNewContext(`(${source.slice(node.start, node.end)})`, {
      token: 'fixture', empresaId: 'tenant', setSubmitting: value => { submitting = value; }, setError: value => { error = value; },
      downloadCrmQuotePdf: async request => { payload = request; if (fail) throw new Error('technical failure'); },
    });
    await download('quote-id');
    assert.equal(payload.quoteId, 'quote-id');
    assert.equal(payload.empresaId, 'tenant');
    assert.equal(error, fail ? 'No se pudo generar el PDF de la cotizacion.' : '');
    assert.equal(submitting, false);
  }
});
