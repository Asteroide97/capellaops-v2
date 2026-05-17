import { createContext, useContext, useEffect, useState } from "react";

import { apiRequest } from "../api/client";


const AuthContext = createContext(null);
const TOKEN_KEY = "capella_ops_token";
const EMPRESA_KEY = "capella_ops_empresa_id";


export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_KEY));
  const [empresaId, setEmpresaId] = useState(() => window.localStorage.getItem(EMPRESA_KEY));
  const [user, setUser] = useState(null);
  const [empresa, setEmpresa] = useState(null);
  const [membership, setMembership] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [modules, setModules] = useState([]);
  const [ready, setReady] = useState(false);

  function persistSession(nextToken, nextEmpresaId) {
    window.localStorage.setItem(TOKEN_KEY, nextToken);
    window.localStorage.setItem(EMPRESA_KEY, nextEmpresaId);
    setToken(nextToken);
    setEmpresaId(nextEmpresaId);
  }

  function clearSession() {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(EMPRESA_KEY);
    setToken(null);
    setEmpresaId(null);
    setUser(null);
    setEmpresa(null);
    setMembership(null);
    setEmpresas([]);
    setModules([]);
  }

  async function hydrateSession(activeToken, activeEmpresaId) {
    const me = await apiRequest("/me", {
      token: activeToken,
      empresaId: activeEmpresaId,
    });
    const moduleResponse = await apiRequest("/modules", {
      token: activeToken,
      empresaId: activeEmpresaId,
    });

    setUser(me.user);
    setEmpresa(me.empresa);
    setMembership(me.membership);
    setEmpresas(me.empresas);
    setModules(moduleResponse.modules);
  }

  async function login(credentials) {
    const response = await apiRequest("/auth/login", {
      method: "POST",
      body: credentials,
    });

    persistSession(response.access_token, response.empresa.id);
    setUser(response.user);
    setEmpresa(response.empresa);
    setMembership(response.membership);
    setEmpresas([response.empresa]);
    const moduleResponse = await apiRequest("/modules", {
      token: response.access_token,
      empresaId: response.empresa.id,
    });
    setModules(moduleResponse.modules);
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

    persistSession(response.access_token, response.empresa.id);
    setUser(response.user);
    setEmpresa(response.empresa);
    setMembership(response.membership);
    setEmpresas([response.empresa]);
    const moduleResponse = await apiRequest("/modules", {
      token: response.access_token,
      empresaId: response.empresa.id,
    });
    setModules(moduleResponse.modules);
  }

  async function refreshSession(nextEmpresaId = empresaId) {
    if (!token || !nextEmpresaId) {
      return;
    }

    await hydrateSession(token, nextEmpresaId);
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
      } catch {
        if (!cancelled) {
          clearSession();
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
    login,
    registerStart,
    registerVerify,
    logout,
    refreshSession,
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
