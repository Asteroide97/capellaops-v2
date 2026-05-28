import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  BarChart3,
  ChevronDown,
  FolderKanban,
  LayoutDashboard,
  MonitorSmartphone,
  ReceiptText,
  ShieldCheck,
  Users,
} from "lucide-react";

import { useAuth } from "../auth/AuthContext";
import { inventoryModuleIcon, inventoryNavItems } from "../pages/inventory/navigation";


const ICON_SIZE = 16;
const ICON_STROKE = 1.9;

const moduleIconMap = {
  billing_pending: ReceiptText,
  crm: Users,
  inventory: inventoryModuleIcon,
  pm: FolderKanban,
  pos: MonitorSmartphone,
  superadmin: ShieldCheck,
};


function NavIcon({ icon: Icon, className = "nav-icon" }) {
  if (!Icon) {
    return null;
  }

  return <Icon className={className} size={ICON_SIZE} strokeWidth={ICON_STROKE} />;
}


function NavLabel({ icon, label, child = false }) {
  return (
    <span className={`nav-item-content ${child ? "nav-item-content-child" : ""}`}>
      <NavIcon className={child ? "nav-icon nav-icon-child" : "nav-icon"} icon={icon} />
      <span className={child ? "nav-text nav-text-child" : "nav-text"}>{label}</span>
    </span>
  );
}


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

  const visibleModules = useMemo(
    () => modules.filter((module) => module.visible_in_sidebar),
    [modules],
  );

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
          <NavLabel icon={LayoutDashboard} label="Dashboard" />
        </NavLink>

        {visibleModules.map((module) => {
          const moduleIcon = moduleIconMap[module.name];

          if (module.name === "inventory" && module.enabled && module.route) {
            const isInventoryActive = location.pathname.startsWith("/inventario");

            return (
              <div className="nav-group" key={module.name}>
                <button
                  className={`nav-item nav-toggle ${isInventoryActive ? "active" : ""}`}
                  onClick={() => setInventoryExpanded((current) => !current)}
                  type="button"
                >
                  <NavLabel icon={moduleIcon} label={module.label} />
                  <ChevronDown
                    aria-hidden="true"
                    className={`nav-toggle-icon ${inventoryExpanded ? "expanded" : ""}`}
                    size={16}
                    strokeWidth={ICON_STROKE}
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
                        <NavLabel child icon={item.icon} label={item.label} />
                      </NavLink>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          }

          if (module.enabled && module.route) {
            return (
              <NavLink className={getNavClass} key={module.name} to={module.route}>
                <NavLabel icon={moduleIcon} label={module.label} />
              </NavLink>
            );
          }

          return (
            <div className="nav-item disabled" key={module.name}>
              <NavLabel icon={moduleIcon} label={module.label} />
              {module.pending ? <span className="pill">Pendiente</span> : null}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
