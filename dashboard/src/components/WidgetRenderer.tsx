"use client";

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { ReactNode } from "react";
import type { DashboardWidget, QueryResult } from "@/lib/types";
import { fieldUnit, formatDate, formatMetricValue, formatValue } from "@/lib/format";

export type WidgetState = { status: "loading" } | { status: "error"; message: string } | { status: "success"; result: QueryResult };

interface Props { widget: DashboardWidget; state: WidgetState }

export function WidgetRenderer({ widget, state }: Props) {
  if (state.status === "loading") return <section className="widget" aria-labelledby={`${widget.id}-title`} aria-busy="true"><WidgetHeader widget={widget} /><div className="skeleton" /></section>;
  if (state.status === "error") return <section className="widget" aria-labelledby={`${widget.id}-title`}><WidgetHeader widget={widget} /><p className="state-error" role="alert">{state.message}</p></section>;

  const { result } = state;
  return <section className="widget" aria-labelledby={`${widget.id}-title`} data-testid={`widget-${widget.id}`}>
    <WidgetHeader widget={widget} />
    {result.rows.length === 0 ? <p className="state-empty">No data for the selected filters.</p> : (
      widgetRegistry[widget.type]?.(widget, result) ?? <p className="state-error">Unsupported widget type: {widget.type}</p>
    )}
  </section>;
}

function WidgetHeader({ widget }: { widget: DashboardWidget }) {
  return <div className="widget-heading"><h2 id={`${widget.id}-title`}>{widget.title}</h2><span>{widget.model.replaceAll("_", " ")}</span></div>;
}

type Renderer = (widget: DashboardWidget, result: QueryResult) => ReactNode;

const widgetRegistry: Record<string, Renderer> = {
  metric: metricWidget,
  area_chart: areaChartWidget,
  bar_chart: barChartWidget,
  table: tableWidget,
};

function metricWidget(_widget: DashboardWidget, result: QueryResult) {
  const row = result.rows[0] ?? {};
  return <div className="metric-grid">{result.metrics.map((metric) => (
    <article className="metric-item" key={metric.name}>
      <span>{metric.name.replaceAll("_", " ")}</span>
      <strong>{formatValue(row[metric.name], metric)}</strong>
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
        <YAxis width={72} />
        <Tooltip labelFormatter={(value) => formatDate(value)} formatter={(value, name, item) => {
          const metric = result.metrics.find((field) => field.name === String(name) || field.name.replaceAll("_", " ") === String(name));
          return [metric ? formatMetricValue(value, metric, (item?.payload ?? {}) as Record<string, unknown>) : String(value ?? "Unavailable"), String(name)];
        }} />
        {result.metrics.map((metric, index) => <Area key={metric.name} type="monotone" dataKey={metric.name} name={metric.name.replaceAll("_", " ")} stroke={index ? "#f59e0b" : "#3478f6"} fill={index ? "#fef3c7" : "#dbeafe"} connectNulls={false} />)}
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

function tableWidget(_widget: DashboardWidget, result: QueryResult) {
  const fields = [...result.dimensions, ...result.metrics];
  return <div className="table-scroll"><table>
    <thead><tr>{fields.map((field) => <th key={field.name}>{field.name.replaceAll("_", " ")}</th>)}</tr></thead>
    <tbody>{result.rows.map((row, index) => <tr key={index}>{fields.map((field) => <td key={field.name}>{result.metrics.some((item) => item.name === field.name) ? formatMetricValue(row[field.name], field, row) : field.name.includes("date") ? formatDate(row[field.name]) : String(row[field.name] ?? "Unavailable")}</td>)}</tr>)}</tbody>
  </table></div>;
}
