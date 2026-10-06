import type { IntentName } from "../types/math";

export interface Operation {
  /** `null` lets the API detect the operation from the input. */
  intent: IntentName | null;
  label: string;
  placeholder: string;
}

/** The operation selector, in display order. */
export const OPERATIONS: readonly Operation[] = [
  { intent: null, label: "Automático", placeholder: "Ex.: 2x + 5 = 17" },
  { intent: "arithmetic", label: "Calcular", placeholder: "Ex.: 0.1 + 0.2" },
  { intent: "simplify", label: "Simplificar", placeholder: "Ex.: x² + 2x + x²" },
  { intent: "factor", label: "Fatorar", placeholder: "Ex.: x² - 4 ou 360" },
  { intent: "expand", label: "Expandir", placeholder: "Ex.: (x + 1)^3" },
  { intent: "solve_equation", label: "Resolver equação", placeholder: "Ex.: x² - 5x + 6 = 0" },
  { intent: "solve_system", label: "Resolver sistema", placeholder: "Ex.: x + y = 3; x - y = 1" },
  {
    intent: "polynomial_division",
    label: "Dividir polinômios",
    placeholder: "Ex.: (x^3 - 1)/(x - 1)",
  },
];

/** Short name shown next to a result. */
export const INTENT_LABELS: Record<IntentName, string> = {
  arithmetic: "Aritmética",
  simplify: "Simplificação",
  factor: "Fatoração",
  expand: "Expansão",
  solve_equation: "Equação",
  solve_system: "Sistema",
  polynomial_division: "Divisão de polinômios",
};
