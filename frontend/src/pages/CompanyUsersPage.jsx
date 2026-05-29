import { useEffect, useState } from "react";

import {
  deactivateCompanyUser,
  getCompanyUsers,
  inviteCompanyUser,
  updateCompanyUser,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import FeaturePlaceholder from "../components/FeaturePlaceholder";
import {
  ActionButton,
  DataCard,
  DataTable,
  EmptyState,
  Field,
  FormGrid,
  PageHeader,
  StatusBadge,
  formatDateTime,
  safeDisplayText,
  toDisplayText,
} from "./inventory/shared";


const defaultInviteForm = {
  full_name: "",
  email: "",
  role: "user",
};


function formatLimit(current, max) {
  if (max === null || max === undefined) {
    return `${current} / Ilimitado`;
  }
  return `${current} / ${max}`;
}


export default function CompanyUsersPage() {
  const { empresa, empresaId, limits, membership, token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [inviteForm, setInviteForm] = useState(defaultInviteForm);
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({
    plan_code: "",
    limits,
  });
  const canManage = membership?.role === "owner" || membership?.role === "admin";

  async function loadCompanyUsers() {
    const response = await getCompanyUsers({ token, empresaId });
    setItems(response.items);
    setMeta({
      plan_code: response.plan_code,
      limits: response.limits,
    });
  }

  useEffect(() => {
    async function bootstrap() {
      if (!token || !empresaId || !canManage) {
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");
      try {
        await loadCompanyUsers();
      } catch (requestError) {
        setError(requestError.message || "No se pudieron cargar los usuarios de la empresa.");
      } finally {
        setLoading(false);
      }
    }

    bootstrap();
  }, [token, empresaId, canManage]);

  if (!canManage) {
    return (
      <FeaturePlaceholder
        title="Usuarios de empresa"
        subtitle="Solo owner o admin pueden administrar miembros de la empresa."
        items={["Invitaciones", "Roles", "Límites por plan", "Membresías activas"]}
        note="El backend también valida este permiso."
        tone="warning"
      />
    );
  }

  if (loading) {
    return <div className="screen-center">Cargando usuarios de la empresa...</div>;
  }

  const currentLimits = meta.limits ?? limits;
  const isUserLimitReached =
    currentLimits?.max_usuarios !== null &&
    currentLimits?.max_usuarios !== undefined &&
    currentLimits.usuarios_actuales >= currentLimits.max_usuarios;

  async function handleInviteSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const response = await inviteCompanyUser({
        token,
        empresaId,
        payload: inviteForm,
      });
      setSuccess(response.message);
      setInviteForm(defaultInviteForm);
      await loadCompanyUsers();
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar la invitacion.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRoleChange(membershipId, role) {
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const response = await updateCompanyUser({
        membershipId,
        token,
        empresaId,
        payload: { role },
      });
      setSuccess(response.message);
      await loadCompanyUsers();
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el rol.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(item) {
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const response = item.is_active
        ? await deactivateCompanyUser({
            membershipId: item.id,
            token,
            empresaId,
          })
        : await updateCompanyUser({
            membershipId: item.id,
            token,
            empresaId,
            payload: { is_active: true },
          });
      setSuccess(response.message);
      await loadCompanyUsers();
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el estado del usuario.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="inventory-stack">
      <PageHeader
        eyebrow="Empresa"
        title="Usuarios"
        subtitle="Administra miembros vinculados a la empresa activa."
        meta={
          <div className="inventory-inline-meta">
            <StatusBadge tone="info">{`Plan ${toDisplayText(meta.plan_code || empresa?.plan_code, "—")}`}</StatusBadge>
            <span className="table-note">
              Usuarios: {formatLimit(currentLimits?.usuarios_actuales ?? 0, currentLimits?.max_usuarios)}
            </span>
          </div>
        }
      />

      <DataCard title="Invitar usuario" subtitle="Los usuarios adicionales pertenecen a esta empresa; no crean una empresa nueva.">
        {error ? <p className="form-error">{error}</p> : null}
        {success ? <p className="form-success">{success}</p> : null}
        {isUserLimitReached ? (
          <div className="security-note">
            <strong>Límite alcanzado</strong>
            <span>
              Tu plan permite hasta {currentLimits?.max_usuarios} usuarios. Actualiza tu plan para invitar más usuarios.
            </span>
          </div>
        ) : null}

        <form onSubmit={handleInviteSubmit}>
          <FormGrid>
            <Field label="Nombre">
              <input
                onChange={(event) => setInviteForm((current) => ({ ...current, full_name: event.target.value }))}
                type="text"
                value={inviteForm.full_name}
              />
            </Field>

            <Field label="Correo">
              <input
                onChange={(event) => setInviteForm((current) => ({ ...current, email: event.target.value }))}
                required
                type="email"
                value={inviteForm.email}
              />
            </Field>

            <Field label="Rol">
              <select
                onChange={(event) => setInviteForm((current) => ({ ...current, role: event.target.value }))}
                value={inviteForm.role}
              >
                <option value="user">Usuario</option>
                <option value="admin">Admin</option>
                <option value="almacenista">Almacenista</option>
              </select>
            </Field>
          </FormGrid>

          <div className="inventory-actions">
            <ActionButton disabled={submitting || isUserLimitReached} tone="primary" type="submit">
              {submitting ? "Guardando..." : "Registrar invitacion"}
            </ActionButton>
          </div>
        </form>
      </DataCard>

      <DataCard
        title="Miembros de la empresa"
        subtitle={`Empresa actual: ${safeDisplayText(empresa?.name)}`}
      >
        {items.length === 0 ? (
          <EmptyState
            title="No hay miembros adicionales."
            note="El owner actual ya cuenta dentro del límite del plan."
          />
        ) : (
          <DataTable
            columns={[
              "Nombre",
              "Correo",
              "Rol",
              "Estado",
              "Ultimo acceso",
              "Acciones",
            ]}
          >
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{toDisplayText(item.full_name)}</strong>
                    <div className="table-note">{item.kind === "invitation" ? "Invitacion pendiente" : "Miembro"}</div>
                  </td>
                  <td>{item.email}</td>
                  <td>
                    {item.kind === "member" && item.role !== "owner" ? (
                      <div className="inventory-inline-actions">
                        <select
                          defaultValue={item.role}
                          onChange={(event) => handleRoleChange(item.id, event.target.value)}
                        >
                          <option value="user">Usuario</option>
                          <option value="admin">Admin</option>
                          <option value="almacenista">Almacenista</option>
                        </select>
                      </div>
                    ) : (
                      toDisplayText(item.role)
                    )}
                  </td>
                  <td>
                    <StatusBadge tone={item.status === "pending" ? "warning" : item.is_active ? "success" : "neutral"}>
                      {item.status === "pending" ? "Invitado" : item.is_active ? "Activo" : "Inactivo"}
                    </StatusBadge>
                  </td>
                  <td>{formatDateTime(item.last_login_at)}</td>
                  <td className="inventory-row-actions">
                    {item.kind === "member" && item.role !== "owner" ? (
                      <ActionButton
                        disabled={submitting}
                        onClick={() => handleToggleActive(item)}
                        size="sm"
                        type="button"
                      >
                        {item.is_active ? "Desactivar" : "Reactivar"}
                      </ActionButton>
                    ) : (
                      <span className="table-note">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>
    </div>
  );
}
