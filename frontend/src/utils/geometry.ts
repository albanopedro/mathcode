import type { MathResult } from "../types/math";

/**
 * The figures of the Geometria operation, as in the backend's catalog
 * (math_engine/geometry.py, ADR 0014): what each one computes and which
 * measures it takes.
 */
export interface FigureOption {
  value: string;
  label: string;
  group: string;
  calculations: { value: string; label: string }[];
  /** The measures, as shown under the fields. */
  measures: string;
  example: string;
}

const AREA = { value: "area", label: "Área" };
const PERIMETER = { value: "perimeter", label: "Perímetro" };
const VOLUME = { value: "volume", label: "Volume" };
const SURFACE = { value: "surface_area", label: "Área da superfície" };

const PLANE = "Figuras planas";
const SOLIDS = "Sólidos";
const TRIANGLES = "Triângulos";
const ANALYTIC = "Geometria analítica";

export const FIGURES: readonly FigureOption[] = [
  {
    value: "circle",
    label: "Círculo",
    group: PLANE,
    calculations: [AREA, { value: "perimeter", label: "Circunferência" }],
    measures: "r (raio) ou d (diâmetro)",
    example: "r = 5",
  },
  {
    value: "square",
    label: "Quadrado",
    group: PLANE,
    calculations: [AREA, PERIMETER],
    measures: "l (lado)",
    example: "l = 4",
  },
  {
    value: "rectangle",
    label: "Retângulo",
    group: PLANE,
    calculations: [AREA, PERIMETER],
    measures: "b (base) e h (altura)",
    example: "b = 4; h = 3",
  },
  {
    value: "triangle",
    label: "Triângulo",
    group: PLANE,
    calculations: [AREA, PERIMETER, { value: "classify", label: "Classificação" }],
    measures: "a, b, c (lados) ou, para a área, b (base) e h (altura)",
    example: "a = 3; b = 4; c = 5",
  },
  {
    value: "trapezoid",
    label: "Trapézio",
    group: PLANE,
    calculations: [AREA],
    measures: "B (base maior), b (base menor) e h (altura)",
    example: "B = 6; b = 4; h = 3",
  },
  {
    value: "rhombus",
    label: "Losango",
    group: PLANE,
    calculations: [AREA, PERIMETER],
    measures: "D (diagonal maior) e d (diagonal menor)",
    example: "D = 6; d = 8",
  },
  {
    value: "parallelogram",
    label: "Paralelogramo",
    group: PLANE,
    calculations: [AREA, PERIMETER],
    measures: "b (base) e h (altura) para a área; a e b (lados) para o perímetro",
    example: "b = 5; h = 2",
  },
  {
    value: "cube",
    label: "Cubo",
    group: SOLIDS,
    calculations: [VOLUME, SURFACE],
    measures: "a (aresta)",
    example: "a = 3",
  },
  {
    value: "box",
    label: "Paralelepípedo",
    group: SOLIDS,
    calculations: [VOLUME, SURFACE],
    measures: "a (comprimento), b (largura) e c (altura)",
    example: "a = 2; b = 3; c = 4",
  },
  {
    value: "sphere",
    label: "Esfera",
    group: SOLIDS,
    calculations: [VOLUME, SURFACE],
    measures: "r (raio)",
    example: "r = 3",
  },
  {
    value: "cylinder",
    label: "Cilindro",
    group: SOLIDS,
    calculations: [VOLUME, SURFACE],
    measures: "r (raio) e h (altura)",
    example: "r = 2; h = 5",
  },
  {
    value: "cone",
    label: "Cone",
    group: SOLIDS,
    calculations: [VOLUME, SURFACE],
    measures: "r (raio) e h (altura)",
    example: "r = 3; h = 4",
  },
  {
    value: "right_triangle",
    label: "Triângulo retângulo (Pitágoras)",
    group: TRIANGLES,
    calculations: [{ value: "missing_side", label: "Lado que falta" }],
    measures: "dois de a, b (catetos) e c (hipotenusa)",
    example: "a = 3; b = 4",
  },
  {
    value: "points",
    label: "Pontos",
    group: ANALYTIC,
    calculations: [
      { value: "distance", label: "Distância" },
      { value: "midpoint", label: "Ponto médio" },
      { value: "line", label: "Reta por dois pontos" },
      { value: "polygon_area", label: "Área do polígono" },
    ],
    measures: "pontos entre parênteses, separados por ';'",
    example: "(1, 2); (4, 6)",
  },
];

export const FIGURE_GROUPS = [PLANE, SOLIDS, TRIANGLES, ANALYTIC] as const;

export function figure(value: string): FigureOption {
  return FIGURES.find((option) => option.value === value) ?? FIGURES[0]!;
}

/** `details` of a geometry result (docs/architecture.md, §4). */
export interface GeometryDetails {
  figure: string;
  calculation: string;
  measures: Record<string, string>;
  points: string[];
  formula: string | null;
  quantity: "length" | "area" | "volume" | null;
  equation?: string;
  slope?: string | null;
}

export function geometryDetails(result: MathResult): GeometryDetails | null {
  if (result.intent !== "geometry") {
    return null;
  }
  const d = result.details;
  const valid =
    typeof d.figure === "string" &&
    typeof d.calculation === "string" &&
    typeof d.measures === "object" &&
    d.measures !== null &&
    Array.isArray(d.points) &&
    (d.formula === null || typeof d.formula === "string");
  return valid ? (d as unknown as GeometryDetails) : null;
}

export const QUANTITY_LABELS = {
  length: "em unidades de comprimento",
  area: "em unidades de área",
  volume: "em unidades de volume",
} as const;
