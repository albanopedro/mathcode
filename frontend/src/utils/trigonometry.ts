import type { MathResult } from "../types/math";

/** The calculations of the Trigonometria operation (math_engine/trigonometry.py, ADR 0016). */
export interface TrigCalculationOption {
  value: string;
  label: string;
  /** What goes in the input, as shown under the fields. */
  input: string;
  example: string;
}

export const TRIG_CALCULATIONS: readonly TrigCalculationOption[] = [
  {
    value: "convert",
    label: "Converter ângulo (graus ↔ radianos)",
    input: "um ângulo; com ° vira radianos, sem ° vira graus",
    example: "30° ou pi/6",
  },
  {
    value: "reduce",
    label: "Redução ao 1º quadrante",
    input: "um ângulo ou uma função dele",
    example: "sin(150°)",
  },
  {
    value: "identity",
    label: "Verificar identidade",
    input: "uma igualdade com variável",
    example: "sin(x)^2 + cos(x)^2 = 1",
  },
  {
    value: "triangle",
    label: "Resolver triângulo",
    input: "três medidas: lados a, b, c e os ângulos opostos A, B, C",
    example: "a = 5; b = 7; C = 60°",
  },
];

export function trigCalculation(value: string): TrigCalculationOption {
  return TRIG_CALCULATIONS.find((option) => option.value === value) ?? TRIG_CALCULATIONS[0]!;
}

// -- details of a trigonometry result (docs/architecture.md, §4) ------------------------------

export interface ReductionRow {
  function: string;
  latex: string | null;
  sign: number;
  /** "-\cos\left(30^\circ\right)"; null on an axis. */
  reduced_latex: string | null;
}

export interface ReductionDetails {
  calculation: "reduce";
  quadrant: number | null;
  first: string;
  first_latex: string;
  turns: number;
  reference: string;
  reference_latex: string;
  values: ReductionRow[];
}

export interface IdentityDetails {
  calculation: "identity";
  holds: boolean;
  proved: boolean;
  variables: string[];
  counterexample: {
    point: Record<string, { plain: string; latex: string }>;
    left_latex: string | null;
    right_latex: string | null;
  } | null;
}

export interface TriangleRow {
  side: string;
  side_latex: string;
  side_given: boolean;
  angle: string;
  angle_latex: string;
  angle_given: boolean;
}

export interface TriangleDetails {
  calculation: "triangle";
  case: string;
  law: string;
  triangles: { rows: TriangleRow[] }[];
}

export interface ConversionDetails {
  calculation: "convert";
  to: "degrees" | "radians";
}

export type TrigDetails = ConversionDetails | ReductionDetails | IdentityDetails | TriangleDetails;

export function trigDetails(result: MathResult): TrigDetails | null {
  if (result.intent !== "trigonometry") {
    return null;
  }
  const d = result.details;
  switch (d.calculation) {
    case "convert":
      return d.to === "degrees" || d.to === "radians" ? (d as unknown as ConversionDetails) : null;
    case "reduce":
      return Array.isArray(d.values) && typeof d.reference_latex === "string"
        ? (d as unknown as ReductionDetails)
        : null;
    case "identity":
      return typeof d.holds === "boolean" ? (d as unknown as IdentityDetails) : null;
    case "triangle":
      return Array.isArray(d.triangles) && typeof d.law === "string"
        ? (d as unknown as TriangleDetails)
        : null;
    default:
      return null;
  }
}

// -- periodic solutions of an equation (ADR 0016) ----------------------------------------------

export interface PeriodicDetails {
  variable: string;
  integer: string;
  solutions_latex: string[];
  listed_total: number;
  interval: { latex: string; given: boolean } | null;
  rejected_families?: string[];
}

export function periodicDetails(result: MathResult): PeriodicDetails | null {
  const d = result.details;
  if (result.intent !== "solve_equation" || d.solution_set !== "periodic") {
    return null;
  }
  const valid =
    Array.isArray(d.solutions_latex) &&
    typeof d.listed_total === "number" &&
    typeof d.integer === "string";
  return valid ? (d as unknown as PeriodicDetails) : null;
}

/** "x = \frac{\pi}{6},\ \frac{5\pi}{6}" for the list inside the interval. */
export function listedLatex(details: PeriodicDetails): string {
  return `${details.variable} = ${details.solutions_latex.join(",\\ ")}`;
}
