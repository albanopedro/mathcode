import type { MathResult } from "../types/math";

/**
 * The calculations of the Probabilidade operation, as in the backend's catalog
 * (math_engine/probability.py, ADR 0015): what each one takes and an example.
 */
export interface ProbabilityCalculationOption {
  value: string;
  label: string;
  group: string;
  /** The values, as shown under the fields. */
  values: string;
  example: string;
}

const COUNTING = "Contagem";
const EVENTS = "Eventos";
const BINOMIAL = "Distribuição binomial";

const N_AND_K = "n (elementos) e k (escolhidos)";
const EVENTS_AB = "P(A) e P(B)";
const BINOMIAL_VALUES = "n (tentativas), k (sucessos) e p (chance de sucesso)";

export const PROBABILITY_CALCULATIONS: readonly ProbabilityCalculationOption[] = [
  {
    value: "factorial",
    label: "Fatorial ou permutação (n!)",
    group: COUNTING,
    values: "n",
    example: "n = 5",
  },
  {
    value: "arrangement",
    label: "Arranjo A(n, k)",
    group: COUNTING,
    values: N_AND_K,
    example: "n = 6; k = 2",
  },
  {
    value: "arrangement_repetition",
    label: "Arranjo com repetição (nᵏ)",
    group: COUNTING,
    values: N_AND_K,
    example: "n = 3; k = 2",
  },
  {
    value: "combination",
    label: "Combinação C(n, k)",
    group: COUNTING,
    values: N_AND_K,
    example: "n = 10; k = 3",
  },
  {
    value: "combination_repetition",
    label: "Combinação com repetição",
    group: COUNTING,
    values: N_AND_K,
    example: "n = 3; k = 2",
  },
  {
    value: "anagrams",
    label: "Anagramas",
    group: COUNTING,
    values: "uma palavra",
    example: "BANANA",
  },
  {
    value: "complement",
    label: "Não A",
    group: EVENTS,
    values: "P(A)",
    example: "P(A) = 1/4",
  },
  {
    value: "intersection",
    label: "A e B",
    group: EVENTS,
    values: "P(A), P(B) e P(A ou B)",
    example: "P(A) = 1/2; P(B) = 1/3; P(A ou B) = 2/3",
  },
  {
    value: "intersection_independent",
    label: "A e B (independentes)",
    group: EVENTS,
    values: EVENTS_AB,
    example: "P(A) = 1/2; P(B) = 1/3",
  },
  {
    value: "union",
    label: "A ou B",
    group: EVENTS,
    values: "P(A), P(B) e P(A e B)",
    example: "P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6",
  },
  {
    value: "union_independent",
    label: "A ou B (independentes)",
    group: EVENTS,
    values: EVENTS_AB,
    example: "P(A) = 1/2; P(B) = 1/3",
  },
  {
    value: "conditional",
    label: "A dado B",
    group: EVENTS,
    values: "P(A e B) e P(B)",
    example: "P(A e B) = 1/6; P(B) = 1/3",
  },
  {
    value: "binomial_exact",
    label: "P(X = k)",
    group: BINOMIAL,
    values: BINOMIAL_VALUES,
    example: "n = 5; k = 3; p = 1/2",
  },
  {
    value: "binomial_at_most",
    label: "P(X ≤ k)",
    group: BINOMIAL,
    values: BINOMIAL_VALUES,
    example: "n = 5; k = 3; p = 1/2",
  },
  {
    value: "binomial_at_least",
    label: "P(X ≥ k)",
    group: BINOMIAL,
    values: BINOMIAL_VALUES,
    example: "n = 5; k = 3; p = 1/2",
  },
  {
    value: "binomial_summary",
    label: "Média e variância",
    group: BINOMIAL,
    values: "n (tentativas) e p (chance de sucesso)",
    example: "n = 10; p = 30%",
  },
];

export const PROBABILITY_GROUPS = [COUNTING, EVENTS, BINOMIAL] as const;

export function probabilityCalculation(value: string): ProbabilityCalculationOption {
  return (
    PROBABILITY_CALCULATIONS.find((option) => option.value === value) ??
    PROBABILITY_CALCULATIONS[0]!
  );
}

/** `details` of a probability result (docs/architecture.md, §4). */
export interface ProbabilityDetails {
  calculation: string;
  group: "counting" | "events" | "binomial";
  values: Record<string, string>;
  formula: string;
  /** "37,5%"; null for counts and for the binomial summary. */
  percent: string | null;
  percent_exact: boolean | null;
  letters?: { letter: string; count: number }[];
  summary?: { mean: string; variance: string; std: string };
}

export function probabilityDetails(result: MathResult): ProbabilityDetails | null {
  if (result.intent !== "probability") {
    return null;
  }
  const d = result.details;
  const valid =
    typeof d.calculation === "string" &&
    (d.group === "counting" || d.group === "events" || d.group === "binomial") &&
    typeof d.values === "object" &&
    d.values !== null &&
    typeof d.formula === "string" &&
    (d.percent === null || typeof d.percent === "string");
  return valid ? (d as unknown as ProbabilityDetails) : null;
}

/** "A (3 vezes), N (2 vezes)": the letters that repeat, which divide the count. */
export function repeatedLetters(details: ProbabilityDetails): string | null {
  const repeated = (details.letters ?? []).filter((item) => item.count > 1);
  if (repeated.length === 0) {
    return null;
  }
  return repeated.map((item) => `${item.letter} (${item.count} vezes)`).join(", ");
}
