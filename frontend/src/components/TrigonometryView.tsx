import type { TrigDetails } from "../utils/trigonometry";
import { MathFormula } from "./MathFormula";

interface TrigonometryViewProps {
  details: TrigDetails;
}

const FUNCTION_LATEX: Record<string, string> = {
  sin: "\\sin",
  cos: "\\cos",
  tan: "\\tan",
  sec: "\\sec",
  csc: "\\csc",
  cot: "\\cot",
};

const CELL = "border-b border-slate-100 px-1.5 py-1.5 whitespace-nowrap";

/** What a trigonometry result adds below the headline (ADR 0016). */
export function TrigonometryView({ details }: TrigonometryViewProps) {
  switch (details.calculation) {
    case "reduce":
      return (
        <div className="flex flex-col gap-2 text-sm text-slate-600">
          <p>
            {details.quadrant ? `${details.quadrant}º quadrante` : "Sobre um eixo"}; primeira
            determinação <MathFormula latex={details.first_latex} />
            {details.turns !== 0 &&
              ` (${Math.abs(details.turns)} volta(s) completa(s) ${details.turns > 0 ? "descontada(s)" : "acrescentada(s)"})`}
            {details.quadrant !== null && (
              <>
                ; ângulo de referência <MathFormula latex={details.reference_latex} />
              </>
            )}
            .
          </p>
          <div className="overflow-x-auto">
            <table className="text-left">
              <caption className="sr-only">Valores no ângulo</caption>
              <thead>
                <tr className="text-xs text-slate-500">
                  <th className={CELL}>Função</th>
                  {details.quadrant !== null && <th className={CELL}>Redução</th>}
                  <th className={CELL}>Valor</th>
                </tr>
              </thead>
              <tbody>
                {details.values.map((row) => (
                  <tr key={row.function}>
                    <td className={CELL}>
                      <MathFormula latex={FUNCTION_LATEX[row.function] ?? row.function} />
                    </td>
                    {details.quadrant !== null && (
                      <td className={CELL}>
                        {row.reduced_latex && <MathFormula latex={row.reduced_latex} />}
                      </td>
                    )}
                    <td className={CELL}>
                      {row.latex === null ? "não definida" : <MathFormula latex={row.latex} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );
    case "identity": {
      if (details.holds) {
        return (
          <p className="text-sm text-slate-600">
            {details.proved
              ? "É identidade: vale para todo valor onde os dois lados são definidos."
              : "Nenhum valor testado distingue os lados, mas a igualdade não foi provada."}
          </p>
        );
      }
      const counterexample = details.counterexample;
      if (!counterexample) {
        return null;
      }
      const point = Object.entries(counterexample.point)
        .map(([name, value]) => `${name} = ${value.latex}`)
        .join(",\\ ");
      return (
        <p className="overflow-x-auto text-sm text-slate-600">
          Não é identidade: em <MathFormula latex={point} />, o lado esquerdo vale{" "}
          <MathFormula latex={counterexample.left_latex ?? "?"} /> e o direito{" "}
          <MathFormula latex={counterexample.right_latex ?? "?"} />.
        </p>
      );
    }
    case "triangle":
      return (
        <div className="flex flex-col gap-3 text-sm text-slate-600">
          <p>Pela {details.law}. As medidas informadas estão marcadas com *.</p>
          {details.triangles.map((triangle, index) => (
            <div key={index} className="overflow-x-auto">
              <table className="text-left">
                <caption className="text-left text-xs text-slate-500">
                  {details.triangles.length > 1 ? `Triângulo ${index + 1}` : "Triângulo"}
                </caption>
                <thead>
                  <tr className="text-xs text-slate-500">
                    <th className={CELL}>Lado</th>
                    <th className={CELL}>Ângulo oposto</th>
                  </tr>
                </thead>
                <tbody>
                  {triangle.rows.map((row) => (
                    <tr key={row.side}>
                      <td className={CELL}>
                        <MathFormula latex={`${row.side} = ${row.side_latex}`} />
                        {row.side_given && " *"}
                      </td>
                      <td className={CELL}>
                        <MathFormula
                          latex={`${row.angle} ${row.angle_latex.startsWith("\\approx") ? "" : "= "}${row.angle_latex}`}
                        />
                        {row.angle_given && " *"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      );
    default:
      return null;
  }
}
