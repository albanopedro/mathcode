import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { captions } from "./captions";
import { graphDetails, layout, traces } from "./graph";

describe("graphDetails", () => {
  it.each(["graphParabola", "graphTwo", "graphTan", "graphNoPoints"] as const)(
    "reads the real API response '%s'",
    (name) => {
      const details = graphDetails(fixtures[name]);
      expect(details).not.toBeNull();
      expect(details!.functions[0]!.x.length).toBe(details!.functions[0]!.y.length);
    },
  );

  it("is null for other operations", () => {
    expect(graphDetails(fixtures.equation)).toBeNull();
  });

  it("does not trust malformed graph details", () => {
    const broken = {
      ...fixtures.graphParabola,
      details: { ...fixtures.graphParabola.details, functions: [{ label: "x", x: [1], y: [] }] },
    };
    expect(graphDetails(broken)).toBeNull();
  });
});

describe("traces", () => {
  it("draws one line per function and keeps gaps as null", () => {
    const details = graphDetails(fixtures.graphTan)!;
    const [line] = traces(details) as Array<{ connectgaps: boolean; y: (number | null)[] }>;
    expect(line!.connectgaps).toBe(false);
    expect(line!.y).toContain(null);
  });

  it("adds the relevant points as markers", () => {
    const details = graphDetails(fixtures.graphParabola)!;
    const all = traces(details) as Array<{ mode: string; text?: string[] }>;
    expect(all).toHaveLength(2);
    expect(all[1]!.mode).toBe("markers");
    expect(all[1]!.text).toEqual(["Raiz: (1, 0)", "Raiz: (3, 0)", "Intercepto em y: (0, 3)"]);
  });

  it("names the function of each point when there are several", () => {
    const details = graphDetails(fixtures.graphTwo)!;
    const points = traces(details).at(-1) as { text: string[] };
    expect(points.text[0]).toBe("Raiz de y = x^2: (0, 0)");
  });

  it("has no marker trace without points", () => {
    expect(traces(graphDetails(fixtures.graphNoPoints)!)).toHaveLength(1);
  });

  it("uses the ranges chosen by the API", () => {
    const details = graphDetails(fixtures.graphParabola)!;
    const result = layout(details) as { xaxis: { range: number[] }; yaxis: { range: number[] } };
    expect(result.xaxis.range).toEqual(details.x_range);
    expect(result.yaxis.range).toEqual(details.y_range);
  });
});

describe("graph captions", () => {
  it("lists the range, the roots and the intercept", () => {
    expect(captions(fixtures.graphParabola)).toEqual([
      "x de -10 a 10.",
      "Raízes: x = 1; x = 3.",
      "Intercepto em y: (0, 3).",
    ]);
  });

  it("names each function when there are several", () => {
    expect(captions(fixtures.graphTwo)).toEqual([
      "x de -10 a 10.",
      "Raiz de y = x^2: x = 0.",
      "Intercepto em y de y = x^2: (0, 0).",
      "Raiz de y = 2*x + 1: x = -1/2.",
      "Intercepto em y de y = 2*x + 1: (0, 1).",
    ]);
  });

  it("shows only the range when there are no points", () => {
    expect(captions(fixtures.graphNoPoints)).toEqual(["x de 1 a 5."]);
  });
});

describe("graph range text", () => {
  it("shows the range as the user typed it", () => {
    expect(captions(fixtures.graphTan)[0]).toBe("x de -2pi a 2pi.");
  });
});
