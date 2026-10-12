export function formatQuoteCommercialDate(value) {
  const match = typeof value === "string" && /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return "—";
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText), month = Number(monthText), day = Number(dayText);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1]) return "—";
  return `${dayText}/${monthText}/${yearText}`;
}

export function parseQuoteTaxPercent(value) {
  const text = String(value ?? "").trim().replace(",", ".");
  const percent = text === "" ? 0 : Number(text);
  if (!Number.isFinite(percent) || percent < 0 || percent > 100 ||
      (text !== "" && !/^\d+(?:\.\d*)?$/.test(text))) {
    return { error: "Captura un IVA de 0 a 100%.", percent: null, factor: null };
  }
  // The stored factor has four decimals, so percent accepts two meaningful decimals.
  if ((text.split(".")[1] || "").replace(/0+$/, "").length > 2) {
    return { error: "Usa hasta dos decimales en IVA (%).", percent: null, factor: null };
  }
  return { error: "", percent, factor: Number((percent / 100).toFixed(4)) };
}

export function quoteTaxFactorToPercent(value) {
  return String(Number((Number(value ?? 0) * 100).toFixed(2)));
}
