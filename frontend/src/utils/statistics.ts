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

/** One row of the frequency table (ADR 0032). */
export interface FrequencyRow {
  value: string;
  frequency: number;
  /** Exact fraction, e.g. "1/3". */
  relative: string;
  cumulative: number;
}

/** `details` of a statistics result (docs/architecture.md, §4). */
export interface StatisticsDetails {
  /** The measure asked for; null for the whole summary. */
  measure: string | null;
  count: number;
  /** True when the data were given with frequencies (weights). */
  weighted: boolean;
  data: string[];
  sorted: string[];
  modes: string[];
  frequency: FrequencyRow[];
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

function isFrequencyRow(value: unknown): value is FrequencyRow {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const row = value as Record<string, unknown>;
  return (
    isString(row.value) &&
    typeof row.frequency === "number" &&
    Number.isInteger(row.frequency) &&
    isString(row.relative) &&
    typeof row.cumulative === "number" &&
    Number.isInteger(row.cumulative)
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
    typeof d.weighted === "boolean" &&
    isStringArray(d.data) &&
    isStringArray(d.sorted) &&
    isStringArray(d.modes) &&
    Array.isArray(d.frequency) &&
    d.frequency.every(isFrequencyRow) &&
    Array.isArray(d.measures) &&
    d.measures.every(isMeasure);
  return valid ? (d as unknown as StatisticsDetails) : null;
}
