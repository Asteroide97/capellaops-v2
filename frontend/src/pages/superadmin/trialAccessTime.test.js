import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { spawnSync } from 'node:child_process';

process.env.TZ = 'America/Mexico_City';
const source = readFileSync(new URL('../SuperadminPage.jsx', import.meta.url), 'utf8');
const require = createRequire(new URL('../../../package.json', import.meta.url));
const tree = require('@babel/parser').parse(source, { sourceType: 'module', plugins: ['jsx'] });
const component = tree.program.body.find(node => node.type === 'ExportDefaultDeclaration').declaration;
const helperUrl = new URL('./trialAccessTime.js', import.meta.url);
const helpers = existsSync(helperUrl) ? await import(helperUrl.href) : {};
const raw = '2026-06-17T17:04:00Z';

function action(name, context) {
  const node = component.body.body.find(node => node.type === 'FunctionDeclaration' && node.id.name === name);
  assert.ok(node, name);
  return runInNewContext(`(${source.slice(node.start, node.end)})`, context);
}

function ui(original = raw) {
  let form, stored = original;
  const sent = [], errors = [];
  const context = {
    ...helpers, Date, token: 'synthetic-fixture', actionReason: 'Synthetic test', selectedCompanyDetail: null,
    setBusy() {}, setError: value => { if (value) errors.push(value); }, setSuccess() {},
    setSelectedCompanyDetail: value => { context.selectedCompanyDetail = value; },
    setSelectedUserDetail() {}, setActiveTab() {}, loadPortalData: async () => {},
    setAccessForm: value => { form = value; context.accessForm = value; },
    getSuperadminCompanyDetail: async () => ({ id: 'synthetic-company', plan_code: 'basico', access_status: 'trial', trial_ends_at: stored }),
    updateCompanyAccess: async ({ payload }) => {
      sent.push(payload); stored = payload.trial_ends_at ?? stored;
      return { id: 'synthetic-company', plan_code: payload.plan_code, access_status: payload.access_status, trial_ends_at: stored };
    },
  };
  return { context, sent, errors, form: () => form,
    open: () => action('handleLoadCompanyDetail', context)('synthetic-company'),
    save: () => action('handleUpdateCompanyAccess', context)({ preventDefault() {} }),
  };
}

test('trial editor displays the same instant as the UTC-6 list using the real load handler', async () => {
  const page = ui();
  await page.open();
  assert.equal(page.form().trial_ends_at, '2026-06-17T11:04');
});

test('open/save unchanged preserves the full original timestamp including microseconds and offset', async () => {
  for (const original of [raw, '2026-06-17T17:04:05.123456+00:00', '2026-06-17T11:04:05.123456-06:00']) {
    const page = ui(original); await page.open(); await page.save();
    assert.equal(page.sent[0].trial_ends_at, original);
    assert.equal(page.errors.length, 0);
  }
});

test('changing plan/status alone does not shift expiration or drop fractional precision', async () => {
  const original = '2026-06-17T17:04:05.123456Z';
  const page = ui(original); await page.open();
  page.context.accessForm.plan_code = 'pro'; page.context.accessForm.access_status = 'active';
  await page.save();
  assert.equal(page.sent[0].trial_ends_at, original);
  assert.equal(page.sent[0].plan_code, 'pro');
  assert.equal(page.sent[0].access_status, 'active');
});

test('editing local time converts once and subsequent saves do not shift it again', async () => {
  const page = ui(); await page.open();
  page.context.accessForm.trial_ends_at = '2026-06-17T12:04:05.123';
  await page.save();
  assert.equal(page.sent[0].trial_ends_at, '2026-06-17T18:04:05.123Z');
  await page.save();
  assert.equal(page.sent[1].trial_ends_at, page.sent[0].trial_ends_at);
});

test('invalid local timestamp does not reach the API and gives a neutral form error', async () => {
  const page = ui(); await page.open();
  page.context.accessForm.trial_ends_at = 'not-a-date';
  await page.save();
  assert.equal(page.sent.length, 0);
  assert.ok(page.errors.some(message => message.includes('fecha')));
  assert.equal(page.context.accessForm.trial_ends_at, 'not-a-date');
});

test('local conversion preserves seconds/milliseconds; unchanged round-trip retains backend microseconds', () => {
  assert.equal(helpers.toTrialLocalInput('2026-06-17T17:04:05.123456Z'), '2026-06-17T11:04:05.123');
  assert.equal(helpers.serializeTrialInput('2026-06-17T11:04:05.123', '2026-06-17T17:04:05.123456Z'),
    '2026-06-17T17:04:05.123456Z');
  assert.equal(helpers.serializeTrialInput('', raw), null);
  assert.equal(helpers.serializeTrialInput('2026-06-17T12:04:05.123', '2026-06-17T17:04:05.123456Z'),
    '2026-06-17T18:04:05.123456Z');
});

test('editing at minute zero is valid; impossible calendar dates cannot roll over silently', () => {
  for (const [value, expected] of [['2026-06-17T12:00', '2026-06-17T18:00:00.000Z'],
    ['2026-06-17T00:00:00.000', '2026-06-17T06:00:00.000Z'],
    ['2026-06-17T12:00:05.120', '2026-06-17T18:00:05.120Z']]) {
    assert.equal(helpers.serializeTrialInput(value, raw), expected);
  }
  for (const value of ['2026-02-30T12:04', '2026-06-17T25:04', '2026-06-17T12:60', 'not-a-date']) {
    assert.throws(() => helpers.serializeTrialInput(value, raw), /fecha/);
  }
});

test('round-trip uses the browser timezone across midnight and DST overlap without changing the original', () => {
  assert.ok(helpers.toTrialLocalInput);
  for (const [zone, original, expected] of [
    ['America/Mexico_City', '2026-06-17T02:04:00Z', '2026-06-16T20:04'],
    ['UTC', raw, '2026-06-17T17:04'],
    ['America/New_York', '2026-11-01T06:30:00.123456Z', '2026-11-01T01:30:00.123'],
  ]) {
    const child = spawnSync(process.execPath, ['--input-type=module', '-e',
      `import {toTrialLocalInput,serializeTrialInput} from ${JSON.stringify(helperUrl.href)};
       const raw=${JSON.stringify(original)},local=toTrialLocalInput(raw);
       console.log(JSON.stringify([local,serializeTrialInput(local,raw)]));`],
      { env: { ...process.env, TZ: zone }, encoding: 'utf8' });
    assert.equal(child.status, 0, child.stderr);
    assert.deepEqual(JSON.parse(child.stdout), [expected, original]);
  }
});

test('Superadmin uses the same form mapper on load and after save; input accepts fractional seconds', () => {
  assert.ok(source.includes('step="0.001"'));
  assert.equal((source.match(/setAccessForm\(createCompanyAccessForm\(response\)\)/g) || []).length, 2);
  assert.ok(!source.includes('response.trial_ends_at.slice(0, 16)'));
  assert.ok(!source.includes('new Date(accessForm.trial_ends_at).toISOString()'));
});
