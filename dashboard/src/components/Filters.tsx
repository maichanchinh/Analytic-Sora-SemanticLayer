"use client";

import type { AppOption, DashboardConfig, DashboardFilters } from "@/lib/types";
import { initialDateRange, shiftDate } from "@/lib/query";

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
      {has("app_id") && <label className="application-filter">Application
        <select value={filters.app_id} onChange={(event) => onChange({ ...filters, app_id: event.target.value })}>
          <option value="">All applications</option>
          {apps.map((app) => <option key={app.app_id} value={app.app_id}>{app.display_name}</option>)}
        </select>
      </label>}
      {has("country_code") && <details className="country-filter">
        <summary><span>Country</span><strong>{filters.country_code.length ? `${filters.country_code.length} selected` : "All countries"}</strong></summary>
        <div className="country-options" role="group" aria-label="Select countries">
          {countries.map((country) => <label key={country.country_code}>
            <input type="checkbox" checked={filters.country_code.includes(country.country_code)} onChange={(event) => {
              const selected = new Set(filters.country_code);
              if (event.target.checked) selected.add(country.country_code);
              else selected.delete(country.country_code);
              onChange({ ...filters, country_code: [...selected] });
            }} />
            {country.country_name} ({country.country_code})
          </label>)}
          {filters.country_code.length > 0 && <button type="button" onClick={() => onChange({ ...filters, country_code: [] })}>Clear selection</button>}
        </div>
      </details>}
      {has("date_range") && <div className="date-filter">
        {config.id === "ua_app_overview" ? <>
          <div className="period-control">
            <label>Period
              <select value={periodValue(filters.date_range)} onChange={(event) => {
                const today = shiftDate(initialDateRange().to, 1);
                if (event.target.value === "custom") return;
                const end = event.target.value === "today" ? today : shiftDate(today, -1);
                const days = event.target.value === "today" ? 1 : Number(event.target.value);
                onChange({ ...filters, date_range: { from: shiftDate(end, -(days - 1)), to: end } });
              }}>
                <option value="today">Today</option>
                <option value="1">Yesterday</option>
                <option value="3">3 days</option>
                <option value="7">7 days</option>
                <option value="custom">Custom dates</option>
              </select>
            </label>
            <div className="period-navigation" role="group" aria-label="Navigate period by one day">
              <button
                type="button"
                aria-label="Previous day"
                title="Previous day"
                onClick={() => shiftPeriod(-1, filters, onChange)}
              >‹</button>
              <button
                type="button"
                aria-label="Next day"
                title="Next day"
                disabled={filters.date_range.to >= shiftDate(initialDateRange().to, 1)}
                onClick={() => shiftPeriod(1, filters, onChange)}
              >›</button>
            </div>
          </div>
          <label>From<input type="date" value={filters.date_range.from} max={filters.date_range.to} onChange={(event) => onChange({ ...filters, date_range: { ...filters.date_range, from: event.target.value } })} /></label>
          <label>To<input type="date" value={filters.date_range.to} min={filters.date_range.from} max={shiftDate(initialDateRange().to, 1)} onChange={(event) => onChange({ ...filters, date_range: { ...filters.date_range, to: event.target.value } })} /></label>
        </> : <>
        <label>From<input type="date" value={filters.date_range.from} onChange={(event) => onChange({ ...filters, date_range: { ...filters.date_range, from: event.target.value } })} /></label>
        <label>To<input type="date" value={filters.date_range.to} onChange={(event) => onChange({ ...filters, date_range: { ...filters.date_range, to: event.target.value } })} /></label>
        </>}
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

function shiftPeriod(
  days: number,
  filters: DashboardFilters,
  onChange: (filters: DashboardFilters) => void,
) {
  const from = shiftDate(filters.date_range.from, days);
  const to = shiftDate(filters.date_range.to, days);
  const today = shiftDate(initialDateRange().to, 1);
  if (to > today) return;
  onChange({ ...filters, date_range: { from, to } });
}

function periodValue(range: { from: string; to: string }): string {
  const today = shiftDate(initialDateRange().to, 1);
  if (range.from === today && range.to === today) return "today";
  const days = (new Date(`${range.to}T12:00:00Z`).getTime() - new Date(`${range.from}T12:00:00Z`).getTime()) / 86_400_000 + 1;
  if (range.to === initialDateRange().to && [1, 3, 7].includes(days)) return String(days);
  return "custom";
}
