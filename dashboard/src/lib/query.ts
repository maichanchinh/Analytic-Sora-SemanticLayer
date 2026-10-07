import type { DashboardFilters, DashboardWidget, DateRange, QueryRequest } from "@/lib/types";

export function queryForWidget(
  widget: DashboardWidget,
  filters: DashboardFilters,
  modelDimensions: ReadonlySet<string>,
): QueryRequest {
  const allowedFilters = new Set(widget.filters ?? []);
  const queryFilters: Record<string, string | string[] | number | number[]> = Object.fromEntries(
    Object.entries(widget.query_filters ?? {}).filter(([name]) => modelDimensions.has(name)),
  );

  if (filters.app_id && modelDimensions.has("app_id")) queryFilters.app_id = filters.app_id;
  if (modelDimensions.has("country_code")) {
    if (Array.isArray(filters.country_code) && filters.country_code.length) {
      queryFilters.country_code = filters.country_code;
    } else if (typeof filters.country_code === "string" && filters.country_code) {
      queryFilters.country_code = filters.country_code;
    }
  }
  if (filters.campaign_id && allowedFilters.has("campaign_id") && modelDimensions.has("campaign_id")) {
    queryFilters.campaign_id = filters.campaign_id;
  }
  if (filters.cohort_day && allowedFilters.has("cohort_day") && modelDimensions.has("cohort_day")) {
    queryFilters.cohort_day = filters.cohort_day;
  }

  const dateRange = widget.trailing_days
    ? { from: shiftDate(filters.date_range.from, -(widget.trailing_days - 1)), to: filters.date_range.to }
    : filters.date_range;

  return {
    model: widget.model,
    metrics: widget.metrics,
    dimensions: widget.dimensions,
    filters: queryFilters,
    ...(!widget.ignore_date_range && (modelDimensions.has("business_date") || modelDimensions.has("cohort_date"))
      ? { date_range: dateRange }
      : {}),
  };
}

export function initialDateRange(now = new Date()): { from: string; to: string } {
  const today = businessDate(now);
  const yesterday = shiftDate(today, -1);
  return { from: yesterday, to: yesterday };
}

export function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return localDate(date);
}

export function comparisonDateRange(range: DateRange): DateRange {
  return { from: shiftDate(range.from, -1), to: shiftDate(range.to, -1) };
}

function localDate(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function businessDate(date: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}`;
}
