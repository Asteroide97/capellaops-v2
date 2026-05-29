import { useEffect, useMemo, useState } from "react";

import {
  deactivateCompanyUser,
  inviteCompanyUser,
  listCompanyUsers,
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
  MetricCard,
  ModalShell,
  PageHeader,
  ResultMeta,
  StatusBadge,
  safeDisplayText,
} from "./inventory/shared";

const defaultInviteForm = {
  full_name: "",
  email: "",
  role: "user",
};

const roleOptions = [
  { value: "user", label: "Usuario" },
  { value: "admin", label: "Admin" },
  { value: "almacenista", label: "Almacenista" },
];

const inviteMessages = {
  invited: "Invitacion registrada. El envio de email queda pendiente.",
  linked_existing_user: "El usuario existente fue vinculado a esta empresa.",
  already_member: "Este correo ya pertenece a esta empresa.",
};

function formatLimit(current, max) {
  if (max === null || max === undefined) {
    return `${current} / Ilimitado`;
  }
  return `${current} / ${max}`;
}

function formatPlanLabel(planCode) {
  const map = {
    basico: "Plan Basico",
    pro: "Plan Pro",
    total: "Plan Total",
  };
  return map[String(planCode ?? "").toLowerCase()] ?? "Plan";
}

function formatOptionalDateTime(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function getRoleLabel(role) {
  const normalized = String(role ?? "").toLowerCase();
  if (normalized === "owner") {
    return "Owner";
  }
  if (normalized === "admin") {
    return "Admin";
  }
  if (normalized === "almacenista") {
    return "Almacenista";
  }
  return "Usuario";
}

function getRoleTone(role) {
  const normalized = String(role ?? "").toLowerCase();
  if (normalized === "owner") {
    return "success";
  }
  if (normalized === "admin") {
    return "info";
  }
  if (normalized === "almacenista") {
    return "warning";
  }
  return "neutral";
}

function getPlanUsersMeta(planCode, maxUsers) {
  if (maxUsers === null || maxUsers === undefined) {
    return `${formatPlanLabel(planCode)} | Usuarios ilimitados`;
  }
  return `${formatPlanLabel(planCode)} | ${maxUsers} incluidos`;
}

export default function CompanyUsersPage() {
  const { empresa, empresaId, limits, membership, refreshSession, token, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [inviteForm, setInviteForm] = useState(defaultInviteForm);
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({
    plan_code: empresa?.plan_code ?? "",
    limits,
  });
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [roleTarget, setRoleTarget] = useState(null);
  const [roleValue, setRoleValue] = useState("user");
  const [statusTarget, setStatusTarget] = useState(null);

  const canManage = membership?.role === "owner" || membership?.role === "admin";

  async function loadCompanyUsers() {
    const response = await listCompanyUsers({ token, empresaId });
    setItems(response.items ?? []);
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

  const currentLimits = meta.limits ?? limits;
  const members = useMemo(() => items.filter((item) => item.kind === "member"), [items]);
  const pendingInvitations = useMemo(
    () => items.filter((item) => item.kind === "invitation"),
    [items],
  );
  const activeMembers = useMemo(() => members.filter((item) => item.is_active), [members]);
  const activeRoles = useMemo(() => {
    const roleSet = new Set(activeMembers.map((item) => getRoleLabel(item.role)));
    return Array.from(roleSet);
  }, [activeMembers]);

  const isUserLimitReached =
    currentLimits?.max_usuarios !== null &&
    currentLimits?.max_usuarios !== undefined &&
    (currentLimits?.usuarios_actuales ?? 0) >= currentLimits.max_usuarios;

  function resetFeedback() {
    setError("");
    setSuccess("");
  }

  function openInviteModal() {
    resetFeedback();
    setInviteForm(defaultInviteForm);
    setInviteModalOpen(true);
  }

  function closeInviteModal() {
    if (submitting) {
      return;
    }

    setInviteModalOpen(false);
    setInviteForm(defaultInviteForm);
  }

  function openRoleModal(item) {
    resetFeedback();
    setRoleTarget(item);
    setRoleValue(item.role ?? "user");
  }

  function closeRoleModal() {
    if (submitting) {
      return;
    }

    setRoleTarget(null);
    setRoleValue("user");
  }

  function openStatusModal(item) {
    resetFeedback();
    setStatusTarget(item);
  }

  function closeStatusModal() {
    if (submitting) {
      return;
    }

    setStatusTarget(null);
  }

  async function syncUsersState() {
    await loadCompanyUsers();
    await refreshSession();
  }

  async function handleInviteSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    resetFeedback();

    try {
      const response = await inviteCompanyUser({
        token,
        empresaId,
        payload: inviteForm,
      });
      setSuccess(inviteMessages[response.status] ?? response.message);
      setInviteForm(defaultInviteForm);
      setInviteModalOpen(false);
      await syncUsersState();
    } catch (requestError) {
      setError(requestError.message || "No se pudo registrar la invitacion.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRoleSubmit(event) {
    event.preventDefault();
    if (!roleTarget) {
      return;
    }

    setSubmitting(true);
    resetFeedback();

    try {
      const response = await updateCompanyUser({
        membershipId: roleTarget.id,
        token,
        empresaId,
        payload: { role: roleValue },
      });
      setSuccess(response.message || "Rol actualizado correctamente.");
      setRoleTarget(null);
      await syncUsersState();
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el rol.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStatusSubmit() {
    if (!statusTarget) {
      return;
    }

    setSubmitting(true);
    resetFeedback();

    try {
      const response = statusTarget.is_active
        ? await deactivateCompanyUser({
            membershipId: statusTarget.id,
            token,
            empresaId,
          })
        : await updateCompanyUser({
            membershipId: statusTarget.id,
            token,
            empresaId,
            payload: { is_active: true },
          });
      setSuccess(response.message || "Estado actualizado correctamente.");
      setStatusTarget(null);
      await syncUsersState();
    } catch (requestError) {
      setError(requestError.message || "No se pudo actualizar el estado del usuario.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!canManage) {
    return (
      <FeaturePlaceholder
        title="Usuarios de empresa"
        subtitle="Solo owner o admin pueden administrar miembros de la empresa."
        items={["Invitaciones", "Roles", "Limites por plan", "Membresias activas"]}
        note="El backend tambien valida este permiso."
        tone="warning"
      />
    );
  }

  if (loading) {
    return <div className="screen-center">Cargando usuarios de la empresa...</div>;
  }

  return (
    <div className="inventory-shell inventory-screen company-users-screen">
      <PageHeader
        eyebrow="Empresa"
        title="Usuarios"
        subtitle="Administra los miembros vinculados a la empresa activa."
        actions={
          <ActionButton
            disabled={isUserLimitReached || submitting}
            onClick={openInviteModal}
            tone="primary"
            type="button"
          >
            Invitar usuario
          </ActionButton>
        }
        meta={
          <div className="inventory-inline-meta">
            <StatusBadge tone="info">{formatPlanLabel(meta.plan_code || empresa?.plan_code)}</StatusBadge>
            <span className="table-note">
              Usuarios: {formatLimit(currentLimits?.usuarios_actuales ?? 0, currentLimits?.max_usuarios)}
            </span>
          </div>
        }
      />

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la accion" : "Operacion completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-4 company-users-summary-grid">
        <MetricCard
          icon="USR"
          label="Usuarios del plan"
          meta="Usuarios activos"
          tone="success"
          value={formatLimit(currentLimits?.usuarios_actuales ?? 0, currentLimits?.max_usuarios)}
        />
        <MetricCard
          icon="PLN"
          label="Limite del plan"
          meta={getPlanUsersMeta(meta.plan_code || empresa?.plan_code, currentLimits?.max_usuarios)}
          tone="info"
          value={formatPlanLabel(meta.plan_code || empresa?.plan_code)}
        />
        <MetricCard
          icon="INV"
          label="Invitaciones pendientes"
          meta="Pendientes de activacion"
          tone="warning"
          value={pendingInvitations.length}
        />
        <MetricCard
          icon="ROL"
          label="Roles activos"
          meta={activeRoles.length > 0 ? activeRoles.join(" | ") : "Sin roles activos"}
          tone="neutral"
          value={activeRoles.length}
        />
      </section>

      <DataCard
        title="Capacidad del plan"
        subtitle="El owner cuenta dentro del limite de usuarios de la empresa."
      >
        {currentLimits?.max_usuarios === null || currentLimits?.max_usuarios === undefined ? (
          <div className="inventory-form-note inventory-form-note-success">
            <strong>Usuarios ilimitados en este plan.</strong>
            <p className="table-note">Puedes seguir vinculando miembros sin tope numerico configurado.</p>
          </div>
        ) : isUserLimitReached ? (
          <div className="inventory-form-note inventory-form-note-warning">
            <strong>Limite alcanzado</strong>
            <p className="table-note">
              Tu plan permite hasta {currentLimits.max_usuarios} usuarios. Actualiza tu plan para invitar mas.
            </p>
          </div>
        ) : (
          <div className="inventory-form-note">
            <strong>Cupo disponible</strong>
            <p className="table-note">
              Aun puedes agregar {Math.max(0, currentLimits.max_usuarios - currentLimits.usuarios_actuales)} usuario(s)
              en este plan.
            </p>
          </div>
        )}
      </DataCard>

      <DataCard
        actions={
          <ActionButton disabled={loading || submitting} onClick={loadCompanyUsers} size="sm" type="button">
            Actualizar
          </ActionButton>
        }
        subtitle="Usuarios con acceso a esta empresa."
        title="Miembros de la empresa"
      >
        <ResultMeta label="miembros" loaded={members.length} total={members.length} />
        {members.length === 0 ? (
          <EmptyState
            note="El owner actual ya cuenta dentro del limite del plan."
            title="No hay miembros adicionales."
          />
        ) : (
          <DataTable columns={["Usuario", "Rol", "Estado", "Ultimo acceso", "Acciones"]}>
            <tbody>
              {members.map((item) => {
                const isOwner = item.role === "owner";
                const isSelf = item.usuario_id === user?.id;
                const canChangeRole = !isOwner && !isSelf;
                const canToggleState = !isOwner && !isSelf;

                return (
                  <tr key={item.id}>
                    <td>
                      <div className="inventory-cell-main">{safeDisplayText(item.full_name, "Sin nombre")}</div>
                      <div className="inventory-cell-sub">{safeDisplayText(item.email)}</div>
                    </td>
                    <td>
                      <StatusBadge tone={getRoleTone(item.role)}>{getRoleLabel(item.role)}</StatusBadge>
                    </td>
                    <td>
                      <StatusBadge tone={item.is_active ? "success" : "neutral"}>
                        {item.is_active ? "Activo" : "Inactivo"}
                      </StatusBadge>
                    </td>
                    <td>{formatOptionalDateTime(item.last_login_at)}</td>
                    <td>
                      <div className="company-users-row-actions">
                        {canChangeRole ? (
                          <ActionButton onClick={() => openRoleModal(item)} size="sm" type="button">
                            Cambiar rol
                          </ActionButton>
                        ) : null}
                        {canToggleState ? (
                          <ActionButton
                            onClick={() => openStatusModal(item)}
                            size="sm"
                            tone={item.is_active ? "danger" : "primary"}
                            type="button"
                          >
                            {item.is_active ? "Desactivar" : "Reactivar"}
                          </ActionButton>
                        ) : null}
                        {isOwner ? <span className="table-note">Owner principal</span> : null}
                        {isSelf ? <span className="table-note">Tu acceso actual</span> : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      {pendingInvitations.length > 0 ? (
        <DataCard
          subtitle="Invitaciones registradas para incorporarse a esta empresa."
          title="Invitaciones pendientes"
        >
          <ResultMeta
            label="invitaciones"
            loaded={pendingInvitations.length}
            total={pendingInvitations.length}
          />
          <DataTable columns={["Correo", "Rol", "Fecha", "Estado", "Acciones"]}>
            <tbody>
              {pendingInvitations.map((item) => (
                <tr key={item.id}>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(item.email)}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(item.full_name, "Invitacion sin nombre")}</div>
                  </td>
                  <td>
                    <StatusBadge tone={getRoleTone(item.role)}>{getRoleLabel(item.role)}</StatusBadge>
                  </td>
                  <td>{formatOptionalDateTime(item.created_at)}</td>
                  <td>
                    <StatusBadge tone="warning">Pendiente</StatusBadge>
                  </td>
                  <td>
                    <div className="company-users-row-actions">
                      <ActionButton disabled size="sm" type="button">
                        Reenviar
                      </ActionButton>
                      <ActionButton disabled size="sm" type="button">
                        Cancelar
                      </ActionButton>
                    </div>
                    <div className="inventory-cell-sub">Acciones de email pendientes.</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </DataCard>
      ) : null}

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeInviteModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              disabled={submitting || isUserLimitReached}
              form="company-user-invite-form"
              tone="primary"
              type="submit"
            >
              {submitting ? "Registrando..." : "Registrar invitacion"}
            </ActionButton>
          </div>
        }
        onClose={closeInviteModal}
        open={inviteModalOpen}
        size="medium"
        subtitle="Los usuarios invitados se vinculan a esta empresa. No se crea una empresa nueva."
        title="Invitar usuario"
      >
        <form className="inventory-modal-form" id="company-user-invite-form" onSubmit={handleInviteSubmit}>
          <div className="inventory-form-note">
            <strong>Vinculacion a empresa existente</strong>
            <p className="table-note">
              Si el correo ya existe en Capella Ops, se vinculara a esta empresa sin crear otra empresa nueva.
            </p>
          </div>
          <FormGrid>
            <Field label="Nombre">
              <input
                onChange={(event) => setInviteForm((current) => ({ ...current, full_name: event.target.value }))}
                placeholder="Nombre del usuario"
                type="text"
                value={inviteForm.full_name}
              />
            </Field>
            <Field label="Correo">
              <input
                onChange={(event) => setInviteForm((current) => ({ ...current, email: event.target.value }))}
                placeholder="usuario@empresa.com"
                required
                type="email"
                value={inviteForm.email}
              />
            </Field>
            <Field hint="Rol operativo dentro de la empresa." label="Rol" span={2}>
              <select
                onChange={(event) => setInviteForm((current) => ({ ...current, role: event.target.value }))}
                value={inviteForm.role}
              >
                {roleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeRoleModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={submitting} form="company-user-role-form" tone="primary" type="submit">
              {submitting ? "Guardando..." : "Guardar rol"}
            </ActionButton>
          </div>
        }
        onClose={closeRoleModal}
        open={Boolean(roleTarget)}
        size="medium"
        subtitle="Actualiza el rol operativo del miembro dentro de la empresa activa."
        title="Cambiar rol"
      >
        <form className="inventory-modal-form" id="company-user-role-form" onSubmit={handleRoleSubmit}>
          <div className="inventory-form-note">
            <strong>{safeDisplayText(roleTarget?.full_name, "Usuario")}</strong>
            <p className="table-note">{safeDisplayText(roleTarget?.email)}</p>
          </div>
          <Field label="Nuevo rol">
            <select onChange={(event) => setRoleValue(event.target.value)} value={roleValue}>
              {roleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={submitting} onClick={closeStatusModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton
              disabled={submitting}
              onClick={handleStatusSubmit}
              tone={statusTarget?.is_active ? "danger" : "primary"}
              type="button"
            >
              {submitting
                ? "Procesando..."
                : statusTarget?.is_active
                  ? "Confirmar desactivacion"
                  : "Confirmar reactivacion"}
            </ActionButton>
          </div>
        }
        onClose={closeStatusModal}
        open={Boolean(statusTarget)}
        size="medium"
        subtitle={
          statusTarget?.is_active
            ? "Este usuario perdera acceso a la empresa activa."
            : "El usuario volvera a tener acceso a esta empresa."
        }
        title={statusTarget?.is_active ? "Desactivar usuario" : "Reactivar usuario"}
      >
        <div className="inventory-modal-form">
          <div className={`inventory-form-note ${statusTarget?.is_active ? "inventory-form-note-warning" : "inventory-form-note-success"}`}>
            <strong>{safeDisplayText(statusTarget?.full_name, "Usuario")}</strong>
            <p className="table-note">{safeDisplayText(statusTarget?.email)}</p>
          </div>
          <p className="table-note">
            {statusTarget?.is_active
              ? "Este usuario perdera acceso a la empresa. Continuar?"
              : "Este usuario recuperara acceso a la empresa. Continuar?"}
          </p>
        </div>
      </ModalShell>
    </div>
  );
}
