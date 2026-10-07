import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import type { Interpretation } from "../types/math";
import { describeInterpretation } from "./interpretation";

describe("describeInterpretation", () => {
  it("names the AI model and asks for a check", () => {
    expect(describeInterpretation(fixtures.aiEquation.interpretation!)).toEqual({
      source: "IA (opencode/space-bunny-free)",
      operation: "Equação",
      expression: "x + 3 = 10",
      options: ["variável: x"],
      byAi: true,
    });
  });

  it("names the local rules", () => {
    const text = describeInterpretation(fixtures.phraseRules.interpretation!);

    expect(text.source).toBe("regras locais");
    expect(text.operation).toBe("Derivada");
    expect(text.byAi).toBe(false);
  });

  it("labels the options in Portuguese", () => {
    const interpretation: Interpretation = {
      method: "ai",
      intent: "limit",
      expression: "sin(x)/x",
      options: { variable: "x", point: "0", side: "left", order: 2, other: "?" },
      provider: "opencode",
      model: null,
    };

    const text = describeInterpretation(interpretation);

    expect(text.source).toBe("IA (opencode)");
    expect(text.options).toEqual([
      "variável: x",
      "ponto: 0",
      "lado: esquerda",
      "ordem: 2",
      "other: ?",
    ]);
  });

  it("names the statistics measure in Portuguese", () => {
    const text = describeInterpretation(fixtures.statisticsPhrase.interpretation!);
    expect(text.operation).toBe("Estatística");
    expect(text.options).toEqual(["medida: desvio padrão populacional"]);
  });
});
