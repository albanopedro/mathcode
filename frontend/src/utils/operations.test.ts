import { describe, expect, it } from "vitest";

import { buildOptions, EMPTY_FIELDS, OPERATIONS, type Operation } from "./operations";

function operation(label: string): Operation {
  const found = OPERATIONS.find((op) => op.label === label);
  if (!found) {
    throw new Error(`no operation ${label}`);
  }
  return found;
}

describe("buildOptions", () => {
  it("sends nothing for operations without fields", () => {
    expect(buildOptions(operation("Fatorar"), { ...EMPTY_FIELDS, variable: "x" })).toBeNull();
  });

  it("sends the derivative order as a number and skips an empty variable", () => {
    expect(buildOptions(operation("Derivar"), { ...EMPTY_FIELDS, order: "3" })).toEqual({
      order: 3,
    });
    expect(buildOptions(operation("Derivar"), { ...EMPTY_FIELDS, variable: " y " })).toEqual({
      variable: "y",
      order: 1,
    });
  });

  it("passes an invalid order through, so the API can explain it", () => {
    expect(buildOptions(operation("Derivar"), { ...EMPTY_FIELDS, order: "2.5" })).toEqual({
      order: "2.5",
    });
  });

  it("sends only the bounds that were filled", () => {
    const integrate = operation("Integrar");
    expect(buildOptions(integrate, EMPTY_FIELDS)).toBeNull();
    expect(buildOptions(integrate, { ...EMPTY_FIELDS, lower: "0", upper: " inf " })).toEqual({
      lower: "0",
      upper: "inf",
    });
    expect(buildOptions(integrate, { ...EMPTY_FIELDS, lower: "0" })).toEqual({ lower: "0" });
  });

  it("sends the point and the side of a limit", () => {
    expect(
      buildOptions(operation("Limite"), { ...EMPTY_FIELDS, point: "pi/2", side: "left" }),
    ).toEqual({ point: "pi/2", side: "left" });
  });

  it("ignores fields the operation does not use", () => {
    const values = { ...EMPTY_FIELDS, lower: "0", upper: "1", point: "0", order: "5" };
    expect(buildOptions(operation("Limite"), values)).toEqual({ point: "0", side: "both" });
  });
});
