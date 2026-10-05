import { describe, expect, it } from "vitest";
import { initialDateRange, queryForWidget } from "@/lib/query";
import type { DashboardFilters, DashboardWidget } from "@/lib/types";

const filters: DashboardFilters = {
  app_id: "app.one",
  country_code: "US",
  date_range: { from: "2026-10-01", to: "2026-10-30" },
  campaign_id: "campaign-4",
  cohort_day: "7",
};

function widget(overrides: Partial<DashboardWidget> = {}): DashboardWidget {
  return {
    id: "sample", type: "table", title: "Sample", model: "sample_model",
    metrics: ["users"], dimensions: ["country_code"], ...overrides,
  };
}

describe("queryForWidget", () => {
  it("passes only dimensions supported by a model and applies inclusive date range", () => {
    const request = queryForWidget(widget(), filters, new Set(["app_id", "country_code", "business_date"]));
    expect(request.filters).toEqual({ app_id: "app.one", country_code: "US" });
    expect(request.date_range).toEqual({ from: "2026-10-01", to: "2026-10-30" });
  });

  it("applies campaign and cohort filters only when configured for the widget", () => {
    const request = queryForWidget(
      widget({ filters: ["campaign_id", "cohort_day"] }),
      filters,
      new Set(["campaign_id", "cohort_day", "cohort_date"]),
    );
    expect(request.filters).toEqual({ campaign_id: "campaign-4", cohort_day: "7" });
    expect(request.date_range).toEqual(filters.date_range);
  });

  it("does not attach a date range to a model without a registered time dimension", () => {
    const request = queryForWidget(widget(), filters, new Set(["country_code"]));
    expect(request.date_range).toBeUndefined();
  });
});

describe("initialDateRange", () => {
  it("defaults to a 30-day inclusive range", () => {
    expect(initialDateRange(new Date(2026, 9, 30))).toEqual({ from: "2026-10-01", to: "2026-10-30" });
  });
});
