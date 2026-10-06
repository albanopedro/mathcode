import { describe, expect, it } from "vitest";

import { isHealthResponse } from "./health";

describe("isHealthResponse", () => {
  it("accepts a valid response", () => {
    expect(isHealthResponse({ status: "ok", version: "0.1.0", environment: "test" })).toBe(true);
  });

  it.each([
    ["null", null],
    ["a string", "ok"],
    ["a wrong status", { status: "down", version: "0.1.0", environment: "test" }],
    ["a missing version", { status: "ok", environment: "test" }],
    ["an unknown environment", { status: "ok", version: "0.1.0", environment: "staging" }],
  ])("rejects %s", (_label, value) => {
    expect(isHealthResponse(value)).toBe(false);
  });
});
