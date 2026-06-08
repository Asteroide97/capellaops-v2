const SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? "";
const RECAPTCHA_ENABLED = String(import.meta.env.VITE_RECAPTCHA_ENABLED ?? "true").trim().toLowerCase() !== "false";
const SCRIPT_SELECTOR = "script[data-recaptcha-script='true']";
const DEV = import.meta.env.DEV;
const SCRIPT_TIMEOUT_MS = 10000;
const EXECUTE_TIMEOUT_MS = 12000;

let loadPromise;


function logRecaptchaDebug(label, value) {
  if (!DEV) {
    return;
  }

  console.warn(`[recaptcha] ${label}`, value);
}


function withTimeout(promise, timeoutMs, timeoutMessage) {
  return new Promise((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      reject(new Error(timeoutMessage));
    }, timeoutMs);

    promise
      .then((value) => {
        window.clearTimeout(timeoutId);
        resolve(value);
      })
      .catch((error) => {
        window.clearTimeout(timeoutId);
        reject(error);
      });
  });
}


function waitForGrecaptcha(timeoutMs = SCRIPT_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();

    function check() {
      if (window.grecaptcha?.ready && window.grecaptcha?.execute) {
        logRecaptchaDebug("grecaptcha_loaded", true);
        resolve(window.grecaptcha);
        return;
      }

      if (Date.now() - startedAt >= timeoutMs) {
        logRecaptchaDebug("grecaptcha_loaded", false);
        reject(new Error("No se pudo cargar Google reCAPTCHA. Revisa bloqueadores del navegador o dominios permitidos."));
        return;
      }

      window.setTimeout(check, 50);
    }

    check();
  });
}


function appendRecaptchaScript() {
  return new Promise((resolve, reject) => {
    let script = document.querySelector(SCRIPT_SELECTOR);

    if (!script) {
      script = document.createElement("script");
      script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(SITE_KEY)}`;
      script.async = true;
      script.defer = true;
      script.dataset.recaptchaScript = "true";
      document.head.appendChild(script);
    }

    if (window.grecaptcha?.ready && window.grecaptcha?.execute) {
      resolve(window.grecaptcha);
      return;
    }

    const handleLoad = async () => {
      try {
        const grecaptcha = await waitForGrecaptcha();
        resolve(grecaptcha);
      } catch (error) {
        logRecaptchaDebug("grecaptcha_wait_failed", error);
        reject(error);
      }
    };

    const handleError = () => {
      const nextError = new Error("No se pudo cargar Google reCAPTCHA. Revisa bloqueadores del navegador o dominios permitidos.");
      logRecaptchaDebug("grecaptcha_script_failed", nextError.message);
      reject(nextError);
    };

    script.addEventListener("load", handleLoad, { once: true });
    script.addEventListener("error", handleError, { once: true });

    if (script.dataset.loaded === "true") {
      void handleLoad();
    } else {
      script.addEventListener(
        "load",
        () => {
          script.dataset.loaded = "true";
        },
        { once: true },
      );
    }
  });
}


async function ensureRecaptchaLoaded() {
  logRecaptchaDebug("recaptcha_enabled", RECAPTCHA_ENABLED);
  logRecaptchaDebug("recaptcha_site_key_present", Boolean(SITE_KEY));

  if (!RECAPTCHA_ENABLED) {
    return null;
  }

  if (!SITE_KEY) {
    throw new Error("reCAPTCHA no está configurado en el frontend.");
  }

  if (window.grecaptcha?.ready && window.grecaptcha?.execute) {
    logRecaptchaDebug("grecaptcha_loaded", true);
    return window.grecaptcha;
  }

  if (!loadPromise) {
    loadPromise = appendRecaptchaScript().catch((error) => {
      loadPromise = undefined;
      throw error;
    });
  }

  return loadPromise;
}


export async function getRecaptchaToken(action = "register_start") {
  if (!RECAPTCHA_ENABLED) {
    logRecaptchaDebug("recaptcha_skipped", action);
    return null;
  }

  const grecaptcha = await ensureRecaptchaLoaded();

  if (!grecaptcha?.ready || !grecaptcha?.execute) {
    throw new Error("No se pudo cargar Google reCAPTCHA. Revisa bloqueadores del navegador o dominios permitidos.");
  }

  const token = await withTimeout(
    new Promise((resolve, reject) => {
      try {
        grecaptcha.ready(() => {
          grecaptcha
            .execute(SITE_KEY, { action })
            .then(resolve)
            .catch((error) => {
              logRecaptchaDebug("grecaptcha_execute_failed", error);
              reject(new Error("reCAPTCHA rechazó la ejecución. Verifica que el dominio esté autorizado para esta site key."));
            });
        });
      } catch (error) {
        logRecaptchaDebug("grecaptcha_ready_failed", error);
        reject(new Error("reCAPTCHA rechazó la ejecución. Verifica que el dominio esté autorizado para esta site key."));
      }
    }),
    EXECUTE_TIMEOUT_MS,
    "reCAPTCHA tardó demasiado en responder.",
  );

  const isValidToken = typeof token === "string" && token.length > 20;
  logRecaptchaDebug("recaptcha_token_present", isValidToken);

  if (!isValidToken) {
    throw new Error("No se pudo obtener un token válido de reCAPTCHA.");
  }

  return token;
}


export function hasRecaptchaSiteKey() {
  return Boolean(SITE_KEY);
}


export function isRecaptchaEnabled() {
  return RECAPTCHA_ENABLED;
}
