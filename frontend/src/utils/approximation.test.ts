import { afterEach, describe, expect, it } from "vitest";

import { DEFAULT_DISPLAY, DISPLAY_KEY, formatApprox, loadDisplay, saveDisplay } from "./approximation";

describe("formatApprox", () => {
  it("rounds to significant digits, with a decimal comma", () => {
    expect(formatApprox("0.523598775598299", 6)).toBe("0,523599");
    expect(formatApprox("0.523598775598299", 2)).toBe("0,52");
    expect(formatApprox("3.14159265358979", 15)).toBe("3,14159265358979");
    expect(formatApprox("0.375", 6)).toBe("0,375"); // no trailing zeros
    expect(formatApprox("-1.41421356237310", 4)).toBe("-1,414");
  });

  it("keeps the separators of lists and points", () => {
    expect(formatApprox("-1.41421356237310; 1.41421356237310", 3)).toBe("-1,41; 1,41");
    expect(formatApprox("(0.5, 1.73205080756888)", 3)).toBe("(0,5, 1,73)");
  });

  it("writes large and tiny numbers with a power of ten", () => {
    expect(formatApprox("1.23456789012346e+20", 4)).toBe("1,235·10²⁰");
    expect(formatApprox("9.33263618503219e-302", 3)).toBe("9,33·10⁻³⁰²");
  });

  it("clamps the digits to 2–15", () => {
    expect(formatApprox("0.523598775598299", 1)).toBe("0,52");
    expect(formatApprox("0.523598775598299", 40)).toBe("0,523598775598299");
  });
});

describe("display preference", () => {
  afterEach(() => localStorage.clear());

  it("is remembered, and falls back to exact with 6 digits", () => {
    expect(loadDisplay()).toEqual(DEFAULT_DISPLAY);
    saveDisplay({ mode: "approx", digits: 9 });
    expect(loadDisplay()).toEqual({ mode: "approx", digits: 9 });
    localStorage.setItem(DISPLAY_KEY, JSON.stringify({ mode: "x", digits: 99 }));
    expect(loadDisplay()).toEqual(DEFAULT_DISPLAY);
    localStorage.setItem(DISPLAY_KEY, "{");
    expect(loadDisplay()).toEqual(DEFAULT_DISPLAY);
  });
});
