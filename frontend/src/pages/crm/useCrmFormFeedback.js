import { createElement, useEffect, useState } from "react";

const emptyFeedback = () => ({ message: "", fields: {} });
const technicalMessage = /SQL|traceback|backend|payload|endpoint|Internal Server Error|Failed to fetch|Not Found|\[object Object\]|^\s*[{[<]/i;

export function mapCrmFormFeedback(error, kind, form, override) {
  const fields = {};
  const detail = error?.detail ?? error?.data?.detail;
  const raw = override || (typeof error === "string" ? error : error?.message);
  const fallback = "No se pudo guardar. Revisa los datos e intenta nuevamente.";
  const message = typeof raw === "string" && raw.trim() && !technicalMessage.test(raw)
    ? raw.trim() : fallback;
  if (error?.status >= 500) return { message: fallback, fields };
  const fieldMessage = (name) => ({
    probabilidad: "La probabilidad debe estar entre 0 y 100.",
    monto_estimado: "Revisa el monto estimado; debe ser mayor o igual a cero.",
    cliente_id: "Revisa el cliente seleccionado.",
    titulo: "Revisa el titulo.",
    cantidad: "La cantidad debe ser mayor a cero.",
    descuento: "Revisa el descuento de esta partida.",
    descripcion: "Revisa la descripcion de esta partida.",
    precio_unitario: "Revisa el precio unitario de esta partida.",
  })[name];

  if (Array.isArray(detail)) {
    for (const item of detail) {
      const path = Array.isArray(item?.loc) ? item.loc.filter(part => part !== "body") : [];
      if (path.length === 1 && ["cliente_id", "titulo", ...(kind === "opportunity" ? ["probabilidad", "monto_estimado"] : [])].includes(path[0])) {
        fields[path[0]] = fieldMessage(path[0]);
      } else if (kind === "quote" && path.length === 3 && path[0] === "items" &&
          Number.isInteger(path[1]) && form.items?.[path[1]] &&
          ["cantidad", "descuento", "descripcion", "precio_unitario"].includes(path[2])) {
        fields[path.join(".")] = fieldMessage(path[2]);
      }
    }
    return { fields, message: Object.keys(fields).length ? "Revisa los campos indicados." : fallback };
  }

  if (kind === "opportunity" && message === "La probabilidad debe estar entre 0 y 100.") {
    fields.probabilidad = message;
  }
  if (kind === "opportunity" && ["El monto estimado debe ser mayor o igual a cero.", "Captura un monto estimado valido."].includes(message)) {
    fields.monto_estimado = message;
  }
  if (/^Selecciona un cliente para (la cotizacion|la oportunidad)\.$/.test(message)) fields.cliente_id = message;
  if (/^Captura el titulo de (la cotizacion|la oportunidad)\.$/.test(message)) fields.titulo = message;
  if (kind === "quote") {
    // The business 400 has no item index; only mark a line when its captured values prove the mismatch.
    const index = (form.items || []).findIndex(item => {
      if (message === "El descuento no puede superar el subtotal de la partida.") {
        return Number(item.descuento) > Number(item.cantidad) * Number(item.precio_unitario);
      }
      if (["La cantidad de cada partida debe ser mayor a cero.", "La cantidad debe ser mayor a cero."].includes(message)) {
        return Number(item.cantidad || 0) <= 0;
      }
      if (message === "Cada partida debe tener descripcion.") return !String(item.descripcion || "").trim();
      return false;
    });
    if (index >= 0) {
      const field = message.includes("descuento") ? "descuento" : message.includes("descripcion") ? "descripcion" : "cantidad";
      fields[`items.${index}.${field}`] = message;
    }
  }
  return { message, fields };
}

export function focusCrmFormError(form) {
  (form?.querySelector('[aria-invalid="true"]') || form?.querySelector('[data-crm-form-error]'))?.focus();
}

export function activateCrmEditor(form) {
  const dialog = form.closest('[role="dialog"]');
  const backdrop = form.closest(".inventory-modal-backdrop");
  if (!dialog || !backdrop) return undefined;
  const previousFocus = form.ownerDocument.activeElement;
  const previousModal = dialog.getAttribute("aria-modal");
  dialog.setAttribute("aria-modal", "true");
  const background = [];
  // Disable sibling branches, never the ancestors containing this editor. Restore exactly on close.
  for (let branch = backdrop; branch.parentElement; branch = branch.parentElement) {
    for (const sibling of branch.parentElement.children) {
      if (sibling === branch) continue;
      background.push([sibling, sibling.getAttribute("inert"), sibling.getAttribute("aria-hidden")]);
      sibling.setAttribute("inert", "");
      sibling.setAttribute("aria-hidden", "true");
    }
    if (branch.parentElement === form.ownerDocument.body) break;
  }
  const focusable = () => Array.from(dialog.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]',
  )).filter(element => element.getClientRects().length && !element.closest("[inert]"));
  const keepTabInside = (event) => {
    if (event.key !== "Tab") return;
    const elements = focusable();
    const target = event.shiftKey ? elements.at(-1) : elements[0];
    const boundary = event.shiftKey ? elements[0] : elements.at(-1);
    if (target && (form.ownerDocument.activeElement === boundary || !dialog.contains(form.ownerDocument.activeElement))) {
      event.preventDefault();
      target.focus();
    }
  };
  dialog.addEventListener("keydown", keepTabInside);
  form.querySelector("input:not([disabled]), select:not([disabled]), textarea:not([disabled])")?.focus();
  return () => {
    dialog.removeEventListener("keydown", keepTabInside);
    if (previousModal === null) dialog.removeAttribute("aria-modal");
    else dialog.setAttribute("aria-modal", previousModal);
    for (const [element, inert, hidden] of background) {
      if (inert === null) element.removeAttribute("inert"); else element.setAttribute("inert", inert);
      if (hidden === null) element.removeAttribute("aria-hidden"); else element.setAttribute("aria-hidden", hidden);
    }
    if (previousFocus?.isConnected && !previousFocus.closest("[inert]")) previousFocus.focus();
  };
}

export function useCrmFormFeedback(open, formRef, kind) {
  const [feedback, setFeedback] = useState(emptyFeedback);
  const formId = kind === "quote" ? "crm-quote-form" : "crm-opportunity-form";
  useEffect(() => {
    if (open && formRef.current) return activateCrmEditor(formRef.current);
  }, [open, formRef]);
  useEffect(() => {
    if (open && feedback.message) focusCrmFormError(formRef.current);
  }, [open, feedback, formRef]);
  return {
    ...feedback, formId,
    clear: () => setFeedback(emptyFeedback()),
    show: (error, form, override) => setFeedback(mapCrmFormFeedback(error, kind, form, override)),
    fieldProps: name => ({ name, "aria-invalid": Boolean(feedback.fields[name]),
      "aria-describedby": feedback.fields[name] ? `${formId}-error-${name}` : undefined }),
  };
}

export function CrmFormError({ feedback }) {
  return feedback.message ? createElement("p", {
    className: "form-error", role: "alert", tabIndex: -1, "data-crm-form-error": true,
  }, feedback.message) : null;
}

export function CrmFieldError({ feedback, name }) {
  return feedback.fields[name] ? createElement("span", {
    className: "form-error", id: `${feedback.formId}-error-${name}`,
  }, feedback.fields[name]) : null;
}
