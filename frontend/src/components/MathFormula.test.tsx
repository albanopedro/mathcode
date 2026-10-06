import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MathFormula } from "./MathFormula";

describe("MathFormula", () => {
  it("renders LaTeX with KaTeX, including MathML for screen readers", () => {
    const { container } = render(<MathFormula latex={String.raw`\frac{3}{10}`} display />);

    expect(container.querySelector(".katex-display")).not.toBeNull();
    expect(container.querySelector("math")).not.toBeNull();
    expect(container.querySelector("annotation")).toHaveTextContent(String.raw`\frac{3}{10}`);
  });

  it("re-renders when the formula changes", () => {
    const { container, rerender } = render(<MathFormula latex="x = 6" />);
    rerender(<MathFormula latex="x = 7" />);

    expect(container.querySelector("annotation")).toHaveTextContent("x = 7");
  });

  it("shows invalid LaTeX as text instead of throwing", () => {
    const { container } = render(<MathFormula latex={String.raw`\frac{1`} />);

    expect(container.textContent).toContain(String.raw`\frac{1`);
  });
});
