import FeaturePlaceholder from "../components/FeaturePlaceholder";


export default function PmPage() {
  return (
    <FeaturePlaceholder
      title="PM"
      subtitle="Base lista para proyectos, fases, tareas y responsables."
      items={["Portafolio", "Tableros", "Cronograma", "Responsables"]}
      note="Disponible en el plan total según el catálogo de módulos."
    />
  );
}

