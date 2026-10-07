import type { IntentName } from "../types/math";

/** Extra inputs an operation asks for, besides the expression. */
export type OperationField = "variable" | "order" | "bounds" | "point" | "side";

export interface Operation {
  /** `null` lets the API detect the operation from the input. */
  intent: IntentName | null;
  label: string;
  placeholder: string;
  fields: readonly OperationField[];
}

/** The operation selector, in display order. */
export const OPERATIONS: readonly Operation[] = [
  { intent: null, label: "Automático", placeholder: "Ex.: 2x + 5 = 17", fields: [] },
  { intent: "arithmetic", label: "Calcular", placeholder: "Ex.: 0.1 + 0.2", fields: [] },
  { intent: "simplify", label: "Simplificar", placeholder: "Ex.: x² + 2x + x²", fields: [] },
  { intent: "factor", label: "Fatorar", placeholder: "Ex.: x² - 4 ou 360", fields: [] },
  { intent: "expand", label: "Expandir", placeholder: "Ex.: (x + 1)^3", fields: [] },
  {
    intent: "solve_equation",
    label: "Resolver equação",
    placeholder: "Ex.: x² - 5x + 6 = 0",
    fields: [],
  },
  {
    intent: "solve_system",
    label: "Resolver sistema",
    placeholder: "Ex.: x + y = 3; x - y = 1",
    fields: [],
  },
  {
    intent: "polynomial_division",
    label: "Dividir polinômios",
    placeholder: "Ex.: (x^3 - 1)/(x - 1)",
    fields: [],
  },
  {
    intent: "derivative",
    label: "Derivar",
    placeholder: "Ex.: x² sen(x)",
    fields: ["variable", "order"],
  },
  {
    intent: "integral",
    label: "Integrar",
    placeholder: "Ex.: x² ou 1/x",
    fields: ["variable", "bounds"],
  },
  {
    intent: "limit",
    label: "Limite",
    placeholder: "Ex.: sen(x)/x",
    fields: ["variable", "point", "side"],
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
  derivative: "Derivada",
  integral: "Integral",
  limit: "Limite",
};

/** What the extra inputs hold; empty texts mean "not given". */
export interface FieldValues {
  variable: string;
  /** Kept as typed; sent as a number when it is an integer. */
  order: string;
  lower: string;
  upper: string;
  point: string;
  side: "both" | "left" | "right";
}

export const EMPTY_FIELDS: FieldValues = {
  variable: "",
  order: "1",
  lower: "",
  upper: "",
  point: "",
  side: "both",
};

export type CalculationOptions = Record<string, string | number>;

/**
 * The `options` sent to the API, only with the fields this operation uses.
 * Nothing is validated here: the API explains what is wrong.
 */
export function buildOptions(operation: Operation, values: FieldValues): CalculationOptions | null {
  const options: CalculationOptions = {};
  for (const field of operation.fields) {
    switch (field) {
      case "variable":
        if (values.variable.trim()) {
          options.variable = values.variable.trim();
        }
        break;
      case "order": {
        const order = Number(values.order.trim());
        options.order = values.order.trim() !== "" && Number.isInteger(order) ? order : values.order;
        break;
      }
      case "bounds":
        if (values.lower.trim()) {
          options.lower = values.lower.trim();
        }
        if (values.upper.trim()) {
          options.upper = values.upper.trim();
        }
        break;
      case "point":
        if (values.point.trim()) {
          options.point = values.point.trim();
        }
        break;
      case "side":
        options.side = values.side;
        break;
    }
  }
  return Object.keys(options).length > 0 ? options : null;
}
