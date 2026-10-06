"use client";

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ReactNode } from "react";
import type { AppOption, DashboardWidget, QueryResult } from "@/lib/types";
import { fieldUnit, formatAxisValue, formatDate, formatMetricValue } from "@/lib/format";

export type WidgetState = { status: "loading" } | { status: "error"; message: string } | { status: "success"; result: QueryResult; comparison?: QueryResult };

interface Props { widget: DashboardWidget; state: WidgetState; apps?: AppOption[] }

export function WidgetRenderer({ widget, state, apps = [] }: Props) {
  if (state.status === "loading") return <section className="widget" aria-labelledby={`${widget.id}-title`} aria-busy="true"><WidgetHeader widget={widget} /><div className="skeleton" /></section>;
  if (state.status === "error") return <section className="widget" aria-labelledby={`${widget.id}-title`}><WidgetHeader widget={widget} /><p className="state-error" role="alert">{state.message}</p></section>;

  const { result } = state;
  return <section className="widget" aria-labelledby={`${widget.id}-title`} data-testid={`widget-${widget.id}`}>
    <WidgetHeader widget={widget} />
    {result.rows.length === 0 ? <p className="state-empty">No data for the selected filters.</p> : (
      widgetRegistry[widget.type]?.(widget, result, apps) ?? <p className="state-error">Unsupported widget type: {widget.type}</p>
    )}
  </section>;
}

function WidgetHeader({ widget }: { widget: DashboardWidget }) {
  return <div className="widget-heading"><h2 id={`${widget.id}-title`}>{widget.title}</h2><span>{widget.model.replaceAll("_", " ")}</span></div>;
}

type Renderer = (widget: DashboardWidget, result: QueryResult, apps: AppOption[]) => ReactNode;

const widgetRegistry: Record<string, Renderer> = {
  metric: metricWidget,
  area_chart: areaChartWidget,
  bar_chart: barChartWidget,
  table: tableWidget,
};

function metricWidget(_widget: DashboardWidget, result: QueryResult) {
  const row = result.rows[0] ?? {};
  const comparison = result.comparisons?.[0]?.metrics ?? {};
  return <div className="metric-grid">{result.metrics.map((metric) => (
    <article className="metric-item" key={metric.name}>
      <span>{metric.name.replaceAll("_", " ")}</span>
      <strong>{formatMetricValue(row[metric.name], metric, row)}</strong>
      {metric.name in comparison && <ChangeIndicator comparison={comparison[metric.name]} metric={metric.name} field={metric} row={row} />}
      <small title={metric.null_behavior ?? metric.description ?? undefined}>{fieldUnit(metric)}{row[metric.name] == null && metric.null_behavior ? " · why unavailable" : ""}</small>
    </article>
  ))}</div>;
}

function areaChartWidget(_widget: DashboardWidget, result: QueryResult) {
  const dateField = result.dimensions[0]?.name;
  if (!dateField || result.metrics.length === 0) return <p className="state-empty">Chart fields are unavailable.</p>;
  return <div className="chart" role="img" aria-label="Area chart">
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={[...result.rows].sort((left, right) => String(left[dateField]).localeCompare(String(right[dateField])))} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e7ebf2" />
        <XAxis dataKey={dateField} tickFormatter={(value) => formatDate(value)} minTickGap={30} />
        <YAxis yAxisId="primary" width={72} tickFormatter={(value) => formatAxisValue(value, result.metrics[0])} />
        {result.metrics.some((metric) => metric.name.startsWith("cost_")) && <YAxis yAxisId="secondary" orientation="right" width={72} tickFormatter={(value) => formatAxisValue(value, result.metrics.find((metric) => metric.name.startsWith("cost_"))!)} />}
        <Legend />
        <Tooltip labelFormatter={(value) => formatDate(value)} formatter={(value, name, item) => {
          const metric = result.metrics.find((field) => field.name === String(name) || field.name.replaceAll("_", " ") === String(name));
          return [metric ? formatMetricValue(value, metric, (item?.payload ?? {}) as Record<string, unknown>) : String(value ?? "Unavailable"), String(name)];
        }} />
        {result.metrics.map((metric, index) => {
          const color = ["#3478f6", "#f59e0b", "#10a778"][index % 3];
          const yAxisId = metric.name.startsWith("cost_") ? "secondary" : "primary";
          return <Area key={metric.name} yAxisId={yAxisId} type="monotone" dataKey={metric.name} name={metric.name.replaceAll("_", " ")} stroke={color} fill={color} fillOpacity={0.14} connectNulls={false} />;
        })}
      </AreaChart>
    </ResponsiveContainer>
  </div>;
}

function barChartWidget(_widget: DashboardWidget, result: QueryResult) {
  const category = result.dimensions.at(-1)?.name;
  const metric = result.metrics[0];
  if (!category || !metric) return <p className="state-empty">Chart fields are unavailable.</p>;
  return <div className="chart" role="img" aria-label="Bar chart">
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={result.rows} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e7ebf2" />
        <XAxis dataKey={category} /><YAxis /><Tooltip formatter={(value, name, item) => {
          const metricField = result.metrics.find((field) => field.name === String(name) || field.name.replaceAll("_", " ") === String(name));
          return [metricField ? formatMetricValue(value, metricField, (item?.payload ?? {}) as Record<string, unknown>) : String(value ?? "Unavailable"), String(name)];
        }} />
        <Bar dataKey={metric.name} name={metric.name.replaceAll("_", " ")} fill="#3478f6" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  </div>;
}

function tableWidget(_widget: DashboardWidget, result: QueryResult, apps: AppOption[]) {
  const fields = [...result.dimensions, ...result.metrics];
  const comparisons = new Map((result.comparisons ?? []).map((item) => [JSON.stringify(item.dimensions), item.metrics]));
  const rows = [...result.rows].sort((left, right) => Number(right.estimated_earnings ?? 0) - Number(left.estimated_earnings ?? 0));
  return <div className="table-scroll"><table>
    <thead><tr>{fields.map((field) => <th key={field.name}>{field.name === "app_id" ? "App" : field.name.replaceAll("_", " ")}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => {
      const comparison = comparisons.get(JSON.stringify(Object.fromEntries(result.dimensions.map((field) => [field.name, row[field.name]]))));
      return <tr key={index}>{fields.map((field) => <td key={field.name}>{result.metrics.some((item) => item.name === field.name) ? <>{formatMetricValue(row[field.name], field, row)}{comparison?.[field.name] && <ChangeIndicator comparison={comparison[field.name]} metric={field.name} field={field} row={row} />}</> : field.name === "app_id" ? (apps.find((app) => app.app_id === row.app_id)?.display_name ?? String(row.app_id ?? "Unavailable")) : String(row[field.name] ?? "Unavailable")}</td>)}</tr>;
    })}</tbody>
  </table></div>;
}

function ChangeIndicator({ comparison, metric, field, row }: { comparison: { previous: number | null; delta: number | null; percent_change: number | null }; metric: string; field: QueryResult["metrics"][number]; row?: Record<string, unknown> }) {
  const change = comparison.delta;
  if (change === null) return <small className="change-unavailable">No prior data</small>;
  const sign = change > 0 ? "+" : "";
  const formattedChange = formatMetricValue(change, field, row ?? {});
  const favorable = /cost/i.test(metric) ? change <= 0 : change >= 0;
  return <small className={`metric-change ${favorable ? "positive" : "negative"}`}>
    {sign}{formattedChange}{comparison.percent_change === null ? " · —" : ` (${sign}${comparison.percent_change.toFixed(2)}%)`}
  </small>;
}
