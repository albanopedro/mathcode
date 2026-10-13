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
  FEATURED,
  type FieldValues,
  indexOfOperation,
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
    const index = indexOfOperation(entry.intent);
    setInput(entry.input);
    setEditorKey((key) => key + 1);
    setOperationIndex(index);
    setFields(entry.fields);
    setAllowAi(entry.allowAi);
    void run(entry.input, index, entry.fields, entry.allowAi);
  }

  const featured = FEATURED.some((option) => indexOfOperation(option.intent) === operationIndex);

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="card flex flex-col gap-5 p-4 sm:p-6">
        <div className="flex flex-col gap-2">
          <p aria-hidden="true" className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Operação
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <div role="radiogroup" aria-label="Operações frequentes" className="flex flex-wrap gap-2">
              {FEATURED.map((option) => {
                const index = indexOfOperation(option.intent);
                const on = index === operationIndex;
                return (
                  <label
                    key={option.label}
                    className={`pill has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-indigo-600 ${on ? "pill-on" : "pill-off"}`}
                  >
                    <input
                      type="radio"
                      name="featured-operation"
                      checked={on}
                      onChange={() => setOperationIndex(index)}
                      className="sr-only"
                    />
                    {option.label}
                  </label>
                );
              })}
            </div>
            {/* Every operation, the featured ones too: "Mais operações" when one of those is on. */}
            <span className="relative inline-flex">
              <select
                id="operation"
                aria-label="Operação"
                value={featured ? "" : operationIndex}
                onChange={(event) => setOperationIndex(Number(event.target.value))}
                className={`pill appearance-none pr-8 ${featured ? "pill-off" : "pill-on"}`}
              >
                <option value="" disabled hidden>
                  Mais operações…
                </option>
                {OPERATIONS.map((option, index) => (
                  <option key={option.label} value={index} className="bg-white text-slate-900">
                    {option.label}
                  </option>
                ))}
              </select>
              <svg
                aria-hidden="true"
                viewBox="0 0 20 20"
                className={`pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 ${featured ? "text-slate-500" : "text-white"}`}
              >
                <path fill="currentColor" d="M5.3 7.3a1 1 0 0 1 1.4 0L10 10.6l3.3-3.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 0 1 0-1.4Z" />
              </svg>
            </span>
          </div>
        </div>
        <OperationFields operation={operation} values={fields} onChange={setFields} />
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label
              htmlFor={visual ? undefined : "expression"}
              className="text-xs font-semibold tracking-wide text-slate-500 uppercase"
            >
              Expressão ou equação
            </label>
            <div className="flex gap-2">
              <Switch
                on={live}
                label="Ao vivo"
                onClick={() => {
                  saveLive(!live);
                  setLive(!live);
                }}
              />
              <Switch
                on={visual}
                label="Editor visual"
                onClick={() => {
                  saveEditor(!visual);
                  setVisual(!visual);
                }}
              />
            </div>
          </div>
          {visual ? (
            <div className="flex flex-col gap-2 sm:flex-row">
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
              <SubmitButton disabled={!canSubmit} loading={loading} />
            </div>
          ) : (
            // The field and its button in one box, like a search bar: the box shows the focus.
            <div className="flex flex-col gap-2 rounded-2xl border border-slate-500 bg-white p-1.5 shadow-sm transition focus-within:border-indigo-600 focus-within:ring-4 focus-within:ring-indigo-100 sm:flex-row">
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
                className="min-w-0 flex-1 bg-transparent px-3 py-2.5 font-mono text-lg text-slate-900 placeholder:text-slate-500 focus-visible:outline-none"
              />
              <SubmitButton disabled={!canSubmit} loading={loading} />
            </div>
          )}
          {visual && (
            <p className="text-sm text-slate-600">
              Será calculado:{" "}
              <code className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-slate-800">
                {input || "…"}
              </code>
            </p>
          )}
        </div>
        <HelpText id="expression-help" onPick={pick} />
        {takesAi(operation.intent) && (
          <div className="flex items-start gap-2.5 rounded-xl bg-slate-50 p-3 text-sm">
            <input
              id="allow-ai"
              type="checkbox"
              checked={allowAi}
              onChange={(event) => setAllowAi(event.target.checked)}
              aria-describedby="allow-ai-help"
              className="mt-0.5 size-4 accent-indigo-600"
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
        {loading && <ResultSkeleton />}
        {state.status === "done" &&
          (state.live && !state.result.success ? (
            <LiveHint result={state.result} />
          ) : (
            // A new key per result: each one enters with the short animation.
            <div
              key={state.seq}
              className={`animate-fade-up transition-opacity duration-200 ${busy ? "opacity-60" : ""}`}
            >
              <Outcome result={state.result} />
            </div>
          ))}
        {state.status === "failed" && (
          <div
            role="alert"
            className="animate-fade-up rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-900"
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

/** A switch shown as a small pill with a light: on (aria-pressed) or off. */
function Switch({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`pill px-2.5 py-1 text-xs ${on ? "border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100" : "pill-off"}`}
    >
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full transition ${on ? "bg-indigo-600" : "bg-slate-400"}`}
      />
      {label}
    </button>
  );
}

function SubmitButton({ disabled, loading }: { disabled: boolean; loading: boolean }) {
  return (
    <button type="submit" disabled={disabled} className="btn-primary">
      {loading ? "Calculando…" : "Calcular"}
      {!loading && (
        <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4">
          <path
            fill="currentColor"
            d="M10.3 4.3a1 1 0 0 1 1.4 0l5 5a1 1 0 0 1 0 1.4l-5 5a1 1 0 0 1-1.4-1.4l3.3-3.3H4a1 1 0 1 1 0-2h9.6l-3.3-3.3a1 1 0 0 1 0-1.4Z"
          />
        </svg>
      )}
    </button>
  );
}

/** While the first result is on its way: the shape of a result card, pulsing gently. */
function ResultSkeleton() {
  return (
    <div className="card flex flex-col gap-4 p-5 sm:p-6">
      <p className="text-sm text-slate-500">Calculando…</p>
      <div aria-hidden="true" className="flex animate-pulse flex-col gap-3 motion-reduce:animate-none">
        <div className="mx-auto h-8 w-1/2 rounded-lg bg-slate-100" />
        <div className="h-12 rounded-xl bg-slate-100" />
      </div>
    </div>
  );
}

/** What a live calculation says when the input is not (yet) a calculation: a hint, not an alert. */
function LiveHint({ result }: { result: MathResult }) {
  return (
    <p className="animate-fade-up rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-sm text-slate-600">
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
