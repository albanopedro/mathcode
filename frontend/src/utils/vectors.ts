import type { MathResult } from "../types/math";

/** `details` of a vector result (docs/architecture.md, §4): the vectors used. */
export interface VectorDetails {
  operation: string;
  dimension: number;
  vectors: string[];
  vectors_latex: string[];
}

export function vectorDetails(result: MathResult): VectorDetails | null {
  if (result.intent !== "vector") {
    return null;
  }
  const d = result.details;
  const isStrings = (value: unknown) =>
    Array.isArray(value) && value.every((item) => typeof item === "string");
  const valid =
    typeof d.operation === "string" &&
    typeof d.dimension === "number" &&
    isStrings(d.vectors) &&
    isStrings(d.vectors_latex);
  return valid ? (d as unknown as VectorDetails) : null;
}
