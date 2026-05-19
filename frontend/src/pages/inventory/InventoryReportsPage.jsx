import InventoryPlaceholderPage from "./InventoryPlaceholderPage";


export default function InventoryReportsPage() {
  return (
    <InventoryPlaceholderPage
      title="Reportes de inventario"
      subtitle="Esta vista reunirá reportes operativos, exportaciones y tableros de control."
      note="En una fase posterior se agregarán reportes históricos, exportación y análisis cruzado entre compras, existencias y POS."
      items={["Existencias por almacén", "Valuación", "Movimientos históricos", "Análisis operativo"]}
    />
  );
}
