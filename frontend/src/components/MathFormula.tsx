import { useEffect, useRef, useState } from "react";

import { katexIfLoaded, loadKatex } from "../utils/katex";

interface MathFormulaProps {
  latex: string;
  display?: boolean;
  className?: string;
}

/**
 * Renders LaTeX with KaTeX into its own element (no innerHTML from React).
 * KaTeX also emits MathML, which is what screen readers read. KaTeX itself is
 * loaded on demand (utils/katex.ts); until then the element is empty and busy.
 */
export function MathFormula({ latex, display = false, className }: MathFormulaProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [katex, setKatex] = useState(katexIfLoaded);

  useEffect(() => {
    if (katex) {
      return;
    }
    let cancelled = false;
    void loadKatex().then((module) => {
      if (!cancelled) {
        setKatex(() => module);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [katex]);

  useEffect(() => {
    if (katex && ref.current) {
      katex.render(latex, ref.current, {
        displayMode: display,
        throwOnError: false,
        output: "htmlAndMathml",
      });
    }
  }, [katex, latex, display]);

  return (
    <span ref={ref} className={className} data-latex={latex} aria-busy={katex ? undefined : true} />
  );
}
