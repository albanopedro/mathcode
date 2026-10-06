import { type FormEvent, useState } from "react";

import { useCalculator } from "../hooks/useCalculator";
import type { MathResult } from "../types/math";
import { OPERATIONS } from "../utils/operations";
import { ErrorView } from "./ErrorView";
import { ResultView } from "./ResultView";

export function Calculator() {
  const [input, setInput] = useState("");
  const [operationIndex, setOperationIndex] = useState(0);
  const operation = OPERATIONS[operationIndex] ?? OPERATIONS[0]!;
  const { state, submit } = useCalculator();
  const loading = state.status === "loading";
  const canSubmit = input.trim() !== "" && !loading;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSubmit) {
      void submit(input, operation.intent);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <label htmlFor="operation" className="text-sm font-medium text-slate-700">
            Operação
          </label>
          <select
            id="operation"
            value={operationIndex}
            onChange={(event) => setOperationIndex(Number(event.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-slate-500 focus:ring-2 focus:ring-slate-200 focus:outline-none"
          >
            {OPERATIONS.map((option, index) => (
              <option key={option.label} value={index}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <label htmlFor="expression" className="text-sm font-medium text-slate-700">
          Expressão ou equação
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id="expression"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={operation.placeholder}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            aria-describedby="expression-help"
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-4 py-3 font-mono text-lg shadow-sm focus:border-slate-500 focus:ring-2 focus:ring-slate-200 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-lg bg-slate-900 px-6 py-3 font-medium text-white shadow-sm hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {loading ? "Calculando…" : "Calcular"}
          </button>
        </div>
        <p id="expression-help" className="text-sm text-slate-500">
          Use ^ para potência, sqrt(x) ou √ para raiz e ° para graus. Separe argumentos
          e as equações de um sistema com ;, como em log(8; 2) ou x + y = 3; x - y = 1.
        </p>
      </form>

      <div aria-live="polite" aria-busy={loading}>
        {loading && <p className="text-slate-500">Calculando…</p>}
        {state.status === "done" && <Outcome result={state.result} />}
        {state.status === "failed" && (
          <div
            role="alert"
            className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-rose-900"
          >
            <h2 className="font-medium">Não foi possível calcular</h2>
            <p>{state.message}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function Outcome({ result }: { result: MathResult }) {
  if (result.success && result.result && result.verification) {
    return <ResultView result={result} value={result.result} verification={result.verification} />;
  }
  if (result.error) {
    return <ErrorView result={result} error={result.error} />;
  }
  return null;
}
