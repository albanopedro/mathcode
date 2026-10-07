import { describe, expect, it } from "vitest";

import { fixtures } from "../test/fixtures";
import { captions } from "./captions";

describe("captions", () => {
  it.each([
    ["noSolution", ["A equação não tem solução real."]],
    ["allReals", ["Todo número real é solução: os dois lados são sempre iguais."]],
    [
      "allRealsExcept",
      ["Todo número real é solução, exceto x = 0, onde a equação não é definida."],
    ],
    ["doubleRoot", ["Raiz dupla: x = 1."]],
    ["systemNone", ["O sistema não tem solução."]],
    ["systemInfinite", ["Infinitas soluções: y pode assumir qualquer valor real."]],
    ["factorUnchanged", ["Não há fatoração sobre os racionais além desta forma."]],
    ["division", ["A divisão é exata: o resto é 0."]],
    ["unverified", ["Não foi encontrada uma forma mais simples."]],
  ] as const)("explains %s", (name, expected) => {
    expect(captions(fixtures[name])).toEqual(expected);
  });

  it.each(["equation", "quadratic", "factor", "expand", "systemUnique", "primeFactors", "arithmetic"] as const)(
    "adds nothing when the result speaks for itself (%s)",
    (name) => {
      expect(captions(fixtures[name])).toEqual([]);
    },
  );

  it("names higher multiplicities", () => {
    const triple = {
      ...fixtures.doubleRoot,
      details: { ...fixtures.doubleRoot.details, multiplicities: [3] },
    };
    expect(captions(triple)).toEqual(["Raiz tripla: x = 1."]);
    const fifth = { ...triple, details: { ...triple.details, multiplicities: [5] } };
    expect(captions(fifth)).toEqual(["Raiz de multiplicidade 5: x = 1."]);
  });

  it("ignores details of the wrong type", () => {
    const odd = { ...fixtures.doubleRoot, details: { solutions: "1", multiplicities: "2" } };
    expect(captions(odd)).toEqual([]);
  });
});

describe("calculus captions", () => {
  it.each([
    ["derivative", ["Derivada de ordem 2 em relação a x."]],
    ["integralIndefinite", ["Primitiva em relação a x; C é uma constante qualquer."]],
    ["integralDefinite", ["Integral de 0 a 1 em relação a x."]],
    ["integralDivergent", ["Integral de 1 a ∞ em relação a x.", "A integral diverge."]],
    ["limitFinite", ["Limite quando x → 0."]],
    ["limitOneSided", ["Limite quando x → 0 pela direita."]],
    ["limitSides", ["O limite não existe: pela esquerda tende a -1 e pela direita a 1."]],
    ["limitOscillates", ["O limite não existe: a função oscila perto de x = 0."]],
  ] as const)("explains %s", (name, expected) => {
    expect(captions(fixtures[name])).toEqual(expected);
  });

  it("names a first derivative without its order", () => {
    const first = { ...fixtures.derivative, details: { variable: "t", order: 1 } };
    expect(captions(first)).toEqual(["Derivada em relação a t."]);
  });
});
