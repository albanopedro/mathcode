import katex from "katex";
import { useEffect, useRef } from "react";

interface MathFormulaProps {
  latex: string;
  display?: boolean;
  className?: string;
}

/**
 * Renders LaTeX with KaTeX into its own element (no innerHTML from React).
 * KaTeX also emits MathML, which is what screen readers read.
 */
export function MathFormula({ latex, display = false, className }: MathFormulaProps) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (ref.current) {
      katex.render(latex, ref.current, {
        displayMode: display,
        throwOnError: false,
        output: "htmlAndMathml",
      });
    }
  }, [latex, display]);

  return <span ref={ref} className={className} data-latex={latex} />;
}
