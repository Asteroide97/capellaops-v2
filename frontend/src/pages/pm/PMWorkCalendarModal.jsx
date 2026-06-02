import { useEffect, useState } from "react";

import {
  ActionButton,
  Field,
  ModalShell,
} from "../inventory/shared";
import { formatWorkCalendarSummary, weekdayOptions } from "./shared";

const defaultForm = {
  nombre: "Calendario estándar",
  lunes: true,
  martes: true,
  miercoles: true,
  jueves: true,
  viernes: true,
  sabado: false,
  domingo: false,
};

function toForm(calendar) {
  if (!calendar) {
    return defaultForm;
  }
  return {
    nombre: calendar.nombre ?? "Calendario estándar",
    lunes: Boolean(calendar.lunes),
    martes: Boolean(calendar.martes),
    miercoles: Boolean(calendar.miercoles),
    jueves: Boolean(calendar.jueves),
    viernes: Boolean(calendar.viernes),
    sabado: Boolean(calendar.sabado),
    domingo: Boolean(calendar.domingo),
  };
}

export default function PMWorkCalendarModal({
  calendar,
  onClose,
  onSave,
  open,
  saving = false,
}) {
  const [form, setForm] = useState(defaultForm);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }
    setForm(toForm(calendar));
    setError("");
  }, [calendar, open]);

  function handleCheckboxChange(key) {
    setForm((current) => ({ ...current, [key]: !current[key] }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const enabledDays = weekdayOptions.filter((item) => Boolean(form[item.key]));
    if (enabledDays.length === 0) {
      setError("Selecciona al menos un día laboral.");
      return;
    }
    setError("");
    await onSave?.({
      nombre: form.nombre.trim() || "Calendario estándar",
      lunes: Boolean(form.lunes),
      martes: Boolean(form.martes),
      miercoles: Boolean(form.miercoles),
      jueves: Boolean(form.jueves),
      viernes: Boolean(form.viernes),
      sabado: Boolean(form.sabado),
      domingo: Boolean(form.domingo),
    });
  }

  const footer = (
    <div className="inventory-actions inventory-actions-wrap">
      <ActionButton disabled={saving} onClick={onClose} type="button">
        Cancelar
      </ActionButton>
      <ActionButton disabled={saving} form="pm-work-calendar-form" tone="primary" type="submit">
        {saving ? "Guardando..." : "Guardar calendario"}
      </ActionButton>
    </div>
  );

  return (
    <ModalShell
      footer={footer}
      onClose={onClose}
      open={open}
      size="md"
      subtitle="Define los días laborales que debe usar la planeación del proyecto."
      title="Calendario laboral"
    >
      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>No se pudo guardar el calendario</strong>
          <p className="table-note">{error}</p>
        </div>
      ) : null}

      <form className="inventory-modal-form" id="pm-work-calendar-form" onSubmit={handleSubmit}>
        <Field label="Nombre">
          <input
            onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))}
            placeholder="Calendario estándar"
            type="text"
            value={form.nombre}
          />
        </Field>

        <div className="inventory-form-note">
          <strong>Días laborales</strong>
          <p className="table-note">{formatWorkCalendarSummary(form)}</p>
        </div>

        <div className="pm-calendar-grid">
          {weekdayOptions.map((item) => (
            <label className="pm-calendar-day-option" key={item.key}>
              <input
                checked={Boolean(form[item.key])}
                onChange={() => handleCheckboxChange(item.key)}
                type="checkbox"
              />
              <span>{item.label}</span>
            </label>
          ))}
        </div>
      </form>
    </ModalShell>
  );
}
