import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import AppLayout from "./components/AppLayout";
import FeaturePlaceholder from "./components/FeaturePlaceholder";
import DashboardPage from "./pages/DashboardPage";
import BillingPendingPage from "./pages/BillingPendingPage";
import CrmPage from "./pages/CrmPage";
import InventoryPage from "./pages/InventoryPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import PmPage from "./pages/PmPage";
import PosPage from "./pages/PosPage";
import RegisterPage from "./pages/RegisterPage";
import SuperadminPage from "./pages/SuperadminPage";


function ProtectedRoute() {
  const { token, ready } = useAuth();

  if (!ready) {
    return <div className="screen-center">Cargando sesión...</div>;
  }

  if (!token) {
    return <Navigate to="/login" replace />;
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
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route
            path="/inventario"
            element={
              <ModuleRoute moduleName="inventory">
                <InventoryPage />
              </ModuleRoute>
            }
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
