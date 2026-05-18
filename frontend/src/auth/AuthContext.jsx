import { createContext, useContext, useEffect, useState } from "react";

import { apiRequest, getInventoryOnboardingStatus } from "../api/client";


const AuthContext = createContext(null);
const TOKEN_KEY = "capella_ops_token";
const EMPRESA_KEY = "capella_ops_empresa_id";
const ORIGINAL_SUPERADMIN_TOKEN_KEY = "capella_ops_original_superadmin_token";
const ORIGINAL_SUPERADMIN_EMPRESA_KEY = "capella_ops_original_superadmin_empresa_id";

const DEFAULT_ONBOARDING = {
  requiresFirstWarehouse: false,
  warehousesCount: 0,
  message: "",
};


function buildOnboardingState(payload = DEFAULT_ONBOARDING) {
  return {
    requiresFirstWarehouse: Boolean(payload.requires_first_warehouse ?? payload.requiresFirstWarehouse),
    warehousesCount: payload.warehouses_count ?? payload.warehousesCount ?? 0,
    message: payload.message ?? "",
  };
}


export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_KEY));
  const [empresaId, setEmpresaId] = useState(() => window.localStorage.getItem(EMPRESA_KEY));
  const [user, setUser] = useState(null);
  const [empresa, setEmpresa] = useState(null);
  const [membership, setMembership] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [modules, setModules] = useState([]);
  const [impersonation, setImpersonation] = useState(false);
  const [impersonatedBy, setImpersonatedBy] = useState(null);
  const [impersonationEndsAt, setImpersonationEndsAt] = useState(null);
  const [inventoryOnboarding, setInventoryOnboarding] = useState(DEFAULT_ONBOARDING);
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(false);

  function persistSession(nextToken, nextEmpresaId) {
    window.localStorage.setItem(TOKEN_KEY, nextToken);
    window.localStorage.setItem(EMPRESA_KEY, nextEmpresaId);
    setToken(nextToken);
    setEmpresaId(nextEmpresaId);
  }

  function persistOriginalSuperadminSession(currentToken, currentEmpresaId) {
    window.localStorage.setItem(ORIGINAL_SUPERADMIN_TOKEN_KEY, currentToken);
    window.localStorage.setItem(ORIGINAL_SUPERADMIN_EMPRESA_KEY, currentEmpresaId);
  }

  function clearOriginalSuperadminSession() {
    window.localStorage.removeItem(ORIGINAL_SUPERADMIN_TOKEN_KEY);
    window.localStorage.removeItem(ORIGINAL_SUPERADMIN_EMPRESA_KEY);
  }

  function clearSession() {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(EMPRESA_KEY);
    clearOriginalSuperadminSession();
    setToken(null);
    setEmpresaId(null);
    setUser(null);
    setEmpresa(null);
    setMembership(null);
    setEmpresas([]);
    setModules([]);
    setImpersonation(false);
    setImpersonatedBy(null);
    setImpersonationEndsAt(null);
    setInventoryOnboarding(buildOnboardingState());
    setNotice("");
  }

  async function hydrateSession(activeToken, activeEmpresaId) {
    const [me, moduleResponse] = await Promise.all([
      apiRequest("/me", {
        token: activeToken,
        empresaId: activeEmpresaId,
      }),
      apiRequest("/modules", {
        token: activeToken,
        empresaId: activeEmpresaId,
      }),
    ]);

    setUser(me.user);
    setEmpresa(me.empresa);
    setMembership(me.membership);
    setEmpresas(me.empresas);
    setModules(moduleResponse.modules);
    setImpersonation(Boolean(me.impersonation));
    setImpersonatedBy(me.impersonated_by ?? null);
    setImpersonationEndsAt(me.impersonation_ends_at ?? null);
    setInventoryOnboarding(buildOnboardingState());

    const inventoryModule = moduleResponse.modules.find(
      (module) => module.name === "inventory" && module.enabled,
    );
    const shouldCheckOnboarding = Boolean(inventoryModule) && !me.user.is_superadmin;
    if (shouldCheckOnboarding) {
      try {
        const nextOnboarding = await getInventoryOnboardingStatus({
          token: activeToken,
          empresaId: activeEmpresaId,
        });
        setInventoryOnboarding(buildOnboardingState(nextOnboarding));
      } catch (error) {
        if (error?.status === 401) {
          throw error;
        }

        setInventoryOnboarding(buildOnboardingState());
        setNotice("No se pudo validar el estado inicial de inventario.");
      }
    }
  }

  async function login(credentials) {
    const response = await apiRequest("/auth/login", {
      method: "POST",
      body: credentials,
    });

    setNotice("");
    persistSession(response.access_token, response.empresa.id);
    await hydrateSession(response.access_token, response.empresa.id);
  }

  async function registerStart(payload) {
    const requestBody = {
      empresa_nombre: payload.empresa_nombre,
      nombre_completo: payload.nombre_completo,
      email: payload.email,
      country_code: payload.country_code,
      phone_number: payload.phone_number,
      password: payload.password,
      plan_code: payload.plan_code,
      recaptcha_token: payload.recaptcha_token,
    };

    return apiRequest("/auth/register/start", {
      method: "POST",
      body: requestBody,
    });
  }

  async function registerVerify(payload) {
    const response = await apiRequest("/auth/register/verify", {
      method: "POST",
      body: {
        pending_id: payload.pending_id,
        code: payload.code,
      },
    });

    setNotice("");
    persistSession(response.access_token, response.empresa.id);
    await hydrateSession(response.access_token, response.empresa.id);
  }

  async function refreshSession(nextEmpresaId = empresaId) {
    if (!token || !nextEmpresaId) {
      return;
    }

    await hydrateSession(token, nextEmpresaId);
  }

  async function startImpersonationSession(nextSession) {
    if (!token || !empresaId) {
      throw new Error("No hay una sesión base para iniciar la impersonación.");
    }

    if (!impersonation) {
      persistOriginalSuperadminSession(token, empresaId);
    }

    persistSession(nextSession.access_token, nextSession.empresa_id);
    await hydrateSession(nextSession.access_token, nextSession.empresa_id);
    setNotice("Impersonación iniciada.");
  }

  async function exitImpersonation() {
    const originalToken = window.localStorage.getItem(ORIGINAL_SUPERADMIN_TOKEN_KEY);
    const originalEmpresaId = window.localStorage.getItem(ORIGINAL_SUPERADMIN_EMPRESA_KEY);

    if (!originalToken || !originalEmpresaId) {
      throw new Error("No hay una impersonación activa.");
    }

    clearOriginalSuperadminSession();
    persistSession(originalToken, originalEmpresaId);
    await hydrateSession(originalToken, originalEmpresaId);
    setNotice("Impersonación finalizada.");
  }

  function dismissNotice() {
    setNotice("");
  }

  function logout() {
    clearSession();
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (!token || !empresaId) {
        setReady(true);
        return;
      }

      try {
        await hydrateSession(token, empresaId);
      } catch (error) {
        if (!cancelled) {
          if (error?.status === 401) {
            clearSession();
          } else {
            setNotice(error?.message ?? "No se pudo actualizar la sesión actual.");
          }
        }
      } finally {
        if (!cancelled) {
          setReady(true);
        }
      }
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [token, empresaId]);

  useEffect(() => {
    if (!ready && !token) {
      setReady(true);
    }
  }, [ready, token]);

  const value = {
    token,
    empresaId,
    user,
    empresa,
    membership,
    empresas,
    modules,
    ready,
    impersonation,
    impersonatedBy,
    impersonationEndsAt,
    requiresFirstWarehouse: inventoryOnboarding.requiresFirstWarehouse,
    warehousesCount: inventoryOnboarding.warehousesCount,
    onboardingMessage: inventoryOnboarding.message,
    notice,
    login,
    registerStart,
    registerVerify,
    refreshSession,
    startImpersonationSession,
    exitImpersonation,
    dismissNotice,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}


export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth debe usarse dentro de AuthProvider.");
  }

  return context;
}
