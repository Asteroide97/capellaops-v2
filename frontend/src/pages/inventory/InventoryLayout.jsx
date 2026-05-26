import { Outlet, useLocation } from "react-router-dom";

import { inventoryNavItems } from "./navigation";


export default function InventoryLayout() {
  const location = useLocation();
  const currentItem =
    inventoryNavItems.find((item) => location.pathname === item.path) ??
    inventoryNavItems.find((item) => location.pathname.startsWith(item.path));

  return (
    <section className="inventory-shell">
      <div className="hero-card inventory-hero">
        <div>
          <p className="eyebrow">Inventario Operativo</p>
          <h2>{currentItem?.label ?? "Inventario"}</h2>
          <p>
            {currentItem?.description ??
              "Control multiempresa de existencias, movimientos, traspasos y compras conectadas al stock real."}
          </p>
        </div>
      </div>

      <Outlet />
    </section>
  );
}
