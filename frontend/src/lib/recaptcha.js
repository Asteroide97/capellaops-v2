const SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY ?? "";
const SCRIPT_SELECTOR = "script[data-recaptcha-script='true']";
const DEV = import.meta.env.DEV;

let loadPromise;


function logRecaptchaDebug(label, value) {
  if (!DEV) {
    return;
  }

  console.info(`[recaptcha] ${label}=${value}`);
}


function waitForGrecaptcha(timeoutMs = 8000) {
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
        reject(new Error("No se pudo cargar reCAPTCHA."));
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
        reject(error);
      }
    };

    const handleError = () => {
      reject(new Error("No se pudo cargar reCAPTCHA."));
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
  logRecaptchaDebug("recaptcha_site_key_present", Boolean(SITE_KEY));

  if (!SITE_KEY) {
    throw new Error("reCAPTCHA no esta configurado en el frontend.");
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
  const grecaptcha = await ensureRecaptchaLoaded();

  const token = await new Promise((resolve, reject) => {
    grecaptcha.ready(() => {
      grecaptcha
        .execute(SITE_KEY, { action })
        .then(resolve)
        .catch(() => reject(new Error("No se pudo ejecutar reCAPTCHA.")));
    });
  });

  const isValidToken = typeof token === "string" && token.length > 20;
  logRecaptchaDebug("recaptcha_token_present", isValidToken);

  if (!isValidToken) {
    throw new Error("No se pudo obtener un token valido de reCAPTCHA.");
  }

  return token;
}


export function hasRecaptchaSiteKey() {
  return Boolean(SITE_KEY);
}
