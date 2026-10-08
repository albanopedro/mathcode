import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { vectorDetails } from "./vectors";

describe("vectorDetails", () => {
  it("reads the vectors a real result was computed from", () => {
    expect(vectorDetails(fixtures.vectorCross)).toEqual({
      operation: "cross",
      dimension: 3,
      vectors: ["[1, 2, 3]", "[4, 5, 6]"],
      vectors_latex: ["\\left(1,\\ 2,\\ 3\\right)", "\\left(4,\\ 5,\\ 6\\right)"],
    });
  });

  it("is null for other intents and malformed details", () => {
    expect(vectorDetails(fixtures.matrixDeterminant)).toBeNull();
    expect(vectorDetails({ ...fixtures.vectorNorm, details: { vectors: [1] } })).toBeNull();
  });
});
