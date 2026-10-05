import type { CSSProperties } from "react";
import { WidgetRenderer, type WidgetState } from "@/components/WidgetRenderer";
import type { DashboardConfig } from "@/lib/types";

interface Props {
  config: DashboardConfig;
  widgetStates: Record<string, WidgetState>;
}

export function DashboardRenderer({ config, widgetStates }: Props) {
  const columns = Math.max(1, Math.min(config.layout?.columns ?? 12, 12));
  return <>
    <div className="section-heading"><div><h2>Overview</h2><p>Results reflect the selected date range and supported filters.</p></div><span className="result-count">{config.widgets.length} widgets</span></div>
    <div className="widget-grid" style={{ "--columns": columns } as CSSProperties}>
      {config.widgets.map((widget) => <div className="widget-slot" key={widget.id} style={{ "--span": Math.min(widget.span ?? columns, columns) } as CSSProperties}>
        <WidgetRenderer widget={widget} state={widgetStates[widget.id] ?? { status: "loading" }} />
      </div>)}
    </div>
  </>;
}
