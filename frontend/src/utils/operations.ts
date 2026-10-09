import type { IntentName } from "../types/math";

/** Extra inputs an operation asks for, besides the expression. */
export type OperationField =
  | "variable"
  | "order"
  | "bounds"
  | "point"
  | "side"
  | "x_range"
  | "matrix_operation"
  | "vector_operation"
  | "geometry"
  | "probability"
  | "interval"
  | "trig_calculation";

/** What to compute from a matrix expression (ADR 0012), in the order of the field. */
export const MATRIX_OPERATIONS = [
  { value: "determinant", label: "Determinante" },
  { value: "inverse", label: "Inversa" },
  { value: "transpose", label: "Transposta" },
  { value: "trace", label: "Traço" },
  { value: "rank", label: "Posto" },
  { value: "evaluate", label: "Calcular expressão" },
] as const;

export type MatrixOperation = (typeof MATRIX_OPERATIONS)[number]["value"];

/** What to compute from vectors (ADR 0013); dot, cross and angle take two: "u; v". */
export const VECTOR_OPERATIONS = [
  { value: "norm", label: "Norma" },
  { value: "unit", label: "Vetor unitário" },
  { value: "dot", label: "Produto escalar" },
  { value: "cross", label: "Produto vetorial" },
  { value: "angle", label: "Ângulo" },
  { value: "evaluate", label: "Calcular expressão" },
] as const;

export type VectorOperation = (typeof VECTOR_OPERATIONS)[number]["value"];

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
    placeholder: "Ex.: x² - 5x + 6 = 0 ou sin(x) = 1/2",
    fields: ["interval"],
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
  {
    intent: "graph",
    label: "Gráfico",
    placeholder: "Ex.: x² - 4x + 3 ou sen(x); cos(x)",
    fields: ["x_range"],
  },
  {
    intent: "statistics",
    label: "Estatística",
    placeholder: "Ex.: 2, 4, 4, 4, 5, 5, 7, 9",
    fields: [],
  },
  {
    intent: "matrix",
    label: "Matrizes",
    placeholder: "Ex.: [[1, 2], [3, 4]]",
    fields: ["matrix_operation"],
  },
  {
    intent: "vector",
    label: "Vetores",
    placeholder: "Ex.: [1, 2, 3] ou [1, 2, 3]; [4, 5, 6]",
    fields: ["vector_operation"],
  },
  {
    intent: "geometry",
    label: "Geometria",
    placeholder: "Ex.: r = 5 ou b = 4; h = 3",
    fields: ["geometry"],
  },
  {
    intent: "probability",
    label: "Probabilidade",
    placeholder: "Ex.: n = 10; k = 3 ou P(A) = 1/2; P(B) = 1/3",
    fields: ["probability"],
  },
  {
    intent: "trigonometry",
    label: "Trigonometria",
    placeholder: "Ex.: 30°, sin(150°) ou a = 5; b = 7; C = 60°",
    fields: ["trig_calculation"],
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
  graph: "Gráfico",
  statistics: "Estatística",
  matrix: "Matriz",
  vector: "Vetor",
  geometry: "Geometria",
  probability: "Probabilidade",
  trigonometry: "Trigonometria",
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
  x_min: string;
  x_max: string;
  matrix_operation: MatrixOperation;
  vector_operation: VectorOperation;
  /** A figure of utils/geometry.ts and one of its calculations. */
  geometry_figure: string;
  geometry_calculation: string;
  /** A calculation of utils/probability.ts. */
  probability_calculation: string;
  /** A calculation of utils/trigonometry.ts. */
  trig_calculation: string;
}

export const EMPTY_FIELDS: FieldValues = {
  variable: "",
  order: "1",
  lower: "",
  upper: "",
  point: "",
  side: "both",
  x_min: "",
  x_max: "",
  matrix_operation: "determinant",
  vector_operation: "norm",
  geometry_figure: "circle",
  geometry_calculation: "area",
  probability_calculation: "factorial",
  trig_calculation: "convert",
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
      case "interval":
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
      case "matrix_operation":
        options.operation = values.matrix_operation;
        break;
      case "vector_operation":
        options.operation = values.vector_operation;
        break;
      case "geometry":
        options.figure = values.geometry_figure;
        options.calculation = values.geometry_calculation;
        break;
      case "probability":
        options.calculation = values.probability_calculation;
        break;
      case "trig_calculation":
        options.calculation = values.trig_calculation;
        break;
      case "x_range":
        if (values.x_min.trim()) {
          options.x_min = values.x_min.trim();
        }
        if (values.x_max.trim()) {
          options.x_max = values.x_max.trim();
        }
        break;
    }
  }
  return Object.keys(options).length > 0 ? options : null;
}
