import FeaturePlaceholder from "../components/FeaturePlaceholder";


export default function PosPage() {
  return (
    <FeaturePlaceholder
      title="POS"
      subtitle="Punto de venta preparado para tickets, cobro rápido y cierre de caja."
      items={["Ventas", "Cobro rápido", "Corte", "Historial"]}
      note="Disponible para planes Pro y Total."
    />
  );
}

