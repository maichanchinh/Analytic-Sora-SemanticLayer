"use client";

import { useState } from "react";
import type { AppOption, DashboardConfig, DashboardFilters, DateRange } from "@/lib/types";
import { Icon } from "@/components/Icon";
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
      {has("app_id") && <label className="application-filter"><span className="filter-label"><Icon name="application" />Application</span>
        <select value={filters.app_id} onChange={(event) => onChange({ ...filters, app_id: event.target.value })}>
          <option value="">All applications</option>
          {apps.map((app) => <option key={app.app_id} value={app.app_id}>{app.display_name}</option>)}
        </select>
      </label>}
      {has("country_code") && <details className="country-filter">
        <summary><span className="filter-label"><Icon name="country" />Country</span><strong>{filters.country_code.length ? `${filters.country_code.length} selected` : "All countries"}</strong></summary>
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
        {config.id === "ua_app_overview" && <div className="period-control">
          <label><span className="filter-label"><Icon name="period" />Period</span>
            <select value={periodValue(filters.date_range)} onChange={(event) => {
              if (event.target.value === "custom") return;
              const today = shiftDate(initialDateRange().to, 1);
              const end = event.target.value === "today" ? today : shiftDate(today, -1);
              const days = event.target.value === "today" ? 1 : Number(event.target.value);
              onChange({ ...filters, date_range: { from: shiftDate(end, -(days - 1)), to: end } });
            }}>
              <option value="today">Today</option><option value="1">Yesterday</option>
              <option value="3">3 days</option><option value="7">7 days</option><option value="custom">Custom dates</option>
            </select>
          </label>
          <div className="period-navigation" role="group" aria-label="Navigate period by one day">
            <button type="button" aria-label="Previous day" title="Previous day" onClick={() => shiftPeriod(-1, filters, onChange)}>‹</button>
            <button type="button" aria-label="Next day" title="Next day" disabled={filters.date_range.to >= shiftDate(initialDateRange().to, 1)} onClick={() => shiftPeriod(1, filters, onChange)}>›</button>
          </div>
        </div>}
        <DateRangePicker value={filters.date_range} onChange={(date_range) => onChange({ ...filters, date_range })} />
      </div>}
      {hasLocal("campaign_id") && <label><span className="filter-label"><Icon name="activity" />Campaign</span>
        <select value={filters.campaign_id} onChange={(event) => onChange({ ...filters, campaign_id: event.target.value })}>
          <option value="">All campaigns</option>
          {campaigns.map((campaign) => <option key={campaign.campaign_id} value={campaign.campaign_id}>{campaign.campaign_name}</option>)}
        </select>
      </label>}
      {hasLocal("cohort_day") && <label><span className="filter-label"><Icon name="calendar" />Cohort day</span>
        <select value={filters.cohort_day} onChange={(event) => onChange({ ...filters, cohort_day: event.target.value })}>
          <option value="">All cohort days</option><option value="1">D1</option><option value="7">D7</option><option value="30">D30</option>
        </select>
      </label>}
    </section>
  );
}

function DateRangePicker({ value, onChange }: { value: DateRange; onChange: (range: DateRange) => void }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"range" | "day">("range");
  const [month, setMonth] = useState(() => new Date(`${value.to}T12:00:00`));
  const [start, setStart] = useState<string | null>(null);
  const today = shiftDate(initialDateRange().to, 1);
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const years = Array.from({ length: 11 }, (_, index) => new Date().getFullYear() - 5 + index);
  const label = value.from === value.to ? formatDate(value.from) : `${formatDate(value.from)} – ${formatDate(value.to)}`;

  function pick(day: number) {
    const selected = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    if (selected > today) return;
    if (mode === "day") {
      onChange({ from: selected, to: selected }); setOpen(false); setStart(null); return;
    }
    if (start === null || selected < start) { setStart(selected); return; }
    onChange({ from: start, to: selected }); setOpen(false); setStart(null);
  }

  return <div className="date-picker">
    <button type="button" className="date-picker-trigger" aria-label="Choose date range" aria-expanded={open} onClick={() => {
      if (!open) setMonth(new Date(`${value.to}T12:00:00`));
      setOpen(!open);
    }}>
      <span>{label}</span><Icon name="calendar" />
    </button>
    {open && <div className="date-picker-popover" role="dialog" aria-label="Choose date range">
      <div className="date-picker-mode" role="group" aria-label="Date selection mode">
        <button type="button" aria-pressed={mode === "range"} onClick={() => { setMode("range"); setStart(null); }}>Range</button>
        <button type="button" aria-pressed={mode === "day"} onClick={() => { setMode("day"); setStart(null); }}>Single day</button>
      </div>
      <div className="date-picker-heading">
        <button type="button" aria-label="Previous month" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>‹</button>
        <select aria-label="Select month" value={month.getMonth()} onChange={(event) => setMonth(new Date(month.getFullYear(), Number(event.target.value), 1))}>
          {Array.from({ length: 12 }, (_, index) => <option key={index} value={index}>{new Date(2000, index, 1).toLocaleString("en", { month: "long" })}</option>)}
        </select>
        <select aria-label="Select year" value={month.getFullYear()} onChange={(event) => setMonth(new Date(Number(event.target.value), month.getMonth(), 1))}>
          {years.map((year) => <option key={year}>{year}</option>)}
        </select>
        <button type="button" aria-label="Next month" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>›</button>
      </div>
      <div className="date-picker-grid" role="grid">
        {(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]).map((day) => <span key={day} role="columnheader">{day}</span>)}
        {Array.from({ length: offset }, (_, index) => <span key={`empty-${index}`} />)}
        {Array.from({ length: days }, (_, index) => {
          const day = index + 1;
          const date = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const selected = date === value.from || date === value.to || (date > value.from && date < value.to);
          return <button key={date} type="button" role="gridcell" aria-label={formatDate(date)} aria-pressed={selected} disabled={date > today} onClick={() => pick(day)}>{day}</button>;
        })}
      </div>
      <div className="date-picker-hint">{mode === "range" ? start ? "Choose an end date" : "Choose a start date" : "Choose a date"}</div>
    </div>}
  </div>;
}

function formatDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" });
}

function shiftPeriod(days: number, filters: DashboardFilters, onChange: (filters: DashboardFilters) => void) {
  const from = shiftDate(filters.date_range.from, days);
  const to = shiftDate(filters.date_range.to, days);
  if (to > shiftDate(initialDateRange().to, 1)) return;
  onChange({ ...filters, date_range: { from, to } });
}

function periodValue(range: { from: string; to: string }): string {
  const today = shiftDate(initialDateRange().to, 1);
  if (range.from === today && range.to === today) return "today";
  const days = (new Date(`${range.to}T12:00:00Z`).getTime() - new Date(`${range.from}T12:00:00Z`).getTime()) / 86_400_000 + 1;
  if (range.to === initialDateRange().to && [1, 3, 7].includes(days)) return String(days);
  return "custom";
}
