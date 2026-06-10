import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createFirstWarehouse } from "../api/client";
import { useAuth } from "../auth/AuthContext";


export default function FirstWarehouseSetupPage() {
  const navigate = useNavigate();
  const { token, empresaId, limits, refreshSession, onboardingMessage, warehousesCount } = useAuth();
  const [form, setForm] = useState({
    nombre: "Principal",
    codigo: "PRINCIPAL",
    descripcion: "Almacen principal",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const maxWarehouses = limits?.max_almacenes ?? null;
  const currentWarehouses = limits?.almacenes_actuales ?? warehousesCount ?? 0;
  const isWarehouseLimitReached = maxWarehouses !== null && currentWarehouses >= maxWarehouses;

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      await createFirstWarehouse({
        token,
        empresaId,
        payload: {
          nombre: form.nombre,
          codigo: form.codigo,
          descripcion: form.descripcion,
        },
      });
      await refreshSession();
      navigate("/empresa/perfil?onboarding=1", { replace: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo crear el almacen inicial.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="screen-center">
      <form className="auth-card setup-card" onSubmit={handleSubmit}>
        <div>
          <p className="eyebrow">Setup inicial</p>
          <h2>Configura tu primer almacen</h2>
          <p>
            El registro crea la empresa y tu usuario owner. El siguiente paso es crear
            el primer almacen para comenzar a operar inventario.
          </p>
        </div>

        <div className="security-note">
          <strong>Inventario</strong>
          <span>{onboardingMessage || "Crea tu primer almacen para comenzar."}</span>
        </div>

        <div className="security-note">
          <strong>Branding opcional</strong>
          <span>Al continuar podrás agregar logo y datos de empresa sin bloquear el uso de la app.</span>
        </div>

        <div className="security-note">
          <strong>Limite del plan</strong>
          <span>
            Almacenes: {currentWarehouses} / {maxWarehouses ?? "Ilimitado"}
          </span>
        </div>

        <label>
          Nombre del almacen
          <input
            onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))}
            required
            type="text"
            value={form.nombre}
          />
        </label>

        <label>
          Codigo
          <input
            onChange={(event) =>
              setForm((current) => ({ ...current, codigo: event.target.value.toUpperCase() }))
            }
            required
            type="text"
            value={form.codigo}
          />
        </label>

        <label>
          Descripcion opcional
          <textarea
            onChange={(event) =>
              setForm((current) => ({ ...current, descripcion: event.target.value }))
            }
            rows={3}
            value={form.descripcion}
          />
        </label>

        {error ? <p className="form-error">{error}</p> : null}
        {isWarehouseLimitReached ? (
          <p className="form-error">
            Tu plan permite hasta {maxWarehouses} almacen(es). Actualiza tu plan para agregar mas.
          </p>
        ) : null}

        <button className="primary-button" disabled={loading || isWarehouseLimitReached} type="submit">
          {loading ? "Creando..." : "Crear almacen y continuar"}
        </button>
      </form>
    </div>
  );
}
