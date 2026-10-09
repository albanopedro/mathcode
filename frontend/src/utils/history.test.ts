import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { addEntry, HISTORY_KEY, loadHistory, MAX_HISTORY, saveHistory } from "./history";
import { EMPTY_FIELDS } from "./operations";

const request = { input: "2x + 5 = 17", intent: null, fields: EMPTY_FIELDS, allowAi: false };

describe("history", () => {
  it("adds the newest first, with the result or the error", () => {
    let entries = addEntry([], request, fixtures.equation);
    entries = addEntry(entries, { ...request, input: "1/0" }, fixtures.divisionByZero);
    expect(entries.map((e) => e.input)).toEqual(["1/0", "2x + 5 = 17"]);
    expect(entries[1]).toMatchObject({ success: true, summary: "x = 6" });
    expect(entries[0]!.success).toBe(false);
    expect(entries[0]!.summary).toMatch(/zero/i);
  });

  it("moves a repeated calculation up instead of repeating it", () => {
    let entries = addEntry([], request, fixtures.equation);
    entries = addEntry(entries, { ...request, input: "x^2" }, fixtures.equation);
    entries = addEntry(entries, request, fixtures.equation);
    expect(entries.map((e) => e.input)).toEqual(["2x + 5 = 17", "x^2"]);
  });

  it(`keeps the last ${MAX_HISTORY}`, () => {
    let entries = addEntry([], request, fixtures.equation);
    for (let i = 0; i < 60; i++) {
      entries = addEntry(entries, { ...request, input: String(i) }, fixtures.arithmetic);
    }
    expect(entries).toHaveLength(MAX_HISTORY);
    expect(entries[0]!.input).toBe("59");
  });

  it("saves and loads, ignoring anything malformed", () => {
    saveHistory(addEntry([], request, fixtures.equation));
    expect(loadHistory().map((e) => e.input)).toEqual(["2x + 5 = 17"]);

    localStorage.setItem(HISTORY_KEY, "not json");
    expect(loadHistory()).toEqual([]);
    localStorage.setItem(HISTORY_KEY, JSON.stringify([{ input: 1 }, "x"]));
    expect(loadHistory()).toEqual([]);
  });

  it("fills fields that an older version did not save", () => {
    const [entry] = addEntry([], request, fixtures.equation);
    const { trig_calculation: _, ...older } = entry!.fields;
    localStorage.setItem(HISTORY_KEY, JSON.stringify([{ ...entry, fields: older }]));
    expect(loadHistory()[0]!.fields.trig_calculation).toBe("convert");
  });

  it("works without storage", () => {
    expect(loadHistory(null)).toEqual([]);
    expect(() => saveHistory([], null)).not.toThrow();
  });
});
