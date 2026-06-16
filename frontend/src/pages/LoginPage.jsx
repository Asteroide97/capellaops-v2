import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  completePasswordReset,
  startPasswordReset,
  verifyPasswordReset,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";


const RESET_START_MESSAGE = "Si los datos coinciden, enviaremos un codigo de verificacion.";


function buildInitialResetForm(email = "") {
  return {
    email,
    phone: "",
    code: "",
    newPassword: "",
    confirmPassword: "",
  };
}


function getResetErrorMessage(step, error) {
  if (step === 1) {
    return "No pudimos enviar el codigo en este momento. Intenta nuevamente.";
  }

  if (step === 2) {
    return "No se pudo validar el codigo. Revisa los datos e intentalo de nuevo.";
  }

  if (error?.status === 400) {
    return "No se pudo actualizar la contrasena. Solicita un nuevo codigo e intentalo de nuevo.";
  }

  return "No se pudo actualizar la contrasena en este momento. Intenta nuevamente.";
}


export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [view, setView] = useState("login");
  const [form, setForm] = useState({
    email: "",
    password: "",
    empresa_id: "",
  });
  const [resetForm, setResetForm] = useState(buildInitialResetForm());
  const [resetStep, setResetStep] = useState(1);
  const [resetToken, setResetToken] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginSuccess, setLoginSuccess] = useState("");
  const [resetError, setResetError] = useState("");
  const [resetNotice, setResetNotice] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);

  const resetSteps = useMemo(
    () => [
      { id: 1, label: "Datos" },
      { id: 2, label: "Codigo" },
      { id: 3, label: "Nueva contrasena" },
    ],
    [],
  );

  async function handleSubmit(event) {
    event.preventDefault();
    setLoginLoading(true);
    setLoginError("");
    setLoginSuccess("");

    try {
      await login({
        email: form.email.trim(),
        password: form.password,
        empresa_id: form.empresa_id.trim() || null,
      });
      navigate("/");
    } catch (submitError) {
      setLoginError(submitError.message);
    } finally {
      setLoginLoading(false);
    }
  }

  function openResetFlow() {
    setView("reset");
    setResetStep(1);
    setResetToken("");
    setResetError("");
    setResetNotice("");
    setLoginError("");
    setLoginSuccess("");
    setResetForm((current) => ({
      ...buildInitialResetForm(form.email.trim() || current.email),
      phone: current.phone,
    }));
  }

  function returnToLogin(message = "") {
    setView("login");
    setResetStep(1);
    setResetToken("");
    setResetError("");
    setResetNotice("");
    setResetLoading(false);
    setForm((current) => ({
      ...current,
      email: resetForm.email.trim() || current.email,
      password: "",
    }));
    setLoginSuccess(message);
  }

  async function handleResetSubmit(event) {
    event.preventDefault();
    setResetLoading(true);
    setResetError("");

    try {
      if (resetStep === 1) {
        const response = await startPasswordReset({
          email: resetForm.email.trim(),
          phone: resetForm.phone.trim(),
        });
        setResetNotice(response.message || RESET_START_MESSAGE);
        setResetStep(2);
        return;
      }

      if (resetStep === 2) {
        const response = await verifyPasswordReset({
          email: resetForm.email.trim(),
          phone: resetForm.phone.trim(),
          code: resetForm.code.trim(),
        });
        setResetToken(response.reset_token);
        setResetNotice("Codigo validado. Ahora captura tu nueva contrasena.");
        setResetStep(3);
        return;
      }

      if (resetForm.newPassword.length < 8) {
        setResetError("La nueva contrasena debe tener al menos 8 caracteres.");
        return;
      }

      if (resetForm.newPassword !== resetForm.confirmPassword) {
        setResetError("La confirmacion de la contrasena no coincide.");
        return;
      }

      await completePasswordReset({
        reset_token: resetToken,
        new_password: resetForm.newPassword,
      });
      setResetForm(buildInitialResetForm(resetForm.email.trim()));
      returnToLogin("Contrasena actualizada. Ya puedes iniciar sesion.");
    } catch (submitError) {
      setResetError(getResetErrorMessage(resetStep, submitError));
    } finally {
      setResetLoading(false);
    }
  }

  function updateResetField(field, value) {
    setResetForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function renderStepIndicator() {
    return (
      <div className="auth-step-list" aria-label="Pasos para recuperar la contrasena">
        {resetSteps.map((step) => {
          const statusClass =
            step.id === resetStep ? "is-active" : step.id < resetStep ? "is-complete" : "";
          return (
            <span key={step.id} className={`auth-step-chip ${statusClass}`.trim()}>
              {step.id}. {step.label}
            </span>
          );
        })}
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <section className="auth-hero">
        <p className="eyebrow">Capella Ops V2</p>
        <h1>Controla tu operacion en un solo lugar</h1>
        <p>Accede a tus modulos de operacion, ventas, inventario y proyectos desde una sola plataforma.</p>
      </section>

      {view === "login" ? (
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-card-header">
            <div>
              <h2>Iniciar sesion</h2>
              <p>Ingresa con tu correo y contrasena.</p>
            </div>
          </div>

          {loginSuccess ? <p className="form-success auth-success-banner">{loginSuccess}</p> : null}

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
            Contrasena
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
            Empresa (opcional)
            <input
              onChange={(event) => setForm({ ...form, empresa_id: event.target.value })}
              placeholder="Solo si tienes acceso a varias empresas"
              type="text"
              value={form.empresa_id}
            />
            <span className="field-hint">Normalmente puedes dejar este campo vacio.</span>
          </label>

          <div className="auth-inline-actions">
            <button className="link-button auth-inline-link" onClick={openResetFlow} type="button">
              Olvide mi contrasena
            </button>
          </div>

          {loginError ? <p className="form-error">{loginError}</p> : null}

          <button className="primary-button" disabled={loginLoading} type="submit">
            {loginLoading ? "Ingresando..." : "Entrar"}
          </button>

          <p className="auth-link">
            No tienes cuenta? <Link to="/registro">Crear empresa</Link>
          </p>
        </form>
      ) : (
        <form className="auth-card" onSubmit={handleResetSubmit}>
          <div className="auth-card-header">
            <div>
              <h2>Recuperar contrasena</h2>
              <p>Te ayudaremos a verificar tu identidad por SMS y definir una nueva contrasena.</p>
            </div>
            {renderStepIndicator()}
          </div>

          <div className="security-note">
            <strong>Privacidad</strong>
            <span>Por seguridad, este flujo no confirma si el correo o el telefono pertenecen a una cuenta.</span>
          </div>

          {resetStep === 1 ? (
            <div className="auth-form-section">
              <div className="auth-form-section-header">
                <h3>Datos de acceso</h3>
                <p>Ingresa el correo y telefono registrados para recibir el codigo.</p>
              </div>

              <label>
                Correo
                <input
                  autoComplete="email"
                  onChange={(event) => updateResetField("email", event.target.value)}
                  required
                  type="email"
                  value={resetForm.email}
                />
              </label>

              <label>
                Telefono
                <input
                  autoComplete="tel"
                  onChange={(event) => updateResetField("phone", event.target.value)}
                  placeholder="+528711234567"
                  required
                  type="tel"
                  value={resetForm.phone}
                />
              </label>
            </div>
          ) : null}

          {resetStep === 2 ? (
            <div className="auth-form-section">
              <div className="auth-form-section-header">
                <h3>Codigo de verificacion</h3>
                <p>Captura el codigo SMS enviado al telefono registrado.</p>
              </div>

              <div className="auth-reset-summary">
                <span>
                  <strong>Correo:</strong> {resetForm.email}
                </span>
                <span>
                  <strong>Telefono:</strong> {resetForm.phone}
                </span>
              </div>

              <label>
                Codigo
                <input
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  maxLength={6}
                  onChange={(event) => updateResetField("code", event.target.value.replace(/\D/g, ""))}
                  placeholder="123456"
                  required
                  type="text"
                  value={resetForm.code}
                />
              </label>
            </div>
          ) : null}

          {resetStep === 3 ? (
            <div className="auth-form-section">
              <div className="auth-form-section-header">
                <h3>Nueva contrasena</h3>
                <p>Define una nueva contrasena para tu cuenta.</p>
              </div>

              <label>
                Nueva contrasena
                <input
                  autoComplete="new-password"
                  minLength={8}
                  onChange={(event) => updateResetField("newPassword", event.target.value)}
                  required
                  type="password"
                  value={resetForm.newPassword}
                />
              </label>

              <label>
                Confirmar nueva contrasena
                <input
                  autoComplete="new-password"
                  minLength={8}
                  onChange={(event) => updateResetField("confirmPassword", event.target.value)}
                  required
                  type="password"
                  value={resetForm.confirmPassword}
                />
              </label>
            </div>
          ) : null}

          {resetNotice ? <p className="form-success auth-success-banner">{resetNotice}</p> : null}
          {resetError ? <p className="form-error">{resetError}</p> : null}

          <div className="auth-inline-actions">
            <button className="ghost-button" onClick={() => returnToLogin()} type="button">
              Volver a iniciar sesion
            </button>

            {resetStep > 1 && resetStep < 3 ? (
              <button
                className="ghost-button"
                onClick={() => {
                  setResetStep(resetStep - 1);
                  setResetError("");
                  setResetNotice("");
                }}
                type="button"
              >
                Cambiar datos
              </button>
            ) : null}

            <button className="primary-button" disabled={resetLoading} type="submit">
              {resetLoading
                ? "Procesando..."
                : resetStep === 1
                  ? "Enviar codigo"
                  : resetStep === 2
                    ? "Verificar codigo"
                    : "Actualizar contrasena"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
