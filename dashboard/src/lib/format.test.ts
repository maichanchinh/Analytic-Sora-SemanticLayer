import { describe, expect, it } from "vitest";
import { fieldUnit, formatMetricValue, formatValue } from "@/lib/format";

describe("formatValue", () => {
  it("preserves null as an unavailable value", () => {
    expect(formatValue(null, { name: "revenue_usd", unit: "USD" })).toBe("Unavailable");
  });

  it("formats currencies and ratios from semantic metadata", () => {
    expect(formatValue(12.5, { name: "revenue", unit: "USD" })).toContain("12,50");
    expect(formatValue(12.5, { name: "revenue", unit: "USD" })).toContain("US$");
    expect(formatValue(140, { name: "cost", unit: "VND" })).toContain("₫");
    expect(formatValue(0.25, { name: "retention", unit: "ratio" })).toBe("25%");
  });

  it("does not mistake native currency for a normalized currency", () => {
    expect(fieldUnit({ name: "estimated_earnings", unit: "currency" })).toBe("Native currency");
  });

  it("formats native USD and VND using vi-VN currency conventions", () => {
    const usd = formatMetricValue(14.09, { name: "campaign_spend", unit: "currency", currency_column: "currency_code" }, { currency_code: "USD" });
    const vnd = formatMetricValue(140, { name: "campaign_spend", unit: "currency", currency_column: "currency_code" }, { currency_code: "VND" });
    expect(usd).toContain("14,09");
    expect(usd).toContain("US$");
    expect(vnd).toContain("140");
    expect(vnd).toContain("₫");
  });

  it("keeps null native currency values unavailable", () => {
    expect(formatMetricValue(null, { name: "campaign_spend", unit: "currency", currency_column: "currency_code" }, { currency_code: "USD" })).toBe("Unavailable");
  });
});
