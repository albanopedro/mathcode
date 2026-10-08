import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { matrixDetails } from "./matrices";

describe("matrixDetails", () => {
  it("reads the matrix a real result was computed from", () => {
    expect(matrixDetails(fixtures.matrixIrrational)).toEqual({
      operation: "inverse",
      rows: 2,
      cols: 2,
      matrix: "[[sqrt(2), 1], [1, sqrt(2)]]",
      matrix_latex: "\\left[\\begin{matrix}\\sqrt{2} & 1\\\\1 & \\sqrt{2}\\end{matrix}\\right]",
    });
  });

  it("is null for other intents and malformed details", () => {
    expect(matrixDetails(fixtures.arithmetic)).toBeNull();
    expect(matrixDetails({ ...fixtures.matrixProduct, details: { rows: "2" } })).toBeNull();
  });
});
