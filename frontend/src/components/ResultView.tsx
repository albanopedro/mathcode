import type { MathResult, ResultValue, VerificationReport } from "../types/math";
import { captions } from "../utils/captions";
import { LONG_RESULT_CHARS } from "../utils/display";
import { INTENT_LABELS } from "../utils/operations";
import { MathFormula } from "./MathFormula";
import { Verification } from "./Verification";

interface ResultViewProps {
  result: MathResult;
  value: ResultValue;
  verification: VerificationReport;
}

export function ResultView({ result, value, verification }: ResultViewProps) {
  const lines = captions(result);

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

      {value.plain.length > LONG_RESULT_CHARS ? (
        <div className="flex flex-col gap-1">
          <p className="font-mono text-sm break-all text-slate-800">{value.plain}</p>
          <p className="text-xs text-slate-500">
            Resultado longo ({value.plain.length} caracteres), exibido como texto.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto text-xl">
          <MathFormula latex={value.latex} display />
        </div>
      )}

      {value.approx !== null && (
        <p className="font-mono text-slate-700">
          <span aria-label="aproximadamente">≈</span> {value.approx}
        </p>
      )}
      {lines.map((line) => (
        <p key={line} className="text-slate-700">
          {line}
        </p>
      ))}

      {result.normalized_input && (
        <p className="text-sm text-slate-500">
          Entendido como:{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700">
            {result.normalized_input}
          </code>
        </p>
      )}

      <Verification report={verification} />

      {result.warnings.length > 0 && (
        <ul aria-label="Avisos" className="flex flex-col gap-2">
          {result.warnings.map((warning) => (
            <li
              key={warning.code + warning.message}
              className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-900"
            >
              {warning.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
