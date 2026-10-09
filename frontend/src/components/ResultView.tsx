import type { MathResult, ResultValue, VerificationReport } from "../types/math";
import { INTENT_LABELS } from "../utils/operations";
import { InterpretationNote } from "./InterpretationNote";
import { PlanSteps } from "./PlanSteps";
import { ResultBody } from "./ResultBody";
import { Verification } from "./Verification";

interface ResultViewProps {
  result: MathResult;
  value: ResultValue;
  verification: VerificationReport;
}

export function ResultView({ result, value, verification }: ResultViewProps) {
  const plan = result.plan.length > 0;
  return (
    <section
      aria-labelledby="result-title"
      className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id="result-title" className="text-sm font-medium text-slate-500">
          Resultado
        </h2>
        {result.intent && (
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
            {INTENT_LABELS[result.intent]}
          </span>
        )}
      </div>
      {plan ? (
        <>
          <p className="text-slate-700">{planSummary(result)}</p>
          {result.interpretation && <InterpretationNote interpretation={result.interpretation} />}
          <PlanSteps steps={result.plan} />
          <Verification report={verification} />
        </>
      ) : (
        <ResultBody result={result} value={value} verification={verification} />
      )}
    </section>
  );
}

/** "3 de 3 passos calculados, para f = x^2 - 4x + 3." */
function planSummary(result: MathResult): string {
  const { steps, calculated, function: f } = result.details;
  const total = typeof steps === "number" ? steps : result.plan.length;
  const done = typeof calculated === "number" ? calculated : total;
  const about = typeof f === "string" && f !== "" ? `, para f = ${f}` : "";
  return `${done} de ${total} passos calculados${about}.`;
}
