import InventoryPlaceholderPage from "./InventoryPlaceholderPage";

export default function WorkOrdersPage() {
  return (
    <InventoryPlaceholderPage
      title="Órdenes de trabajo"
      subtitle="Esta vista cubrirá consumos, tareas, refacciones y evidencia operativa por orden."
      note="Aquí se enlazarán materiales, equipos, tiempos y responsables dentro del flujo operativo."
      items={["Consumo de materiales", "Tareas operativas", "Responsables", "Seguimiento de ejecución"]}
    />
  );
}
