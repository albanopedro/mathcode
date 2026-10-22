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
      "q1",
      "q3",
      "iqr",
      "mode",
      "min",
      "max",
      "range",
      "variance",
      "std",
      "sample_variance",
      "sample_std",
    ]);
    const measureNamed = (name: string) =>
      (details?.measures ?? []).find((measure) => measure.name === name);
    expect(measureNamed("q1")?.plain).toBe("4");
    expect(measureNamed("q3")?.plain).toBe("6");
    expect(measureNamed("iqr")?.plain).toBe("2");
    expect(details?.weighted).toBe(false);
    expect(details?.frequency).toHaveLength(5);
  });

  it("reads weighted data and its frequency table", () => {
    const details = statisticsDetails(fixtures.statisticsWeighted);
    expect(details).not.toBeNull();
    expect(details?.weighted).toBe(true);
    expect(details?.count).toBe(10);
    expect(details?.frequency).toEqual([
      { value: "7", frequency: 2, relative: "1/5", cumulative: 2 },
      { value: "8", frequency: 3, relative: "3/10", cumulative: 5 },
      { value: "9", frequency: 5, relative: "1/2", cumulative: 10 },
    ]);
    expect(details?.measures.find((measure) => measure.name === "mean")?.label).toBe(
      "Média ponderada",
    );
  });

  it("keeps the frequency table as the measure asked for", () => {
    const details = statisticsDetails(fixtures.statisticsFrequency);
    expect(details?.measure).toBe("frequency");
    expect(details?.frequency).toEqual([
      { value: "1", frequency: 1, relative: "1/4", cumulative: 1 },
      { value: "2", frequency: 2, relative: "1/2", cumulative: 3 },
      { value: "3", frequency: 1, relative: "1/4", cumulative: 4 },
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
    expect(
      statisticsDetails({
        ...fixtures.statisticsSummary,
        details: {
          ...fixtures.statisticsSummary.details,
          frequency: [{ value: "1", frequency: 1, relative: "1", cumulative: "1" }],
        },
      }),
    ).toBeNull();
  });
});
