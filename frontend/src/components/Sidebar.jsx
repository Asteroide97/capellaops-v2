import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { inventoryNavItems } from "../pages/inventory/navigation";


export default function Sidebar() {
  const { empresa, modules } = useAuth();
  const location = useLocation();
  const [inventoryExpanded, setInventoryExpanded] = useState(location.pathname.startsWith("/inventario"));
  const getNavClass = ({ isActive }) => (isActive ? "nav-item active" : "nav-item");

  useEffect(() => {
    if (location.pathname.startsWith("/inventario")) {
      setInventoryExpanded(true);
    }
  }, [location.pathname]);

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
          .map((module) => {
            if (module.name === "inventory" && module.enabled && module.route) {
              const isInventoryActive = location.pathname.startsWith("/inventario");
              return (
                <div className="nav-group" key={module.name}>
                  <button
                    className={`nav-item nav-toggle ${isInventoryActive ? "active" : ""}`}
                    onClick={() => setInventoryExpanded((current) => !current)}
                    type="button"
                  >
                    <span>{module.label}</span>
                    <span
                      aria-hidden="true"
                      className={`nav-toggle-icon ${inventoryExpanded ? "expanded" : ""}`}
                    />
                  </button>

                  {inventoryExpanded ? (
                    <div className="nav-children">
                      {inventoryNavItems.map((item) => (
                        <NavLink
                          className={({ isActive }) => (isActive ? "nav-child nav-child-active" : "nav-child")}
                          key={item.key}
                          to={item.path}
                        >
                          {item.label}
                        </NavLink>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            }

            return module.enabled && module.route ? (
              <NavLink className={getNavClass} key={module.name} to={module.route}>
                <span>{module.label}</span>
              </NavLink>
            ) : (
              <div className="nav-item disabled" key={module.name}>
                <span>{module.label}</span>
                {module.pending ? <span className="pill">Pendiente</span> : null}
              </div>
            );
          })}
      </nav>
    </aside>
  );
}
