import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { createFirstWarehouse } from "../api/client";
import { useAuth } from "../auth/AuthContext";


export default function FirstWarehouseSetupPage() {
  const navigate = useNavigate();
  const { token, empresaId, refreshSession, onboardingMessage } = useAuth();
  const [form, setForm] = useState({
    nombre: "Principal",
    codigo: "PRINCIPAL",
    descripcion: "Almacén principal",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
      navigate("/", { replace: true });
    } catch (requestError) {
      setError(requestError.message || "No se pudo crear el almacén inicial.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="screen-center">
      <form className="auth-card setup-card" onSubmit={handleSubmit}>
        <div>
          <p className="eyebrow">Setup inicial</p>
          <h2>Configura tu primer almacén</h2>
          <p>
            Antes de comenzar, crea el almacén principal donde controlarás tus productos y
            existencias.
          </p>
        </div>

        <div className="security-note">
          <strong>Inventario</strong>
          <span>{onboardingMessage || "Crea tu primer almacén para comenzar."}</span>
        </div>

        <label>
          Nombre del almacén
          <input
            onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))}
            required
            type="text"
            value={form.nombre}
          />
        </label>

        <label>
          Código
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
          Descripción opcional
          <textarea
            onChange={(event) =>
              setForm((current) => ({ ...current, descripcion: event.target.value }))
            }
            rows={3}
            value={form.descripcion}
          />
        </label>

        {error ? <p className="form-error">{error}</p> : null}

        <button className="primary-button" disabled={loading} type="submit">
          {loading ? "Creando..." : "Crear almacén y continuar"}
        </button>
      </form>
    </div>
  );
}
