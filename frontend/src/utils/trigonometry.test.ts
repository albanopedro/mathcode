import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import {
  TRIG_CALCULATIONS,
  listedLatex,
  periodicDetails,
  trigCalculation,
  trigDetails,
} from "./trigonometry";

describe("trigonometry catalog", () => {
  it("has every calculation of the backend, each with its input and an example", () => {
    expect(TRIG_CALCULATIONS.map((option) => option.value)).toEqual([
      "convert",
      "reduce",
      "identity",
      "triangle",
    ]);
    expect(trigCalculation("unknown").value).toBe("convert");
  });
});

describe("trigDetails", () => {
  it("reads each kind of real result", () => {
    expect(trigDetails(fixtures.trigReduce)?.calculation).toBe("reduce");
    expect(trigDetails(fixtures.trigIdentityFalse)?.calculation).toBe("identity");
    expect(trigDetails(fixtures.trigTriangleAmbiguous)?.calculation).toBe("triangle");
    expect(trigDetails(fixtures.trigConvert)?.calculation).toBe("convert");
  });

  it("ignores other intents and malformed details", () => {
    expect(trigDetails(fixtures.geometryCircle)).toBeNull();
    expect(trigDetails({ ...fixtures.trigReduce, details: { calculation: "reduce" } })).toBeNull();
  });
});

describe("periodicDetails", () => {
  it("reads the list of an equation with periodic solutions", () => {
    const details = periodicDetails(fixtures.trigPeriodic)!;
    expect(details.interval?.latex).toBe("[0, 2 \\pi)");
    expect(listedLatex(details)).toBe("x = \\frac{\\pi}{6},\\ \\frac{5 \\pi}{6}");
    expect(periodicDetails(fixtures.equation)).toBeNull();
  });
});
