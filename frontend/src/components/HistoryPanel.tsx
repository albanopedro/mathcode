import { useState } from "react";

import type { HistoryEntry } from "../utils/history";
import { INTENT_LABELS } from "../utils/operations";

interface HistoryPanelProps {
  entries: HistoryEntry[];
  onRedo: (entry: HistoryEntry) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
}

const TIME = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

/** The last calculations, kept only in this browser. */
export function HistoryPanel({ entries, onRedo, onRemove, onClear }: HistoryPanelProps) {
  const [confirming, setConfirming] = useState(false);

  return (
    <details className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <summary className="cursor-pointer font-medium text-slate-700">
        Histórico ({entries.length})
      </summary>
      <p className="mt-2 text-xs text-slate-500">
        Guardado só neste navegador (os últimos 50); nada é enviado ao servidor.
      </p>
      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">Nenhum cálculo ainda.</p>
      ) : (
        <>
          <ul aria-label="Cálculos anteriores" className="mt-3 flex flex-col gap-2">
            {entries.map((entry) => (
              <li
                key={entry.id}
                className="flex items-start gap-2 rounded-lg border border-slate-100 p-2"
              >
                <button
                  type="button"
                  onClick={() => onRedo(entry)}
                  className="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left focus-visible:outline-2 focus-visible:outline-slate-500"
                  aria-label={`Refazer: ${entry.input}`}
                >
                  <span className="max-w-full truncate font-mono text-sm text-slate-800">
                    {entry.input}
                  </span>
                  <span
                    className={`max-w-full truncate text-xs ${entry.success ? "text-slate-600" : "text-rose-700"}`}
                  >
                    {entry.success ? "= " : "Erro: "}
                    {entry.summary}
                  </span>
                  <span className="text-xs text-slate-500">
                    {entry.intent ? INTENT_LABELS[entry.intent] : "Automático"} ·{" "}
                    {TIME.format(new Date(entry.at))}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onRemove(entry.id)}
                  aria-label={`Apagar do histórico: ${entry.input}`}
                  className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-2 focus-visible:outline-slate-500"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex gap-2 text-sm">
            {confirming ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    onClear();
                    setConfirming(false);
                  }}
                  className="rounded-lg bg-rose-700 px-3 py-1.5 font-medium text-white hover:bg-rose-800"
                >
                  Confirmar: apagar tudo
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50"
                >
                  Cancelar
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50"
              >
                Limpar histórico
              </button>
            )}
          </div>
        </>
      )}
    </details>
  );
}
