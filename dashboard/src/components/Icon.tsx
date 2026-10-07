export type IconName =
  | "dashboard" | "application" | "country" | "calendar" | "period"
  | "cost" | "revenue" | "profit" | "roas" | "activity" | "sun" | "moon";

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return <svg aria-hidden="true" className={className} width={size} height={size} viewBox="0 0 24 24" {...common}>
    {name === "dashboard" && <><rect x="3" y="3" width="8" height="8" rx="2" /><rect x="13" y="3" width="8" height="5" rx="2" /><rect x="13" y="10" width="8" height="11" rx="2" /><rect x="3" y="13" width="8" height="8" rx="2" /></>}
    {name === "application" && <><rect x="4" y="3" width="16" height="18" rx="3" /><path d="M9 7h6M8 17h8" /><circle cx="12" cy="12" r="2" /></>}
    {name === "country" && <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>}
    {name === "calendar" && <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>}
    {name === "period" && <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>}
    {name === "cost" && <><path d="M4 6h16M6 6l1 14h10l1-14M9 6V4h6v2M10 10v6M14 10v6" /></>}
    {name === "revenue" && <><path d="M12 3v18M17 7.5C17 6.1 15 5 12 5S7 6.1 7 7.5 9 10 12 10s5 1.1 5 2.5-2 2.5-5 2.5-5-1.1-5-2.5" /></>}
    {name === "profit" && <><path d="M4 17l5-5 4 3 7-8" /><path d="M14 7h6v6" /></>}
    {name === "roas" && <><path d="M4.9 19a10 10 0 1 1 14.2 0" /><path d="M12 13l5-5M6 18h12" /><circle cx="12" cy="13" r="1" /></>}
    {name === "activity" && <><path d="M3 12h4l3-8 4 16 3-8h4" /></>}
    {name === "sun" && <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" /></>}
    {name === "moon" && <path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5 8.5 8.5 0 1 0 20.5 15.5Z" />}
  </svg>;
}
