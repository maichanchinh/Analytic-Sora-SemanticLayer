import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { WidgetRenderer } from "@/components/WidgetRenderer";
import type { DashboardWidget, QueryResult } from "@/lib/types";

const baseWidget: DashboardWidget = {
  id: "kpis", type: "metric", title: "Financial KPIs", model: "finance_daily",
  metrics: ["revenue_usd"], dimensions: [],
};

const result: QueryResult = {
  model: "finance_daily", dimensions: [],
  metrics: [{ name: "revenue_usd", unit: "USD" }],
  rows: [{ revenue_usd: null }],
};

describe("WidgetRenderer", () => {
  afterEach(cleanup);

  it("shows a loading state", () => {
    render(<WidgetRenderer widget={baseWidget} state={{ status: "loading" }} />);
    expect(screen.getByRole("region", { name: "Financial KPIs" })).toHaveAttribute("aria-busy", "true");
  });

  it("shows query errors without hiding widget title", () => {
    render(<WidgetRenderer widget={baseWidget} state={{ status: "error", message: "Unsupported metric" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Unsupported metric");
    expect(screen.getByText("Financial KPIs")).toBeInTheDocument();
  });

  it("renders null as unavailable instead of zero", () => {
    render(<WidgetRenderer widget={baseWidget} state={{ status: "success", result }} />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });

  it("renders empty results and unsupported widget types clearly", () => {
    render(<WidgetRenderer widget={baseWidget} state={{ status: "success", result: { ...result, rows: [] } }} />);
    expect(screen.getByText("No data for the selected filters.")).toBeInTheDocument();
    render(<WidgetRenderer widget={{ ...baseWidget, type: "heatmap" }} state={{ status: "success", result }} />);
    expect(screen.getByText("Unsupported widget type: heatmap")).toBeInTheDocument();
  });
});
