/**
 * The color theme (Phase 11, ADR 0019): follow the system, or always light or
 * dark. The choice is kept in this browser; index.html applies it before React
 * starts, so the page does not flash white in the dark.
 */
export const THEME_KEY = "mathcode.theme.v1";

export type ThemeChoice = "system" | "light" | "dark";

const DARK_QUERY = "(prefers-color-scheme: dark)";

export function loadTheme(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

export function saveTheme(choice: ThemeChoice): void {
  try {
    if (choice === "system") {
      window.localStorage.removeItem(THEME_KEY);
    } else {
      window.localStorage.setItem(THEME_KEY, choice);
    }
  } catch {
    // Blocked storage: the choice lasts until the page is closed.
  }
}

export function systemIsDark(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(DARK_QUERY).matches;
}

export function resolveTheme(choice: ThemeChoice): "light" | "dark" {
  return choice === "system" ? (systemIsDark() ? "dark" : "light") : choice;
}

export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.classList.toggle("dark", resolveTheme(choice) === "dark");
}

export function watchSystem(onChange: () => void): () => void {
  if (typeof window.matchMedia !== "function") {
    return () => {};
  }
  const query = window.matchMedia(DARK_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
