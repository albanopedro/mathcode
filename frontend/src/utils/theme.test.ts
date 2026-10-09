import { afterEach, describe, expect, it, vi } from "vitest";

import { applyTheme, loadTheme, resolveTheme, saveTheme, THEME_KEY, watchSystem } from "./theme";

function mockSystem(dark: boolean) {
  const listeners: (() => void)[] = [];
  const query = {
    matches: dark,
    addEventListener: (_: string, listener: () => void) => listeners.push(listener),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("matchMedia", vi.fn(() => query));
  return { query, fire: () => listeners.forEach((listener) => listener()) };
}

describe("theme", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.classList.remove("dark");
  });

  it("follows the system unless light or dark was chosen", () => {
    mockSystem(true);
    expect(loadTheme()).toBe("system");
    expect(resolveTheme("system")).toBe("dark");
    expect(resolveTheme("light")).toBe("light");
    saveTheme("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    expect(loadTheme()).toBe("light");
    saveTheme("system"); // the default is not stored
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });

  it("ignores unknown stored values", () => {
    localStorage.setItem(THEME_KEY, "sepia");
    expect(loadTheme()).toBe("system");
  });

  it("puts the dark class on the page", () => {
    mockSystem(false);
    applyTheme("dark");
    expect(document.documentElement).toHaveClass("dark");
    applyTheme("system");
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("hears when the system changes", () => {
    const system = mockSystem(false);
    const changed = vi.fn();
    watchSystem(changed);
    system.query.matches = true;
    system.fire();
    expect(changed).toHaveBeenCalledOnce();
  });
});
