/** Formats integer minor units exactly; the UI never derives or rounds money itself. */
export function formatMinor(amountMinor: number, currency: string, locale = "en-US"): string {
  if (!Number.isInteger(amountMinor)) return "—";
  let digits: number;
  try {
    digits = new Intl.NumberFormat(locale, { style: "currency", currency }).resolvedOptions().maximumFractionDigits ?? 2;
  } catch {
    // Unknown currency code: show the exact stored minor units rather than guess a scale.
    return `${amountMinor} ${currency} (minor units)`;
  }
  const sign = amountMinor < 0 ? "-" : "";
  const absolute = Math.abs(amountMinor);
  const scale = 10 ** digits;
  const whole = Math.trunc(absolute / scale);
  const fraction = absolute % scale;
  const formattedWhole = new Intl.NumberFormat(locale, { style: "currency", currency, maximumFractionDigits: 0, minimumFractionDigits: 0 }).format(whole);
  if (digits === 0) return `${sign}${formattedWhole}`;
  return `${sign}${formattedWhole}.${String(fraction).padStart(digits, "0")}`;
}

export function formatDateTime(value: string | null | undefined, locale = "en-US"): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(date) + " UTC";
}

export function humanize(value: string): string {
  const text = value.replaceAll("_", " ").replaceAll("-", " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function shortId(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : "—";
}
