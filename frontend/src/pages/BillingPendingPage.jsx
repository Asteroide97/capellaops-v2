import { useAuth } from "../auth/AuthContext";
import FeaturePlaceholder from "../components/FeaturePlaceholder";


export default function BillingPendingPage() {
  const { user } = useAuth();

  if (!user?.is_superadmin) {
    return (
      <FeaturePlaceholder
        title="Facturación pendiente"
        subtitle="Este módulo existe como pendiente y está bloqueado para clientes."
        items={[
          "Sin factura.com",
          "Sin timbrado CFDI",
          "Sin CSD",
          "Sin operaciones fiscales",
        ]}
        note="Solo un superadmin puede ver la página técnica cuando este módulo sea habilitado en una fase futura."
        tone="warning"
      />
    );
  }

  return (
    <FeaturePlaceholder
      title="Facturación pendiente"
      subtitle="Vista técnica reservada para superadmin. El módulo fiscal todavía no ejecuta ninguna operación."
      items={[
        "Estado: pendiente",
        "Integración fiscal: bloqueada",
        "Factura.com: no implementado",
        "CFDI/CSD: no implementado",
      ]}
      note="Esta página solo documenta el estado técnico actual. No debe exponerse funcionalidad fiscal a clientes."
      tone="warning"
    />
  );
}

