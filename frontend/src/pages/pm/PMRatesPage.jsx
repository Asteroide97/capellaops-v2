import { useEffect, useMemo, useState } from "react";
import { Plus, UserRound, Users2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import {
  createPmRoleRate,
  createPmUserRate,
  deactivatePmRoleRate,
  deactivatePmUserRate,
  listCompanyUsers,
  listPmRoleRates,
  listPmUserRates,
  updatePmRoleRate,
  updatePmUserRate,
} from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
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
  formatDate,
  formatMoney,
  safeDisplayText,
} from "../inventory/shared";
import { pmRateRoleOptions } from "./shared";


const defaultUserRateForm = {
  usuario_id: "",
  usuario_email: "",
  usuario_nombre_snapshot: "",
  tarifa_hora: "",
  moneda: "MXN",
  effective_from: "",
  effective_to: "",
  notas: "",
};

const defaultRoleRateForm = {
  rol: "colaborador",
  tarifa_hora: "",
  moneda: "MXN",
  effective_from: "",
  effective_to: "",
  notas: "",
};


function userRateToForm(rate) {
  if (!rate) {
    return defaultUserRateForm;
  }
  return {
    usuario_id: rate.usuario_id ?? "",
    usuario_email: rate.usuario_email ?? "",
    usuario_nombre_snapshot: rate.usuario_nombre_snapshot ?? "",
    tarifa_hora: rate.tarifa_hora ?? "",
    moneda: rate.moneda ?? "MXN",
    effective_from: rate.effective_from ?? "",
    effective_to: rate.effective_to ?? "",
    notas: rate.notas ?? "",
  };
}


function roleRateToForm(rate) {
  if (!rate) {
    return defaultRoleRateForm;
  }
  return {
    rol: rate.rol ?? "colaborador",
    tarifa_hora: rate.tarifa_hora ?? "",
    moneda: rate.moneda ?? "MXN",
    effective_from: rate.effective_from ?? "",
    effective_to: rate.effective_to ?? "",
    notas: rate.notas ?? "",
  };
}


export default function PMRatesPage() {
  const navigate = useNavigate();
  const { empresaId, token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [userRates, setUserRates] = useState([]);
  const [roleRates, setRoleRates] = useState([]);
  const [companyUsers, setCompanyUsers] = useState([]);
  const [userRateModalOpen, setUserRateModalOpen] = useState(false);
  const [roleRateModalOpen, setRoleRateModalOpen] = useState(false);
  const [editingUserRate, setEditingUserRate] = useState(null);
  const [editingRoleRate, setEditingRoleRate] = useState(null);
  const [userRateForm, setUserRateForm] = useState(defaultUserRateForm);
  const [roleRateForm, setRoleRateForm] = useState(defaultRoleRateForm);

  const companyUserOptions = useMemo(
    () =>
      (companyUsers ?? [])
        .filter((item) => item.kind === "member" && item.is_active)
        .map((item) => ({
          id: item.usuario_id ?? item.id,
          usuario_id: item.usuario_id ?? "",
          email: item.email ?? "",
          full_name: item.full_name ?? "",
        }))
        .filter((item) => item.usuario_id),
    [companyUsers],
  );

  async function loadRatesPage() {
    if (!token || !empresaId) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [userRatesResponse, roleRatesResponse, companyUsersResponse] = await Promise.all([
        listPmUserRates({ token, empresaId, filters: { activa: true, limit: 100, offset: 0 } }),
        listPmRoleRates({ token, empresaId, filters: { activa: true, limit: 100, offset: 0 } }),
        listCompanyUsers({ token, empresaId }),
      ]);
      setUserRates(userRatesResponse.items ?? []);
      setRoleRates(roleRatesResponse.items ?? []);
      setCompanyUsers(companyUsersResponse.items ?? []);
    } catch (requestError) {
      setError(requestError.message || "No se pudieron cargar las tarifas PM.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRatesPage();
  }, [token, empresaId]);

  function closeUserRateModal() {
    if (saving) {
      return;
    }
    setEditingUserRate(null);
    setUserRateForm(defaultUserRateForm);
    setUserRateModalOpen(false);
  }

  function closeRoleRateModal() {
    if (saving) {
      return;
    }
    setEditingRoleRate(null);
    setRoleRateForm(defaultRoleRateForm);
    setRoleRateModalOpen(false);
  }

  function openCreateUserRateModal() {
    setEditingUserRate(null);
    setUserRateForm(defaultUserRateForm);
    setUserRateModalOpen(true);
  }

  function openEditUserRateModal(rate) {
    setEditingUserRate(rate);
    setUserRateForm(userRateToForm(rate));
    setUserRateModalOpen(true);
  }

  function openCreateRoleRateModal() {
    setEditingRoleRate(null);
    setRoleRateForm(defaultRoleRateForm);
    setRoleRateModalOpen(true);
  }

  function openEditRoleRateModal(rate) {
    setEditingRoleRate(rate);
    setRoleRateForm(roleRateToForm(rate));
    setRoleRateModalOpen(true);
  }

  async function handleSaveUserRate(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        usuario_id: userRateForm.usuario_id || null,
        usuario_email: userRateForm.usuario_email.trim(),
        usuario_nombre_snapshot: userRateForm.usuario_nombre_snapshot.trim() || null,
        tarifa_hora: Number(userRateForm.tarifa_hora || 0),
        moneda: userRateForm.moneda.trim() || "MXN",
        effective_from: userRateForm.effective_from || null,
        effective_to: userRateForm.effective_to || null,
        notas: userRateForm.notas.trim() || null,
      };
      if (editingUserRate?.id) {
        await updatePmUserRate({ rateId: editingUserRate.id, token, empresaId, payload });
        setSuccess("Tarifa por usuario actualizada.");
      } else {
        await createPmUserRate({ token, empresaId, payload });
        setSuccess("Tarifa por usuario creada.");
      }
      closeUserRateModal();
      await loadRatesPage();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la tarifa por usuario.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRoleRate(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        rol: roleRateForm.rol,
        tarifa_hora: Number(roleRateForm.tarifa_hora || 0),
        moneda: roleRateForm.moneda.trim() || "MXN",
        effective_from: roleRateForm.effective_from || null,
        effective_to: roleRateForm.effective_to || null,
        notas: roleRateForm.notas.trim() || null,
      };
      if (editingRoleRate?.id) {
        await updatePmRoleRate({ rateId: editingRoleRate.id, token, empresaId, payload });
        setSuccess("Tarifa por rol actualizada.");
      } else {
        await createPmRoleRate({ token, empresaId, payload });
        setSuccess("Tarifa por rol creada.");
      }
      closeRoleRateModal();
      await loadRatesPage();
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar la tarifa por rol.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateUserRate(rate) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmUserRate({ rateId: rate.id, token, empresaId });
      setSuccess("Tarifa por usuario desactivada.");
      await loadRatesPage();
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar la tarifa por usuario.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateRoleRate(rate) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmRoleRate({ rateId: rate.id, token, empresaId });
      setSuccess("Tarifa por rol desactivada.");
      await loadRatesPage();
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar la tarifa por rol.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando tarifas PM...</div>;
  }

  return (
    <div className="inventory-shell inventory-screen pm-screen">
      <PageHeader
        eyebrow="PM Fase 3"
        title="Tarifas PM"
        subtitle="Configura costos por hora para usuarios y roles."
        actions={
          <div className="inventory-actions">
            <ActionButton onClick={() => navigate("/pm")} type="button">
              Dashboard PM
            </ActionButton>
            <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateUserRateModal} type="button">
              Tarifa usuario
            </ActionButton>
            <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateRoleRateModal} tone="primary" type="button">
              Tarifa rol
            </ActionButton>
          </div>
        }
      />

      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operacion" : "Operacion completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      <section className="inventory-metric-grid inventory-metric-grid-4">
        <MetricCard icon={<UserRound size={18} strokeWidth={1.9} />} label="Tarifas usuario" meta="Activas" tone="info" value={userRates.length} />
        <MetricCard icon={<Users2 size={18} strokeWidth={1.9} />} label="Tarifas rol" meta="Activas" tone="success" value={roleRates.length} />
        <MetricCard icon={<UserRound size={18} strokeWidth={1.9} />} label="Usuarios empresa" meta="Disponibles para tarifa" tone="neutral" value={companyUserOptions.length} />
        <MetricCard icon={<Users2 size={18} strokeWidth={1.9} />} label="Roles configurables" meta="Owner, proyecto y operativos" tone="warning" value={pmRateRoleOptions.length} />
      </section>

      <div className="inventory-form-note">
        <strong>Snapshot historico</strong>
        <p className="table-note">
          Las tarifas nuevas no modifican registros historicos; cada hora guarda snapshot de la tarifa aplicada.
        </p>
      </div>

      <DataCard
        actions={
          <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateUserRateModal} tone="primary" type="button">
            Nueva tarifa usuario
          </ActionButton>
        }
        subtitle="Tarifas especificas por persona. Tienen prioridad sobre las tarifas por rol."
        title="Tarifas por usuario"
      >
        <ResultMeta label="tarifas" loaded={userRates.length} total={userRates.length} />
        {userRates.length === 0 ? (
          <EmptyState compact note="Agrega una tarifa por usuario para resolver costos horarios con precision." title="Sin tarifas de usuario" />
        ) : (
          <DataTable columns={["Usuario", "Tarifa hora", "Moneda", "Vigencia desde", "Vigencia hasta", "Estado", "Acciones"]}>
            <tbody>
              {userRates.map((rate) => (
                <tr key={rate.id}>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(rate.usuario_nombre_snapshot, "Sin nombre")}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(rate.usuario_email, "—")}</div>
                  </td>
                  <td>{formatMoney(rate.tarifa_hora)}</td>
                  <td>{safeDisplayText(rate.moneda, "MXN")}</td>
                  <td>{safeDisplayText(formatDate(rate.effective_from), "—")}</td>
                  <td>{safeDisplayText(formatDate(rate.effective_to), "—")}</td>
                  <td><StatusBadge tone={rate.activa ? "success" : "neutral"}>{rate.activa ? "Activa" : "Inactiva"}</StatusBadge></td>
                  <td>
                    <div className="table-actions">
                      <ActionButton onClick={() => openEditUserRateModal(rate)} size="sm" type="button">
                        Editar
                      </ActionButton>
                      <ActionButton onClick={() => handleDeactivateUserRate(rate)} size="sm" tone="danger" type="button">
                        Desactivar
                      </ActionButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <DataCard
        actions={
          <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateRoleRateModal} tone="primary" type="button">
            Nueva tarifa rol
          </ActionButton>
        }
        subtitle="Tarifas fallback por rol de empresa o de proyecto."
        title="Tarifas por rol"
      >
        <ResultMeta label="tarifas" loaded={roleRates.length} total={roleRates.length} />
        {roleRates.length === 0 ? (
          <EmptyState compact note="Agrega una tarifa por rol para cubrir miembros sin tarifa personal." title="Sin tarifas por rol" />
        ) : (
          <DataTable columns={["Rol", "Tarifa hora", "Moneda", "Vigencia desde", "Vigencia hasta", "Estado", "Acciones"]}>
            <tbody>
              {roleRates.map((rate) => (
                <tr key={rate.id}>
                  <td>{safeDisplayText(pmRateRoleOptions.find((item) => item.value === rate.rol)?.label ?? rate.rol)}</td>
                  <td>{formatMoney(rate.tarifa_hora)}</td>
                  <td>{safeDisplayText(rate.moneda, "MXN")}</td>
                  <td>{safeDisplayText(formatDate(rate.effective_from), "—")}</td>
                  <td>{safeDisplayText(formatDate(rate.effective_to), "—")}</td>
                  <td><StatusBadge tone={rate.activa ? "success" : "neutral"}>{rate.activa ? "Activa" : "Inactiva"}</StatusBadge></td>
                  <td>
                    <div className="table-actions">
                      <ActionButton onClick={() => openEditRoleRateModal(rate)} size="sm" type="button">
                        Editar
                      </ActionButton>
                      <ActionButton onClick={() => handleDeactivateRoleRate(rate)} size="sm" tone="danger" type="button">
                        Desactivar
                      </ActionButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </DataCard>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeUserRateModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-user-rate-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingUserRate ? "Actualizar tarifa" : "Guardar tarifa"}
            </ActionButton>
          </div>
        }
        onClose={closeUserRateModal}
        open={userRateModalOpen}
        size="large"
        subtitle="La tarifa por usuario tiene prioridad sobre la tarifa por rol."
        title={editingUserRate ? "Editar tarifa por usuario" : "Nueva tarifa por usuario"}
      >
        <form className="inventory-modal-form" id="pm-user-rate-form" onSubmit={handleSaveUserRate}>
          <FormGrid>
            <Field label="Usuario existente">
              <select
                onChange={(event) => {
                  const selected = companyUserOptions.find((item) => item.usuario_id === event.target.value);
                  setUserRateForm((current) => ({
                    ...current,
                    usuario_id: event.target.value,
                    usuario_email: selected?.email ?? current.usuario_email,
                    usuario_nombre_snapshot: selected?.full_name ?? current.usuario_nombre_snapshot,
                  }));
                }}
                value={userRateForm.usuario_id}
              >
                <option value="">Sin vincular usuario</option>
                {companyUserOptions.map((companyUser) => (
                  <option key={companyUser.id} value={companyUser.usuario_id}>
                    {companyUser.full_name || companyUser.email}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Correo">
              <input
                onChange={(event) => setUserRateForm((current) => ({ ...current, usuario_email: event.target.value }))}
                required
                type="email"
                value={userRateForm.usuario_email}
              />
            </Field>
            <Field label="Nombre">
              <input
                onChange={(event) => setUserRateForm((current) => ({ ...current, usuario_nombre_snapshot: event.target.value }))}
                type="text"
                value={userRateForm.usuario_nombre_snapshot}
              />
            </Field>
            <Field label="Tarifa por hora">
              <input
                min="0"
                onChange={(event) => setUserRateForm((current) => ({ ...current, tarifa_hora: event.target.value }))}
                required
                step="0.01"
                type="number"
                value={userRateForm.tarifa_hora}
              />
            </Field>
            <Field label="Moneda">
              <input
                onChange={(event) => setUserRateForm((current) => ({ ...current, moneda: event.target.value.toUpperCase() }))}
                value={userRateForm.moneda}
              />
            </Field>
            <Field label="Vigencia desde">
              <input
                onChange={(event) => setUserRateForm((current) => ({ ...current, effective_from: event.target.value }))}
                type="date"
                value={userRateForm.effective_from}
              />
            </Field>
            <Field label="Vigencia hasta">
              <input
                onChange={(event) => setUserRateForm((current) => ({ ...current, effective_to: event.target.value }))}
                type="date"
                value={userRateForm.effective_to}
              />
            </Field>
            <Field label="Notas" span={2}>
              <textarea
                onChange={(event) => setUserRateForm((current) => ({ ...current, notas: event.target.value }))}
                rows={4}
                value={userRateForm.notas}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeRoleRateModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-role-rate-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingRoleRate ? "Actualizar tarifa" : "Guardar tarifa"}
            </ActionButton>
          </div>
        }
        onClose={closeRoleRateModal}
        open={roleRateModalOpen}
        size="large"
        subtitle="Tarifa fallback aplicada cuando no existe una tarifa personal vigente."
        title={editingRoleRate ? "Editar tarifa por rol" : "Nueva tarifa por rol"}
      >
        <form className="inventory-modal-form" id="pm-role-rate-form" onSubmit={handleSaveRoleRate}>
          <FormGrid>
            <Field label="Rol">
              <select
                onChange={(event) => setRoleRateForm((current) => ({ ...current, rol: event.target.value }))}
                value={roleRateForm.rol}
              >
                {pmRateRoleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tarifa por hora">
              <input
                min="0"
                onChange={(event) => setRoleRateForm((current) => ({ ...current, tarifa_hora: event.target.value }))}
                required
                step="0.01"
                type="number"
                value={roleRateForm.tarifa_hora}
              />
            </Field>
            <Field label="Moneda">
              <input
                onChange={(event) => setRoleRateForm((current) => ({ ...current, moneda: event.target.value.toUpperCase() }))}
                value={roleRateForm.moneda}
              />
            </Field>
            <Field label="Vigencia desde">
              <input
                onChange={(event) => setRoleRateForm((current) => ({ ...current, effective_from: event.target.value }))}
                type="date"
                value={roleRateForm.effective_from}
              />
            </Field>
            <Field label="Vigencia hasta">
              <input
                onChange={(event) => setRoleRateForm((current) => ({ ...current, effective_to: event.target.value }))}
                type="date"
                value={roleRateForm.effective_to}
              />
            </Field>
            <Field label="Notas" span={2}>
              <textarea
                onChange={(event) => setRoleRateForm((current) => ({ ...current, notas: event.target.value }))}
                rows={4}
                value={roleRateForm.notas}
              />
            </Field>
          </FormGrid>
        </form>
      </ModalShell>
    </div>
  );
}
