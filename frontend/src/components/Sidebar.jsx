import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
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
import { isPmPath, pmModuleIcon, pmNavItems, resolvePmNavKey } from "../pages/pm/navigation";
import { posModuleIcon, posNavItems } from "../pages/pos/navigation";


const ICON_SIZE = 16;
const ICON_STROKE = 1.9;

const moduleIconMap = {
  billing_pending: ReceiptText,
  crm: Users,
  inventory: inventoryModuleIcon,
  pm: pmModuleIcon,
  pos: posModuleIcon,
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
  const { empresa, membership, modules, user } = useAuth();
  const location = useLocation();
  const [inventoryExpanded, setInventoryExpanded] = useState(location.pathname.startsWith("/inventario"));
  const [pmExpanded, setPmExpanded] = useState(isPmPath(location.pathname));
  const [posExpanded, setPosExpanded] = useState(location.pathname.startsWith("/pos"));
  const getNavClass = ({ isActive }) => (isActive ? "nav-item active" : "nav-item");
  const currentPmView = resolvePmNavKey(location.pathname, location.search);
  const currentPosView = (() => {
    if (!location.pathname.startsWith("/pos")) {
      return "";
    }
    const view = new URLSearchParams(location.search).get("view");
    return view || "sell";
  })();

  useEffect(() => {
    if (location.pathname.startsWith("/inventario")) {
      setInventoryExpanded(true);
    }
    if (isPmPath(location.pathname)) {
      setPmExpanded(true);
    }
    if (location.pathname.startsWith("/pos")) {
      setPosExpanded(true);
    }
  }, [location.pathname]);

  const canAccessBillingQueue = user?.is_superadmin || ["owner", "admin"].includes(String(membership?.role ?? "").toLowerCase());

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

          if (module.name === "pos" && module.enabled && module.route) {
            const isPosActive = location.pathname.startsWith("/pos");

            return (
              <div className="nav-group" key={module.name}>
                <button
                  className={`nav-item nav-toggle ${isPosActive ? "active" : ""}`}
                  onClick={() => setPosExpanded((current) => !current)}
                  type="button"
                >
                  <NavLabel icon={moduleIcon} label={module.label} />
                  <ChevronDown
                    aria-hidden="true"
                    className={`nav-toggle-icon ${posExpanded ? "expanded" : ""}`}
                    size={16}
                    strokeWidth={ICON_STROKE}
                  />
                </button>

                {posExpanded ? (
                  <div className="nav-children">
                    {posNavItems.map((item) => {
                      const isActive = isPosActive && currentPosView === item.view;
                      return (
                        <Link
                          className={isActive ? "nav-child nav-child-active" : "nav-child"}
                          key={item.key}
                          to={item.path}
                        >
                          <NavLabel child icon={item.icon} label={item.label} />
                        </Link>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          }

          if (module.name === "pm" && module.enabled && module.route) {
            const isPmActive = isPmPath(location.pathname);

            return (
              <div className="nav-group" key={module.name}>
                <button
                  className={`nav-item nav-toggle ${isPmActive ? "active" : ""}`}
                  onClick={() => setPmExpanded((current) => !current)}
                  type="button"
                >
                  <NavLabel icon={moduleIcon} label={module.label} />
                  <ChevronDown
                    aria-hidden="true"
                    className={`nav-toggle-icon ${pmExpanded ? "expanded" : ""}`}
                    size={16}
                    strokeWidth={ICON_STROKE}
                  />
                </button>

                {pmExpanded ? (
                  <div className="nav-children">
                    {pmNavItems.map((item) => {
                      const isActive = isPmActive && currentPmView === item.key;
                      return (
                        <Link
                          className={isActive ? "nav-child nav-child-active" : "nav-child"}
                          key={item.key}
                          to={item.path}
                        >
                          <NavLabel child icon={item.icon} label={item.label} />
                        </Link>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          }

          if (module.name === "billing_pending" && canAccessBillingQueue) {
            return (
              <NavLink className={getNavClass} key={module.name} to={module.route || "/facturacion-pendiente"}>
                <NavLabel icon={moduleIcon} label={module.label} />
              </NavLink>
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
