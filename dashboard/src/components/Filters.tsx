"use client";

import type { AppOption, DashboardConfig, DashboardFilters } from "@/lib/types";

interface FiltersProps {
  config: DashboardConfig;
  filters: DashboardFilters;
  apps: AppOption[];
  countries: Array<{ country_code: string; country_name: string }>;
  campaigns: Array<{ campaign_id: string; campaign_name: string }>;
  onChange: (filters: DashboardFilters) => void;
}

export function Filters({ config, filters, apps, countries, campaigns, onChange }: FiltersProps) {
  const has = (filter: string) => config.filters.includes(filter as never);
  const hasLocal = (filter: string) => config.widgets.some((widget) => widget.filters?.includes(filter));

  return (
    <section className="filter-panel" aria-label="Dashboard filters">
      {has("app_id") && <label>Application
        <select value={filters.app_id} onChange={(event) => onChange({ ...filters, app_id: event.target.value })}>
          <option value="">All applications</option>
          {apps.map((app) => <option key={app.app_id} value={app.app_id}>{app.display_name}</option>)}
        </select>
      </label>}
      {has("country_code") && <label>Country
        <select value={filters.country_code} onChange={(event) => onChange({ ...filters, country_code: event.target.value })}>
          <option value="">All countries</option>
          {countries.map((country) => <option key={country.country_code} value={country.country_code}>{country.country_name} ({country.country_code})</option>)}
        </select>
      </label>}
      {has("date_range") && <div className="date-filter">
        <label>From<input type="date" value={filters.date_range.from} onChange={(event) => onChange({ ...filters, date_range: { ...filters.date_range, from: event.target.value } })} /></label>
        <label>To<input type="date" value={filters.date_range.to} onChange={(event) => onChange({ ...filters, date_range: { ...filters.date_range, to: event.target.value } })} /></label>
      </div>}
      {hasLocal("campaign_id") && <label>Campaign
        <select value={filters.campaign_id} onChange={(event) => onChange({ ...filters, campaign_id: event.target.value })}>
          <option value="">All campaigns</option>
          {campaigns.map((campaign) => <option key={campaign.campaign_id} value={campaign.campaign_id}>{campaign.campaign_name}</option>)}
        </select>
      </label>}
      {hasLocal("cohort_day") && <label>Cohort day
        <select value={filters.cohort_day} onChange={(event) => onChange({ ...filters, cohort_day: event.target.value })}>
          <option value="">All cohort days</option>
          <option value="1">D1</option><option value="7">D7</option><option value="30">D30</option>
        </select>
      </label>}
    </section>
  );
}
