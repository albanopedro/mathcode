import type { StatisticsDetails } from "../utils/statistics";
import { MathFormula } from "./MathFormula";

/** Every measure of the summary; the one asked for is highlighted. */
export function StatisticsView({ details }: { details: StatisticsDetails }) {
  const frequencyAsked = details.measure === "frequency";
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
                  className={`border-t border-slate-100 ${asked ? "bg-indigo-50 font-medium" : ""}`}
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
        {details.weighted ? "Dados agrupados" : "Dados em ordem"} (n = {details.count}):{" "}
        <span className="font-mono text-slate-700">
          {details.weighted
            ? details.frequency.map((row) => `${row.value} (×${row.frequency})`).join("; ")
            : details.sorted.join("; ")}
        </span>
      </p>
      <section
        aria-label="Tabela de frequências"
        aria-current={frequencyAsked ? "true" : undefined}
        className={`overflow-x-auto rounded ${
          frequencyAsked ? "bg-indigo-50 p-2 ring-1 ring-indigo-200" : ""
        }`}
      >
        <h3 className="mb-1 text-sm font-medium text-slate-700">Tabela de frequências</h3>
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Tabela de frequências</caption>
          <thead className="text-xs text-slate-500">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">
                Valor
              </th>
              <th scope="col" className="py-1 pr-3 font-medium">
                Frequência
              </th>
              <th scope="col" className="py-1 pr-3 font-medium">
                Relativa
              </th>
              <th scope="col" className="py-1 font-medium">
                Acumulada
              </th>
            </tr>
          </thead>
          <tbody>
            {details.frequency.map((row) => (
              <tr key={row.value} className="border-t border-slate-100">
                <th
                  scope="row"
                  className="py-1.5 pr-3 text-left font-mono font-normal text-slate-900"
                >
                  {row.value}
                </th>
                <td className="py-1.5 pr-3 text-slate-900">{row.frequency}</td>
                <td className="py-1.5 pr-3 font-mono text-slate-900">{row.relative}</td>
                <td className="py-1.5 text-slate-900">{row.cumulative}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
