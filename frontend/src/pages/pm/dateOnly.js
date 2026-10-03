const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function parseDateOnly(value) {
  if (typeof value !== "string") return null;
  const match = DATE_ONLY_PATTERN.exec(value);
  if (!match) return null;

  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return { value, date };
}

export function toPmDateInputValue(value) {
  return parseDateOnly(value)?.value ?? "";
}

export function pmCalendarDayNumber(value) {
  const parsed = parseDateOnly(value);
  if (!parsed) return null;
  const [, year, month, day] = DATE_ONLY_PATTERN.exec(parsed.value);
  return Date.UTC(Number(year), Number(month) - 1, Number(day)) / 86400000;
}

export function formatPmCalendarDate(value) {
  if (!value) return "—";
  const parsed = parseDateOnly(value);
  if (!parsed) return "—";
  return new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeZone: "UTC" }).format(parsed.date);
}
