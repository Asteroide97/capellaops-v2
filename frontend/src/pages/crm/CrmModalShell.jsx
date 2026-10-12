import { useEffect, useRef, useState } from "react";
import { ActionButton, ModalShell } from "../inventory/shared";
import { activateCrmModal, crmFormSignature, requestCrmModalClose } from "./crmModalFocus.js";

export function CrmModalShell({ open, onClose, title, children, ...props }) {
  const rootRef = useRef(null), noticeRef = useRef(null), baselineRef = useRef(""), returnToFieldRef = useRef(null);
  const closeRef = useRef(onClose), requestRef = useRef(null), titleRef = useRef(title);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  closeRef.current = onClose; titleRef.current = title;
  requestRef.current = () => {
    if (confirmDiscard) { noticeRef.current?.querySelector("button")?.focus(); return; }
    const dialog = rootRef.current?.querySelector('[role="dialog"]');
    if (!dialog) return;
    requestCrmModalClose(dialog, baselineRef.current, () => closeRef.current(), () => {
      returnToFieldRef.current = dialog.ownerDocument.activeElement;
      setConfirmDiscard(true);
    });
  };
  useEffect(() => {
    if (!open) return;
    const dialog = rootRef.current.querySelector('[role="dialog"]');
    baselineRef.current = crmFormSignature(dialog);
    setConfirmDiscard(false);
    return activateCrmModal(dialog, { title: titleRef.current, onEscape: () => requestRef.current() });
  }, [open]);
  useEffect(() => {
    if (confirmDiscard) noticeRef.current?.querySelector("button")?.focus();
  }, [confirmDiscard]);
  if (!open) return null;
  return (
    <div ref={rootRef} style={{ display: "contents" }} onClickCapture={event => {
      if (event.target.closest?.("[data-crm-modal-close]")) {
        event.preventDefault(); event.stopPropagation(); requestRef.current();
      }
    }}>
      <ModalShell {...props} open title={title} onClose={() => requestRef.current()}>
        {confirmDiscard ? (
          <div className="inventory-form-note inventory-form-note-danger" ref={noticeRef} role="alert">
            <p>Tienes cambios sin guardar. ¿Quieres descartarlos?</p>
            <div className="inventory-actions">
              <ActionButton type="button" onClick={() => {
                setConfirmDiscard(false); returnToFieldRef.current?.focus();
              }}>Seguir editando</ActionButton>
              <ActionButton type="button" tone="danger" onClick={() => closeRef.current()}>Descartar cambios</ActionButton>
            </div>
          </div>
        ) : null}
        {children}
      </ModalShell>
    </div>
  );
}
