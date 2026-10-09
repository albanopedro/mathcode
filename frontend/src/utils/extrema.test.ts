import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { extremaDetails } from "./extrema";
import { takesAi } from "./operations";

describe("extremaDetails", () => {
  it("reads the points of a real response", () => {
    const details = extremaDetails(fixtures.extremaCubic);
    expect(details).not.toBeNull();
    expect(details!.variable).toBe("x");
    expect(details!.vertex).toBe(false);
    expect(details!.points.map((point) => [point.x, point.y, point.kind])).toEqual([
      ["-1", "2", "max"],
      ["1", "-2", "min"],
    ]);
  });

  it("knows a vertex", () => {
    expect(extremaDetails(fixtures.extremaVertexPhrase)?.vertex).toBe(true);
  });

  it("ignores other results and malformed details", () => {
    expect(extremaDetails(fixtures.derivative)).toBeNull();
    expect(
      extremaDetails({ ...fixtures.extremaCubic, details: { ...fixtures.extremaCubic.details, points: [{}] } }),
    ).toBeNull();
  });
});

describe("takesAi", () => {
  it("is true for Automático and Assistente only", () => {
    expect(takesAi(null)).toBe(true);
    expect(takesAi("assistant")).toBe(true);
    expect(takesAi("derivative")).toBe(false);
  });
});
