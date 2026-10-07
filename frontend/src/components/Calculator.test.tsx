import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fixtures, jsonResponse } from "../test/fixtures";
import type { MathResult } from "../types/math";
import { LONG_RESULT_CHARS } from "../utils/display";
import { Calculator } from "./Calculator";

// The graph component is tested in GraphView.test.tsx; here Plotly stays out.
vi.mock("plotly.js-basic-dist-min", () => ({
  default: { newPlot: () => Promise.resolve(), purge: () => {} },
}));

function answer(result: MathResult, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(result, status)));
}

async function calculateText(text: string, operation?: string) {
  const user = userEvent.setup();
  render(<Calculator />);
  if (operation) {
    await user.selectOptions(screen.getByLabelText("Operação"), operation);
  }
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
    expect(within(result).getByText(/teorema de Sturm/)).toBeInTheDocument();
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

  it("detects the operation by default, sending no intent", async () => {
    answer(fixtures.equation);
    await calculateText("2x + 5 = 17");
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body).toEqual({ input: "2x + 5 = 17" });
  });

  it.each([
    ["Fatorar", "factor"],
    ["Expandir", "expand"],
    ["Resolver sistema", "solve_system"],
    ["Dividir polinômios", "polynomial_division"],
  ])("sends the chosen operation (%s)", async (label, intent) => {
    answer(fixtures.factor);
    await calculateText("x^2 - 4", label);
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body).toEqual({ input: "x^2 - 4", intent });
  });

  it("adapts the example to the chosen operation", async () => {
    const user = userEvent.setup();
    render(<Calculator />);
    await user.selectOptions(screen.getByLabelText("Operação"), "Dividir polinômios");

    expect(screen.getByLabelText("Expressão ou equação")).toHaveAttribute(
      "placeholder",
      "Ex.: (x^3 - 1)/(x - 1)",
    );
  });

  it.each([
    [fixtures.factor, "Fatoração"],
    [fixtures.expand, "Expansão"],
    [fixtures.division, "Divisão de polinômios"],
    [fixtures.systemUnique, "Sistema"],
  ])("labels the operation of the result", async (fixture, label) => {
    answer(fixture);
    await calculateText(fixture.input);

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText(label)).toBeInTheDocument();
  });

  it("shows a system as cases", async () => {
    answer(fixtures.systemUnique);
    await calculateText("x + y = 3; x - y = 1");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(result.querySelector("annotation")?.textContent).toContain(String.raw`\begin{cases}`);
  });

  it("shows captions built from the details", async () => {
    answer(fixtures.doubleRoot);
    await calculateText("x^2 - 2x + 1 = 0");

    expect(await screen.findByText("Raiz dupla: x = 1.")).toBeInTheDocument();
  });

  it("shows a partial verification honestly", async () => {
    answer(fixtures.partial);
    await calculateText("sqrt(x + 2) = x");

    expect(await screen.findByText(/^Verificação parcial/)).toBeInTheDocument();
    expect(screen.getByText("Não foi provado que não existem outras soluções.")).toBeInTheDocument();
  });

  it("shows omitted complex solutions as a warning", async () => {
    answer(fixtures.complexOmitted);
    await calculateText("x^2 + 1 = 0");

    expect(await screen.findByText(/complexa\(s\), omitida/)).toBeInTheDocument();
    expect(screen.getByText("A equação não tem solução real.")).toBeInTheDocument();
  });
});

describe("Calculator: calculus fields", () => {
  it("shows only the fields of the chosen operation", async () => {
    const user = userEvent.setup();
    render(<Calculator />);
    expect(screen.queryByLabelText("Ordem")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Operação"), "Derivar");
    expect(screen.getByLabelText("Variável")).toBeInTheDocument();
    expect(screen.getByLabelText("Ordem")).toBeInTheDocument();
    expect(screen.queryByLabelText("Ponto")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Operação"), "Integrar");
    expect(screen.getByLabelText("De")).toBeInTheDocument();
    expect(screen.getByLabelText("Até")).toBeInTheDocument();
    expect(screen.queryByLabelText("Ordem")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Operação"), "Limite");
    expect(screen.getByLabelText("Ponto")).toBeInTheDocument();
    expect(screen.getByLabelText("Lado")).toBeInTheDocument();
  });

  it("sends the fields as options", async () => {
    answer(fixtures.integralDefinite);
    const user = userEvent.setup();
    render(<Calculator />);
    await user.selectOptions(screen.getByLabelText("Operação"), "Integrar");
    await user.type(screen.getByLabelText("De"), "0");
    await user.type(screen.getByLabelText("Até"), "1");
    await user.type(screen.getByLabelText("Expressão ou equação"), "x^2{Enter}");
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body).toEqual({
      input: "x^2",
      intent: "integral",
      options: { lower: "0", upper: "1" },
    });
  });

  it("sends the limit side and point", async () => {
    answer(fixtures.limitOneSided);
    const user = userEvent.setup();
    render(<Calculator />);
    await user.selectOptions(screen.getByLabelText("Operação"), "Limite");
    await user.type(screen.getByLabelText("Ponto"), "0");
    await user.selectOptions(screen.getByLabelText("Lado"), "Pela direita");
    await user.type(screen.getByLabelText("Expressão ou equação"), "sqrt(x){Enter}");
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body.options).toEqual({ point: "0", side: "right" });
  });

  it.each([
    [fixtures.derivative, "Derivada"],
    [fixtures.integralIndefinite, "Integral"],
    [fixtures.limitFinite, "Limite"],
  ])("labels and explains calculus results", async (fixture, label) => {
    answer(fixture);
    await calculateText(fixture.input);

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText(label)).toBeInTheDocument();
  });

  it("shows that a limit does not exist, with its sides", async () => {
    answer(fixtures.limitSides);
    await calculateText("abs(x)/x");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(result.querySelector("annotation")?.textContent).toBe(String.raw`\nexists`);
    expect(within(result).getByText(/pela esquerda tende a -1/)).toBeInTheDocument();
  });

  it("explains an invalid option from the API", async () => {
    answer(fixtures.invalidOrder);
    await calculateText("x^2");

    expect(await screen.findByRole("alert")).toHaveTextContent(/ordem da derivada/);
  });
});

describe("Calculator: graphs", () => {
  it("offers the x range fields and sends them", async () => {
    answer(fixtures.graphParabola);
    const user = userEvent.setup();
    render(<Calculator />);
    await user.selectOptions(screen.getByLabelText("Operação"), "Gráfico");
    await user.type(screen.getByLabelText("x de"), "-2pi");
    await user.type(screen.getByLabelText("x até"), "2pi");
    await user.type(screen.getByLabelText("Expressão ou equação"), "sen(x){Enter}");
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body).toEqual({
      input: "sen(x)",
      intent: "graph",
      options: { x_min: "-2pi", x_max: "2pi" },
    });
  });

  it("shows the graph area, the points and the verification", async () => {
    answer(fixtures.graphParabola);
    await calculateText("y = x^2 - 4x + 3");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText("Gráfico")).toBeInTheDocument();
    expect(within(result).getByRole("img", { name: /Gráfico de y = x\^2/ })).toBeInTheDocument();
    expect(within(result).getByText("Raízes: x = 1; x = 3.")).toBeInTheDocument();
  });
});
