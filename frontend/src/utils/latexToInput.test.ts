import { describe, expect, it } from "vitest";

import { latexToInput } from "./latexToInput";

describe("latexToInput", () => {
  it.each([
    ["x^2+3x", "x^2+3x"],
    ["x^{10}", "x^(10)"],
    ["\\frac{1}{2}x", "(1)/(2)x"],
    ["\\frac{x+1}{x-1}", "(x+1)/(x-1)"],
    ["\\sqrt{2}", "sqrt(2)"],
    ["\\sqrt[3]{8}", "(8)^(1/(3))"],
    ["\\sin\\left(x\\right)", "sin(x)"],
    ["\\sin x", "sin(x)"],
    ["\\cos\\left(30^{\\circ}\\right)", "cos(30°)"],
    ["2\\pi", "2pi"],
    ["3\\cdot4", "3*4"],
    ["3\\times4\\div2", "3*4/2"],
    ["\\left|x-1\\right|", "abs(x-1)"],
    ["\\left\\vert x\\right\\vert", "abs(x)"],
    ["\\ln\\left(x\\right)+\\log_{2}\\left(8\\right)", "ln(x)+log(8; 2)"],
    ["\\operatorname{sen}\\left(x\\right)", "sen(x)"],
    ["x^2-5x+6=0", "x^2-5x+6=0"],
    ["\\left[1,\\,2\\right]", "[1, 2]".replace(" ", "")],
    ["5!", "5!"],
    ["e^{-x^2}", "e^(-x^2)"],
  ])("%s → %s", (latex, input) => {
    expect(latexToInput(latex)).toBe(input);
  });

  it("keeps unknown commands so the parser can explain them", () => {
    expect(latexToInput("\\alpha+1")).toBe("\\alpha+1");
  });
});
