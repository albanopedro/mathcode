import { useCallback, useState } from "react";

import type { MathResult } from "../types/math";
import {
  addEntry,
  type HistoryEntry,
  loadHistory,
  saveHistory,
} from "../utils/history";

type Request = Pick<HistoryEntry, "input" | "intent" | "fields" | "allowAi">;

/** The history in this browser, saved on every change. */
export function useHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>(() => loadHistory());

  const update = useCallback((change: (current: HistoryEntry[]) => HistoryEntry[]) => {
    setEntries((current) => {
      const next = change(current);
      saveHistory(next);
      return next;
    });
  }, []);

  const add = useCallback(
    (request: Request, result: MathResult) => update((current) => addEntry(current, request, result)),
    [update],
  );
  const remove = useCallback(
    (id: string) => update((current) => current.filter((entry) => entry.id !== id)),
    [update],
  );
  const clear = useCallback(() => update(() => []), [update]);

  return { entries, add, remove, clear };
}
