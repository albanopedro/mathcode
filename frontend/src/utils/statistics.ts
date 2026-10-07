import type { MathResult } from "../types/math";

/** One row of the summary (ADR 0011); `latex` null: not defined for these data. */
export interface StatisticsMeasure {
  name: string;
  label: string;
  symbol: string;
  plain: string | null;
  latex: string | null;
  approx: string | null;
}

/** `details` of a statistics result (docs/architecture.md, §4). */
export interface StatisticsDetails {
  /** The measure asked for; null for the whole summary. */
  measure: string | null;
  count: number;
  data: string[];
  sorted: string[];
  modes: string[];
  measures: StatisticsMeasure[];
}

const isString = (value: unknown): value is string => typeof value === "string";
const isNullableString = (value: unknown) => value === null || isString(value);
const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every(isString);

function isMeasure(value: unknown): value is StatisticsMeasure {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const m = value as Record<string, unknown>;
  return (
    isString(m.name) &&
    isString(m.label) &&
    isString(m.symbol) &&
    isNullableString(m.plain) &&
    isNullableString(m.latex) &&
    isNullableString(m.approx)
  );
}

/** The summary of a statistics result, or null for anything else or a malformed one. */
export function statisticsDetails(result: MathResult): StatisticsDetails | null {
  if (result.intent !== "statistics") {
    return null;
  }
  const d = result.details;
  const valid =
    isNullableString(d.measure) &&
    typeof d.count === "number" &&
    isStringArray(d.data) &&
    isStringArray(d.sorted) &&
    isStringArray(d.modes) &&
    Array.isArray(d.measures) &&
    d.measures.every(isMeasure);
  return valid ? (d as unknown as StatisticsDetails) : null;
}
