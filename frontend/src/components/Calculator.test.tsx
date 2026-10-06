import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fixtures, jsonResponse } from "../test/fixtures";
import type { MathResult } from "../types/math";
import { LONG_RESULT_CHARS } from "../utils/display";
import { Calculator } from "./Calculator";

function answer(result: MathResult, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(result, status)));
}

async function calculateText(text: string) {
  const user = userEvent.setup();
  render(<Calculator />);
  await user.type(screen.getByLabelText("Expressão ou equação"), text);
  await user.click(screen.getByRole("button", { name: "Calcular" }));
  return user;
}

describe("Calculator", () => {
  it("disables the button while the input is empty", async () => {
    const user = userEvent.setup();
    render(<Calculator />);
    const button = screen.getByRole("button", { name: "Calcular" });

    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText("Expressão ou equação"), "   ");
    expect(button).toBeDisabled();
  });

  it("shows the result, how it was understood and its verification", async () => {
    answer(fixtures.equation);
    await calculateText("2x + 5 = 17");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(result.querySelector("annotation")).toHaveTextContent("x = 6");
    expect(within(result).getByText("Equação")).toBeInTheDocument();
    expect(within(result).getByText("2*x + 5 = 17")).toBeInTheDocument();
    expect(within(result).getByText("Resultado verificado simbolicamente.")).toBeInTheDocument();
    expect(within(result).getByText("Como foi verificado")).toBeInTheDocument();
    expect(within(result).getByText(/não existem outras soluções/)).toBeInTheDocument();
  });

  it("submits with Enter", async () => {
    answer(fixtures.arithmetic);
    const user = userEvent.setup();
    render(<Calculator />);

    await user.type(screen.getByLabelText("Expressão ou equação"), "0.1 + 0.2{Enter}");

    expect(await screen.findByText("0.3")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("shows the decimal approximation", async () => {
    answer(fixtures.arithmetic);
    await calculateText("0.1 + 0.2");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText("0.3")).toBeInTheDocument();
    expect(within(result).getByText(/conferido numericamente por um avaliador independente/)).toBeInTheDocument();
  });

  it("shows a very long result as wrapping text instead of a formula", async () => {
    const digits = "1".repeat(LONG_RESULT_CHARS + 1);
    answer({
      ...fixtures.arithmetic,
      result: { plain: digits, latex: digits, approx: null },
    });
    await calculateText("2^10000");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText(digits)).toHaveClass("break-all");
    expect(result.querySelector(".katex")).toBeNull();
    expect(within(result).getByText(/Resultado longo/)).toBeInTheDocument();
  });

  it("shows warnings", async () => {
    answer(fixtures.warnings);
    await calculateText("sen(30) + log(100)");

    const warnings = await screen.findByRole("list", { name: "Avisos" });
    expect(within(warnings).getByText(/radianos/)).toBeInTheDocument();
    expect(within(warnings).getByText(/base 10/)).toBeInTheDocument();
  });

  it("shows a domain change warning", async () => {
    answer(fixtures.simplifyDomain);
    await calculateText("(x^2 - 1)/(x - 1)");

    expect(await screen.findByText(/só equivale a ela para x ≠ 1/)).toBeInTheDocument();
  });

  it.each([
    [fixtures.noSolution, "A equação não tem solução real."],
    [fixtures.allReals, /Todo número real é solução/],
  ])("explains special solution sets", async (fixture, caption) => {
    answer(fixture);
    await calculateText(fixture.input);

    expect(await screen.findByText(caption)).toBeInTheDocument();
  });

  it("says so when a result could not be verified", async () => {
    answer(fixtures.unverified);
    await calculateText("sqrt(x - 1000)");

    expect(await screen.findByText("Não foi possível verificar este resultado.")).toBeInTheDocument();
  });

  it("shows a math error and marks where it is in the input", async () => {
    answer(fixtures.divisionByZero);
    await calculateText("10 + 1/0");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Divisão por zero.");
    expect(within(alert).getByText("/", { selector: "mark" })).toBeInTheDocument();
    expect(alert).toHaveTextContent("problema no caractere 7");
    expect(screen.queryByRole("region", { name: "Resultado" })).not.toBeInTheDocument();
  });

  it("marks the end of the input when something is missing there", async () => {
    answer(fixtures.parseError);
    await calculateText("2 +");

    const alert = await screen.findByRole("alert");
    // A highlighted non-breaking space after the last character.
    expect(alert.querySelector("mark")?.textContent).toBe(" ");
    expect(alert).toHaveTextContent("problema no caractere 4");
  });

  it("shows a timeout as an error", async () => {
    answer(fixtures.timeout);
    await calculateText("(x+1)^1000*(x+2)^1000");

    expect(await screen.findByRole("alert")).toHaveTextContent(/passou de 5 s/);
  });

  it("shows a failed verification without the result", async () => {
    answer({
      ...fixtures.timeout,
      intent: "arithmetic",
      error: { code: "VERIFICATION_FAILED", message: "Não confirmado.", position: null },
      verification: {
        status: "failed",
        method: "independent_numeric",
        checks: ["O avaliador independente obteve 4."],
        message: "A verificação independente contradiz o resultado.",
      },
    });
    await calculateText("2 + 2");

    const alert = await screen.findByRole("alert");
    expect(
      within(alert).getByText("A verificação independente contradiz o resultado."),
    ).toBeInTheDocument();
    expect(within(alert).getByText("O avaliador independente obteve 4.")).toBeInTheDocument();
  });

  it("shows when the API cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await calculateText("2 + 2");

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível conectar à API.");
  });

  it("shows a loading state and blocks a second submission", async () => {
    let resolve: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((r) => (resolve = r))),
    );
    await calculateText("2 + 2");

    const button = screen.getByRole("button", { name: "Calculando…" });
    expect(button).toBeDisabled();

    resolve(jsonResponse(fixtures.arithmetic));
    expect(await screen.findByRole("button", { name: "Calcular" })).toBeEnabled();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("replaces the previous result with the new one", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(fixtures.arithmetic))
        .mockResolvedValueOnce(jsonResponse(fixtures.divisionByZero)),
    );
    const user = await calculateText("0.1 + 0.2");
    await screen.findByRole("region", { name: "Resultado" });

    const field = screen.getByLabelText("Expressão ou equação");
    await user.clear(field);
    await user.type(field, "10 + 1/0{Enter}");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Resultado" })).not.toBeInTheDocument();
  });
});
