import type { MathResult } from "../types/math";

/** `details` of a matrix result (docs/architecture.md, §4): A, the matrix operated on. */
export interface MatrixDetails {
  operation: string;
  rows: number;
  cols: number;
  matrix: string;
  matrix_latex: string;
}

export function matrixDetails(result: MathResult): MatrixDetails | null {
  if (result.intent !== "matrix") {
    return null;
  }
  const d = result.details;
  const valid =
    typeof d.operation === "string" &&
    typeof d.rows === "number" &&
    typeof d.cols === "number" &&
    typeof d.matrix === "string" &&
    typeof d.matrix_latex === "string";
  return valid ? (d as unknown as MatrixDetails) : null;
}
