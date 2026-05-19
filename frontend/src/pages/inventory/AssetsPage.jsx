import InventoryPlaceholderPage from "./InventoryPlaceholderPage";


export default function AssetsPage() {
  return (
    <InventoryPlaceholderPage
      title="Equipos y activos"
      subtitle="Esta vista concentrará equipos, herramientas y activos operativos asociados al inventario."
      note="En una fase posterior se conectará con responsables, mantenimientos, historial de uso y órdenes de trabajo."
      items={["Catálogo de equipos", "Asignación a responsables", "Mantenimientos", "Historial de servicio"]}
    />
  );
}
