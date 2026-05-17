import { NavLink } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";


export default function Sidebar() {
  const { empresa, modules } = useAuth();
  const getNavClass = ({ isActive }) => (isActive ? "nav-item active" : "nav-item");

  return (
    <aside className="sidebar">
      <div className="brand-card">
        <div className="brand-mark">CO</div>
        <div>
          <h2>Capella Ops</h2>
          <p>{empresa?.slug ?? "multiempresa"}</p>
        </div>
      </div>

      <nav className="nav-stack">
        <NavLink className={getNavClass} to="/">
          Dashboard
        </NavLink>

        {modules
          .filter((module) => module.visible_in_sidebar)
          .map((module) =>
            module.enabled && module.route ? (
              <NavLink className={getNavClass} key={module.name} to={module.route}>
                <span>{module.label}</span>
              </NavLink>
            ) : (
              <div className="nav-item disabled" key={module.name}>
                <span>{module.label}</span>
                {module.pending ? <span className="pill">Pendiente</span> : null}
              </div>
            ),
          )}
      </nav>
    </aside>
  );
}

