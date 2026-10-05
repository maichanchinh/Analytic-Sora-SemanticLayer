import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DashboardConfig, QueryRequest } from "@/lib/types";

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
        ] });
      }
      if (url.endsWith("/api/v1/query")) {
        const body = JSON.parse(String(init?.body)) as QueryRequest;
        queries.push(body);
        const rows = body.model === "dim_country"
          ? [{ country_code: "US", country_name: "United States" }]
          : [{ business_date: body.date_range?.from ?? "2026-10-01", sessions: 2 }];
        return jsonResponse({ model: body.model, dimensions: [], metrics: [], rows });
      }
      return jsonResponse({ detail: "Not found" }, 404);
    }));

    const { DashboardClient } = await import("@/components/DashboardClient");
    render(<DashboardClient />);
    await screen.findByRole("region", { name: "Engagement" });
    await waitFor(() => expect(queries.some((query) => query.model === "ga4_daily_overview")).toBe(true));

    fireEvent.change(screen.getByRole("combobox", { name: "Application" }), { target: { value: "app-one" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Country" }), { target: { value: "US" } });
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-10-03" } });

    await waitFor(() => {
      const request = [...queries].reverse().find((query) => query.model === "ga4_daily_overview");
      expect(request).toMatchObject({
        filters: { app_id: "app-one", country_code: "US" },
        date_range: { from: "2026-10-01", to: "2026-10-03" },
      });
    });
  });
});

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
