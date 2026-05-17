import FeaturePlaceholder from "../components/FeaturePlaceholder";


export default function InventoryPage() {
  return (
    <FeaturePlaceholder
      title="Inventario"
      subtitle="Base preparada para SKUs, stock, almacenes y movimientos."
      items={["Productos", "Existencias", "Almacenes", "Entradas y salidas"]}
      note="Este placeholder representa el módulo disponible para todos los planes."
    />
  );
}

