import type { MathResult } from "../types/math";

/** `details` of a graph result (docs/architecture.md, §4). */
export interface GraphFunction {
  label: string;
  latex: string;
  x: number[];
  y: (number | null)[];
}

export interface GraphPoint {
  function: number;
  kind: "root" | "y_intercept";
  x: string;
  y: string;
  x_value: number;
  y_value: number;
  exact: boolean;
}

export interface GraphDetails {
  variable: string;
  x_range: [number, number];
  x_range_text: [string, string];
  y_range: [number, number];
  y_clipped: boolean;
  functions: GraphFunction[];
  points: GraphPoint[];
}

const isNumber = (value: unknown): value is number => typeof value === "number";
const isPair = (value: unknown): value is [number, number] =>
  Array.isArray(value) && value.length === 2 && value.every(isNumber);

function isFunction(value: unknown): value is GraphFunction {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const f = value as Record<string, unknown>;
  return (
    typeof f.label === "string" &&
    typeof f.latex === "string" &&
    Array.isArray(f.x) &&
    f.x.every(isNumber) &&
    Array.isArray(f.y) &&
    f.y.every((y) => y === null || isNumber(y)) &&
    f.x.length === f.y.length
  );
}

function isPoint(value: unknown): value is GraphPoint {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const p = value as Record<string, unknown>;
  return (
    isNumber(p.function) &&
    (p.kind === "root" || p.kind === "y_intercept") &&
    typeof p.x === "string" &&
    typeof p.y === "string" &&
    isNumber(p.x_value) &&
    isNumber(p.y_value) &&
    typeof p.exact === "boolean"
  );
}

/** The graph data of a result, or null if it is not a (well-formed) graph. */
export function graphDetails(result: MathResult): GraphDetails | null {
  if (result.intent !== "graph") {
    return null;
  }
  const d = result.details;
  const ok =
    typeof d.variable === "string" &&
    isPair(d.x_range) &&
    Array.isArray(d.x_range_text) &&
    d.x_range_text.length === 2 &&
    isPair(d.y_range) &&
    typeof d.y_clipped === "boolean" &&
    Array.isArray(d.functions) &&
    d.functions.length > 0 &&
    d.functions.every(isFunction) &&
    Array.isArray(d.points) &&
    d.points.every(isPoint);
  return ok ? (d as unknown as GraphDetails) : null;
}

/** Plotly traces: one line per function (gaps stay gaps), plus the points. */
/** Colors drawn by Plotly itself, outside CSS: they follow the theme (ADR 0019). */
function ink(dark: boolean) {
  return dark
    ? { text: "#e2e8f0", grid: "#334155", axis: "#94a3b8", point: "#f8fafc" }
    : { text: "#0f172a", grid: "#e2e8f0", axis: "#475569", point: "#0f172a" };
}

export function traces(details: GraphDetails, dark = false): object[] {
  const lines = details.functions.map((f) => ({
    type: "scatter",
    mode: "lines",
    x: f.x,
    y: f.y,
    name: `y = ${f.label}`,
    connectgaps: false,
    hovertemplate: `${details.variable} = %{x}<br>y = %{y}<extra></extra>`,
  }));
  if (details.points.length === 0) {
    return lines;
  }
  const several = details.functions.length > 1;
  return [
    ...lines,
    {
      type: "scatter",
      mode: "markers",
      x: details.points.map((p) => p.x_value),
      y: details.points.map((p) => p.y_value),
      text: details.points.map((p) => {
        const what = p.kind === "root" ? "Raiz" : "Intercepto em y";
        const of = several ? ` de y = ${details.functions[p.function]?.label ?? ""}` : "";
        return `${what}${of}: (${p.x}, ${p.y})`;
      }),
      hovertemplate: "%{text}<extra></extra>",
      marker: { size: 9, color: ink(dark).point },
      showlegend: false,
    },
  ];
}

export function layout(details: GraphDetails, dark = false): object {
  const colors = ink(dark);
  const axis = { gridcolor: colors.grid, zerolinecolor: colors.axis, linecolor: colors.axis };
  return {
    margin: { l: 48, r: 12, t: 12, b: 36 },
    xaxis: { range: details.x_range, zeroline: true, title: { text: details.variable }, ...axis },
    yaxis: { range: details.y_range, zeroline: true, ...axis },
    showlegend: details.functions.length > 1,
    // Left-aligned and small: a centered legend was cut on phone screens.
    legend: { orientation: "h", x: 0, xanchor: "left", y: -0.25, font: { size: 11 } },
    hovermode: "closest",
    font: { family: "inherit", color: colors.text },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
  };
}
