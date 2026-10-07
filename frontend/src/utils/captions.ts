import type { MathResult } from "../types/math";
import { graphDetails } from "./graph";

const MULTIPLICITY_NAMES: Record<number, string> = { 2: "dupla", 3: "tripla", 4: "quádrupla" };

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

const numbers = (value: unknown): number[] =>
  Array.isArray(value) ? value.filter((item): item is number => typeof item === "number") : [];

/**
 * Sentences that explain a successful result in words, built only from what
 * the API returned in `details` (nothing is computed here).
 */
export function captions(result: MathResult): string[] {
  const details = result.details;
  const lines: string[] = [];

  switch (result.intent) {
    case "solve_equation": {
      const variable = typeof details.variable === "string" ? details.variable : "x";
      const excluded = strings(details.excluded);
      if (details.solution_set === "none") {
        lines.push("A equação não tem solução real.");
      } else if (details.solution_set === "all_reals") {
        lines.push(
          excluded.length > 0
            ? `Todo número real é solução, exceto ${variable} = ${excluded.join(", ")}, onde a equação não é definida.`
            : "Todo número real é solução: os dois lados são sempre iguais.",
        );
      }
      const solutions = strings(details.solutions);
      numbers(details.multiplicities).forEach((multiplicity, index) => {
        if (multiplicity > 1 && solutions[index] !== undefined) {
          const name = MULTIPLICITY_NAMES[multiplicity] ?? `de multiplicidade ${multiplicity}`;
          lines.push(`Raiz ${name}: ${variable} = ${solutions[index]}.`);
        }
      });
      break;
    }
    case "solve_system": {
      const free = strings(details.free_variables);
      if (details.solution_set === "none") {
        lines.push("O sistema não tem solução.");
      } else if (details.solution_set === "infinite") {
        lines.push(
          free.length === 1
            ? `Infinitas soluções: ${free[0]} pode assumir qualquer valor real.`
            : `Infinitas soluções: ${free.join(", ")} podem assumir quaisquer valores reais.`,
        );
      }
      break;
    }
    case "factor":
      if (details.changed === false) {
        lines.push("Não há fatoração sobre os racionais além desta forma.");
      }
      break;
    case "expand":
      if (details.changed === false) {
        lines.push("A expressão já está expandida.");
      }
      break;
    case "simplify":
      if (details.changed === false) {
        lines.push("Não foi encontrada uma forma mais simples.");
      }
      break;
    case "polynomial_division":
      if (details.exact === true) {
        lines.push("A divisão é exata: o resto é 0.");
      }
      break;
    case "derivative": {
      const variable = text(details.variable, "x");
      const order = typeof details.order === "number" ? details.order : 1;
      lines.push(
        order === 1
          ? `Derivada em relação a ${variable}.`
          : `Derivada de ordem ${order} em relação a ${variable}.`,
      );
      break;
    }
    case "integral": {
      const variable = text(details.variable, "x");
      if (details.definite === true) {
        lines.push(
          `Integral de ${text(details.lower, "?")} a ${text(details.upper, "?")} em relação a ${variable}.`,
        );
        if (details.converges === false) {
          lines.push("A integral diverge.");
        }
      } else {
        lines.push(`Primitiva em relação a ${variable}; C é uma constante qualquer.`);
      }
      break;
    }
    case "graph": {
      const graph = graphDetails(result);
      if (!graph) {
        break;
      }
      const [from, to] = graph.x_range_text;
      lines.push(`${graph.variable} de ${from} a ${to}.`);
      graph.functions.forEach((f, index) => {
        const of = graph.functions.length > 1 ? ` de y = ${f.label}` : "";
        const points = graph.points.filter((p) => p.function === index);
        const roots = points.filter((p) => p.kind === "root").map((p) => `${graph.variable} = ${p.x}`);
        if (roots.length > 0) {
          lines.push(`${roots.length === 1 ? "Raiz" : "Raízes"}${of}: ${roots.join("; ")}.`);
        }
        const intercept = points.find((p) => p.kind === "y_intercept");
        if (intercept) {
          lines.push(`Intercepto em y${of}: (0, ${intercept.y}).`);
        }
      });
      break;
    }
    case "limit": {
      const variable = text(details.variable, "x");
      const point = text(details.point, "?");
      const side = SIDE_WORDS[text(details.side, "both")] ?? "";
      if (details.exists === false) {
        if (details.oscillates === true) {
          lines.push(`O limite não existe: a função oscila perto de ${variable} = ${point}.`);
        } else if (typeof details.left === "string" && typeof details.right === "string") {
          lines.push(
            `O limite não existe: pela esquerda tende a ${details.left} e pela direita a ${details.right}.`,
          );
        } else {
          lines.push("O limite não existe.");
        }
      } else {
        lines.push(`Limite quando ${variable} → ${point}${side}.`);
      }
      break;
    }
  }
  return lines;
}

const SIDE_WORDS: Record<string, string> = {
  both: "",
  left: " pela esquerda",
  right: " pela direita",
};

const text = (value: unknown, fallback: string): string =>
  typeof value === "string" ? value : fallback;
