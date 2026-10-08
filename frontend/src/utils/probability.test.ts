import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import {
  PROBABILITY_CALCULATIONS,
  probabilityCalculation,
  probabilityDetails,
  repeatedLetters,
} from "./probability";

describe("probability catalog", () => {
  it("has every calculation of the backend, each with its values and an example", () => {
    expect(PROBABILITY_CALCULATIONS.map((option) => option.value)).toEqual([
      "factorial",
      "arrangement",
      "arrangement_repetition",
      "combination",
      "combination_repetition",
      "anagrams",
      "complement",
      "intersection",
      "intersection_independent",
      "union",
      "union_independent",
      "conditional",
      "binomial_exact",
      "binomial_at_most",
      "binomial_at_least",
      "binomial_summary",
    ]);
    for (const option of PROBABILITY_CALCULATIONS) {
      expect(option.values).not.toBe("");
      expect(option.example).not.toBe("");
    }
  });

  it("falls back to the first calculation", () => {
    expect(probabilityCalculation("lottery").value).toBe("factorial");
  });
});

describe("probabilityDetails", () => {
  it("reads a real result", () => {
    const details = probabilityDetails(fixtures.probabilityBinomial);
    expect(details?.group).toBe("binomial");
    expect(details?.percent).toBe("81,25%");
    expect(details?.percent_exact).toBe(true);
    expect(details?.values).toEqual({ n: "5", k: "3", p: "1/2" });
  });

  it("ignores other intents and malformed details", () => {
    expect(probabilityDetails(fixtures.geometryCircle)).toBeNull();
    expect(
      probabilityDetails({ ...fixtures.probabilityBinomial, details: { group: "lottery" } }),
    ).toBeNull();
  });

  it("names only the letters that repeat", () => {
    const anagrams = probabilityDetails(fixtures.probabilityAnagrams)!;
    expect(repeatedLetters(anagrams)).toBe("A (3 vezes), N (2 vezes)");
    expect(repeatedLetters({ ...anagrams, letters: [{ letter: "A", count: 1 }] })).toBeNull();
    expect(repeatedLetters(probabilityDetails(fixtures.probabilityBinomial)!)).toBeNull();
  });
});
