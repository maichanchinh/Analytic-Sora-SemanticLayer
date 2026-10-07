"use client";

import { useEffect, useState } from "react";
import { Filters } from "@/components/Filters";
import { DashboardRenderer } from "@/components/DashboardRenderer";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { type WidgetState } from "@/components/WidgetRenderer";
import { getApps, getCampaigns, getCountries, getDashboard, getDashboardList, getDimensionCatalog, runQueryBatch } from "@/lib/api";
import { initialDateRange, queryForWidget } from "@/lib/query";
import type { AppOption, DashboardConfig, DashboardFilters } from "@/lib/types";

const emptyFilters = (): DashboardFilters => ({
  app_id: "", country_code: [], date_range: initialDateRange(), campaign_id: "", cohort_day: "",
});

export function DashboardClient() {
  const [dashboards, setDashboards] = useState<Array<{ id: string; title: string }>>([]);
  const [config, setConfig] = useState<DashboardConfig | null>(null);
  const [apps, setApps] = useState<AppOption[]>([]);
  const [countries, setCountries] = useState<Array<{ country_code: string; country_name: string }>>([]);
  const [campaigns, setCampaigns] = useState<Array<{ campaign_id: string; campaign_name: string }>>([]);
  const [dimensions, setDimensions] = useState<Record<string, Set<string>>>({});
  const [filters, setFilters] = useState(emptyFilters);
  const [widgetStates, setWidgetStates] = useState<Record<string, WidgetState>>({});
  const [pageError, setPageError] = useState("");
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([getDashboardList(), getDimensionCatalog()])
      .then(async ([items, catalog]) => {
        if (!active) return;
        setDashboards(items);
        setDimensions(catalog);
        const [appResult, countryResult] = await Promise.allSettled([getApps(), getCountries()]);
        if (!active) return;
        if (appResult.status === "fulfilled") setApps(appResult.value);
        if (countryResult.status === "fulfilled") setCountries(countryResult.value);
        const selectedId = new URLSearchParams(window.location.search).get("id") ?? items[0]?.id;
        if (!selectedId) throw new Error("API chưa có dashboard config.");
        setConfig(await getDashboard(selectedId));
        setPageError("");
      })
      .catch((error: unknown) => active && setPageError(error instanceof Error ? error.message : "Không tải được dashboard."))
      .finally(() => active && setLoadingDashboard(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!config?.widgets.some((widget) => widget.filters?.includes("campaign_id"))) return;
    let active = true;
    setCampaigns([]);
    getCampaigns(filters)
      .then((options) => active && setCampaigns(options))
      .catch(() => active && setCampaigns([]));
    return () => { active = false; };
  }, [config, filters.app_id, filters.country_code, filters.date_range.from, filters.date_range.to]);

  useEffect(() => {
    if (!config) return;
    let active = true;
    const supportedTypes = new Set(["metric", "area_chart", "bar_chart", "table"]);
    setWidgetStates(Object.fromEntries(config.widgets.map((widget) => [widget.id, { status: "loading" }])));
    const initialStates: Record<string, WidgetState> = {};
    const queries = config.widgets.flatMap((widget) => {
      if (!supportedTypes.has(widget.type)) {
        initialStates[widget.id] = { status: "error", message: `Unsupported widget type: ${widget.type}` };
        return [];
      }
      const modelDimensions = dimensions[widget.model] ?? new Set();
      const request = queryForWidget(widget, filters, modelDimensions);
      return [{
        id: widget.id,
        ...request,
        ...(widget.compare_previous ? { compare_previous_period: true } : {}),
      }];
    });

    if (!queries.length) {
      setWidgetStates(initialStates);
      return () => { active = false; };
    }

    runQueryBatch(queries)
      .then(({ results }) => {
        const resultsById = new Map(results.map((result) => [result.id, result]));
        const entries = config.widgets.map((widget) => {
          const result = resultsById.get(widget.id);
          if (!result) {
            return [widget.id, initialStates[widget.id] ?? { status: "error", message: "Widget query returned no result." }] as const;
          }
          if ("error" in result) {
            return [widget.id, { status: "error", message: result.error } satisfies WidgetState] as const;
          }
          return [widget.id, { status: "success", result: result.result } satisfies WidgetState] as const;
        });
        if (active) setWidgetStates(Object.fromEntries(entries));
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "Widget query failed.";
        const entries = config.widgets.map((widget) => [
          widget.id,
          initialStates[widget.id] ?? { status: "error", message },
        ] as const);
        if (active) setWidgetStates(Object.fromEntries(entries));
      });
    return () => { active = false; };
  }, [config, dimensions, filters]);

  const changeDashboard = async (id: string) => {
    setLoadingDashboard(true);
    setPageError("");
    try {
      setConfig(await getDashboard(id));
      window.history.replaceState(null, "", `?id=${encodeURIComponent(id)}`);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Không tải được dashboard config.");
    } finally {
      setLoadingDashboard(false);
    }
  };

  return <main className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
    <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
      <button className="sidebar-toggle" type="button" aria-label={sidebarCollapsed ? "Expand menu" : "Collapse menu"} aria-expanded={!sidebarCollapsed} onClick={() => setSidebarCollapsed((value) => !value)}>{sidebarCollapsed ? "›" : "‹"}</button>
      <a className="brand" href="/" aria-label="Sora dashboard home"><span className="brand-mark">S</span><span className="brand-copy">Sora<span className="brand-muted"> / Analytics</span></span></a>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Dashboards">
        {dashboards.map((item) => <button key={item.id} className={`nav-item ${config?.id === item.id ? "active" : ""}`} onClick={() => void changeDashboard(item.id)}><Icon name="dashboard" /><span className="nav-item-label">{item.title}</span></button>)}
      </nav>
      <div className="sidebar-footer"><span className="status-dot" /> Read-only semantic data</div>
    </aside>
    <section className="main-content">
      <header className="topbar"><div><span className="eyebrow">ANALYTICS WORKSPACE</span><div className="breadcrumb">Dashboards <span>/</span> {config?.title ?? "Overview"}</div></div><div className="topbar-actions"><ThemeToggle /><div className="avatar" aria-label="Analytics">SA</div></div></header>
      <div className="page-content">
        {loadingDashboard && <div className="page-state">Loading dashboard configuration…</div>}
        {pageError && <div className="page-error" role="alert"><strong>Dashboard unavailable</strong><span>{pageError}</span></div>}
        {config && !loadingDashboard && <>
          <div className="page-title-row"><div><div className="eyebrow">PERFORMANCE OVERVIEW</div><h1>{config.title}</h1><p>Monitor revenue, cost and ROAS across your apps.</p></div><div className="updated-badge"><span className="status-dot" /> API data</div></div>
          <Filters config={config} filters={filters} apps={apps} countries={countries} campaigns={campaigns} onChange={setFilters} />
          <DashboardRenderer config={config} widgetStates={widgetStates} apps={apps} dateRange={filters.date_range} />
        </>}
        <footer className="page-footer">Data served by Sora Semantic Layer · Read-only Silver analytics</footer>
      </div>
    </section>
  </main>;
}
