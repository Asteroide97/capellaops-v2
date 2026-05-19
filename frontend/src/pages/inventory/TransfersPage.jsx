import CountsSection from "../../components/inventory/CountsSection";
import TransfersSection from "../../components/inventory/TransfersSection";
import { useAuth } from "../../auth/AuthContext";


export default function TransfersPage() {
  const { token, empresaId } = useAuth();

  return (
    <div className="dashboard-stack">
      <div className="module-board">
        <article className="module-card">
          <div className="module-card-top">
            <h3>Traspasos entre almacenes</h3>
          </div>
          <p>
            Confirma salidas y entradas entre almacenes sin perder trazabilidad sobre existencias.
          </p>
        </article>
        <article className="module-card">
          <div className="module-card-top">
            <h3>Conteos físicos</h3>
          </div>
          <p>
            Captura diferencias contra sistema y aplica ajustes auditables por almacén.
          </p>
        </article>
      </div>

      <TransfersSection active empresaId={empresaId} token={token} />
      <CountsSection active empresaId={empresaId} token={token} />
    </div>
  );
}
