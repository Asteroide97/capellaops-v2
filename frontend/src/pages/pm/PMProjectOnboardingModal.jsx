import { Check, Circle, ClipboardList, Flag, ListChecks, Play, Route, Settings2 } from "lucide-react";

import { ActionButton, ModalShell } from "../inventory/shared";

const onboardingSteps = [
  {
    icon: ClipboardList,
    title: "Crear o importar presupuesto",
    description: "Captura tu presupuesto en Capella o importa el Excel que ya utilizas. Siempre revisarás los datos antes de guardarlos.",
  },
  {
    icon: ListChecks,
    title: "Revisar y planificar",
    description: "Confirma capítulos y partidas. Después agrega fechas, responsables y requisitos previos.",
  },
  {
    icon: Play,
    title: "Generar plan",
    description: "Convierte las partidas en tareas para el plan de trabajo y el cronograma.",
  },
  {
    icon: Route,
    title: "Revisar cronograma",
    description: "Confirma fechas, dependencias y ruta crítica.",
  },
  {
    icon: Flag,
    title: "Crear línea base",
    description: "Guarda el plan validado para medir desviaciones durante la ejecución.",
  },
  {
    icon: Settings2,
    title: "Ejecutar y controlar",
    description: "Registra avance, fotos, materiales, horas, costos y estimaciones.",
  },
];

export default function PMProjectOnboardingModal({ onClose, onStartBudget, open }) {
  return (
    <ModalShell
      footer={(
        <div className="inventory-actions inventory-actions-wrap">
          <ActionButton onClick={onClose} type="button">Ver después</ActionButton>
          <ActionButton icon={<ClipboardList size={16} />} onClick={onStartBudget} tone="primary" type="button">
            Configurar presupuesto
          </ActionButton>
        </div>
      )}
      onClose={onClose}
      open={open}
      size="large"
      subtitle="Ahora vamos a preparar el proyecto para convertir el presupuesto en un plan de trabajo."
      title="Proyecto creado"
    >
      <div className="pm-onboarding-steps">
        {onboardingSteps.map((step, index) => {
          const Icon = step.icon;
          const StepState = index === 0 ? Check : Circle;
          return (
            <article className={`pm-onboarding-step ${index === 0 ? "is-current" : ""}`} key={step.title}>
              <span className="pm-onboarding-step-state"><StepState size={17} /></span>
              <span className="pm-onboarding-step-icon"><Icon size={17} /></span>
              <div className="pm-onboarding-step-copy">
                <strong>{step.title}</strong>
                <span>{step.description}</span>
              </div>
              <span className="pm-onboarding-step-number">{index + 1}</span>
            </article>
          );
        })}
      </div>
    </ModalShell>
  );
}
