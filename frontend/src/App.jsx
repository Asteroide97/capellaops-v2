import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import AppLayout from "./components/AppLayout";
import FeaturePlaceholder from "./components/FeaturePlaceholder";
import BillingPendingPage from "./pages/BillingPendingPage";
import CompanyUsersPage from "./pages/CompanyUsersPage";
import CrmPage from "./pages/CrmPage";
import DashboardPage from "./pages/DashboardPage";
import FirstWarehouseSetupPage from "./pages/FirstWarehouseSetupPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import PmPage from "./pages/PmPage";
import PosPage from "./pages/PosPage";
import RegisterPage from "./pages/RegisterPage";
import SuperadminPage from "./pages/SuperadminPage";
import AssetsPage from "./pages/inventory/AssetsPage";
import InventoryLayout from "./pages/inventory/InventoryLayout";
import InventoryReportsPage from "./pages/inventory/InventoryReportsPage";
import InventorySummaryPage from "./pages/inventory/InventorySummaryPage";
import KardexPage from "./pages/inventory/KardexPage";
import MaterialsPage from "./pages/inventory/MaterialsPage";
import MovementsPage from "./pages/inventory/MovementsPage";
import ProjectsInventoryPage from "./pages/inventory/ProjectsInventoryPage";
import PurchaseOrdersPage from "./pages/inventory/PurchaseOrdersPage";
import RequisitionsPage from "./pages/inventory/RequisitionsPage";
import SuppliersPage from "./pages/inventory/SuppliersPage";
import TransfersPage from "./pages/inventory/TransfersPage";
import WarehousesPage from "./pages/inventory/WarehousesPage";
import WorkOrdersPage from "./pages/inventory/WorkOrdersPage";


function ProtectedRoute() {
  const location = useLocation();
  const { token, ready, requiresFirstWarehouse } = useAuth();
  const setupPath = "/configuracion-inicial/almacen";

  if (!ready) {
    return <div className="screen-center">Cargando sesión...</div>;
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  const isSetupRoute = location.pathname === setupPath;
  if (requiresFirstWarehouse && !isSetupRoute) {
    return <Navigate to={setupPath} replace />;
  }

  if (!requiresFirstWarehouse && isSetupRoute) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}


function PublicOnlyRoute({ children }) {
  const { token, ready } = useAuth();

  if (!ready) {
    return <div className="screen-center">Cargando...</div>;
  }

  if (token) {
    return <Navigate to="/" replace />;
  }

  return children;
}


function ModuleRoute({ children, moduleName, allowPending = false }) {
  const { modules, ready } = useAuth();

  if (!ready) {
    return <div className="screen-center">Cargando módulo...</div>;
  }

  const module = modules.find((item) => item.name === moduleName);
  const canRender = allowPending ? Boolean(module) : Boolean(module?.enabled);

  if (!canRender) {
    return (
      <FeaturePlaceholder
        title="Acceso restringido"
        subtitle="Este módulo no está disponible para la empresa activa."
        items={["Plan vigente", "Estado de la empresa", "Permisos backend", "Contexto multiempresa"]}
        note="La visibilidad final depende del backend y de la función central can_access_module."
        tone="warning"
      />
    );
  }

  return children;
}


export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/registro"
        element={
          <PublicOnlyRoute>
            <RegisterPage />
          </PublicOnlyRoute>
        }
      />

      <Route element={<ProtectedRoute />}>
        <Route path="/configuracion-inicial/almacen" element={<FirstWarehouseSetupPage />} />

        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route
            path="/inventario"
            element={
              <ModuleRoute moduleName="inventory">
                <InventoryLayout />
              </ModuleRoute>
            }
          >
            <Route index element={<Navigate replace to="/inventario/resumen" />} />
            <Route path="resumen" element={<InventorySummaryPage />} />
            <Route path="almacenes" element={<WarehousesPage />} />
            <Route path="materiales" element={<MaterialsPage />} />
            <Route path="movimientos" element={<MovementsPage />} />
            <Route path="kardex" element={<KardexPage />} />
            <Route path="traspasos" element={<TransfersPage />} />
            <Route path="proveedores" element={<SuppliersPage />} />
            <Route path="ordenes-compra" element={<PurchaseOrdersPage />} />
            <Route path="requisiciones" element={<RequisitionsPage />} />
            <Route path="proyectos" element={<ProjectsInventoryPage />} />
            <Route path="equipos" element={<AssetsPage />} />
            <Route path="ordenes-trabajo" element={<WorkOrdersPage />} />
            <Route path="reportes" element={<InventoryReportsPage />} />
          </Route>
          <Route
            path="/empresa/usuarios"
            element={<CompanyUsersPage />}
          />
          <Route
            path="/pos"
            element={
              <ModuleRoute moduleName="pos">
                <PosPage />
              </ModuleRoute>
            }
          />
          <Route
            path="/crm"
            element={
              <ModuleRoute moduleName="crm">
                <CrmPage />
              </ModuleRoute>
            }
          />
          <Route
            path="/pm"
            element={
              <ModuleRoute moduleName="pm">
                <PmPage />
              </ModuleRoute>
            }
          />
          <Route
            path="/facturacion-pendiente"
            element={
              <ModuleRoute allowPending moduleName="billing_pending">
                <BillingPendingPage />
              </ModuleRoute>
            }
          />
          <Route path="/superadmin" element={<SuperadminPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
