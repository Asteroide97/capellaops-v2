import { ActionButton, EmptyState } from "../inventory/shared";
import { classifyCrmEmptyState } from "./crmEmptyState";

const firstUse = {
  clients: ["No hay clientes registrados", "Crea el primer cliente para empezar a trabajar el pipeline."],
  contacts: ["No hay contactos registrados", "Agrega el primer contacto para este cliente."],
  opportunities: ["No hay oportunidades registradas", "Crea la primera oportunidad y conecta cliente, monto y etapa."],
  activities: ["No hay actividades registradas", "Programa la primera actividad para empezar el seguimiento."],
  quotes: ["Sin cotizaciones", "No hay cotizaciones registradas."],
};

export function CrmListState({ kind, page, onClear }) {
  const state = classifyCrmEmptyState(kind, page);
  if (state.mode === "data") return null;
  return (
    <>
      {state.hasActiveFilters ? <p className="table-note">Filtros aplicados: {state.filters.join(" · ")}</p> : null}
      {state.mode === "error" ? <p className="form-error" role="alert">{page.error || "No se pudo cargar la informacion. Intenta nuevamente."}</p> : null}
      {state.mode === "loading" ? <p role="status">Cargando...</p> : null}
      {state.mode === "selection" ? <EmptyState title="Sin cliente seleccionado" note="Selecciona un cliente y luego carga o crea contactos." /> : null}
      {state.isFilteredEmpty ? <EmptyState title="Sin resultados" note="No hay resultados con estos filtros."
        action={<ActionButton onClick={onClear} size="sm" type="button">Limpiar</ActionButton>} /> : null}
      {state.isTrulyEmpty ? <EmptyState title={firstUse[kind][0]} note={firstUse[kind][1]} /> : null}
    </>
  );
}
