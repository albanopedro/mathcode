import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { isMathResult } from "./math";

describe("isMathResult", () => {
  it.each(Object.entries(fixtures))("accepts the real API response '%s'", (_name, fixture) => {
    expect(isMathResult(fixture)).toBe(true);
  });

  const valid = fixtures.equation;

  it.each([
    ["null", null],
    ["an array", [valid]],
    ["a missing field", { ...valid, warnings: undefined }],
    ["an unknown intent", { ...valid, intent: "teleport" }],
    ["an unknown verification status", { ...valid, verification: { ...valid.verification, status: "ok" } }],
    ["a result without latex", { ...valid, result: { plain: "x = 6", approx: null } }],
    ["a success with an error", { ...valid, error: { code: "X", message: "y", position: null } }],
    ["a success without verification", { ...valid, verification: null }],
    ["a failure without error", { ...fixtures.parseError, error: null }],
    ["a failure with a value", { ...fixtures.parseError, result: valid.result }],
    ["a non-numeric position", { ...fixtures.parseError, error: { code: "X", message: "y", position: "3" } }],
  ])("rejects %s", (_label, value) => {
    expect(isMathResult(value)).toBe(false);
  });
});
