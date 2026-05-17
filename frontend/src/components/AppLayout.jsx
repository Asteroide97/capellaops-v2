import { Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Sidebar from "./Sidebar";


export default function AppLayout() {
  const { empresa, user, logout } = useAuth();

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="app-content">
        <header className="topbar">
          <div>
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
  );
}

