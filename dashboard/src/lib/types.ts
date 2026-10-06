export type FilterKey = "app_id" | "country_code" | "date_range" | "campaign_id" | "cohort_day";
export type WidgetType = "metric" | "area_chart" | "bar_chart" | "table";

export interface DashboardWidget {
  id: string;
  type: WidgetType | string;
  title: string;
  model: string;
  metrics: string[];
  dimensions: string[];
  filters?: string[];
  query_filters?: Record<string, string | string[] | number | number[]>;
  ignore_date_range?: boolean;
  section?: string;
  compare_previous?: boolean;
  trailing_days?: number;
  span?: number;
  unavailable_metrics?: string[];
}

export interface DashboardConfig {
  id: string;
  title: string;
  filters: FilterKey[];
  layout?: { columns?: number };
  widgets: DashboardWidget[];
}

export interface AppOption {
  app_id: string;
  display_name: string;
}

export interface QueryResult {
  model: string;
  dimensions: FieldMetadata[];
  metrics: FieldMetadata[];
  rows: Array<Record<string, unknown>>;
  comparisons?: Array<{
    dimensions: Record<string, unknown>;
    metrics: Record<string, { previous: number | null; delta: number | null; percent_change: number | null }>;
  }>;
}

export interface FieldMetadata {
  name: string;
  unit?: string;
  currency_column?: string | null;
  description?: string;
  null_behavior?: string | null;
}

export interface DateRange {
  from: string;
  to: string;
}

export interface DashboardFilters {
  app_id: string;
  country_code: string | string[];
  date_range: DateRange;
  campaign_id: string;
  cohort_day: string;
}

export interface QueryRequest {
  model: string;
  metrics: string[];
  dimensions: string[];
  filters: Record<string, string | string[] | number | number[]>;
  date_range?: DateRange;
  compare_previous_period?: boolean;
}
