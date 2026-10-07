"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";

export const THEME_STORAGE_KEY = "sora-dashboard-theme";
type Theme = "light" | "dark";

export function ThemeToggle() {
  const [preference, setPreference] = useState<Theme | null>(null);
  const [systemDark, setSystemDark] = useState(false);
  const dark = preference ? preference === "dark" : systemDark;

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === "light" || saved === "dark") setPreference(saved);
    } catch {
      // Continue with the system preference when browser storage is unavailable.
    }
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!media) return;
    setSystemDark(media.matches);
    const update = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media.addEventListener?.("change", update);
    return () => media.removeEventListener?.("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  function toggle() {
    const next: Theme = dark ? "light" : "dark";
    setPreference(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Theme remains active for this page even if it cannot be persisted.
    }
  }

  return <button
    className="theme-toggle"
    type="button"
    aria-label={`Switch to ${dark ? "light" : "dark"} theme`}
    title={`Switch to ${dark ? "light" : "dark"} theme`}
    onClick={toggle}
  >
    <Icon name={dark ? "sun" : "moon"} size={17} />
  </button>;
}
