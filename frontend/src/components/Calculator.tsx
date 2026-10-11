import { type FormEvent, useEffect, useRef, useState } from "react";

import { type CalculatorState, useCalculator } from "../hooks/useCalculator";
import { useHistory } from "../hooks/useHistory";
import type { MathResult } from "../types/math";
import { loadEditor, saveEditor } from "../utils/editor";
import type { HistoryEntry } from "../utils/history";
import { latexToInput } from "../utils/latexToInput";
import { LIVE_DELAY_MS, loadLive, saveLive } from "../utils/live";
import {
  buildOptions,
  EMPTY_FIELDS,
  type FieldValues,
  OPERATIONS,
  takesAi,
} from "../utils/operations";
import { ErrorView } from "./ErrorView";
import { HelpText } from "./HelpText";
import { HistoryPanel } from "./HistoryPanel";
import { MathEditor } from "./MathEditor";
import { OperationFields } from "./OperationFields";
import { ResultView } from "./ResultView";

export function Calculator() {
  const [input, setInput] = useState("");
  const [operationIndex, setOperationIndex] = useState(0);
  const [fields, setFields] = useState<FieldValues>(EMPTY_FIELDS);
  const [allowAi, setAllowAi] = useState(false);
  // The visual editor (MathLive) writes the text below; the text is what is sent.
  const [visual, setVisual] = useState(() => loadEditor());
  const [editorKey, setEditorKey] = useState(0); // a new editor starts from the text
  // Live: the result follows the typing after a pause (ADR 0023). Never with the AI.
  const [live, setLive] = useState(() => loadLive());
  const lastRequest = useRef("");
  const operation = OPERATIONS[operationIndex] ?? OPERATIONS[0]!;
  const { state, submit, busy, reset } = useCalculator();
  const history = useHistory();
  const loading = state.status === "loading";
  const canSubmit = input.trim() !== "" && !loading;

  async function run(text: string, index: number, values: FieldValues, ai: boolean) {
    const chosen = OPERATIONS[index] ?? OPERATIONS[0]!;
    // The AI only reads phrases in Automático and Assistente.
    const allow = takesAi(chosen.intent) && ai;
    lastRequest.current = requestKey(text, index, values);
    const result = await submit(text, chosen.intent, buildOptions(chosen, values), allow);
    if (result) {
      history.add({ input: text, intent: chosen.intent, fields: values, allowAi: allow }, result);
    }
  }

  // Live calculation: after the typing pauses, calculate what is there. It is not
  // kept in the history (only Calcular and Enter are) and never sends the AI.
  useEffect(() => {
    if (!live) {
      return;
    }
    if (input.trim() === "") {
      lastRequest.current = "";
      reset();
      return;
    }
    const key = requestKey(input, operationIndex, fields);
    if (key === lastRequest.current) {
      return; // already calculated (a button, Enter or the history did it)
    }
    const timer = window.setTimeout(() => {
      lastRequest.current = key;
      const chosen = OPERATIONS[operationIndex] ?? OPERATIONS[0]!;
      void submit(input, chosen.intent, buildOptions(chosen, fields), false, true);
    }, LIVE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [live, input, operationIndex, fields, submit, reset]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSubmit) {
      void run(input, operationIndex, fields, allowAi);
    }
  }

  /** An example: Automático, no extra fields and no AI, calculated at once. */
  function pick(text: string) {
    setInput(text);
    setEditorKey((key) => key + 1);
    setOperationIndex(0);
    setFields(EMPTY_FIELDS);
    setAllowAi(false);
    void run(text, 0, EMPTY_FIELDS, false);
  }

  /** Fills the form with a past calculation and does it again. */
  function redo(entry: HistoryEntry) {
    const index = Math.max(
      0,
      OPERATIONS.findIndex((option) => option.intent === entry.intent),
    );
    setInput(entry.input);
    setEditorKey((key) => key + 1);
    setOperationIndex(index);
    setFields(entry.fields);
    setAllowAi(entry.allowAi);
    void run(entry.input, index, entry.fields, entry.allowAi);
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
            className="rounded-lg border border-slate-500 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-slate-500 focus:ring-2 focus:ring-slate-200 focus:outline-none"
          >
            {OPERATIONS.map((option, index) => (
              <option key={option.label} value={index}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <OperationFields operation={operation} values={fields} onChange={setFields} />
        <div className="flex items-center justify-between gap-2">
          <label htmlFor={visual ? undefined : "expression"} className="text-sm font-medium text-slate-700">
            Expressão ou equação
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              aria-pressed={live}
              onClick={() => {
                saveLive(!live);
                setLive(!live);
              }}
              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50"
            >
              Ao vivo
            </button>
            <button
              type="button"
              aria-pressed={visual}
              onClick={() => {
                saveEditor(!visual);
                setVisual(!visual);
              }}
              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50"
            >
              Editor visual
            </button>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          {visual ? (
            <div className="min-w-0 flex-1">
              <MathEditor
                key={editorKey}
                initial={input}
                onLatex={(latex) => setInput(latexToInput(latex))}
                onSubmit={() => {
                  if (input.trim() !== "" && !loading) {
                    void run(input, operationIndex, fields, allowAi);
                  }
                }}
              />
            </div>
          ) : (
          <input
            id="expression"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape" && input !== "") {
                event.preventDefault();
                setInput("");
              }
            }}
            placeholder={operation.placeholder}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            aria-describedby="expression-help"
            className="min-w-0 flex-1 rounded-lg border border-slate-500 bg-white px-4 py-3 font-mono text-lg shadow-sm focus:border-slate-500 focus:ring-2 focus:ring-slate-200 focus:outline-none"
          />
          )}
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-lg bg-slate-900 px-6 py-3 font-medium text-white shadow-sm hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {loading ? "Calculando…" : "Calcular"}
          </button>
        </div>
        {visual && (
          <p className="text-sm text-slate-600">
            Será calculado:{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-800">
              {input || "…"}
            </code>
          </p>
        )}
        <HelpText id="expression-help" onPick={pick} />
        {takesAi(operation.intent) && (
          <div className="flex items-start gap-2 text-sm">
            <input
              id="allow-ai"
              type="checkbox"
              checked={allowAi}
              onChange={(event) => setAllowAi(event.target.checked)}
              aria-describedby="allow-ai-help"
              className="mt-0.5 size-4 accent-slate-900"
            />
            <div>
              <label htmlFor="allow-ai" className="font-medium text-slate-700">
                Permitir IA
              </label>
              <p id="allow-ai-help" className="text-slate-500">
                Se as regras locais não entenderem a frase, ela é enviada a um modelo de IA
                gratuito, num serviço externo. A IA só traduz a frase; a conta e a verificação
                são feitas pelo Mathcode.
                {live && " No modo ao vivo a IA não é usada: aperte Calcular para ela entrar."}
              </p>
            </div>
          </div>
        )}
      </form>

      {/* A short announcement for screen readers; the result itself is not read aloud whole. */}
      <p role="status" className="sr-only">
        {announcement(state)}
      </p>
      <div id="result-area" tabIndex={-1} aria-busy={loading} className="focus:outline-none">
        {loading && <p className="text-slate-500">Calculando…</p>}
        {state.status === "done" &&
          (state.live && !state.result.success ? (
            <LiveHint result={state.result} />
          ) : (
            <div
              className={`transition-opacity duration-200 motion-reduce:transition-none ${busy ? "opacity-60" : ""}`}
            >
              <Outcome result={state.result} />
            </div>
          ))}
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

      <HistoryPanel
        entries={history.entries}
        onRedo={redo}
        onRemove={history.remove}
        onClear={history.clear}
      />
    </div>
  );
}

/** What a live calculation says when the input is not (yet) a calculation: a hint, not an alert. */
function LiveHint({ result }: { result: MathResult }) {
  return (
    <p className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
      Ainda não dá para calcular: {result.error?.message}
    </p>
  );
}

/** Same calculation, same key: used so that live mode does not repeat what was just done. */
function requestKey(text: string, index: number, values: FieldValues): string {
  return JSON.stringify([text, index, values]);
}

function announcement(state: CalculatorState): string {
  switch (state.status) {
    case "loading":
      return "Calculando…";
    case "failed":
      return `Erro: ${state.message}`;
    case "done": {
      const result = state.result;
      if (state.live && !result.success) {
        return ""; // a hint while typing is not an error to announce
      }
      if (result.success && result.result) {
        const verification = result.verification ? ` ${result.verification.message}` : "";
        return `Resultado: ${result.result.plain}.${verification}`;
      }
      return `Erro: ${result.error?.message ?? "não foi possível calcular."}`;
    }
    default:
      return "";
  }
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
