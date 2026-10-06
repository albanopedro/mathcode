import type { MathResult } from "../types/math";

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
  }
  return lines;
}
