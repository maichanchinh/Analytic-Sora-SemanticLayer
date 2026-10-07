import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Filters } from "@/components/Filters";
import { initialDateRange, shiftDate } from "@/lib/query";
import type { DashboardConfig, DashboardFilters } from "@/lib/types";

const config: DashboardConfig = {
  id: "ua_app_overview",
  title: "UA App Overview",
  filters: ["date_range"],
  widgets: [],
};

function dashboardFilters(range: DashboardFilters["date_range"]): DashboardFilters {
  return {
    app_id: "",
    country_code: [],
    date_range: range,
    campaign_id: "",
    cohort_day: "",
  };
}

describe("Period day navigation", () => {
  afterEach(cleanup);

  it("moves the entire selected range by one day", () => {
    const yesterday = initialDateRange().to;
    const filters = dashboardFilters({
      from: shiftDate(yesterday, -2),
      to: yesterday,
    });
    const onChange = vi.fn();

    render(
      <Filters
        config={config}
        filters={filters}
        apps={[]}
        countries={[]}
        campaigns={[]}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Previous day" }));

    expect(onChange).toHaveBeenCalledWith({
      ...filters,
      date_range: {
        from: shiftDate(filters.date_range.from, -1),
        to: shiftDate(filters.date_range.to, -1),
      },
    });
  });

  it("disables next-day navigation when the range already ends today", () => {
    const today = shiftDate(initialDateRange().to, 1);
    render(
      <Filters
        config={config}
        filters={dashboardFilters({ from: today, to: today })}
        apps={[]}
        countries={[]}
        campaigns={[]}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Next day" })).toBeDisabled();
  });
});

describe("date range picker", () => {
  afterEach(cleanup);

  it("commits a single day after one selection", () => {
    const onChange = vi.fn();
    render(<Filters config={config} filters={dashboardFilters({ from: "2026-10-05", to: "2026-10-05" })} apps={[]} countries={[]} campaigns={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Choose date range" }));
    fireEvent.click(screen.getByRole("button", { name: "Single day" }));
    fireEvent.click(screen.getByRole("gridcell", { name: "Oct 3, 2026" }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ date_range: { from: "2026-10-03", to: "2026-10-03" } }));
  });

  it("waits for the second range date and does not query while browsing months", () => {
    const onChange = vi.fn();
    render(<Filters config={config} filters={dashboardFilters({ from: "2026-10-05", to: "2026-10-05" })} apps={[]} countries={[]} campaigns={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Choose date range" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Select month" }), { target: { value: "7" } });
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("gridcell", { name: "Aug 1, 2026" }));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("gridcell", { name: "Aug 5, 2026" }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ date_range: { from: "2026-08-01", to: "2026-08-05" } }));
  });
});
