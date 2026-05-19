import InventoryPlaceholderPage from "./InventoryPlaceholderPage";


export default function ProjectsInventoryPage() {
  return (
    <InventoryPlaceholderPage
      title="Inventario por proyectos"
      subtitle="Esta vista conectará materiales, requisiciones y consumos contra proyectos activos."
      note="En una fase posterior aquí vivirá la asignación de materiales por proyecto, consumo operativo y trazabilidad comercial."
      items={["Reservas de materiales", "Consumo por proyecto", "Costeo operativo", "Cruce con PM"]}
    />
  );
}
