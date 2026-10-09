import { useDisplay } from "../hooks/useDisplay";
import type { MathResult, ResultValue, VerificationReport } from "../types/math";
import { formatApprox, MAX_DIGITS, MIN_DIGITS } from "../utils/approximation";
import { captions } from "../utils/captions";
import { LONG_RESULT_CHARS } from "../utils/display";
import { geometryDetails, QUANTITY_LABELS } from "../utils/geometry";
import { graphDetails } from "../utils/graph";
import { matrixDetails } from "../utils/matrices";
import { vectorDetails } from "../utils/vectors";
import { INTENT_LABELS } from "../utils/operations";
import { probabilityDetails, repeatedLetters } from "../utils/probability";
import { listedLatex, periodicDetails, trigDetails } from "../utils/trigonometry";
import { statisticsDetails } from "../utils/statistics";
import { CopyButtons } from "./CopyButtons";
import { GraphView } from "./GraphView";
import { InterpretationNote } from "./InterpretationNote";
import { MathFormula } from "./MathFormula";
import { StatisticsView } from "./StatisticsView";
import { TrigonometryView } from "./TrigonometryView";
import { Verification } from "./Verification";

interface ResultViewProps {
  result: MathResult;
  value: ResultValue;
  verification: VerificationReport;
}

export function ResultView({ result, value, verification }: ResultViewProps) {
  const lines = captions(result);
  const { display, change } = useDisplay();
  const approximation = value.approx === null ? null : formatApprox(value.approx, display.digits);
  const showApprox = approximation !== null && display.mode === "approx";
  const graph = graphDetails(result);
  const statistics = statisticsDetails(result);
  const matrix = matrixDetails(result);
  const vector = vectorDetails(result);
  const geometry = geometryDetails(result);
  const probability = probabilityDetails(result);
  const periodic = periodicDetails(result);
  const trig = trigDetails(result);
  // Matrices, vectors, periodic solutions and triangles are drawn as formulas however long
  // their text: they are laid out in short lines (columns, or one line per value).
  const asText =
    !matrix &&
    !vector &&
    !periodic &&
    trig?.calculation !== "triangle" &&
    value.plain.length > LONG_RESULT_CHARS;
  const rejected =
    result.intent === "solve_equation" && Array.isArray(result.details.rejected_families)
      ? (result.details.rejected_families as string[])
      : [];

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

      {showApprox ? (
        <p className="overflow-x-auto font-mono text-2xl break-all text-slate-900">
          <span aria-label="aproximadamente">≈</span> {approximation}
        </p>
      ) : asText ? (
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

      {approximation !== null && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <div role="group" aria-label="Forma do resultado" className="flex rounded-lg border border-slate-300">
            {(["exact", "approx"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={display.mode === mode}
                onClick={() => change({ mode })}
                className={`px-3 py-1 first:rounded-l-lg last:rounded-r-lg focus-visible:outline-2 focus-visible:outline-slate-500 ${
                  display.mode === mode ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-50"
                }`}
              >
                {mode === "exact" ? "Exato" : "Aproximado"}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-slate-600">
            Algarismos
            <select
              value={display.digits}
              onChange={(event) => change({ digits: Number(event.target.value) })}
              className="rounded-lg border border-slate-500 bg-white px-2 py-1"
            >
              {Array.from({ length: MAX_DIGITS - MIN_DIGITS + 1 }, (_, i) => MIN_DIGITS + i).map(
                (digits) => (
                  <option key={digits} value={digits}>
                    {digits}
                  </option>
                ),
              )}
            </select>
          </label>
        </div>
      )}

      <CopyButtons value={value} />

      {graph && <GraphView details={graph} />}

      {approximation !== null &&
        (showApprox ? (
          <p className="overflow-x-auto overflow-y-hidden py-1 text-sm text-slate-600">
            Forma exata: <MathFormula latex={value.latex} />
          </p>
        ) : (
          <p className="font-mono text-slate-700">
            <span aria-label="aproximadamente">≈</span> {approximation}
          </p>
        ))}
      {lines.map((line) => (
        <p key={line} className="text-slate-700">
          {line}
        </p>
      ))}

      {periodic && (
        <div className="flex flex-col gap-1 text-sm text-slate-600">
          {periodic.interval &&
            (periodic.solutions_latex.length > 0 ? (
              <p className="overflow-x-auto overflow-y-hidden py-1">
                Em <MathFormula latex={periodic.interval.latex} />:{" "}
                <MathFormula latex={listedLatex(periodic)} />
                {periodic.listed_total > periodic.solutions_latex.length &&
                  ` (${periodic.listed_total} no total; aparecem as ${periodic.solutions_latex.length} primeiras)`}
              </p>
            ) : (
              <p>
                Nenhuma solução em <MathFormula latex={periodic.interval.latex} />.
              </p>
            ))}
          <p>
            {periodic.integer} pode ser qualquer número inteiro (…, −1, 0, 1, 2, …).
          </p>
        </div>
      )}
      {rejected.length > 0 && (
        <p className="overflow-x-auto text-sm text-slate-600">
          Descartado por estar fora do domínio da equação:{" "}
          {rejected.map((latex) => (
            <span key={latex} className="mr-2 inline-block">
              <MathFormula latex={latex} />
            </span>
          ))}
        </p>
      )}
      {trig && <TrigonometryView details={trig} />}
      {statistics && <StatisticsView details={statistics} />}
      {geometry && (
        <div className="flex flex-col gap-1 text-sm text-slate-600">
          {geometry.quantity && <p>Resultado {QUANTITY_LABELS[geometry.quantity]}.</p>}
          {geometry.formula && (
            <p className="overflow-x-auto">
              Fórmula: <MathFormula latex={geometry.formula} />
            </p>
          )}
          {geometry.equation && (
            <p>
              Equação geral: <span className="font-mono text-slate-700">{geometry.equation}</span>
              {geometry.slope && `; inclinação m = ${geometry.slope}`}
            </p>
          )}
        </div>
      )}
      {probability && (
        <div className="flex flex-col gap-1 text-sm text-slate-600">
          {probability.percent && (
            <p className="text-base text-slate-700">
              Em porcentagem: {probability.percent_exact ? "" : "≈ "}
              {probability.percent}
            </p>
          )}
          {repeatedLetters(probability) && (
            <p>Letras repetidas: {repeatedLetters(probability)}.</p>
          )}
          {/* A formula that wraps has roots taller than the line: pad, don't scroll. */}
          <p className="overflow-x-auto overflow-y-hidden py-1">
            Fórmula: <MathFormula latex={probability.formula} />
          </p>
        </div>
      )}
      {vector && vector.operation !== "evaluate" && (
        <p className="overflow-x-auto text-sm text-slate-600">
          {vector.vectors_latex.map((latex, index) => (
            <span key={latex + String(index)} className="mr-3 inline-block">
              <MathFormula latex={`${index === 0 ? "u" : "v"} = ${latex}`} />
            </span>
          ))}
        </p>
      )}
      {matrix && matrix.operation !== "evaluate" && (
        <p className="overflow-x-auto text-sm text-slate-600">
          Matriz A ({matrix.rows}×{matrix.cols}):{" "}
          <MathFormula latex={`A = ${matrix.matrix_latex}`} />
        </p>
      )}

      {result.interpretation && <InterpretationNote interpretation={result.interpretation} />}

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
