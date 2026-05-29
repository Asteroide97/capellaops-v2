import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { getRecaptchaToken, hasRecaptchaSiteKey } from "../lib/recaptcha";


const planOptions = [
  { value: "basico", label: "Basico", note: "Inventario" },
  { value: "pro", label: "Pro", note: "Inventario, POS y facturacion pendiente" },
  { value: "total", label: "Total", note: "Inventario, POS, CRM y PM" },
];

const countryOptions = [
  { value: "mx", label: "Mexico (+52)", countryCode: "+52", placeholder: "8117777777" },
  { value: "us_ca", label: "Estados Unidos / Canada (+1)", countryCode: "+1", placeholder: "2125550123" },
  { value: "es", label: "Espana (+34)", countryCode: "+34", placeholder: "600111222" },
  { value: "co", label: "Colombia (+57)", countryCode: "+57", placeholder: "3001234567" },
  { value: "ar", label: "Argentina (+54)", countryCode: "+54", placeholder: "91123456789" },
  { value: "cl", label: "Chile (+56)", countryCode: "+56", placeholder: "912345678" },
  { value: "pe", label: "Peru (+51)", countryCode: "+51", placeholder: "912345678" },
  { value: "br", label: "Brasil (+55)", countryCode: "+55", placeholder: "11987654321" },
  { value: "other", label: "Otro", countryCode: "", placeholder: "5512345678" },
];


function normalizeCountryCodeInput(value) {
  const digits = value.replace(/\D/g, "");
  return digits ? `+${digits}` : "";
}


function cleanPhoneNumber(value) {
  return value.replace(/\D/g, "");
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
    empresa_pais: "Mexico",
    empresa_estado: "",
    empresa_ciudad: "",
    empresa_direccion: "",
    nombre_completo: "",
    email: "",
    country_code: "+52",
    phone_number: "",
    password: "",
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
  const [loading, setLoading] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(0);

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

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function buildRegisterPayload() {
    const countryCode = normalizeCountryCodeInput(form.country_code);
    const phoneNumber = cleanPhoneNumber(form.phone_number);

    if (!countryCode || !phoneNumber) {
      throw new Error("Numero de telefono invalido.");
    }

    return {
      empresa_nombre: form.empresa_nombre,
      empresa_razon_social: form.empresa_razon_social,
      empresa_rfc: form.empresa_rfc,
      empresa_giro: form.empresa_giro,
      empresa_telefono: form.empresa_telefono,
      empresa_email_contacto: form.empresa_email_contacto,
      empresa_pais: form.empresa_pais,
      empresa_estado: form.empresa_estado,
      empresa_ciudad: form.empresa_ciudad,
      empresa_direccion: form.empresa_direccion,
      nombre_completo: form.nombre_completo,
      email: form.email,
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
      if (typeof recaptchaToken !== "string" || recaptchaToken.length <= 20) {
        throw new Error("No se pudo obtener un token valido de reCAPTCHA.");
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
      const nextMessage = submitError instanceof Error ? submitError.message : "";
      if (nextMessage.toLowerCase().includes("recaptcha")) {
        setError("No se pudo completar reCAPTCHA. Recarga la pagina e intenta nuevamente.");
      } else {
        setError(nextMessage || "No se pudo enviar el SMS.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleStart(event) {
    event.preventDefault();
    await submitRegisterStart();
  }

  async function handleVerify(event) {
    event.preventDefault();
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
      setError(submitError.message);
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
        <p className="eyebrow">Alta inicial</p>
        <h1>Crea una empresa en trial de 15 dias</h1>
        <p>
          Primero validamos reCAPTCHA y tu telefono. La empresa solo se crea cuando
          confirmas el codigo por SMS.
        </p>
      </section>

      {step === 1 ? (
        <form className="auth-card" onSubmit={handleStart}>
          <div>
            <h2>Registro</h2>
            <p>Enviaremos un codigo por SMS antes de crear la empresa y vincularte como owner.</p>
          </div>

          <label>
            Nombre comercial / empresa
            <input
              onChange={(event) => updateForm("empresa_nombre", event.target.value)}
              required
              type="text"
              value={form.empresa_nombre}
            />
          </label>

          <div className="split-fields">
            <label>
              Razon social
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
              Telefono de empresa
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
                onChange={(event) => updateForm("empresa_email_contacto", event.target.value)}
                placeholder="Por defecto se usara el email del owner"
                type="email"
                value={form.empresa_email_contacto}
              />
            </label>

            <label>
              Pais
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
            Direccion
            <textarea
              onChange={(event) => updateForm("empresa_direccion", event.target.value)}
              rows={2}
              value={form.empresa_direccion}
            />
          </label>

          <div className="security-note">
            <strong>Owner de la empresa</strong>
            <span>Este usuario sera el primer owner/admin de la empresa registrada.</span>
          </div>

          <label>
            Nombre completo
            <input
              onChange={(event) => updateForm("nombre_completo", event.target.value)}
              required
              type="text"
              value={form.nombre_completo}
            />
          </label>

          <label>
            Correo
            <input
              autoComplete="email"
              onChange={(event) => updateForm("email", event.target.value)}
              required
              type="email"
              value={form.email}
            />
          </label>

          <div className="split-fields">
            <label>
              Pais / codigo de pais
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
                Codigo manual
                <input
                  inputMode="tel"
                  maxLength={6}
                  onChange={(event) => updateForm("country_code", normalizeCountryCodeInput(event.target.value))}
                  placeholder="+502"
                  required
                  type="text"
                  value={form.country_code}
                />
              </label>
            ) : null}
          </div>

          <label>
            Telefono
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
          </label>

          <label>
            Contrasena
            <input
              autoComplete="new-password"
              minLength={8}
              onChange={(event) => updateForm("password", event.target.value)}
              required
              type="password"
              value={form.password}
            />
          </label>

          <label>
            Plan inicial
            <select onChange={(event) => updateForm("plan_code", event.target.value)} value={form.plan_code}>
              {planOptions.map((plan) => (
                <option key={plan.value} value={plan.value}>
                  {plan.label} - {plan.note}
                </option>
              ))}
            </select>
          </label>

          <div className="security-note">
            <strong>reCAPTCHA</strong>
            <span>
              {recaptchaConfigured
                ? "Se ejecuta automaticamente al enviar el codigo."
                : "Si el backend exige reCAPTCHA, configura VITE_RECAPTCHA_SITE_KEY antes de continuar."}
            </span>
          </div>

          {error ? <p className="form-error">{error}</p> : null}
          {message ? <p className="form-success">{message}</p> : null}

          <button className="primary-button" disabled={loading} type="submit">
            {loading ? "Enviando..." : "Enviar codigo por SMS"}
          </button>

          <p className="auth-link">
            Ya tienes usuario? <Link to="/login">Iniciar sesion</Link>
          </p>
        </form>
      ) : (
        <form className="auth-card" onSubmit={handleVerify}>
          <div>
            <h2>Confirma tu telefono</h2>
            <p>Te enviamos un codigo por SMS a {verification.masked_phone}.</p>
          </div>

          <label>
            Codigo de 6 digitos
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
            {loading ? "Verificando..." : "Verificar y crear cuenta"}
          </button>

          <button
            className="ghost-button"
            disabled={loading || secondsLeft > 0}
            onClick={handleResendCode}
            type="button"
          >
            {secondsLeft > 0 ? `Reenviar codigo en ${secondsLeft}s` : "Reenviar codigo"}
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
            Volver y editar datos
          </button>
        </form>
      )}
    </div>
  );
}
