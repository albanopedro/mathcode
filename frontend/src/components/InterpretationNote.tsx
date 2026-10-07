import type { Interpretation } from "../types/math";
import { describeInterpretation } from "../utils/interpretation";

/** How a phrase was read: by the local rules, or by an AI model to be checked. */
export function InterpretationNote({ interpretation }: { interpretation: Interpretation }) {
  const text = describeInterpretation(interpretation);
  const read = text.operation !== null || text.expression !== "";

  return (
    <div
      aria-label="Interpretação da frase"
      className={
        text.byAi
          ? "flex flex-col gap-1 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm text-violet-900"
          : "text-sm text-slate-500"
      }
    >
      <p>
        {read ? "Frase interpretada " : "Frase lida "}
        {text.byAi ? "pela " : "pelas "}
        {text.source}
        {text.operation && (
          <>
            {" como "}
            <strong className="font-medium">{text.operation}</strong>
          </>
        )}
        {text.expression && (
          <>
            {": "}
            <code
              className={`rounded px-1.5 py-0.5 font-mono ${text.byAi ? "bg-white/70" : "bg-slate-100 text-slate-700"}`}
            >
              {text.expression}
            </code>
          </>
        )}
        {text.options.length > 0 && ` (${text.options.join(", ")})`}
        {read ? "." : ", sem uma conta para calcular."}
      </p>
      {text.byAi && read && (
        <p>
          A IA só traduziu a frase; o cálculo e a verificação são do Mathcode. Confira se é o
          que você pediu.
        </p>
      )}
    </div>
  );
}
