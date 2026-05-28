import { Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Sidebar from "./Sidebar";


export default function AppLayout() {
  const navigate = useNavigate();
  const {
    dismissNotice,
    empresa,
    exitImpersonation,
    impersonation,
    notice,
    logout,
    user,
  } = useAuth();

  async function handleExitImpersonation() {
    try {
      await exitImpersonation();
      navigate("/superadmin");
    } catch {
      navigate("/superadmin");
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="app-content">
        <div className="app-content-shell">
          {impersonation ? (
            <div className="impersonation-banner">
              <div>
                <strong>
                  Estás impersonando a {user?.full_name} en {empresa?.name}.
                </strong>
              </div>
              <button className="ghost-button" onClick={handleExitImpersonation} type="button">
                Salir de impersonación
              </button>
            </div>
          ) : null}

          {notice ? (
            <div className="feature-card setup-inline-card">
              <div className="setup-inline-row">
                <span>{notice}</span>
                <button className="link-button" onClick={dismissNotice} type="button">
                  Cerrar
                </button>
              </div>
            </div>
          ) : null}

          <header className="topbar">
            <div className="topbar-main">
              <p className="eyebrow">Capella Ops V2</p>
              <h1>{empresa?.name ?? "Panel principal"}</h1>
            </div>

            <div className="topbar-actions">
              <div className="user-chip">
                <strong>{user?.full_name}</strong>
                <span>{user?.email}</span>
              </div>

              <button className="ghost-button" onClick={logout} type="button">
                Cerrar sesión
              </button>
            </div>
          </header>

          <main className="page-container">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
