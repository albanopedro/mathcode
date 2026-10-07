import type { Interpretation } from "../types/math";
import { INTENT_LABELS } from "./operations";

const OPTION_LABELS: Record<string, string> = {
  variable: "variável",
  order: "ordem",
  lower: "de",
  upper: "até",
  point: "ponto",
  side: "lado",
  x_min: "x de",
  x_max: "x até",
  measure: "medida",
};

const MEASURES: Record<string, string> = {
  count: "quantidade",
  sum: "soma",
  mean: "média",
  median: "mediana",
  mode: "moda",
  min: "mínimo",
  max: "máximo",
  range: "amplitude",
  variance: "variância populacional",
  std: "desvio padrão populacional",
  sample_variance: "variância amostral",
  sample_std: "desvio padrão amostral",
};

const SIDES: Record<string, string> = { both: "ambos", left: "esquerda", right: "direita" };

export interface InterpretationText {
  /** Who read the phrase. */
  source: string;
  operation: string | null;
  expression: string;
  /** Options as "label: value", e.g. "variável: x". */
  options: string[];
  /** An AI reading may be wrong: the user is asked to check it. */
  byAi: boolean;
}

export function describeInterpretation(interpretation: Interpretation): InterpretationText {
  const byAi = interpretation.method === "ai";
  const model = interpretation.model ?? interpretation.provider;
  return {
    source: byAi ? (model ? `IA (${model})` : "IA") : "regras locais",
    operation: interpretation.intent ? INTENT_LABELS[interpretation.intent] : null,
    expression: interpretation.expression,
    options: Object.entries(interpretation.options).map(([key, value]) => {
      const names = key === "side" ? SIDES : key === "measure" ? MEASURES : {};
      const shown = names[String(value)] ?? String(value);
      return `${OPTION_LABELS[key] ?? key}: ${shown}`;
    }),
    byAi,
  };
}
