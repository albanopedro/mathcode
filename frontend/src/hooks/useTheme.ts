import { useCallback, useEffect, useState } from "react";

import { applyTheme, loadTheme, saveTheme, type ThemeChoice, watchSystem } from "../utils/theme";

/** The theme chosen, applied to the page; with "system", it follows system changes. */
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(() => loadTheme());

  useEffect(() => {
    applyTheme(choice);
    if (choice !== "system") {
      return;
    }
    return watchSystem(() => applyTheme("system"));
  }, [choice]);

  const choose = useCallback((next: ThemeChoice) => {
    saveTheme(next);
    setChoice(next);
  }, []);

  return { choice, choose };
}

/** Whether the page is dark right now (for things drawn outside CSS, like the graph). */
export function useIsDark(): boolean {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setDark(document.documentElement.classList.contains("dark")),
    );
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return dark;
}
