import { useAuth } from "../auth/AuthContext";


export default function DashboardPage() {
  const { empresa, membership, modules, user } = useAuth();

  return (
    <section className="dashboard-stack">
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

