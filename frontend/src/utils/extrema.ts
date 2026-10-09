import type { MathResult } from "../types/math";

/** A critical point of `details.points` (ADR 0021). */
export interface CriticalPoint {
  x: string;
  x_latex: string;
  y: string;
  y_latex: string;
  kind: "max" | "min" | "none" | "unknown";
}

export interface ExtremaDetails {
  variable: string;
  derivative_latex: string;
  points: CriticalPoint[];
  vertex: boolean;
}

const KINDS: readonly string[] = ["max", "min", "none", "unknown"];

function isPoint(value: unknown): value is CriticalPoint {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const p = value as Record<string, unknown>;
  return (
    typeof p.x === "string" &&
    typeof p.x_latex === "string" &&
    typeof p.y === "string" &&
    typeof p.y_latex === "string" &&
    typeof p.kind === "string" &&
    KINDS.includes(p.kind)
  );
}

/** The details of a maxima-and-minima result, or null for anything else. */
export function extremaDetails(result: MathResult): ExtremaDetails | null {
  if (result.intent !== "extrema") {
    return null;
  }
  const { variable, derivative, points, vertex } = result.details;
  const latex =
    typeof derivative === "object" && derivative !== null
      ? (derivative as Record<string, unknown>).latex
      : undefined;
  if (
    typeof variable !== "string" ||
    typeof latex !== "string" ||
    !Array.isArray(points) ||
    !points.every(isPoint) ||
    typeof vertex !== "boolean"
  ) {
    return null;
  }
  return { variable, derivative_latex: latex, points, vertex };
}
