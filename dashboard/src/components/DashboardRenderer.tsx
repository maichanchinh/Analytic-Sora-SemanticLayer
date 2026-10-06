import type { CSSProperties } from "react";
import { WidgetRenderer, type WidgetState } from "@/components/WidgetRenderer";
import type { AppOption } from "@/lib/types";
import type { DashboardConfig } from "@/lib/types";
import type { DateRange } from "@/lib/types";

interface Props {
  config: DashboardConfig;
  widgetStates: Record<string, WidgetState>;
  apps?: AppOption[];
  dateRange?: DateRange;
}

export function DashboardRenderer({ config, widgetStates, apps = [], dateRange }: Props) {
  const columns = Math.max(1, Math.min(config.layout?.columns ?? 12, 12));
  const sections = [...new Set(config.widgets.map((widget) => widget.section ?? "Overview"))];
  return <>
    {sections.map((section) => {
      const widgets = config.widgets.filter((widget) => (widget.section ?? "Overview") === section);
      return <section className="dashboard-section" key={section}>
        <div className="section-heading"><div><h2>{section}</h2><p>{dateRange ? formatRange(dateRange) : "Results reflect the selected date range and supported filters."}</p></div><span className="result-count">{widgets.length} widgets</span></div>
        <div className="widget-grid" style={{ "--columns": columns } as CSSProperties}>
          {widgets.map((widget) => <div className="widget-slot" key={widget.id} style={{ "--span": Math.min(widget.span ?? columns, columns) } as CSSProperties}>
            <WidgetRenderer widget={dateRange ? { ...widget, title: `${widget.title} · ${formatRange(dateRange)}` } : widget} state={widgetStates[widget.id] ?? { status: "loading" }} apps={apps} />
          </div>)}
        </div>
      </section>;
    })}
  </>;
}

function formatRange(range: DateRange) {
  return range.from === range.to ? range.from : `${range.from} – ${range.to}`;
}
