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
  operation: "cálculo",
  figure: "figura",
  calculation: "cálculo",
};

const GEOMETRY_NAMES: Record<string, string> = {
  circle: "círculo",
  square: "quadrado",
  rectangle: "retângulo",
  triangle: "triângulo",
  trapezoid: "trapézio",
  rhombus: "losango",
  parallelogram: "paralelogramo",
  cube: "cubo",
  box: "paralelepípedo",
  sphere: "esfera",
  cylinder: "cilindro",
  cone: "cone",
  right_triangle: "triângulo retângulo",
  points: "pontos",
  area: "área",
  perimeter: "perímetro",
  volume: "volume",
  surface_area: "área da superfície",
  classify: "classificação",
  missing_side: "lado que falta",
  distance: "distância",
  midpoint: "ponto médio",
  line: "reta",
  polygon_area: "área do polígono",
};

// The "calculation" option of probability (geometry's are in GEOMETRY_NAMES).
const PROBABILITY_NAMES: Record<string, string> = {
  factorial: "fatorial",
  arrangement: "arranjo",
  arrangement_repetition: "arranjo com repetição",
  combination: "combinação",
  combination_repetition: "combinação com repetição",
  anagrams: "anagramas",
  complement: "não A",
  intersection: "A e B",
  intersection_independent: "A e B, independentes",
  union: "A ou B",
  union_independent: "A ou B, independentes",
  conditional: "A dado B",
  binomial_exact: "binomial, P(X = k)",
  binomial_at_most: "binomial, P(X ≤ k)",
  binomial_at_least: "binomial, P(X ≥ k)",
  binomial_summary: "binomial, média e variância",
};

// The "calculation" option of trigonometry.
const TRIGONOMETRY_NAMES: Record<string, string> = {
  convert: "converter ângulo",
  reduce: "redução ao 1º quadrante",
  identity: "verificar identidade",
  triangle: "resolver triângulo",
};

// The "operation" option of matrices and vectors.
const OPERATION_NAMES: Record<string, string> = {
  evaluate: "calcular expressão",
  determinant: "determinante",
  inverse: "inversa",
  transpose: "transposta",
  trace: "traço",
  rank: "posto",
  norm: "norma",
  unit: "vetor unitário",
  dot: "produto escalar",
  cross: "produto vetorial",
  angle: "ângulo",
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
      const names: Record<string, string> =
        {
          side: SIDES,
          measure: MEASURES,
          operation: OPERATION_NAMES,
          figure: GEOMETRY_NAMES,
          calculation: { ...GEOMETRY_NAMES, ...PROBABILITY_NAMES, ...TRIGONOMETRY_NAMES },
        }[key] ?? {};
      const shown = names[String(value)] ?? String(value);
      return `${OPTION_LABELS[key] ?? key}: ${shown}`;
    }),
    byAi,
  };
}
