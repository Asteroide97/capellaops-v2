import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { activateCrmEditor } from './useCrmFormFeedback.js';

const url = new URL('./crmModalFocus.js', import.meta.url);
const module = existsSync(url) ? await import(url.href) : {};
function dom() {
  const document = { activeElement: null };
  function element() {
    const attrs = new Map();
    const node = { ownerDocument: document, children: [], parentElement: null, isConnected: true, disabled: false, readOnly: false,
      getAttribute: name => attrs.get(name) ?? null, setAttribute: (name, value) => attrs.set(name, value), removeAttribute: name => attrs.delete(name),
      getClientRects: () => [{}], focus: () => { document.activeElement = node; },
      closest: selector => {
        for (let current = node; current; current = current.parentElement) {
          if (selector === '[inert]' && current.getAttribute('inert') !== null) return current;
          if (selector.includes('dialog') && current.role === 'dialog') return current;
          if (selector.includes('backdrop') && current.backdrop) return current;
        }
        return null;
      } };
    return node;
  }
  const body = element(), trigger = element(); document.body = body; trigger.parentElement = body; body.children = [trigger]; trigger.focus();
  function modal() {
    const backdrop = element(), dialog = element(), input = element(), last = element();
    backdrop.backdrop = true; dialog.role = 'dialog'; input.tagName = 'INPUT'; input.type = 'text'; input.value = ''; last.tagName = 'BUTTON';
    backdrop.parentElement = body; body.children.push(backdrop); backdrop.children = [dialog]; dialog.parentElement = backdrop;
    input.parentElement = dialog; last.parentElement = dialog; dialog.children = [input, last];
    const listeners = new Set();
    dialog.addEventListener = (name, fn) => { assert.equal(name, 'keydown'); listeners.add(fn); };
    dialog.removeEventListener = (name, fn) => listeners.delete(fn);
    dialog.querySelectorAll = selector => selector.includes('select') && !selector.includes('button') ? [input] : [input, last];
    dialog.querySelector = selector => selector.includes(':disabled') ? null : input;
    dialog.contains = node => [input, last, dialog].includes(node);
    const form = { ownerDocument: document, closest: selector => selector.includes('dialog') ? dialog : backdrop, querySelector: () => input };
    const key = (key, shiftKey = false) => {
      let prevented = false;
      for (const fn of [...listeners]) fn({ key, shiftKey, preventDefault: () => { prevented = true; }, stopPropagation() {} });
      return prevented;
    };
    return { backdrop, dialog, input, last, form, listeners, key };
  }
  return { document, trigger, modal };
}
const activate = (dialog, options, form) => module.activateCrmModal ? module.activateCrmModal(dialog, options) : activateCrmEditor(form);

test('F09 clean Escape closes; focus/Tab remain inside and cleanup restores trigger/inert', () => {
  const env = dom(), modal = env.modal(); let closed = 0;
  const cleanup = activate(modal.dialog, { onEscape: () => { closed++; } }, modal.form);
  assert.equal(env.document.activeElement, modal.input);
  assert.equal(env.trigger.getAttribute('inert'), '');
  modal.last.focus(); assert.equal(modal.key('Tab'), true); assert.equal(env.document.activeElement, modal.input);
  assert.equal(modal.key('Tab', true), true); assert.equal(env.document.activeElement, modal.last);
  modal.key('Escape'); assert.equal(closed, 1);
  cleanup();
  assert.equal(env.document.activeElement, env.trigger);
  assert.equal(env.trigger.getAttribute('inert'), null);
  assert.equal(modal.listeners.size, 0);
});

test('F09 dirty closing requests confirmation, preserves values and does not silently close', () => {
  const env = dom(), modal = env.modal();
  const baseline = module.crmFormSignature?.(modal.dialog);
  modal.input.value = 'Unsaved synthetic name';
  let closed = 0, dirty = 0;
  if (module.requestCrmModalClose) module.requestCrmModalClose(modal.dialog, baseline, () => { closed++; }, () => { dirty++; });
  else closed++;
  assert.equal(closed, 0);
  assert.equal(dirty, 1);
  assert.equal(modal.input.value, 'Unsaved synthetic name');
  modal.input.value = '';
  module.requestCrmModalClose(modal.dialog, baseline, () => { closed++; }, () => { dirty++; });
  assert.equal(closed, 1);
});

test('F09 only top CRM modal is interactive and child cleanup does not release background', () => {
  const env = dom(), parent = env.modal();
  const closeParent = activate(parent.dialog, {}, parent.form);
  const child = env.modal();
  const closeChild = activate(child.dialog, {}, child.form);
  assert.equal(parent.backdrop.getAttribute('inert'), '');
  closeParent();
  assert.equal(env.trigger.getAttribute('inert'), '');
  assert.equal(child.dialog.getAttribute('aria-modal'), 'true');
  closeChild();
  assert.equal(env.trigger.getAttribute('inert'), null);
});

test('F09 consecutive openings do not accumulate listeners or reuse an old trigger', () => {
  const env = dom();
  for (let i = 0; i < 2; i++) {
    const modal = env.modal(); let closed = 0;
    const cleanup = activate(modal.dialog, { onEscape: () => { closed++; } }, modal.form);
    assert.equal(modal.listeners.size, 1);
    modal.key('Escape'); assert.equal(closed, 1);
    cleanup(); assert.equal(modal.listeners.size, 0);
    assert.equal(env.document.activeElement, env.trigger);
  }
});

test('F09 all CRM modals use one adapter; previous form feedback does not add a second trap', () => {
  for (const path of ['../CrmPage.jsx', './CrmQuotesView.jsx']) {
    const source = readFileSync(new URL(path, import.meta.url), 'utf8');
    assert.ok(source.includes('CrmModalShell as ModalShell'));
  }
  const feedback = readFileSync(new URL('./useCrmFormFeedback.js', import.meta.url), 'utf8');
  assert.ok(!feedback.includes('return activateCrmEditor(formRef.current)'));
});

test('F09 removed row trigger falls back to a visible action instead of leaving focus on the body', () => {
  const env = dom(), modal = env.modal();
  const cleanup = activate(modal.dialog, {}, modal.form);
  env.trigger.isConnected = false;
  const replacement = { getClientRects: () => [{}], closest: () => null, focus: () => { env.document.activeElement = replacement; } };
  env.document.body.querySelectorAll = () => [replacement];
  cleanup();
  assert.equal(env.document.activeElement, replacement);
});

test('F09 repeated Escape during discard confirmation retains the original return field', () => {
  const source = readFileSync(new URL('./CrmModalShell.jsx', import.meta.url), 'utf8');
  const require = createRequire(new URL('../../../package.json', import.meta.url));
  const tree = require('@babel/parser').parse(source, { sourceType: 'module', plugins: ['jsx'] });
  let request;
  const walk = node => {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'AssignmentExpression' && node.left?.object?.name === 'requestRef') request = node.right;
    Object.values(node).forEach(value => Array.isArray(value) ? value.forEach(walk) : value && typeof value === 'object' ? walk(value) : null);
  };
  walk(tree);
  const originalField = {}, noticeButton = {};
  const returnToFieldRef = { current: originalField };
  let noticeFocused = false;
  runInNewContext(`(${source.slice(request.start, request.end)})`, {
    confirmDiscard: true, returnToFieldRef,
    noticeRef: { current: { querySelector: () => ({ focus: () => { noticeFocused = true; } }) } },
    rootRef: { current: { querySelector: () => ({ ownerDocument: { activeElement: noticeButton } }) } },
    baselineRef: { current: '' }, closeRef: { current() {} }, setConfirmDiscard() {},
    requestCrmModalClose: (dialog, baseline, close, dirty) => dirty(),
  })();
  assert.equal(returnToFieldRef.current, originalField);
  assert.equal(noticeFocused, true);
});
