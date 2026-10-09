import { useEffect, useRef, useState } from "react";

import { useIsDark } from "../hooks/useTheme";
import { type GraphDetails, layout, traces } from "../utils/graph";

/**
 * Draws the graph with Plotly. Plotly (~1 MB) is loaded only when the first
 * graph appears, so the page itself stays light (ADR 0008).
 */
export function GraphView({ details }: { details: GraphDetails }) {
  const element = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const dark = useIsDark();

  useEffect(() => {
    let cancelled = false;
    let drawn: HTMLDivElement | null = null;
    let purge: ((target: HTMLElement) => void) | null = null;

    import("plotly.js-basic-dist-min")
      .then(async ({ default: Plotly }) => {
        if (cancelled || !element.current) {
          return;
        }
        drawn = element.current;
        purge = Plotly.purge;
        await Plotly.newPlot(drawn, traces(details, dark), layout(details, dark), {
          responsive: true,
          displaylogo: false,
          // "Share chart" uploads the graph to Plotly's cloud (Chart Studio), and it
          // is on by default in Plotly 4: off, by ADR 0001 (no external services).
          showSendToCloud: false,
          modeBarButtonsToRemove: ["select2d", "lasso2d", "sendChartToCloud"],
        });
        if (!cancelled) {
          setStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("failed");
        }
      });

    return () => {
      cancelled = true;
      if (drawn && purge) {
        purge(drawn);
      }
    };
  }, [details, dark]);

  return (
    <figure className="flex flex-col gap-1">
      {status === "loading" && <p className="text-sm text-slate-500">Carregando o gráfico…</p>}
      {status === "failed" && (
        <p role="alert" className="text-sm text-rose-700">
          Não foi possível carregar o gráfico.
        </p>
      )}
      <div
        ref={element}
        data-testid="graph"
        role="img"
        aria-label={`Gráfico de ${details.functions.map((f) => `y = ${f.label}`).join(", ")}`}
        className="h-80 w-full sm:h-96"
      />
    </figure>
  );
}
