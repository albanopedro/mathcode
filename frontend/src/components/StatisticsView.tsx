import type { StatisticsDetails } from "../utils/statistics";
import { MathFormula } from "./MathFormula";

/** Every measure of the summary; the one asked for is highlighted. */
export function StatisticsView({ details }: { details: StatisticsDetails }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Resumo estatístico</caption>
          <thead className="text-xs text-slate-500">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">
                Medida
              </th>
              <th scope="col" className="py-1 pr-3 font-medium">
                Valor
              </th>
              <th scope="col" className="py-1 font-medium">
                Aproximado
              </th>
            </tr>
          </thead>
          <tbody>
            {details.measures.map((measure) => {
              const asked = measure.name === details.measure;
              return (
                <tr
                  key={measure.name}
                  aria-current={asked ? "true" : undefined}
                  className={`border-t border-slate-100 ${asked ? "bg-sky-50 font-medium" : ""}`}
                >
                  <th scope="row" className="py-1.5 pr-3 font-normal text-slate-700">
                    {measure.label} <MathFormula latex={`(${measure.symbol})`} />
                  </th>
                  <td className="py-1.5 pr-3 text-slate-900">
                    {measure.latex === null ? (
                      <span title="Não definido para estes dados">—</span>
                    ) : (
                      <MathFormula latex={measure.latex} />
                    )}
                  </td>
                  <td className="py-1.5 font-mono text-slate-600">
                    {measure.approx === null ? "" : `≈\u00a0${measure.approx}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-sm break-words text-slate-500">
        Dados em ordem (n = {details.count}):{" "}
        <span className="font-mono text-slate-700">{details.sorted.join("; ")}</span>
      </p>
    </div>
  );
}
