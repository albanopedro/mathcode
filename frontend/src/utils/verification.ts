import type { CheckKind, CheckOutcome } from "../types/math";

/** The strategy of each check, as shown next to it (ADR 0010). */
export const KIND_LABELS: Record<CheckKind, string> = {
  symbolic: "Simbólica",
  substitution: "Substituição",
  numeric: "Numérica",
  comparison: "Comparação de métodos",
  completeness: "Completude",
  domain: "Domínio",
  execution: "Execução",
};

/** Icon (visual) and words (screen readers) for each outcome. */
export const OUTCOMES: Record<CheckOutcome, { icon: string; label: string }> = {
  passed: { icon: "✓", label: "Passou" },
  failed: { icon: "✗", label: "Falhou" },
  inconclusive: { icon: "?", label: "Inconclusiva" },
};
