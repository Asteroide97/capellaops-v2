import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";


export default function DashboardPage() {
  const { empresa, membership, modules, onboardingMessage, requiresFirstWarehouse, user } = useAuth();

  return (
    <section className="dashboard-stack">
      {requiresFirstWarehouse ? (
        <div className="feature-card warning">
          <div className="feature-header">
            <p className="eyebrow">Setup inicial</p>
            <h2>Crea tu primer almacén</h2>
            <p>{onboardingMessage || "Crea tu primer almacén para comenzar."}</p>
          </div>
          <Link className="primary-link" to="/configuracion-inicial/almacen">
            Crear primer almacén
          </Link>
        </div>
      ) : null}

      <div className="hero-card">
        <div>
          <p className="eyebrow">Resumen operativo</p>
          <h2>Bienvenido a tu centro multiempresa</h2>
          <p>
            Capella Ops V2 ya conoce tu empresa, tu plan y los módulos visibles desde backend.
          </p>
        </div>

        <div className="hero-grid">
          <article className="metric-card">
            <span>Plan</span>
            <strong>{empresa?.plan_code}</strong>
          </article>
          <article className="metric-card">
            <span>Estatus</span>
            <strong>{empresa?.access_status}</strong>
          </article>
          <article className="metric-card">
            <span>Rol</span>
            <strong>{membership?.role}</strong>
          </article>
          <article className="metric-card">
            <span>Usuario</span>
            <strong>{user?.is_superadmin ? "Superadmin" : "Cliente"}</strong>
          </article>
        </div>
      </div>

      <div className="module-board">
        {modules.map((module) => (
          <article className="module-card" key={module.name}>
            <div className="module-card-top">
              <h3>{module.label}</h3>
              <span className={`status-badge ${module.enabled ? "enabled" : "pending"}`}>
                {module.pending ? "Pendiente" : module.enabled ? "Activo" : "Bloqueado"}
              </span>
            </div>
            <p>{module.description}</p>
            {module.reason ? <small>{module.reason}</small> : null}
          </article>
        ))}
      </div>
    </section>
  );
}
