import { useEffect, useMemo, useState } from "react";
import { AlarmClockCheck, BadgeDollarSign, Clock3, Plus, TriangleAlert } from "lucide-react";

import {
  createPmProjectTimeEntry,
  deactivatePmTimeEntry,
  getPmProjectCosts,
  listPmProjectTimeEntries,
  updatePmTimeEntry,
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
  ResultMeta,
  SectionTitle,
  StatusBadge,
  formatDate,
  formatMoney,
  formatNumber,
  safeDisplayText,
} from "../inventory/shared";
import { getRateSourceLabel, getRateSourceTone } from "./shared";


const defaultTimeEntryForm = {
  fecha: new Date().toISOString().slice(0, 10),
  usuario_id: "",
  tarea_id: "",
  horas: "",
  descripcion: "",
};


function canManageTimeEntry(entry, membershipRole, userId) {
  if (membershipRole === "owner" || membershipRole === "admin") {
    return true;
  }
  return entry?.usuario_id === userId || entry?.created_by === userId;
}


function entryToForm(entry) {
  if (!entry) {
    return defaultTimeEntryForm;
  }
  return {
    fecha: entry.fecha ?? new Date().toISOString().slice(0, 10),
    usuario_id: entry.usuario_id ?? "",
    tarea_id: entry.tarea_id ?? "",
    horas: entry.horas ?? "",
    descripcion: entry.descripcion ?? "",
  };
}


export default function PMProjectTimeCostsTab({
  empresaId,
  members,
  onChanged,
  project,
  projectId,
  tasks,
  token,
}) {
  const { membership, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [costs, setCosts] = useState(null);
  const [timeEntries, setTimeEntries] = useState([]);
  const [timeModalOpen, setTimeModalOpen] = useState(false);
  const [editingTimeEntry, setEditingTimeEntry] = useState(null);
  const [timeEntryForm, setTimeEntryForm] = useState(defaultTimeEntryForm);

  const memberOptions = useMemo(() => {
    const projectMembers = (members ?? [])
      .filter((item) => item.activo)
      .map((item) => ({
        id: item.usuario_id ?? item.id,
        value: item.usuario_id ?? "",
        label: item.nombre_snapshot || item.email || "Miembro",
        email: item.email || "",
      }))
      .filter((item) => item.value);

    if (user?.id && !projectMembers.some((item) => item.value === user.id)) {
      projectMembers.unshift({
        id: user.id,
        value: user.id,
        label: user.full_name || user.email || "Yo",
        email: user.email || "",
      });
    }

    return projectMembers;
  }, [members, user]);

  async function loadTimeCostsTab() {
    if (!token || !empresaId || !projectId) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [costsResponse, entriesResponse] = await Promise.all([
        getPmProjectCosts({ projectId, token, empresaId }),
        listPmProjectTimeEntries({ projectId, token, empresaId, filters: { activo: true, limit: 100, offset: 0 } }),
      ]);
      setCosts(costsResponse);
      setTimeEntries(entriesResponse.items ?? []);
    } catch (requestError) {
      setError(requestError.message || "No se pudo cargar tiempo y costos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTimeCostsTab();
  }, [token, empresaId, projectId]);

  function openCreateModal() {
    setEditingTimeEntry(null);
    setTimeEntryForm({
      ...defaultTimeEntryForm,
      usuario_id: user?.id ?? memberOptions[0]?.value ?? "",
    });
    setTimeModalOpen(true);
  }

  function openEditModal(entry) {
    setEditingTimeEntry(entry);
    setTimeEntryForm(entryToForm(entry));
    setTimeModalOpen(true);
  }

  function closeTimeModal(force = false) {
    if (saving && !force) {
      return;
    }
    setEditingTimeEntry(null);
    setTimeEntryForm(defaultTimeEntryForm);
    setTimeModalOpen(false);
  }

  async function handleSaveTimeEntry(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        fecha: timeEntryForm.fecha,
        usuario_id: timeEntryForm.usuario_id || null,
        tarea_id: timeEntryForm.tarea_id || null,
        horas: Number(timeEntryForm.horas || 0),
        descripcion: timeEntryForm.descripcion.trim() || null,
      };

      if (editingTimeEntry?.id) {
        await updatePmTimeEntry({ timeEntryId: editingTimeEntry.id, token, empresaId, payload });
        setSuccess("Registro de horas actualizado.");
      } else {
        await createPmProjectTimeEntry({ projectId, token, empresaId, payload });
        setSuccess("Horas registradas.");
      }

      await loadTimeCostsTab();
      await onChanged?.();
      closeTimeModal(true);
    } catch (requestError) {
      setError(requestError.message || "No se pudo guardar el registro de horas.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivateTimeEntry(entry) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await deactivatePmTimeEntry({ timeEntryId: entry.id, token, empresaId });
      setSuccess("Registro de horas desactivado.");
      await loadTimeCostsTab();
      await onChanged?.();
    } catch (requestError) {
      setError(requestError.message || "No se pudo desactivar el registro de horas.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando tiempo y costos...</div>;
  }

  return (
    <div className="inventory-content-grid">
      {(error || success) && (
        <div className={`inventory-form-note ${error ? "inventory-form-note-danger" : "inventory-form-note-success"}`}>
          <strong>{error ? "No se pudo completar la operación" : "Operación completada"}</strong>
          <p className="table-note">{error || success}</p>
        </div>
      )}

      {Number(costs?.horas_sin_tarifa ?? 0) > 0 ? (
        <div className="inventory-form-note inventory-form-note-warning">
          <strong>Horas sin tarifa</strong>
          <p className="table-note">
            Hay horas registradas sin tarifa. Configura tarifas para calcular costos reales correctamente.
          </p>
        </div>
      ) : null}

      {Number(costs?.presupuesto_estimado ?? 0) > 0 && Number(costs?.costo_total_real ?? 0) > Number(costs?.presupuesto_estimado ?? 0) ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>Presupuesto excedido</strong>
          <p className="table-note">El costo real ya supera el presupuesto estimado.</p>
        </div>
      ) : null}

      <section className="inventory-metric-grid inventory-metric-grid-6">
        <MetricCard icon={<Clock3 size={18} strokeWidth={1.9} />} label="Horas registradas" meta="Proyecto acumulado" tone="info" value={formatNumber(costs?.horas_totales ?? 0)} />
        <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Costo horas real" meta="Labor acumulada" tone="success" value={formatMoney(costs?.costo_horas_real ?? 0)} />
        <MetricCard icon={<TriangleAlert size={18} strokeWidth={1.9} />} label="Horas sin tarifa" meta="Requieren configuración" tone={Number(costs?.horas_sin_tarifa ?? 0) > 0 ? "warning" : "neutral"} value={formatNumber(costs?.horas_sin_tarifa ?? 0)} />
        <MetricCard icon={<BadgeDollarSign size={18} strokeWidth={1.9} />} label="Costo total real" meta="Materiales + horas" tone="warning" value={formatMoney(costs?.costo_total_real ?? 0)} />
        <MetricCard icon={<AlarmClockCheck size={18} strokeWidth={1.9} />} label="Presupuesto estimado" meta="Base del proyecto" tone="neutral" value={formatMoney(costs?.presupuesto_estimado ?? project?.presupuesto_estimado ?? 0)} />
        <MetricCard icon={<TriangleAlert size={18} strokeWidth={1.9} />} label="Variación presupuesto" meta="Presupuesto - costo real" tone={Number(costs?.variacion_presupuesto ?? 0) < 0 ? "danger" : "success"} value={formatMoney(costs?.variacion_presupuesto ?? 0)} />
      </section>

      <DataCard
        actions={
          <ActionButton icon={<Plus size={16} strokeWidth={1.9} />} onClick={openCreateModal} tone="primary" type="button">
            Agregar horas
          </ActionButton>
        }
        subtitle="Registros reales por proyecto o tarea. Cada registro guarda snapshot de la tarifa aplicada."
        title="Registro de horas"
      >
        <ResultMeta label="registros" loaded={timeEntries.length} total={timeEntries.length} />
        {timeEntries.length === 0 ? (
          <EmptyState
            compact
            note="Registra horas para comenzar a calcular costo laboral real."
            title="Sin horas registradas"
          />
        ) : (
          <DataTable columns={["Fecha", "Usuario", "Tarea", "Horas", "Descripción", "Tarifa aplicada", "Costo total", "Fuente", "Acciones"]}>
            <tbody>
              {timeEntries.map((entry) => (
                <tr key={entry.id}>
                  <td>{safeDisplayText(formatDate(entry.fecha), "—")}</td>
                  <td>
                    <div className="inventory-cell-main">{safeDisplayText(entry.usuario_nombre_snapshot, "Sin usuario")}</div>
                    <div className="inventory-cell-sub">{safeDisplayText(entry.usuario_email_snapshot, "—")}</div>
                  </td>
                  <td>{safeDisplayText(entry.tarea_titulo, "Proyecto general")}</td>
                  <td>{formatNumber(entry.horas)}</td>
                  <td>{safeDisplayText(entry.descripcion, "—")}</td>
                  <td>{formatMoney(entry.costo_hora_aplicado_snapshot)}</td>
                  <td>{formatMoney(entry.costo_total_snapshot)}</td>
                  <td>
                    <StatusBadge tone={getRateSourceTone(entry.fuente_tarifa)}>
                      {getRateSourceLabel(entry.fuente_tarifa)}
                    </StatusBadge>
                  </td>
                  <td>
                    <div className="table-actions">
                      <ActionButton
                        disabled={!canManageTimeEntry(entry, membership?.role, user?.id)}
                        onClick={() => openEditModal(entry)}
                        size="sm"
                        type="button"
                      >
                        Editar
                      </ActionButton>
                      <ActionButton
                        disabled={!canManageTimeEntry(entry, membership?.role, user?.id)}
                        onClick={() => handleDeactivateTimeEntry(entry)}
                        size="sm"
                        tone="danger"
                        type="button"
                      >
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

      <DataCard subtitle="Comparativo base de costos reales del proyecto." title="Costos del proyecto">
        <div className="inventory-metric-grid inventory-metric-grid-3">
          <MetricCard label="Materiales estimados" meta="Planeación" tone="info" value={formatMoney(costs?.costo_materiales_estimado ?? 0)} />
          <MetricCard label="Materiales reales" meta="Consumo real" tone="success" value={formatMoney(costs?.costo_materiales_real ?? 0)} />
          <MetricCard label="Horas reales" meta="Costo laboral" tone="warning" value={formatMoney(costs?.costo_horas_real ?? 0)} />
          <MetricCard label="Total real" meta="Materiales + horas" tone="danger" value={formatMoney(costs?.costo_total_real ?? 0)} />
          <MetricCard label="Presupuesto" meta="Base del proyecto" tone="neutral" value={formatMoney(costs?.presupuesto_estimado ?? project?.presupuesto_estimado ?? 0)} />
          <MetricCard label="Variación" meta="Presupuesto - costo real" tone={Number(costs?.variacion_presupuesto ?? 0) < 0 ? "danger" : "success"} value={formatMoney(costs?.variacion_presupuesto ?? 0)} />
        </div>
      </DataCard>

      <ModalShell
        footer={
          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton disabled={saving} onClick={closeTimeModal} type="button">
              Cancelar
            </ActionButton>
            <ActionButton disabled={saving} form="pm-time-entry-form" tone="primary" type="submit">
              {saving ? "Guardando..." : editingTimeEntry ? "Actualizar horas" : "Registrar horas"}
            </ActionButton>
          </div>
        }
        onClose={closeTimeModal}
        open={timeModalOpen}
        size="large"
        subtitle="Las horas guardan snapshot de la tarifa aplicada. Cambios posteriores de tarifa no alteran el histórico."
        title={editingTimeEntry ? "Editar registro de horas" : "Registrar horas"}
      >
        {error ? (
          <div className="inventory-form-note inventory-form-note-danger">
            <strong>No se pudo guardar el registro de horas</strong>
            <p className="table-note">{error}</p>
          </div>
        ) : null}
        <form className="inventory-modal-form" id="pm-time-entry-form" onSubmit={handleSaveTimeEntry}>
          <SectionTitle subtitle="Proyecto, tarea y usuario responsable." title="Contexto del registro" />
          <FormGrid>
            <Field label="Fecha">
              <input
                onChange={(event) => setTimeEntryForm((current) => ({ ...current, fecha: event.target.value }))}
                required
                type="date"
                value={timeEntryForm.fecha}
              />
            </Field>
            <Field label="Usuario / miembro">
              <select
                onChange={(event) => setTimeEntryForm((current) => ({ ...current, usuario_id: event.target.value }))}
                value={timeEntryForm.usuario_id}
              >
                <option value="">Yo / sin usuario explícito</option>
                {memberOptions.map((memberOption) => (
                  <option key={memberOption.id} value={memberOption.value}>
                    {memberOption.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Tarea">
              <select
                onChange={(event) => setTimeEntryForm((current) => ({ ...current, tarea_id: event.target.value }))}
                value={timeEntryForm.tarea_id}
              >
                <option value="">Proyecto general</option>
                {(tasks ?? []).map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.titulo}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Horas">
              <input
                max="24"
                min="0.25"
                onChange={(event) => setTimeEntryForm((current) => ({ ...current, horas: event.target.value }))}
                required
                step="0.25"
                type="number"
                value={timeEntryForm.horas}
              />
            </Field>
            <Field label="Descripción" span={2}>
              <textarea
                onChange={(event) => setTimeEntryForm((current) => ({ ...current, descripcion: event.target.value }))}
                rows={4}
                value={timeEntryForm.descripcion}
              />
            </Field>
          </FormGrid>
          <div className="inventory-form-note">
            <strong>Tarifa aplicada al guardar</strong>
            <p className="table-note">
              El backend resuelve la tarifa por usuario primero y, si no existe, usa la tarifa por rol. Si no encuentra ninguna, el costo queda en 0.
            </p>
          </div>
        </form>
      </ModalShell>
    </div>
  );
}
