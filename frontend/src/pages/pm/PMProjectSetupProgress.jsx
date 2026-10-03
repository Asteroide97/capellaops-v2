import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, Circle, RotateCw } from "lucide-react";

import { getPmProjectBudget, listPmBudgetImports, listPmProjectBaselines } from "../../api/client";
import { ActionButton, StatusBadge, formatMoney, safeDisplayText } from "../inventory/shared";

function getStepState(done, available = true, warning = false) {
  if (done) return "complete";
  if (warning) return "warning";
  return available ? "pending" : "upcoming";
}

export default function PMProjectSetupProgress({
  empresaId,
  onOpenBaseline,
  onOpenBudget,
  onOpenExecution,
  onReviewStructure,
  project,
  tasks = [],
  token,
}) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [budget, setBudget] = useState(null);
  const [baselines, setBaselines] = useState([]);
  const [importSessions, setImportSessions] = useState([]);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let active = true;
    if (!token || !empresaId || !project?.id) return undefined;

    setLoading(true);
    setLoadError("");
    Promise.allSettled([
      getPmProjectBudget({ projectId: project.id, token, empresaId }),
      listPmProjectBaselines({ projectId: project.id, token, empresaId }),
      listPmBudgetImports({ projectId: project.id, token, empresaId }),
    ]).then(([budgetResult, baselineResult, importResult]) => {
      if (!active) return;
      if (budgetResult.status === "fulfilled") {
        setBudget(budgetResult.value?.budget ?? null);
      } else {
        setBudget(null);
        setLoadError("No se pudo verificar el presupuesto del proyecto.");
      }
      if (baselineResult.status === "fulfilled") {
        setBaselines(Array.isArray(baselineResult.value) ? baselineResult.value : []);
      } else {
        setBaselines([]);
        setLoadError((current) => current || "No se pudo verificar la línea base.");
      }
      if (importResult.status === "fulfilled") {
        setImportSessions(Array.isArray(importResult.value) ? importResult.value : []);
      } else {
        setImportSessions([]);
      }
      setLoading(false);
    });

    return () => { active = false; };
  }, [empresaId, project, retryKey, token]);

  const activeItems = useMemo(
    () => (budget?.items ?? []).filter((item) => item?.activo !== false),
    [budget],
  );
  const activeParts = useMemo(
    () => activeItems.filter((item) => item?.tipo === "partida"),
    [activeItems],
  );
  const projectTaskIds = useMemo(() => new Set((tasks ?? []).filter((task) => task?.activo !== false).map((task) => task.id)), [tasks]);
  const linkedPartCount = activeParts.filter((item) => item.linked_task_id && projectTaskIds.has(item.linked_task_id)).length;
  const hasDetailedBudget = Boolean(budget && activeParts.length > 0);
  const planGenerated = hasDetailedBudget && linkedPartCount === activeParts.length;
  const hasPartialPlan = linkedPartCount > 0 && !planGenerated;
  const generatedTasks = activeParts
    .map((item) => (item.linked_task_id ? (tasks ?? []).find((task) => task.id === item.linked_task_id) : null))
    .filter(Boolean);
  const scheduleReady = planGenerated && generatedTasks.length > 0
    && generatedTasks.every((task) => task.fecha_inicio && task.fecha_vencimiento);
  const activeBaseline = baselines.find((item) => item.estatus === "activa") ?? null;
  const activeImport = importSessions.find((item) => ["review", "ready", "importing"].includes(item.status));
  const planningReady = activeParts.length > 0 && activeParts.every((item) => item.fecha_inicio_sugerida && item.fecha_fin_sugerida);
  const executionStarted = (tasks ?? []).some((task) => Number(task.porcentaje_avance ?? 0) > 0 || ["en_progreso", "completada", "completed", "done"].includes(String(task.estatus ?? "").toLowerCase()));

  const steps = [
    {
      key: "budget",
      title: "Presupuesto",
      done: hasDetailedBudget,
      available: true,
      warning: Boolean(budget && !hasDetailedBudget),
      note: hasDetailedBudget
        ? `${activeParts.length} partidas listas · ${formatMoney(budget.total_venta ?? budget.total_costo ?? 0)}`
        : activeImport
          ? "Hay una revisión de Excel guardada para continuar."
        : budget
          ? "Agrega capítulos y partidas para completar el presupuesto detallado."
          : `Presupuesto de referencia: ${formatMoney(project?.presupuesto_estimado ?? 0)}. Todavía no hay detalle.`,
    },
    {
      key: "planning",
      title: "Planificación",
      done: planningReady,
      available: hasDetailedBudget,
      note: planningReady ? "Las partidas ya tienen fechas sugeridas." : hasDetailedBudget ? "Define fechas y requisitos previos para las partidas." : "Se habilita cuando exista presupuesto detallado.",
    },
    {
      key: "workplan",
      title: "Plan de trabajo",
      done: planGenerated,
      available: planningReady,
      warning: hasPartialPlan,
      note: planGenerated
        ? `${generatedTasks.length} pendientes conectados con las partidas.`
        : hasPartialPlan
          ? `${linkedPartCount} de ${activeParts.length} partidas ya están conectadas.`
          : "Genera los pendientes a partir de la estructura revisada.",
    },
    {
      key: "baseline",
      title: "Línea base",
      done: Boolean(activeBaseline),
      available: scheduleReady,
      note: activeBaseline
        ? `Activa: ${safeDisplayText(activeBaseline.nombre, "Línea base principal")}.`
        : scheduleReady
          ? "Valida el plan para guardar una referencia de control."
          : "Se habilita cuando el cronograma esté configurado.",
    },
    {
      key: "execution",
      title: "Ejecución",
      done: executionStarted,
      available: Boolean(activeBaseline),
      note: executionStarted ? "Ya hay avance registrado en el trabajo." : activeBaseline ? "Registra avances, fotos, materiales, horas y costos." : "Se habilita después de validar el plan.",
    },
  ];
  const completedCount = steps.filter((step) => step.done).length;

  let nextAction = { label: "Preparar presupuesto", onClick: onOpenBudget };
  if (activeImport) {
    nextAction = { label: "Continuar revisión", onClick: onOpenBudget };
  } else if (hasDetailedBudget && !planningReady) {
    nextAction = { label: "Revisar estructura", onClick: onReviewStructure };
  } else if (planningReady && !planGenerated) {
    nextAction = { label: "Generar plan", onClick: onReviewStructure };
  } else if (planGenerated && !scheduleReady) {
    nextAction = { label: "Completar planificación", onClick: onOpenExecution };
  } else if (planGenerated && !activeBaseline) {
    nextAction = { label: "Validar plan", onClick: onOpenBaseline };
  } else if (activeBaseline && !executionStarted) {
    nextAction = { label: "Ir a ejecución", onClick: onOpenExecution };
  } else if (executionStarted) {
    nextAction = { label: "Continuar ejecución", onClick: onOpenExecution };
  }

  return (
    <section className="pm-project-setup" aria-label="Configuración del proyecto">
      <div className="pm-project-setup-head">
        <div>
          <span className="pm-project-setup-eyebrow">Guía del proyecto</span>
          <h2>Configuración del proyecto</h2>
          <p>{loading ? "Revisando el avance de configuración…" : `${completedCount} de 5 pasos completados`}</p>
        </div>
        <div className="pm-project-setup-actions">
          {loadError ? (
            <ActionButton icon={<RotateCw size={15} />} onClick={() => setRetryKey((value) => value + 1)} type="button">
              Actualizar estado
            </ActionButton>
          ) : null}
          {!loading && nextAction.onClick ? (
            <ActionButton icon={<ArrowRight size={15} />} onClick={nextAction.onClick} tone="primary" type="button">
              Siguiente paso
            </ActionButton>
          ) : null}
        </div>
      </div>
      {!loading && nextAction.label ? <p className="pm-project-setup-next-label">{nextAction.label}</p> : null}
      {loadError ? <p className="pm-project-setup-error">{loadError} Los pasos no verificados permanecen pendientes.</p> : null}
      <ol className="pm-project-setup-list">
        <li className="pm-project-setup-row is-complete">
          <span className="pm-project-setup-check"><Check size={15} /></span>
          <strong>Proyecto creado</strong>
          <span>Base del trabajo lista.</span>
          <StatusBadge tone="success">Completado</StatusBadge>
        </li>
        {steps.map((step) => {
          const state = getStepState(step.done, step.available, step.warning);
          const Icon = step.done ? Check : Circle;
          return (
            <li className={`pm-project-setup-row is-${state}`} key={step.key}>
              <span className="pm-project-setup-check"><Icon size={15} /></span>
              <strong>{step.title}</strong>
              <span>{loading ? "Verificando…" : step.note}</span>
              <StatusBadge tone={step.done ? "success" : step.warning ? "warning" : step.available ? "info" : "neutral"}>
                {loading ? "Verificando" : step.done ? "Completado" : step.warning ? "Requiere atención" : step.available ? "Pendiente" : "Después"}
              </StatusBadge>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
