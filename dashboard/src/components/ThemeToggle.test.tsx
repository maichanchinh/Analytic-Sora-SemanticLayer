import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ThemeToggle, THEME_STORAGE_KEY } from "@/components/ThemeToggle";

describe("ThemeToggle", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("starts from the system theme and follows system changes until overridden", async () => {
    let listener: ((event: MediaQueryListEvent) => void) | undefined;
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      matches: true,
      addEventListener: (_name: string, callback: (event: MediaQueryListEvent) => void) => { listener = callback; },
      removeEventListener: vi.fn(),
    })));
    render(<ThemeToggle />);

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    listener?.({ matches: false } as MediaQueryListEvent);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    fireEvent.click(screen.getByRole("button", { name: "Switch to dark theme" }));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    listener?.({ matches: false } as MediaQueryListEvent);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("restores a saved theme preference", async () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    render(<ThemeToggle />);

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();
  });
});
