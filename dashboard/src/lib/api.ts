import type {
  AppOption,
  DashboardConfig,
  QueryBatchItem,
  QueryBatchResponse,
  QueryRequest,
  QueryResult,
} from "@/lib/types";

const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
export const apiBaseUrl = configuredBaseUrl?.replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  if (!apiBaseUrl) {
    throw new Error("Dashboard API chưa được cấu hình. Hãy đặt NEXT_PUBLIC_API_BASE_URL.");
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
  } catch {
    throw new Error("Không kết nối được FastAPI. Hãy kiểm tra API và cấu hình URL.");
  }
  if (!response.ok) throw await responseError(response);
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  if (!apiBaseUrl) {
    throw new Error("Dashboard API chưa được cấu hình. Hãy đặt NEXT_PUBLIC_API_BASE_URL.");
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new Error("Không kết nối được FastAPI. Hãy kiểm tra API và cấu hình URL.");
  }
  if (!response.ok) throw await responseError(response);
  return response.json() as Promise<T>;
}

async function responseError(response: Response): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: string };
    return new Error(body.detail || `FastAPI trả về lỗi ${response.status}.`);
  } catch {
    return new Error(`FastAPI trả về lỗi ${response.status}.`);
  }
}

export async function getApps(): Promise<AppOption[]> {
  const response = await getJson<{ apps: AppOption[] }>("/api/v1/apps");
  return response.apps;
}

export async function getDashboardList(): Promise<Array<{ id: string; title: string }>> {
  const response = await getJson<{ dashboards: Array<{ id: string; title: string }> }>(
    "/api/v1/dashboards",
  );
  return response.dashboards;
}

export function getDashboard(id: string): Promise<DashboardConfig> {
  return getJson<DashboardConfig>(`/api/v1/dashboards/${encodeURIComponent(id)}`);
}

export function runQuery(request: QueryRequest): Promise<QueryResult> {
  return postJson<QueryResult>("/api/v1/query", request);
}

export function runQueryBatch(queries: QueryBatchItem[]): Promise<QueryBatchResponse> {
  return postJson<QueryBatchResponse>("/api/v1/query", { queries });
}

export async function getCountries(): Promise<Array<{ country_code: string; country_name: string }>> {
  const result = await runQuery({
    model: "dim_country",
    metrics: [],
    dimensions: ["country_code", "country_name"],
    filters: {},
  });
  return (result.rows as Array<{ country_code: string; country_name: string }>).sort((left, right) =>
    left.country_name.localeCompare(right.country_name),
  );
}

export async function getDimensionCatalog(): Promise<Record<string, Set<string>>> {
  const response = await getJson<{
    models: Array<{ model: string; dimensions: Array<{ name: string }> }>;
  }>("/api/v1/dimensions");
  return Object.fromEntries(
    response.models.map((model) => [model.model, new Set(model.dimensions.map((field) => field.name))]),
  );
}

export async function getCampaigns(
  filters: DashboardFiltersForOptions,
): Promise<Array<{ campaign_id: string; campaign_name: string }>> {
  const result = await runQuery({
    model: "google_ads_campaign_geo_daily",
    metrics: [],
    dimensions: ["campaign_id", "campaign_name"],
    filters: {
      ...(filters.app_id ? { app_id: filters.app_id } : {}),
      ...(filters.country_code.length ? { country_code: filters.country_code } : {}),
    },
    date_range: filters.date_range,
  });
  const unique = new Map<string, string>();
  for (const row of result.rows) {
    if (typeof row.campaign_id === "string") {
      unique.set(row.campaign_id, String(row.campaign_name ?? row.campaign_id));
    }
  }
  return [...unique].map(([campaign_id, campaign_name]) => ({ campaign_id, campaign_name }));
}

import type { DateRange } from "@/lib/types";

interface DashboardFiltersForOptions {
  app_id: string;
  country_code: string | string[];
  date_range: DateRange;
}
