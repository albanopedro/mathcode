import { useState } from "react";

import { EXAMPLES } from "../utils/examples";

interface HelpTextProps {
  id: string;
  /** Clicking an example calculates it: the form is filled and the calculation done. */
  onPick: (text: string) => void;
}

/** One short line, and clickable examples by subject (ADR 0024). */
export function HelpText({ id, onPick }: HelpTextProps) {
  // Open the first time, so a new user sees what to try; the choice is theirs after that.
  const [open, setOpen] = useState(true);
  return (
    <div className="text-sm text-slate-500">
      <p id={id}>
        Use ^ para potência, √ ou sqrt(x) para raiz, ° para graus e ; para separar; frases
        simples também funcionam.
      </p>
      <details
        open={open}
        onToggle={(event) => setOpen(event.currentTarget.open)}
        className="mt-1"
      >
        <summary className="cursor-pointer text-slate-600">Exemplos (clique para calcular)</summary>
        <ul aria-label="Exemplos" className="mt-2 grid gap-2 sm:grid-cols-2">
          {EXAMPLES.map((example) => (
            <li key={example.subject}>
              <button
                type="button"
                onClick={() => {
                  setOpen(false); // out of the way: the result appears right below
                  onPick(example.text);
                }}
                className="flex h-full w-full flex-col items-start gap-0.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-left shadow-sm transition duration-150 hover:-translate-y-0.5 hover:border-slate-500 hover:shadow motion-reduce:transition-none motion-reduce:hover:translate-y-0"
              >
                <span className="text-xs font-medium text-slate-500">{example.subject}</span>
                <span className="font-mono text-slate-800">{example.text}</span>
              </button>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
