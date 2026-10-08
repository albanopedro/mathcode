import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { FIGURES, figure, geometryDetails } from "./geometry";

describe("geometry catalog", () => {
  it("has every figure of the backend, each with calculations and an example", () => {
    expect(FIGURES.map((option) => option.value)).toEqual([
      "circle",
      "square",
      "rectangle",
      "triangle",
      "trapezoid",
      "rhombus",
      "parallelogram",
      "cube",
      "box",
      "sphere",
      "cylinder",
      "cone",
      "right_triangle",
      "points",
    ]);
    for (const option of FIGURES) {
      expect(option.calculations.length).toBeGreaterThan(0);
      expect(option.example).not.toBe("");
    }
  });

  it("falls back to the first figure", () => {
    expect(figure("hexagon").value).toBe("circle");
  });
});

describe("geometryDetails", () => {
  it("reads a real result", () => {
    const details = geometryDetails(fixtures.geometryCircle);
    expect(details?.formula).toBe("A = \\pi r^2");
    expect(details?.measures).toEqual({ r: "5" });
    expect(details?.quantity).toBe("area");
  });

  it("is null for other intents and malformed details", () => {
    expect(geometryDetails(fixtures.arithmetic)).toBeNull();
    expect(geometryDetails({ ...fixtures.geometryCircle, details: { figure: 1 } })).toBeNull();
  });
});
