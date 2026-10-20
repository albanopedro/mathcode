import { useEffect, useState } from "react";

import type { ResultValue } from "../types/math";

type Copied = "text" | "latex" | "failed" | null;

/** Copies the result as text (the syntax of the input) or as LaTeX. */
export function CopyButtons({ value }: { value: ResultValue }) {
  const [copied, setCopied] = useState<Copied>(null);

  useEffect(() => {
    if (copied === null) {
      return;
    }
    const timer = setTimeout(() => setCopied(null), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy(kind: "text" | "latex") {
    try {
      await navigator.clipboard.writeText(kind === "text" ? value.plain : value.latex);
      setCopied(kind);
    } catch {
      setCopied("failed");
    }
  }

  const button = "btn-secondary";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={() => void copy("text")} className={button}>
        Copiar texto
      </button>
      <button type="button" onClick={() => void copy("latex")} className={button}>
        Copiar LaTeX
      </button>
      <output className="text-xs text-slate-500">
        {copied === "text" && "Texto copiado."}
        {copied === "latex" && "LaTeX copiado."}
        {copied === "failed" && "Não foi possível copiar (o navegador bloqueou)."}
      </output>
    </div>
  );
}
