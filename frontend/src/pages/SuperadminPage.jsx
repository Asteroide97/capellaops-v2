import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  getSuperadminAuditLogs,
  getSuperadminCompanies,
  getSuperadminCompanyDetail,
  getSuperadminOverview,
  getSuperadminUserDetail,
  getSuperadminUsers,
  impersonateUser,
  updateCompanyAccess,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import FeaturePlaceholder from "../components/FeaturePlaceholder";


const superadminTabs = [
  { id: "resumen", label: "Resumen" },
  { id: "empresas", label: "Empresas" },
  { id: "usuarios", label: "Usuarios" },
  { id: "trials", label: "Trials" },
  { id: "pagos", label: "Pagos / Estado comercial" },
  { id: "auditoria", label: "Auditoría" },
];


function formatDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}


function computeTrialState(trialEndsAt) {
  if (!trialEndsAt) {
    return "Sin fecha";
  }

  const now = Date.now();
  const endTime = new Date(trialEndsAt).getTime();
  const diffDays = (endTime - now) / (1000 * 60 * 60 * 24);
  if (diffDays < 0) {
    return "Vencido";
  }
  if (diffDays <= 7) {
    return "Por vencer";
  }
  return "Vigente";
}


function EmptyState({ title, note }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{note}</p>
    </div>
  );
}


export default function SuperadminPage() {
  const navigate = useNavigate();
  const {
    impersonation,
    startImpersonationSession,
    token,
    user,
  } = useAuth();
  const [activeTab, setActiveTab] = useState("resumen");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [overview, setOverview] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [companiesTotal, setCompaniesTotal] = useState(0);
  const [users, setUsers] = useState([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditLogsTotal, setAuditLogsTotal] = useState(0);
  const [selectedCompanyDetail, setSelectedCompanyDetail] = useState(null);
  const [selectedUserDetail, setSelectedUserDetail] = useState(null);
  const [actionReason, setActionReason] = useState("");
  const [companyFilters, setCompanyFilters] = useState({
    q: "",
    plan_code: "",
    access_status: "",
    trial_status: "",
    limit: 25,
    offset: 0,
  });
  const [userFilters, setUserFilters] = useState({
    q: "",
    limit: 25,
    offset: 0,
  });
  const [auditFilters, setAuditFilters] = useState({
    q: "",
    limit: 25,
    offset: 0,
  });
  const [accessForm, setAccessForm] = useState({
    plan_code: "basico",
    access_status: "trial",
    trial_ends_at: "",
  });

  const trialCompanies = useMemo(
    () => companies.filter((company) => company.access_status === "trial"),
    [companies],
  );

  const commercialCompanies = useMemo(
    () =>
      companies.map((company) => ({
        ...company,
        estado_comercial:
          company.estado_pago || "Integración de pagos pendiente",
      })),
    [companies],
  );

  async function loadPortalData({
    nextCompanyFilters = companyFilters,
    nextUserFilters = userFilters,
    nextAuditFilters = auditFilters,
  } = {}) {
    if (!token) {
      return;
    }

    const [overviewResponse, companyResponse, userResponse, auditResponse] = await Promise.all([
      getSuperadminOverview({ token }),
      getSuperadminCompanies({ token, filters: nextCompanyFilters }),
      getSuperadminUsers({ token, filters: nextUserFilters }),
      getSuperadminAuditLogs({ token, filters: nextAuditFilters }),
    ]);

    setOverview(overviewResponse);
    setCompanies(companyResponse.items);
    setCompaniesTotal(companyResponse.total);
    setUsers(userResponse.items);
    setUsersTotal(userResponse.total);
    setAuditLogs(auditResponse.items);
    setAuditLogsTotal(auditResponse.total);
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (!token || !user?.is_superadmin || impersonation) {
        setLoading(false);
        return;
      }

      try {
        await loadPortalData();
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message || "No se pudo cargar el portal Superadmin.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [token, user?.is_superadmin, impersonation]);

  async function handleLoadCompanyDetail(empresaId) {
    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await getSuperadminCompanyDetail({ empresaId, token });
      setSelectedCompanyDetail(response);
      setSelectedUserDetail(null);
      setAccessForm({
        plan_code: response.plan_code,
        access_status: response.access_status,
        trial_ends_at: response.trial_ends_at ? response.trial_ends_at.slice(0, 16) : "",
      });
      setActiveTab("empresas");
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle de la empresa.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadUserDetail(usuarioId) {
    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await getSuperadminUserDetail({ usuarioId, token });
      setSelectedUserDetail(response);
      setSelectedCompanyDetail(null);
      setActiveTab("usuarios");
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar el detalle del usuario.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRefreshAll() {
    setBusy(true);
    setError("");

    try {
      await loadPortalData();
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar la información.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCompanyFilterSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const response = await getSuperadminCompanies({ token, filters: companyFilters });
      setCompanies(response.items);
      setCompaniesTotal(response.total);
    } catch (requestError) {
      setError(requestError.message || "No se pudo filtrar empresas.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUserFilterSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const response = await getSuperadminUsers({ token, filters: userFilters });
      setUsers(response.items);
      setUsersTotal(response.total);
    } catch (requestError) {
      setError(requestError.message || "No se pudo filtrar usuarios.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAuditFilterSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const response = await getSuperadminAuditLogs({ token, filters: auditFilters });
      setAuditLogs(response.items);
      setAuditLogsTotal(response.total);
    } catch (requestError) {
      setError(requestError.message || "No se pudo filtrar la auditoría.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpdateCompanyAccess(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");

    if (!selectedCompanyDetail) {
      setBusy(false);
      setError("Selecciona una empresa primero.");
      return;
    }

    if (!actionReason.trim()) {
      setBusy(false);
      setError("Debes indicar una razón para este cambio.");
      return;
    }

    try {
      const response = await updateCompanyAccess({
        empresaId: selectedCompanyDetail.id,
        token,
        payload: {
          plan_code: accessForm.plan_code,
          access_status: accessForm.access_status,
          trial_ends_at: accessForm.trial_ends_at
            ? new Date(accessForm.trial_ends_at).toISOString()
            : null,
          reason: actionReason,
        },
      });
      setSelectedCompanyDetail(response);
      setSuccess("Estado comercial actualizado.");
      await loadPortalData();
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar la empresa.");
    } finally {
      setBusy(false);
    }
  }

  async function handleImpersonate({ empresaId, usuarioId }) {
    if (!actionReason.trim()) {
      setError("Debes indicar una razón para este cambio.");
      return;
    }

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const response = await impersonateUser({
        token,
        payload: {
          empresa_id: empresaId,
          usuario_id: usuarioId,
          reason: actionReason,
        },
      });
      await startImpersonationSession(response);
      navigate("/");
    } catch (requestError) {
      setError(requestError.message || "No se pudo iniciar la impersonación.");
    } finally {
      setBusy(false);
    }
  }

  async function handleImpersonatePrimary(company) {
    setBusy(true);
    setError("");
    setSuccess("");

    try {
      const detail = await getSuperadminCompanyDetail({ empresaId: company.id, token });
      const primaryUser = detail.users[0];
      if (!primaryUser) {
        throw new Error("La empresa no tiene usuarios para impersonar.");
      }
      await handleImpersonate({
        empresaId: company.id,
        usuarioId: primaryUser.usuario_id,
      });
    } catch (requestError) {
      setError(requestError.message || "No se pudo impersonar al usuario principal.");
      setBusy(false);
    }
  }

  if (impersonation) {
    return (
      <FeaturePlaceholder
        title="Superadmin"
        subtitle="No puedes acceder a Superadmin mientras estás impersonando."
        items={["Salir de impersonación", "Volver al portal", "Revisar contexto actual", "Mantener auditoría"]}
        note="El backend también bloquea el acceso a los endpoints de Superadmin cuando el token está impersonado."
        tone="warning"
      />
    );
  }

  if (!user?.is_superadmin) {
    return (
      <FeaturePlaceholder
        title="Superadmin"
        subtitle="No tienes permiso para acceder al portal Superadmin."
        items={["Permisos centralizados", "Monitoreo", "Soporte", "Configuración avanzada"]}
        note="El frontend no concede acceso por sí mismo. El backend sigue validando este permiso."
        tone="warning"
      />
    );
  }

  if (loading) {
    return <div className="screen-center">Cargando portal Superadmin...</div>;
  }

  return (
    <section className="inventory-shell">
      <div className="hero-card inventory-hero">
        <div>
          <p className="eyebrow">Portal Superadmin</p>
          <h2>Control operativo de clientes, trials, accesos e impersonación</h2>
          <p>
            Este portal no expone secretos ni credenciales. Los cambios críticos quedan
            auditados y la integración de pagos sigue como placeholder.
          </p>
        </div>

        <div className="inventory-actions">
          <button className="ghost-button" disabled={busy} onClick={handleRefreshAll} type="button">
            {busy ? "Actualizando..." : "Actualizar datos"}
          </button>
        </div>
      </div>

      <div className="feature-card setup-inline-card">
        <div className="feature-header">
          <p className="eyebrow">Razón operativa</p>
          <h2>Razón para acciones críticas</h2>
          <p>Esta razón se usará para cambios de estado e impersonaciones.</p>
        </div>
        <label>
          Razón
          <input
            onChange={(event) => setActionReason(event.target.value)}
            placeholder="Ejemplo: soporte operativo, revisión de trial, cambio comercial"
            type="text"
            value={actionReason}
          />
        </label>
      </div>

      <div className="inventory-tabs">
        {superadminTabs.map((tab) => (
          <button
            className={`inventory-tab-button ${activeTab === tab.id ? "active" : ""}`}
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {success ? <p className="form-success">{success}</p> : null}

      {activeTab === "resumen" ? (
        <div className="dashboard-stack">
          <div className="hero-grid">
            <article className="metric-card">
              <span>Empresas</span>
              <strong>{overview?.total_empresas ?? 0}</strong>
            </article>
            <article className="metric-card">
              <span>Usuarios</span>
              <strong>{overview?.total_usuarios ?? 0}</strong>
            </article>
            <article className="metric-card">
              <span>En trial</span>
              <strong>{overview?.empresas_en_trial ?? 0}</strong>
            </article>
            <article className="metric-card">
              <span>Activas</span>
              <strong>{overview?.empresas_activas ?? 0}</strong>
            </article>
            <article className="metric-card">
              <span>Suspendidas</span>
              <strong>{overview?.empresas_suspendidas ?? 0}</strong>
            </article>
            <article className="metric-card">
              <span>Trials por vencer</span>
              <strong>{overview?.trials_por_vencer_7_dias ?? 0}</strong>
            </article>
          </div>

          <div className="module-board">
            <article className="module-card">
              <div className="module-card-top">
                <h3>Plan básico</h3>
                <span className="status-badge enabled">{overview?.plan_counts?.basico ?? 0}</span>
              </div>
            </article>
            <article className="module-card">
              <div className="module-card-top">
                <h3>Plan pro</h3>
                <span className="status-badge enabled">{overview?.plan_counts?.pro ?? 0}</span>
              </div>
            </article>
            <article className="module-card">
              <div className="module-card-top">
                <h3>Plan total</h3>
                <span className="status-badge enabled">{overview?.plan_counts?.total ?? 0}</span>
              </div>
            </article>
          </div>
        </div>
      ) : null}

      {activeTab === "empresas" ? (
        <div className="inventory-grid superadmin-grid">
          <div className="feature-card inventory-form-card">
            <div className="feature-header">
              <p className="eyebrow">Empresas</p>
              <h2>Filtros y acciones</h2>
              <p>Total actual: {companiesTotal}</p>
            </div>

            <form className="inventory-form-grid" onSubmit={handleCompanyFilterSubmit}>
              <label className="inventory-form-span-2">
                Buscar
                <input
                  onChange={(event) =>
                    setCompanyFilters((current) => ({ ...current, q: event.target.value }))
                  }
                  placeholder="Nombre o slug"
                  type="text"
                  value={companyFilters.q}
                />
              </label>

              <label>
                Plan
                <select
                  onChange={(event) =>
                    setCompanyFilters((current) => ({ ...current, plan_code: event.target.value }))
                  }
                  value={companyFilters.plan_code}
                >
                  <option value="">Todos</option>
                  <option value="basico">Básico</option>
                  <option value="pro">Pro</option>
                  <option value="total">Total</option>
                </select>
              </label>

              <label>
                Estado
                <select
                  onChange={(event) =>
                    setCompanyFilters((current) => ({ ...current, access_status: event.target.value }))
                  }
                  value={companyFilters.access_status}
                >
                  <option value="">Todos</option>
                  <option value="trial">trial</option>
                  <option value="active">active</option>
                  <option value="past_due">past_due</option>
                  <option value="suspended">suspended</option>
                  <option value="cancelled">cancelled</option>
                </select>
              </label>

              <label className="inventory-form-span-2">
                Trial
                <select
                  onChange={(event) =>
                    setCompanyFilters((current) => ({ ...current, trial_status: event.target.value }))
                  }
                  value={companyFilters.trial_status}
                >
                  <option value="">Todos</option>
                  <option value="active">Activo</option>
                  <option value="ending_soon">Por vencer</option>
                  <option value="expired">Vencido</option>
                </select>
              </label>

              <button className="primary-button" disabled={busy} type="submit">
                Filtrar empresas
              </button>
            </form>
          </div>

          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Clientes</p>
              <h2>Empresas registradas</h2>
            </div>

            {companies.length === 0 ? (
              <EmptyState title="No hay empresas para mostrar." note="Ajusta filtros o recarga la vista." />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Empresa</th>
                      <th>Plan</th>
                      <th>Estado</th>
                      <th>Trial termina</th>
                      <th>Usuarios</th>
                      <th>Almacenes</th>
                      <th>Materiales</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {companies.map((company) => (
                      <tr key={company.id}>
                        <td>
                          <strong>{company.nombre}</strong>
                          <div className="table-note">Creada: {formatDateTime(company.created_at)}</div>
                        </td>
                        <td>{company.plan_code}</td>
                        <td>{company.access_status}</td>
                        <td>{formatDateTime(company.trial_ends_at)}</td>
                        <td>{company.usuarios_count}</td>
                        <td>{company.almacenes_count}</td>
                        <td>{company.materiales_count}</td>
                        <td className="inventory-row-actions">
                          <button
                            className="link-button"
                            onClick={() => handleLoadCompanyDetail(company.id)}
                            type="button"
                          >
                            Ver detalle
                          </button>
                          <button
                            className="link-button"
                            onClick={() => handleImpersonatePrimary(company)}
                            type="button"
                          >
                            Impersonar principal
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selectedCompanyDetail ? (
              <div className="feature-card">
                <div className="feature-header">
                  <p className="eyebrow">Detalle empresa</p>
                  <h2>{selectedCompanyDetail.nombre}</h2>
                  <p>
                    {selectedCompanyDetail.plan_code} | {selectedCompanyDetail.access_status}
                  </p>
                </div>

                <div className="module-board">
                  <article className="mini-card">
                    <span className="eyebrow">Empresa</span>
                    <strong>{selectedCompanyDetail.razon_social || "Sin razon social"}</strong>
                    <p>{selectedCompanyDetail.rfc || "Sin RFC"}</p>
                  </article>
                  <article className="mini-card">
                    <span className="eyebrow">Contacto</span>
                    <strong>{selectedCompanyDetail.email_contacto || "-"}</strong>
                    <p>{selectedCompanyDetail.telefono || "-"}</p>
                  </article>
                  <article className="mini-card">
                    <span className="eyebrow">Limites</span>
                    <strong>
                      Usuarios {selectedCompanyDetail.limits.usuarios_actuales} / {selectedCompanyDetail.limits.max_usuarios ?? "Ilimitado"}
                    </strong>
                    <p>
                      Almacenes {selectedCompanyDetail.limits.almacenes_actuales} / {selectedCompanyDetail.limits.max_almacenes ?? "Ilimitado"}
                    </p>
                  </article>
                </div>

                <form className="inventory-form-grid" onSubmit={handleUpdateCompanyAccess}>
                  <label>
                    Plan
                    <select
                      onChange={(event) =>
                        setAccessForm((current) => ({ ...current, plan_code: event.target.value }))
                      }
                      value={accessForm.plan_code}
                    >
                      <option value="basico">Básico</option>
                      <option value="pro">Pro</option>
                      <option value="total">Total</option>
                    </select>
                  </label>

                  <label>
                    access_status
                    <select
                      onChange={(event) =>
                        setAccessForm((current) => ({ ...current, access_status: event.target.value }))
                      }
                      value={accessForm.access_status}
                    >
                      <option value="trial">trial</option>
                      <option value="active">active</option>
                      <option value="past_due">past_due</option>
                      <option value="suspended">suspended</option>
                      <option value="cancelled">cancelled</option>
                    </select>
                  </label>

                  <label className="inventory-form-span-2">
                    Trial termina
                    <input
                      onChange={(event) =>
                        setAccessForm((current) => ({ ...current, trial_ends_at: event.target.value }))
                      }
                      type="datetime-local"
                      value={accessForm.trial_ends_at}
                    />
                  </label>

                  <button className="primary-button" disabled={busy} type="submit">
                    Guardar plan / estado
                  </button>
                </form>

                <div className="module-board">
                  <article className="mini-card">
                    <span className="eyebrow">Inventario</span>
                    <strong>{selectedCompanyDetail.inventory_counts.almacenes} almacenes</strong>
                    <p>{selectedCompanyDetail.inventory_counts.materiales} materiales</p>
                  </article>
                  <article className="mini-card">
                    <span className="eyebrow">Stock</span>
                    <strong>{selectedCompanyDetail.inventory_counts.existencias} existencias</strong>
                    <p>{selectedCompanyDetail.inventory_counts.movimientos} movimientos</p>
                  </article>
                </div>

                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>Usuario</th>
                        <th>Rol</th>
                        <th>Teléfono</th>
                        <th>Último login</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedCompanyDetail.users.map((companyUser) => (
                        <tr key={companyUser.usuario_id}>
                          <td>
                            <strong>{companyUser.nombre_completo}</strong>
                            <div className="table-note">{companyUser.email}</div>
                          </td>
                          <td>{companyUser.role}</td>
                          <td>{companyUser.phone_e164_masked || "-"}</td>
                          <td>{formatDateTime(companyUser.last_login_at)}</td>
                          <td className="inventory-row-actions">
                            <button
                              className="link-button"
                              onClick={() => handleLoadUserDetail(companyUser.usuario_id)}
                              type="button"
                            >
                              Ver usuario
                            </button>
                            <button
                              className="link-button"
                              onClick={() =>
                                handleImpersonate({
                                  empresaId: selectedCompanyDetail.id,
                                  usuarioId: companyUser.usuario_id,
                                })
                              }
                              type="button"
                            >
                              Impersonar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {activeTab === "usuarios" ? (
        <div className="inventory-grid superadmin-grid">
          <div className="feature-card inventory-form-card">
            <div className="feature-header">
              <p className="eyebrow">Usuarios</p>
              <h2>Filtros</h2>
              <p>Total actual: {usersTotal}</p>
            </div>

            <form className="inventory-form-grid" onSubmit={handleUserFilterSubmit}>
              <label className="inventory-form-span-2">
                Buscar
                <input
                  onChange={(event) =>
                    setUserFilters((current) => ({ ...current, q: event.target.value }))
                  }
                  placeholder="Nombre o correo"
                  type="text"
                  value={userFilters.q}
                />
              </label>

              <button className="primary-button" disabled={busy} type="submit">
                Filtrar usuarios
              </button>
            </form>
          </div>

          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Usuarios</p>
              <h2>Directorio operativo</h2>
            </div>

            {users.length === 0 ? (
              <EmptyState title="No hay usuarios para mostrar." note="Ajusta filtros o recarga la vista." />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Nombre</th>
                      <th>Email</th>
                      <th>Teléfono</th>
                      <th>Empresas</th>
                      <th>Último login</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((currentUser) => (
                      <tr key={currentUser.id}>
                        <td>{currentUser.nombre_completo}</td>
                        <td>{currentUser.email}</td>
                        <td>{currentUser.phone_e164_masked || "-"}</td>
                        <td>
                          {currentUser.empresas.length === 0
                            ? "-"
                            : currentUser.empresas.map((company) => company.empresa_nombre).join(", ")}
                        </td>
                        <td>{formatDateTime(currentUser.last_login_at)}</td>
                        <td className="inventory-row-actions">
                          <button
                            className="link-button"
                            onClick={() => handleLoadUserDetail(currentUser.id)}
                            type="button"
                          >
                            Ver detalle
                          </button>
                          <button
                            className="link-button"
                            disabled={currentUser.empresas.length === 0}
                            onClick={() =>
                              handleImpersonate({
                                empresaId: currentUser.empresas[0]?.empresa_id,
                                usuarioId: currentUser.id,
                              })
                            }
                            type="button"
                          >
                            Impersonar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selectedUserDetail ? (
              <div className="feature-card">
                <div className="feature-header">
                  <p className="eyebrow">Detalle usuario</p>
                  <h2>{selectedUserDetail.nombre_completo}</h2>
                  <p>{selectedUserDetail.email}</p>
                </div>

                <div className="table-wrap">
                  <table className="inventory-table">
                    <thead>
                      <tr>
                        <th>Empresa</th>
                        <th>Rol</th>
                        <th>Plan</th>
                        <th>Estado</th>
                        <th>Acción</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedUserDetail.empresas.map((company) => (
                        <tr key={`${selectedUserDetail.id}-${company.empresa_id}`}>
                          <td>{company.empresa_nombre}</td>
                          <td>{company.role}</td>
                          <td>{company.plan_code}</td>
                          <td>{company.access_status}</td>
                          <td>
                            <button
                              className="link-button"
                              onClick={() =>
                                handleImpersonate({
                                  empresaId: company.empresa_id,
                                  usuarioId: selectedUserDetail.id,
                                })
                              }
                              type="button"
                            >
                              Impersonar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {activeTab === "trials" ? (
        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Trials</p>
            <h2>Empresas en trial</h2>
          </div>

          {trialCompanies.length === 0 ? (
            <EmptyState title="No hay empresas en trial en la vista actual." note="Actualiza o cambia filtros de empresas." />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Empresa</th>
                    <th>Plan</th>
                    <th>Trial termina</th>
                    <th>Estado trial</th>
                  </tr>
                </thead>
                <tbody>
                  {trialCompanies.map((company) => (
                    <tr key={company.id}>
                      <td>{company.nombre}</td>
                      <td>{company.plan_code}</td>
                      <td>{formatDateTime(company.trial_ends_at)}</td>
                      <td>{computeTrialState(company.trial_ends_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      {activeTab === "pagos" ? (
        <div className="feature-card inventory-table-card">
          <div className="feature-header">
            <p className="eyebrow">Estado comercial</p>
            <h2>Pagos / Estado comercial</h2>
            <p>Stripe y cobros reales siguen pendientes. Esta vista solo controla estatus administrativo.</p>
          </div>

          {commercialCompanies.length === 0 ? (
            <EmptyState title="No hay empresas para mostrar." note="Actualiza la lista de empresas." />
          ) : (
            <div className="table-wrap">
              <table className="inventory-table">
                <thead>
                  <tr>
                    <th>Empresa</th>
                    <th>Plan</th>
                    <th>access_status</th>
                    <th>Trial termina</th>
                    <th>Estado comercial</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {commercialCompanies.map((company) => (
                    <tr key={company.id}>
                      <td>{company.nombre}</td>
                      <td>{company.plan_code}</td>
                      <td>{company.access_status}</td>
                      <td>{formatDateTime(company.trial_ends_at)}</td>
                      <td>{company.estado_comercial}</td>
                      <td>
                        <button
                          className="link-button"
                          onClick={() => handleLoadCompanyDetail(company.id)}
                          type="button"
                        >
                          Gestionar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      {activeTab === "auditoria" ? (
        <div className="inventory-grid superadmin-grid">
          <div className="feature-card inventory-form-card">
            <div className="feature-header">
              <p className="eyebrow">Auditoría</p>
              <h2>Filtros</h2>
              <p>Total actual: {auditLogsTotal}</p>
            </div>

            <form className="inventory-form-grid" onSubmit={handleAuditFilterSubmit}>
              <label className="inventory-form-span-2">
                Buscar
                <input
                  onChange={(event) =>
                    setAuditFilters((current) => ({ ...current, q: event.target.value }))
                  }
                  placeholder="Acción o entidad"
                  type="text"
                  value={auditFilters.q}
                />
              </label>

              <button className="primary-button" disabled={busy} type="submit">
                Filtrar auditoría
              </button>
            </form>
          </div>

          <div className="feature-card inventory-table-card">
            <div className="feature-header">
              <p className="eyebrow">Logs recientes</p>
              <h2>Auditoría del sistema</h2>
            </div>

            {auditLogs.length === 0 ? (
              <EmptyState title="No hay eventos de auditoría." note="Las acciones críticas aparecerán aquí." />
            ) : (
              <div className="table-wrap">
                <table className="inventory-table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Acción</th>
                      <th>Empresa</th>
                      <th>Usuario</th>
                      <th>Entidad</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log) => (
                      <tr key={log.id}>
                        <td>{formatDateTime(log.created_at)}</td>
                        <td>{log.action}</td>
                        <td>{log.empresa_nombre || "-"}</td>
                        <td>{log.usuario_nombre || "-"}</td>
                        <td>{log.entity_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
