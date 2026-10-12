const modalStacks = new WeakMap();
const focusSelector = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]';

function restoreBackground(state) {
  for (const [element, inert, hidden] of state.background) {
    if (inert === null) element.removeAttribute("inert"); else element.setAttribute("inert", inert);
    if (hidden === null) element.removeAttribute("aria-hidden"); else element.setAttribute("aria-hidden", hidden);
  }
  state.background = [];
}

function isolateTop(state) {
  restoreBackground(state);
  const top = state.entries.at(-1);
  for (const entry of state.entries) entry.dialog.setAttribute("aria-modal", entry === top ? "true" : "false");
  if (!top) return;
  for (let branch = top.backdrop; branch?.parentElement; branch = branch.parentElement) {
    for (const sibling of branch.parentElement.children) {
      if (sibling === branch) continue;
      state.background.push([sibling, sibling.getAttribute("inert"), sibling.getAttribute("aria-hidden")]);
      sibling.setAttribute("inert", ""); sibling.setAttribute("aria-hidden", "true");
    }
    if (branch.parentElement === top.document.body) break;
  }
}

function visibleControls(root) {
  return Array.from(root?.querySelectorAll?.(focusSelector) || [])
    .filter(element => element.getClientRects().length && !element.closest("[inert]"));
}

function controls(entry) { return visibleControls(entry.dialog); }

function focusFirst(entry) {
  const editable = entry.initialFocus?.() || entry.dialog.querySelector('input:not([disabled]):not([readonly]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]):not([readonly])');
  (editable || controls(entry)[0])?.focus();
}

export function activateCrmModal(dialog, options = {}) {
  const document = options.document || dialog.ownerDocument;
  const backdrop = options.backdrop || dialog.closest(".inventory-modal-backdrop");
  if (!backdrop) return undefined;
  let state = modalStacks.get(document);
  if (!state) { state = { entries: [], background: [] }; modalStacks.set(document, state); }
  const parent = state.entries.at(-1);
  const entry = { dialog, document, backdrop, initialFocus: options.initialFocus,
    returnFocus: document.activeElement, fallbackFocus: parent?.fallbackFocus || parent?.returnFocus,
    returnRegion: document.activeElement?.closest(".crm-view-stack, main, [role='main']"),
    previousModal: dialog.getAttribute("aria-modal"), previousLabel: dialog.getAttribute("aria-label") };
  if (typeof options.title === "string") dialog.setAttribute("aria-label", options.title);
  state.entries.push(entry);
  isolateTop(state);
  const keydown = event => {
    if (state.entries.at(-1) !== entry) return;
    if (event.key === "Escape" && options.onEscape) {
      event.preventDefault(); event.stopPropagation?.(); options.onEscape();
    } else if (event.key === "Tab") {
      const list = controls(entry), first = list[0], last = list.at(-1);
      const boundary = event.shiftKey ? first : last, target = event.shiftKey ? last : first;
      if (target && (document.activeElement === boundary || !dialog.contains(document.activeElement))) {
        event.preventDefault(); target.focus();
      }
    }
  };
  dialog.addEventListener("keydown", keydown);
  focusFirst(entry);
  let closed = false;
  return () => {
    if (closed) return;
    closed = true;
    const wasTop = state.entries.at(-1) === entry;
    dialog.removeEventListener("keydown", keydown);
    state.entries = state.entries.filter(item => item !== entry);
    isolateTop(state);
    if (entry.previousModal === null) dialog.removeAttribute("aria-modal"); else dialog.setAttribute("aria-modal", entry.previousModal);
    if (entry.previousLabel === null) dialog.removeAttribute("aria-label"); else dialog.setAttribute("aria-label", entry.previousLabel);
    const top = state.entries.at(-1);
    if (wasTop) {
      const target = [entry.returnFocus, entry.fallbackFocus].find(element => element?.isConnected &&
        !element.closest("[inert]") && (!top || top.dialog.contains(element)));
      if (target) target.focus();
      else if (top) focusFirst(top);
      else (visibleControls(entry.returnRegion?.isConnected ? entry.returnRegion : document.body)[0])?.focus();
    }
    if (!top) modalStacks.delete(document);
  };
}

export function crmFormSignature(dialog) {
  return JSON.stringify(Array.from(dialog.querySelectorAll("form input, form select, form textarea"))
    .filter(element => !element.disabled && !element.readOnly && !["submit", "button"].includes(element.type))
    .map(element => [element.tagName, element.type, element.value, Boolean(element.checked)]));
}

export function requestCrmModalClose(dialog, baseline, onClose, onDirty) {
  if (dialog.querySelector('button[type="submit"]:disabled')) return "busy";
  if (crmFormSignature(dialog) !== baseline) { onDirty(); return "dirty"; }
  onClose();
  return "closed";
}
