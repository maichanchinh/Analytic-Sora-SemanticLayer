import type { FieldMetadata } from "@/lib/types";

export function formatValue(value: unknown, field: FieldMetadata): string {
  if (value === null || value === undefined) return "Unavailable";
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return String(value);

  if (field.name.startsWith("roas_")) {
    return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(amount)}x`;
  }
  if (field.unit === "ratio") {
    return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 2 }).format(amount);
  }
  if (["USD", "VND"].includes(field.unit ?? "")) {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: field.unit,
      maximumFractionDigits: field.unit === "VND" ? 0 : 2,
    }).format(amount);
  }
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(amount);
}

export function formatMetricValue(value: unknown, field: FieldMetadata, row: Record<string, unknown>): string {
  const formatted = formatValue(value, field);
  if (formatted === "Unavailable" || field.unit !== "currency") return formatted;
  const currency = field.currency_column ? row[field.currency_column] : undefined;
  return typeof currency === "string" && currency ? `${formatted} ${currency}` : formatted;
}

export function formatAxisValue(value: unknown, field: FieldMetadata): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return String(value ?? "");
  if (["USD", "VND"].includes(field.unit ?? "")) {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: field.unit,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(amount);
  }
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(amount);
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
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined).format(date);
}
