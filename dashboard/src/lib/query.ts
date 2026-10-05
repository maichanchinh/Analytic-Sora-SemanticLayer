import type { DashboardFilters, DashboardWidget, QueryRequest } from "@/lib/types";

export function queryForWidget(
  widget: DashboardWidget,
  filters: DashboardFilters,
  modelDimensions: ReadonlySet<string>,
): QueryRequest {
  const allowedFilters = new Set(widget.filters ?? []);
  const queryFilters: Record<string, string> = {};

  for (const name of ["app_id", "country_code"] as const) {
    if (filters[name] && modelDimensions.has(name)) queryFilters[name] = filters[name];
  }
  if (filters.campaign_id && allowedFilters.has("campaign_id") && modelDimensions.has("campaign_id")) {
    queryFilters.campaign_id = filters.campaign_id;
  }
  if (filters.cohort_day && allowedFilters.has("cohort_day") && modelDimensions.has("cohort_day")) {
    queryFilters.cohort_day = filters.cohort_day;
  }

  return {
    model: widget.model,
    metrics: widget.metrics,
    dimensions: widget.dimensions,
    filters: queryFilters,
    ...(modelDimensions.has("business_date") || modelDimensions.has("cohort_date")
      ? { date_range: filters.date_range }
      : {}),
  };
}

export function initialDateRange(now = new Date()): { from: string; to: string } {
  const end = new Date(now);
  const start = new Date(now);
  start.setDate(start.getDate() - 29);
  return { from: localDate(start), to: localDate(end) };
}

function localDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
