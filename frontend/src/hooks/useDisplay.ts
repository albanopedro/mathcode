import { useCallback, useState } from "react";

import { type DisplayPreference, loadDisplay, saveDisplay } from "../utils/approximation";

/** Exact or approximate, and how many digits: remembered for the next results. */
export function useDisplay() {
  const [display, setDisplay] = useState<DisplayPreference>(() => loadDisplay());
  const change = useCallback((patch: Partial<DisplayPreference>) => {
    setDisplay((current) => {
      const next = { ...current, ...patch };
      saveDisplay(next);
      return next;
    });
  }, []);
  return { display, change };
}
