import { describe, expect, it } from "vitest";
import { fieldUnit, formatMetricValue, formatValue } from "@/lib/format";

describe("formatValue", () => {
  it("preserves null as an unavailable value", () => {
    expect(formatValue(null, { name: "revenue_usd", unit: "USD" })).toBe("Unavailable");
  });

  it("formats currencies and ratios from semantic metadata", () => {
    expect(formatValue(12.5, { name: "revenue", unit: "USD" })).toContain("12.50");
    expect(formatValue(0.25, { name: "retention", unit: "ratio" })).toBe("25%");
  });

  it("does not mistake native currency for a normalized currency", () => {
    expect(fieldUnit({ name: "estimated_earnings", unit: "currency" })).toBe("Native currency");
  });

  it("keeps native currency code beside its amount", () => {
    expect(formatMetricValue(1250, { name: "campaign_spend", unit: "currency", currency_column: "currency_code" }, { currency_code: "USD" })).toContain("USD");
  });
});
