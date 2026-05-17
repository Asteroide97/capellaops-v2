import { useAuth } from "../auth/AuthContext";
import FeaturePlaceholder from "../components/FeaturePlaceholder";


export default function SuperadminPage() {
  const { user, empresa } = useAuth();

  if (!user?.is_superadmin) {
    return (
      <FeaturePlaceholder
        title="Superadmin"
        subtitle="Esta sección es exclusiva para operadores internos."
        items={["Permisos centralizados", "Monitoreo", "Soporte", "Configuración avanzada"]}
        note="El frontend no concede acceso por sí mismo. El backend debe seguir validando permisos."
        tone="warning"
      />
    );
  }

  return (
    <FeaturePlaceholder
      title="Superadmin"
      subtitle={`Panel técnico interno para ${empresa?.name ?? "la empresa actual"}.`}
      items={["Auditoría", "Operaciones internas", "Diagnóstico", "Soporte multiempresa"]}
      note="Placeholder listo para herramientas internas futuras."
    />
  );
}

