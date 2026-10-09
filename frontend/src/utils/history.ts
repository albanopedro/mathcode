import type { IntentName, MathResult } from "../types/math";
import { EMPTY_FIELDS, type FieldValues } from "./operations";

/**
 * The calculation history (Phase 11): kept only in this browser (localStorage),
 * never sent anywhere. Reading and writing never throw: a private window or
 * blocked storage just means no history.
 */
export const HISTORY_KEY = "mathcode.history.v1";
export const MAX_HISTORY = 50;

export interface HistoryEntry {
  id: string;
  /** ISO date of the calculation. */
  at: string;
  input: string;
  intent: IntentName | null;
  /** The extra fields as they were, to fill the form again. */
  fields: FieldValues;
  allowAi: boolean;
  success: boolean;
  /** The result in plain text, or the error message. */
  summary: string;
}

type Request = Pick<HistoryEntry, "input" | "intent" | "fields" | "allowAi">;

const isEntry = (value: unknown): value is HistoryEntry => {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === "string" &&
    typeof v.at === "string" &&
    typeof v.input === "string" &&
    (v.intent === null || typeof v.intent === "string") &&
    typeof v.fields === "object" &&
    v.fields !== null &&
    typeof v.allowAi === "boolean" &&
    typeof v.success === "boolean" &&
    typeof v.summary === "string"
  );
};

export function loadHistory(storage: Storage | null = safeStorage()): HistoryEntry[] {
  try {
    const raw = storage?.getItem(HISTORY_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) {
      return [];
    }
    // Fields saved by an older version get the new fields' defaults.
    return parsed
      .filter(isEntry)
      .slice(0, MAX_HISTORY)
      .map((entry) => ({ ...entry, fields: { ...EMPTY_FIELDS, ...entry.fields } }));
  } catch {
    return [];
  }
}

export function saveHistory(
  entries: HistoryEntry[],
  storage: Storage | null = safeStorage(),
): void {
  try {
    storage?.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, MAX_HISTORY)));
  } catch {
    // Full or blocked storage: the history just is not kept.
  }
}

function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function sameRequest(a: Request, b: Request): boolean {
  return (
    a.input === b.input &&
    a.intent === b.intent &&
    a.allowAi === b.allowAi &&
    JSON.stringify(a.fields) === JSON.stringify(b.fields)
  );
}

/** The new entry first; the same calculation done again moves up instead of repeating. */
export function addEntry(
  entries: HistoryEntry[],
  request: Request,
  result: MathResult,
  now: Date = new Date(),
): HistoryEntry[] {
  const entry: HistoryEntry = {
    ...request,
    id: `${now.getTime()}-${Math.random().toString(36).slice(2, 8)}`,
    at: now.toISOString(),
    success: result.success,
    summary: result.success
      ? (result.result?.plain ?? "")
      : (result.error?.message ?? "Erro"),
  };
  return [entry, ...entries.filter((old) => !sameRequest(old, request))].slice(0, MAX_HISTORY);
}
