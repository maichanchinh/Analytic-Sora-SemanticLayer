import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DashboardConfig, QueryBatchItem, QueryRequest } from "@/lib/types";

const config: DashboardConfig = {
  id: "overview",
  title: "Filter test dashboard",
  filters: ["app_id", "country_code", "date_range"],
  widgets: [{
    id: "engagement",
    type: "table",
    title: "Engagement",
    model: "ga4_daily_overview",
    metrics: ["sessions"],
    dimensions: ["business_date"],
  }, {
    id: "apps",
    type: "table",
    title: "Apps",
    model: "dim_app",
    metrics: [],
    dimensions: ["app_id"],
  }],
};

describe("DashboardClient filters", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("sends the selected app, country and inclusive date range to supported widgets", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    const queries: QueryRequest[] = [];
    const batches: QueryBatchItem[][] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/dashboards")) {
        return jsonResponse({ dashboards: [{ id: config.id, title: config.title }] });
      }
      if (url.endsWith("/api/v1/dashboards/overview")) return jsonResponse(config);
      if (url.endsWith("/api/v1/apps")) {
        return jsonResponse({ apps: [{ app_id: "app-one", display_name: "App One" }] });
      }
      if (url.endsWith("/api/v1/dimensions")) {
        return jsonResponse({ models: [
          { model: "dim_country", dimensions: [{ name: "country_code" }, { name: "country_name" }] },
          { model: "ga4_daily_overview", dimensions: [
            { name: "business_date" }, { name: "app_id" }, { name: "country_code" },
          ] },
          { model: "dim_app", dimensions: [{ name: "app_id" }] },
        ] });
      }
      if (url.endsWith("/api/v1/query")) {
        const body = JSON.parse(String(init?.body)) as QueryRequest | { queries: QueryBatchItem[] };
        if ("queries" in body) {
          batches.push(body.queries);
          return jsonResponse({ results: body.queries.map((query) => query.id === "apps"
            ? { id: query.id, error: "Apps widget failed" }
            : { id: query.id, result: {
              model: query.model,
              dimensions: [],
              metrics: [],
              rows: [{ business_date: query.date_range?.from ?? "2026-10-01", sessions: 2 }],
            } }) });
        }
        queries.push(body);
        return jsonResponse({
          model: body.model,
          dimensions: [],
          metrics: [],
          rows: [{ country_code: "US", country_name: "United States" }],
        });
      }
      return jsonResponse({ detail: "Not found" }, 404);
    }));

    const { DashboardClient } = await import("@/components/DashboardClient");
    render(<DashboardClient />);
    await screen.findByRole("heading", { name: /Engagement/ });
    await screen.findByText("Apps widget failed");
    await waitFor(() => expect(batches.some((batch) => batch.length === 2)).toBe(true));

    fireEvent.change(screen.getByRole("combobox", { name: "Application" }), { target: { value: "app-one" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /United States \(US\)/ }));
    fireEvent.click(screen.getByRole("button", { name: "Choose date range" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Select month" }), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("gridcell", { name: "Aug 1, 2026" }));
    fireEvent.click(screen.getByRole("gridcell", { name: "Aug 3, 2026" }));

    await waitFor(() => {
      const request = [...batches].reverse().flat().find((query) => query.model === "ga4_daily_overview");
      expect(request).toMatchObject({
        filters: { app_id: "app-one", country_code: ["US"] },
        date_range: { from: "2026-08-01", to: "2026-08-03" },
      });
    });
    expect(queries.some((query) => query.model !== "dim_country")).toBe(false);
    expect(batches.at(-1)).toHaveLength(2);
  });
});

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
