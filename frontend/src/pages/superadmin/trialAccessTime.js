const DATE_ERROR = "Revisa la fecha y hora de vencimiento del trial.";
const pad = value => String(value).padStart(2, "0");

function localInput(date) {
  const minutes = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const seconds = date.getSeconds();
  const fraction = String(date.getMilliseconds()).padStart(3, "0").replace(/0+$/, "");
  return minutes + (seconds || fraction ? `:${pad(seconds)}${fraction ? `.${fraction}` : ""}` : "");
}

export function toTrialLocalInput(raw) {
  if (!raw) return "";
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? "" : localInput(date);
}

export function serializeTrialInput(value, originalRaw) {
  if (!value) return null;
  // Date/input precision is milliseconds, but the API can retain microseconds.
  if (originalRaw && value === toTrialLocalInput(originalRaw)) return originalRaw;

  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/.exec(value);
  if (!match) throw new Error(DATE_ERROR);
  const date = new Date(value);
  const seconds = Number(match[2] || 0);
  const fraction = (match[3] || "").replace(/0+$/, "");
  const canonical = match[1] + (seconds || fraction ? `:${pad(seconds)}${fraction ? `.${fraction}` : ""}` : "");
  if (Number.isNaN(date.getTime()) || localInput(date) !== canonical) throw new Error(DATE_ERROR);
  let result = date.toISOString();
  const originalFraction = originalRaw?.match(/\.(\d+)(?:Z|[+-]\d{2}:\d{2})$/)?.[1];
  if (originalFraction?.length > 3 && date.getMilliseconds() === new Date(originalRaw).getMilliseconds()) {
    result = result.replace(/\.\d{3}Z$/, `.${originalFraction}Z`);
  }
  return result;
}

export function createCompanyAccessForm(company) {
  return {
    plan_code: company.plan_code,
    access_status: company.access_status,
    trial_ends_at: toTrialLocalInput(company.trial_ends_at),
    trial_ends_at_original: company.trial_ends_at || "",
  };
}
