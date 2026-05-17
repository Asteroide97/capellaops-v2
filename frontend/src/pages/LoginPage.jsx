import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";


export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({
    email: "",
    password: "",
    empresa_id: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      await login({
        email: form.email,
        password: form.password,
        empresa_id: form.empresa_id || null,
      });
      navigate("/");
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <section className="auth-hero">
        <p className="eyebrow">Capella Ops V2</p>
        <h1>Operación multiempresa en un solo lugar</h1>
        <p>
          Inicia sesión con JWT propio y contexto de empresa validado desde backend.
        </p>
      </section>

      <form className="auth-card" onSubmit={handleSubmit}>
        <div>
          <h2>Iniciar sesión</h2>
          <p>Si tu usuario pertenece a varias empresas, captura también el `empresa_id`.</p>
        </div>

        <label>
          Correo
          <input
            autoComplete="email"
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            required
            type="email"
            value={form.email}
          />
        </label>

        <label>
          Contraseña
          <input
            autoComplete="current-password"
            minLength={8}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            required
            type="password"
            value={form.password}
          />
        </label>

        <label>
          Empresa ID (opcional)
          <input
            onChange={(event) => setForm({ ...form, empresa_id: event.target.value })}
            placeholder="Solo si el usuario pertenece a varias empresas"
            type="text"
            value={form.empresa_id}
          />
        </label>

        {error ? <p className="form-error">{error}</p> : null}

        <button className="primary-button" disabled={loading} type="submit">
          {loading ? "Ingresando..." : "Entrar"}
        </button>

        <p className="auth-link">
          ¿No tienes cuenta? <Link to="/registro">Crear empresa y usuario</Link>
        </p>
      </form>
    </div>
  );
}

