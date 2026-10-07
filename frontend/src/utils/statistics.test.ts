import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { statisticsDetails } from "./statistics";

describe("statisticsDetails", () => {
  it("reads the summary of a real statistics result", () => {
    const details = statisticsDetails(fixtures.statisticsSummary);
    expect(details).not.toBeNull();
    expect(details?.count).toBe(8);
    expect(details?.measure).toBeNull();
    expect(details?.measures.map((m) => m.name)).toEqual([
      "count",
      "sum",
      "mean",
      "median",
      "mode",
      "min",
      "max",
      "range",
      "variance",
      "std",
      "sample_variance",
      "sample_std",
    ]);
  });

  it("keeps the measure asked for", () => {
    expect(statisticsDetails(fixtures.statisticsPhrase)?.measure).toBe("std");
  });

  it("is null for other intents and for malformed details", () => {
    expect(statisticsDetails(fixtures.arithmetic)).toBeNull();
    expect(
      statisticsDetails({ ...fixtures.statisticsSummary, details: { measures: "x" } }),
    ).toBeNull();
  });
});
