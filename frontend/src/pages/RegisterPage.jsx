import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { getRecaptchaToken, hasRecaptchaSiteKey, isRecaptchaEnabled } from "../lib/recaptcha";


const planOptions = [
  { value: "basico", label: "Básico", note: "Inventario" },
  { value: "pro", label: "Pro", note: "Inventario, POS y facturación pendiente" },
  { value: "total", label: "Total", note: "Inventario, POS, CRM y PM" },
];

const countryOptions = [
  { value: "mx", label: "México (+52)", countryCode: "+52", placeholder: "8117777777" },
  { value: "us_ca", label: "Estados Unidos / Canadá (+1)", countryCode: "+1", placeholder: "2125550123" },
  { value: "es", label: "España (+34)", countryCode: "+34", placeholder: "600111222" },
  { value: "co", label: "Colombia (+57)", countryCode: "+57", placeholder: "3001234567" },
  { value: "ar", label: "Argentina (+54)", countryCode: "+54", placeholder: "91123456789" },
  { value: "cl", label: "Chile (+56)", countryCode: "+56", placeholder: "912345678" },
  { value: "pe", label: "Perú (+51)", countryCode: "+51", placeholder: "912345678" },
  { value: "br", label: "Brasil (+55)", countryCode: "+55", placeholder: "11987654321" },
  { value: "other", label: "Otro", countryCode: "", placeholder: "5512345678" },
];

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


function normalizeCountryCodeInput(value) {
  const digits = value.replace(/\D/g, "");
  return digits ? `+${digits}` : "";
}


function cleanPhoneNumber(value) {
  return value.replace(/\D/g, "");
}


function normalizeOptionalText(value) {
  const trimmed = String(value || "").trim();
  return trimmed || null;
}


function normalizeRequiredText(value) {
  return String(value || "").trim();
}


function isValidEmail(value) {
  return emailPattern.test(String(value || "").trim());
}


function translateRegisterError(message) {
  const source = String(message || "").trim();
  const normalized = source.toLowerCase();

  if (!source) {
    return "No se pudo completar el registro.";
  }
  if (normalized.includes("value is not a valid email address")) {
    return "Revisa el correo. Debe tener formato nombre@dominio.com.";
  }
  if (normalized.includes("ya existe un usuario con ese correo")) {
    return "Este correo ya está registrado. Inicia sesión o usa otro correo.";
  }
  if (normalized.includes("este telefono ya esta registrado") || normalized.includes("este teléfono ya está registrado")) {
    return "Este teléfono ya está registrado.";
  }
  if (normalized.includes("numero de telefono invalido") || normalized.includes("número de teléfono inválido")) {
    return "Revisa el teléfono. Debe incluir 10 dígitos o el formato válido de tu país.";
  }
  if (normalized.includes("no se pudo conectar con el backend")) {
    return "El servidor tardó demasiado en responder. Intenta nuevamente.";
  }
  if (normalized.includes("codigo incorrecto") || normalized.includes("código incorrecto")) {
    return "El código no es correcto. Revisa el SMS e intenta nuevamente.";
  }
  if (normalized.includes("el codigo expiro") || normalized.includes("el código expiró")) {
    return "El código venció. Solicita uno nuevo.";
  }
  if (normalized.includes("demasiados intentos")) {
    return "Demasiados intentos. Solicita un nuevo código.";
  }
  if (normalized.includes("recaptcha")) {
    return source;
  }

  return source;
}


export default function RegisterPage() {
  const navigate = useNavigate();
  const { registerStart, registerVerify } = useAuth();
  const [countrySelection, setCountrySelection] = useState("mx");
  const [form, setForm] = useState({
    empresa_nombre: "",
    empresa_razon_social: "",
    empresa_rfc: "",
    empresa_giro: "",
    empresa_telefono: "",
    empresa_email_contacto: "",
    empresa_pais: "México",
    empresa_estado: "",
    empresa_ciudad: "",
    empresa_direccion: "",
    nombre_completo: "",
    email: "",
    country_code: "+52",
    phone_number: "",
    password: "",
    confirm_password: "",
    plan_code: "basico",
  });
  const [verification, setVerification] = useState({
    pending_id: "",
    masked_phone: "",
    code: "",
  });
  const [step, setStep] = useState(1);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [showPasswords, setShowPasswords] = useState(false);

  const recaptchaEnabled = useMemo(() => isRecaptchaEnabled(), []);
  const recaptchaConfigured = useMemo(() => hasRecaptchaSiteKey(), []);
  const selectedCountryOption = useMemo(
    () => countryOptions.find((option) => option.value === countrySelection) ?? countryOptions[0],
    [countrySelection],
  );

  useEffect(() => {
    if (!cooldownUntil) {
      setSecondsLeft(0);
      return undefined;
    }

    const timer = window.setInterval(() => {
      const nextSeconds = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
      setSecondsLeft(nextSeconds);
      if (nextSeconds === 0) {
        window.clearInterval(timer);
      }
    }, 250);

    return () => window.clearInterval(timer);
  }, [cooldownUntil]);

  function clearFieldError(field) {
    setFieldErrors((current) => {
      if (!current[field] && !(field === "password" || field === "confirm_password")) {
        return current;
      }
      const next = { ...current };
      delete next[field];
      if (field === "password" || field === "confirm_password") {
        delete next.password;
        delete next.confirm_password;
      }
      return next;
    });
  }

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    clearFieldError(field);
  }

  function validateStartForm() {
    const nextErrors = {};
    const adminEmail = normalizeRequiredText(form.email);
    const contactEmail = normalizeRequiredText(form.empresa_email_contacto);
    const phoneDigits = cleanPhoneNumber(form.phone_number);
    const countryCode = normalizeCountryCodeInput(form.country_code);

    if (!normalizeRequiredText(form.empresa_nombre)) {
      nextErrors.empresa_nombre = "Escribe el nombre comercial o de la empresa.";
    }
    if (!normalizeRequiredText(form.nombre_completo)) {
      nextErrors.nombre_completo = "Escribe el nombre completo del administrador.";
    }
    if (!adminEmail) {
      nextErrors.email = "Escribe el correo del administrador.";
    } else if (!isValidEmail(adminEmail)) {
      nextErrors.email = "Revisa el correo. Debe tener formato nombre@dominio.com.";
    }
    if (contactEmail && !isValidEmail(contactEmail)) {
      nextErrors.empresa_email_contacto = "Revisa el correo. Debe tener formato nombre@dominio.com.";
    }
    if (!countryCode) {
      nextErrors.country_code = "Escribe un código de país válido.";
    }
    if (!phoneDigits) {
      nextErrors.phone_number = "Revisa el teléfono. Debe incluir 10 dígitos.";
    } else if (["mx", "us_ca"].includes(countrySelection) && phoneDigits.length !== 10) {
      nextErrors.phone_number = "Revisa el teléfono. Debe incluir 10 dígitos.";
    } else if (phoneDigits.length < 8) {
      nextErrors.phone_number = "Revisa el teléfono. Debe incluir un número válido.";
    }
    if (!form.password) {
      nextErrors.password = "Escribe una contraseña.";
    } else if (form.password.length < 8) {
      nextErrors.password = "La contraseña debe tener al menos 8 caracteres.";
    }
    if (!form.confirm_password) {
      nextErrors.confirm_password = "Confirma tu contraseña.";
    } else if (form.password !== form.confirm_password) {
      nextErrors.confirm_password = "Las contraseñas no coinciden.";
    }
    if (!form.plan_code) {
      nextErrors.plan_code = "Selecciona un plan inicial.";
    }

    setFieldErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function buildRegisterPayload() {
    const countryCode = normalizeCountryCodeInput(form.country_code);
    const phoneNumber = cleanPhoneNumber(form.phone_number);

    if (!countryCode || !phoneNumber) {
      throw new Error("Revisa el teléfono. Debe incluir 10 dígitos o el formato válido de tu país.");
    }

    return {
      empresa_nombre: normalizeRequiredText(form.empresa_nombre),
      empresa_razon_social: normalizeOptionalText(form.empresa_razon_social),
      empresa_rfc: normalizeOptionalText(form.empresa_rfc)?.toUpperCase() ?? null,
      empresa_giro: normalizeOptionalText(form.empresa_giro),
      empresa_telefono: normalizeOptionalText(form.empresa_telefono),
      empresa_email_contacto: normalizeOptionalText(form.empresa_email_contacto),
      empresa_pais: normalizeOptionalText(form.empresa_pais),
      empresa_estado: normalizeOptionalText(form.empresa_estado),
      empresa_ciudad: normalizeOptionalText(form.empresa_ciudad),
      empresa_direccion: normalizeOptionalText(form.empresa_direccion),
      nombre_completo: normalizeRequiredText(form.nombre_completo),
      email: normalizeRequiredText(form.email),
      country_code: countryCode,
      phone_number: phoneNumber,
      password: form.password,
      plan_code: form.plan_code,
    };
  }

  async function submitRegisterStart() {
    setLoading(true);
    setError("");
    setMessage("");

    try {
      const payload = buildRegisterPayload();
      const recaptchaToken = await getRecaptchaToken("register_start");
      if (recaptchaEnabled && (typeof recaptchaToken !== "string" || recaptchaToken.length <= 20)) {
        throw new Error("No se pudo completar reCAPTCHA. Recarga la página e intenta nuevamente.");
      }

      const response = await registerStart({
        ...payload,
        recaptcha_token: recaptchaToken,
      });

      setVerification({
        pending_id: response.pending_id,
        masked_phone: response.masked_phone,
        code: "",
      });
      setStep(2);
      setMessage(response.message);
      setCooldownUntil(Date.now() + response.cooldown_seconds * 1000);
    } catch (submitError) {
      if (import.meta.env.DEV) {
        console.warn("[register] register_start_failed", submitError);
      }
      const nextMessage = submitError instanceof Error ? submitError.message : "";
      setError(translateRegisterError(nextMessage || "No se pudo enviar el código SMS."));
    } finally {
      setLoading(false);
    }
  }

  async function handleStart(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!validateStartForm()) {
      return;
    }
    await submitRegisterStart();
  }

  async function handleVerify(event) {
    event.preventDefault();
    if (verification.code.trim().length !== 6) {
      setError("Ingresa el código de 6 dígitos.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");

    try {
      await registerVerify({
        pending_id: verification.pending_id,
        code: verification.code,
      });
      navigate("/");
    } catch (submitError) {
      const nextMessage = submitError instanceof Error ? submitError.message : "";
      setError(translateRegisterError(nextMessage));
    } finally {
      setLoading(false);
    }
  }

  async function handleResendCode() {
    await submitRegisterStart();
  }

  return (
    <div className="auth-shell">
      <section className="auth-hero">
        <p className="eyebrow">Trial de 15 días</p>
        <h1>Prueba Capella Ops gratis por 15 días</h1>
        <p>
          Registra tu empresa, valida tu teléfono y empieza a operar inventario, ventas y proyectos
          desde un solo lugar.
        </p>
        <div className="security-note auth-hero-note">
          <strong>La empresa se crea hasta confirmar el código SMS.</strong>
          <span>Primero validamos la solicitud y luego activamos tu acceso.</span>
        </div>
        <div className="auth-hero-list">
          <div className="auth-hero-list-item">
            <strong>Empresa</strong>
            <span>Captura solo los datos esenciales y completa el resto después.</span>
          </div>
          <div className="auth-hero-list-item">
            <strong>Administrador principal</strong>
            <span>Esta cuenta tendrá acceso completo para configurar la empresa.</span>
          </div>
          <div className="auth-hero-list-item">
            <strong>Verificación SMS</strong>
            <span>Confirmamos tu teléfono antes de crear el trial.</span>
          </div>
        </div>
      </section>

      {step === 1 ? (
        <form className="auth-card" onSubmit={handleStart}>
          <div className="auth-card-header">
            <div>
              <h2>Crear cuenta</h2>
              <p>Primero validaremos tu teléfono. Después podrás configurar tu primer almacén.</p>
            </div>
            <div className="auth-step-list" aria-label="Flujo de registro">
              <div className="auth-step-chip is-active">1. Empresa</div>
              <div className="auth-step-chip is-active">2. Administrador</div>
              <div className="auth-step-chip">3. SMS</div>
            </div>
          </div>

          <section className="auth-form-section">
            <div className="auth-form-section-header">
              <h3>Datos de empresa</h3>
              <p>Empieza con el nombre comercial y agrega los datos fiscales o de contacto si ya los tienes.</p>
            </div>

            <label>
              Nombre comercial / empresa
              <input
                onChange={(event) => updateForm("empresa_nombre", event.target.value)}
                required
                type="text"
                value={form.empresa_nombre}
              />
              {fieldErrors.empresa_nombre ? <span className="field-error">{fieldErrors.empresa_nombre}</span> : null}
            </label>

            <div className="split-fields">
              <label>
                Razón social
                <input
                  onChange={(event) => updateForm("empresa_razon_social", event.target.value)}
                  type="text"
                  value={form.empresa_razon_social}
                />
              </label>

              <label>
                RFC
                <input
                  onChange={(event) => updateForm("empresa_rfc", event.target.value.toUpperCase())}
                  type="text"
                  value={form.empresa_rfc}
                />
              </label>
            </div>

            <div className="split-fields">
              <label>
                Giro / industria
                <input
                  onChange={(event) => updateForm("empresa_giro", event.target.value)}
                  type="text"
                  value={form.empresa_giro}
                />
              </label>

              <label>
                Teléfono de empresa
                <input
                  onChange={(event) => updateForm("empresa_telefono", event.target.value)}
                  type="text"
                  value={form.empresa_telefono}
                />
              </label>
            </div>

            <div className="split-fields">
              <label>
                Email de contacto
                <input
                  autoComplete="email"
                  onChange={(event) => updateForm("empresa_email_contacto", event.target.value)}
                  placeholder="opcional@empresa.com"
                  type="text"
                  value={form.empresa_email_contacto}
                />
                <span className="field-hint">Si lo dejas vacío, usaremos el correo del administrador.</span>
                {fieldErrors.empresa_email_contacto ? <span className="field-error">{fieldErrors.empresa_email_contacto}</span> : null}
              </label>

              <label>
                País
                <input
                  onChange={(event) => updateForm("empresa_pais", event.target.value)}
                  type="text"
                  value={form.empresa_pais}
                />
              </label>
            </div>

            <div className="split-fields">
              <label>
                Estado
                <input
                  onChange={(event) => updateForm("empresa_estado", event.target.value)}
                  type="text"
                  value={form.empresa_estado}
                />
              </label>

              <label>
                Ciudad
                <input
                  onChange={(event) => updateForm("empresa_ciudad", event.target.value)}
                  type="text"
                  value={form.empresa_ciudad}
                />
              </label>
            </div>

            <label>
              Dirección
              <textarea
                onChange={(event) => updateForm("empresa_direccion", event.target.value)}
                rows={2}
                value={form.empresa_direccion}
              />
            </label>
          </section>

          <section className="auth-form-section">
            <div className="auth-form-section-header">
              <h3>Administrador principal</h3>
              <p>Esta persona tendrá acceso completo para configurar la empresa.</p>
            </div>

            <label>
              Nombre completo
              <input
                onChange={(event) => updateForm("nombre_completo", event.target.value)}
                required
                type="text"
                value={form.nombre_completo}
              />
              {fieldErrors.nombre_completo ? <span className="field-error">{fieldErrors.nombre_completo}</span> : null}
            </label>

            <label>
              Correo
              <input
                autoComplete="email"
                onChange={(event) => updateForm("email", event.target.value)}
                required
                type="text"
                value={form.email}
              />
              {fieldErrors.email ? <span className="field-error">{fieldErrors.email}</span> : null}
            </label>

            <div className="split-fields">
              <label>
                País / código de país
                <select
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    const nextOption =
                      countryOptions.find((option) => option.value === nextValue) ?? countryOptions[0];
                    setCountrySelection(nextValue);
                    updateForm("country_code", nextOption.countryCode);
                  }}
                  value={countrySelection}
                >
                  {countryOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              {countrySelection === "other" ? (
                <label>
                  Código manual
                  <input
                    inputMode="tel"
                    maxLength={6}
                    onChange={(event) => updateForm("country_code", normalizeCountryCodeInput(event.target.value))}
                    placeholder="+502"
                    required
                    type="text"
                    value={form.country_code}
                  />
                  {fieldErrors.country_code ? <span className="field-error">{fieldErrors.country_code}</span> : null}
                </label>
              ) : null}
            </div>

            <label>
              Teléfono
              <input
                autoComplete="tel-national"
                inputMode="tel"
                maxLength={20}
                onChange={(event) => updateForm("phone_number", cleanPhoneNumber(event.target.value))}
                placeholder={selectedCountryOption.placeholder}
                required
                type="text"
                value={form.phone_number}
              />
              {fieldErrors.phone_number ? <span className="field-error">{fieldErrors.phone_number}</span> : null}
            </label>

            <div className="split-fields">
              <label>
                Contraseña
                <div className="password-field">
                  <input
                    autoComplete="new-password"
                    minLength={8}
                    onChange={(event) => updateForm("password", event.target.value)}
                    required
                    type={showPasswords ? "text" : "password"}
                    value={form.password}
                  />
                  <button
                    className="password-toggle"
                    onClick={() => setShowPasswords((current) => !current)}
                    type="button"
                  >
                    {showPasswords ? "Ocultar" : "Mostrar"}
                  </button>
                </div>
                <span className="field-hint">Mínimo 8 caracteres.</span>
                {fieldErrors.password ? <span className="field-error">{fieldErrors.password}</span> : null}
              </label>

              <label>
                Confirmar contraseña
                <div className="password-field">
                  <input
                    autoComplete="new-password"
                    minLength={8}
                    onChange={(event) => updateForm("confirm_password", event.target.value)}
                    required
                    type={showPasswords ? "text" : "password"}
                    value={form.confirm_password}
                  />
                </div>
                {fieldErrors.confirm_password ? <span className="field-error">{fieldErrors.confirm_password}</span> : null}
              </label>
            </div>
          </section>

          <section className="auth-form-section">
            <div className="auth-form-section-header">
              <h3>Plan inicial y verificación</h3>
              <p>Todos empiezan con 15 días de prueba. Podrás cambiar el plan después.</p>
            </div>

            <label>
              Plan inicial
              <select onChange={(event) => updateForm("plan_code", event.target.value)} value={form.plan_code}>
                {planOptions.map((plan) => (
                  <option key={plan.value} value={plan.value}>
                    {plan.label} - {plan.note}
                  </option>
                ))}
              </select>
              <span className="field-hint">Puedes cambiarlo después. Todos inician con 15 días de prueba.</span>
              {fieldErrors.plan_code ? <span className="field-error">{fieldErrors.plan_code}</span> : null}
            </label>

            <div className="security-note">
              <strong>Protección automática</strong>
              <span>
                {!recaptchaEnabled
                  ? "reCAPTCHA está desactivado temporalmente en el frontend para pruebas."
                  : recaptchaConfigured
                    ? "Validamos la solicitud antes de enviar el código SMS."
                    : "reCAPTCHA no está configurado."}
              </span>
            </div>
          </section>

          {error ? <p className="form-error">{error}</p> : null}
          {message ? <p className="form-success">{message}</p> : null}

          <button className="primary-button" disabled={loading} type="submit">
            {loading ? "Enviando código..." : "Enviar código por SMS"}
          </button>

          <p className="auth-link">
            ¿Ya tienes usuario? <Link to="/login">Iniciar sesión</Link>
          </p>
        </form>
      ) : (
        <form className="auth-card" onSubmit={handleVerify}>
          <div className="auth-card-header">
            <div>
              <h2>Verifica tu teléfono</h2>
              <p>Enviamos un código SMS a {verification.masked_phone}.</p>
            </div>
            <div className="auth-step-list" aria-label="Flujo de registro">
              <div className="auth-step-chip is-complete">1. Empresa</div>
              <div className="auth-step-chip is-complete">2. Administrador</div>
              <div className="auth-step-chip is-active">3. SMS</div>
            </div>
          </div>

          <div className="security-note">
            <strong>Último paso</strong>
            <span>La empresa se crea cuando confirmes este código.</span>
          </div>

          <label>
            Código de 6 dígitos
            <input
              inputMode="numeric"
              maxLength={6}
              minLength={6}
              onChange={(event) =>
                setVerification((current) => ({
                  ...current,
                  code: event.target.value.replace(/\D/g, "").slice(0, 6),
                }))
              }
              pattern="[0-9]{6}"
              placeholder="123456"
              required
              type="text"
              value={verification.code}
            />
          </label>

          {error ? <p className="form-error">{error}</p> : null}
          {message ? <p className="form-success">{message}</p> : null}

          <button className="primary-button" disabled={loading} type="submit">
            {loading ? "Verificando..." : "Verificar y crear empresa"}
          </button>

          <button
            className="ghost-button"
            disabled={loading || secondsLeft > 0}
            onClick={handleResendCode}
            type="button"
          >
            {secondsLeft > 0 ? `Reenviar código en ${secondsLeft}s` : "Reenviar código"}
          </button>

          <button
            className="link-button"
            onClick={() => {
              setStep(1);
              setError("");
              setMessage("");
            }}
            type="button"
          >
            Cambiar teléfono
          </button>
        </form>
      )}
    </div>
  );
}
