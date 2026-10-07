import type { FieldMetadata } from "@/lib/types";

const LOCALE = "vi-VN";

function numberFormat(options?: Intl.NumberFormatOptions): Intl.NumberFormat {
  return new Intl.NumberFormat(LOCALE, options);
}

function formatCurrency(amount: number, currency: string): string {
  try {
    return numberFormat({ style: "currency", currency }).format(amount);
  } catch {
    return `${numberFormat({ maximumFractionDigits: 2 }).format(amount)} ${currency}`;
  }
}

export function formatValue(value: unknown, field: FieldMetadata): string {
  if (value === null || value === undefined) return "Unavailable";
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return String(value);

  if (field.name.startsWith("roas_")) {
    return `${numberFormat({ maximumFractionDigits: 2 }).format(amount)}x`;
  }
  if (field.unit === "ratio") {
    return numberFormat({ style: "percent", maximumFractionDigits: 2 }).format(amount);
  }
  if (["USD", "VND"].includes(field.unit ?? "")) {
    return formatCurrency(amount, field.unit!);
  }
  return numberFormat({ maximumFractionDigits: 2 }).format(amount);
}

export function formatMetricValue(value: unknown, field: FieldMetadata, row: Record<string, unknown>): string {
  if (value === null || value === undefined) return "Unavailable";
  const amount = typeof value === "number" ? value : Number(value);
  const currency = field.currency_column ? row[field.currency_column] : undefined;
  if (
    Number.isFinite(amount) &&
    (field.unit === "currency" || field.unit === "currency_per_thousand_impressions") &&
    typeof currency === "string" &&
    /^[A-Z]{3}$/.test(currency)
  ) {
    return formatCurrency(amount, currency);
  }
  const formatted = formatValue(value, field);
  if (formatted === "Unavailable" || field.unit !== "currency") return formatted;
  return typeof currency === "string" && currency ? `${formatted} ${currency}` : formatted;
}

export function formatAxisValue(value: unknown, field: FieldMetadata): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return String(value ?? "");
  if (["USD", "VND"].includes(field.unit ?? "")) {
    return numberFormat({
      style: "currency", currency: field.unit,
      notation: "compact",
      maximumFractionDigits: field.unit === "VND" ? 0 : 1,
    }).format(amount);
  }
  return numberFormat({ notation: "compact", maximumFractionDigits: 1 }).format(amount);
}

export function fieldUnit(field: FieldMetadata): string {
  if (field.unit === "currency") return "Native currency";
  if (field.unit === "currency_implicit") return "Reference only · currency unspecified";
  if (field.unit === "currency_per_thousand_impressions") return "Native currency / 1,000 impressions";
  if (field.unit === "currency_micros") return "Micros";
  if (field.unit === "ratio") return "Ratio";
  return field.unit ?? "";
}

export function formatDate(value: unknown): string {
  if (typeof value !== "string") return String(value ?? "Unavailable");
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(LOCALE).format(date);
}
