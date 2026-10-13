import type { PlanStepResult } from "../types/math";
import { ResultBody } from "./ResultBody";

/**
 * The steps of a compound request (Phase 12, ADR 0021), numbered. Each one is a whole
 * result with its own verification; a step that failed shows why, and the others stay.
 */
export function PlanSteps({ steps }: { steps: PlanStepResult[] }) {
  return (
    <ol aria-label="Passos" className="flex flex-col gap-4">
      {steps.map((step, index) => {
        const { result } = step;
        const id = `plan-step-${index + 1}`;
        return (
          <li
            key={id}
            aria-label={`${index + 1}. ${step.title}`}
            // One after the other: each step enters a little after the one before.
            style={{ animationDelay: `${index * 70}ms` }}
            className="animate-fade-up flex flex-col gap-3 rounded-xl border border-slate-200 p-4"
          >
            <h3 id={id} className="flex items-center gap-2 font-medium text-slate-800">
              <span
                aria-hidden="true"
                className="grid size-6 shrink-0 place-items-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700"
              >
                {index + 1}
              </span>
              <span className="sr-only">{index + 1}. </span>
              {step.title}
            </h3>
            {result.success && result.result && result.verification ? (
              <ResultBody result={result} value={result.result} verification={result.verification} />
            ) : (
              <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-900">
                Não foi possível calcular: {result.error?.message ?? "erro desconhecido."}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
