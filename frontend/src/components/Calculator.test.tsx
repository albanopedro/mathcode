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
  // user-event reads "[" as the start of a key name: "[[" types one literal "[".
  await user.type(screen.getByLabelText("Expressão ou equação"), text.replaceAll("[", "[["));
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
    // Only rationals: exact fractions are a second method (ADR 0010).
    expect(within(result).getByText("Resultado verificado simbolicamente.")).toBeInTheDocument();
  });

  it("lists each check with its strategy and outcome", async () => {
    answer(fixtures.arithmetic);
    await calculateText("0.1 + 0.2");

    const result = await screen.findByRole("region", { name: "Resultado" });
    const checks = within(within(result).getByRole("list", { name: "Checagens" })).getAllByRole(
      "listitem",
    );
    expect(checks).toHaveLength(2);
    expect(checks[0]).toHaveTextContent("Numérica");
    expect(checks[0]).toHaveTextContent(/Passou: Um avaliador independente/);
    expect(checks[1]).toHaveTextContent("Comparação de métodos");
    expect(checks[1]).toHaveTextContent(/frações exatas/);
  });

  it("marks what a partial verification could not prove", async () => {
    answer(fixtures.partial);
    await calculateText("sqrt(x + 2) = x");

    const result = await screen.findByRole("region", { name: "Resultado" });
    const checks = within(result).getAllByRole("listitem");
    const open = checks.find((check) => check.textContent?.includes("Inconclusiva:"));
    expect(open).toHaveTextContent("Completude");
    expect(open).toHaveTextContent(/não foi provado que não existem outras soluções/i);
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
        methods: ["numeric"],
        checks: [
          { kind: "numeric", outcome: "failed", message: "O avaliador independente obteve 4." },
        ],
        message: "A verificação independente contradiz o resultado.",
        reason: null,
      },
    });
    await calculateText("2 + 2");

    const alert = await screen.findByRole("alert");
    expect(
      within(alert).getByText("A verificação independente contradiz o resultado."),
    ).toBeInTheDocument();
    const check = within(alert).getByRole("listitem");
    expect(check).toHaveTextContent("Numérica");
    expect(check).toHaveTextContent("Falhou: O avaliador independente obteve 4.");
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

describe("Calculator: phrases and AI", () => {
  it("offers 'Permitir IA' only when the operation is detected, unticked", async () => {
    const user = userEvent.setup();
    render(<Calculator />);

    const box = screen.getByRole("checkbox", { name: "Permitir IA" });
    expect(box).not.toBeChecked();
    expect(box).toHaveAccessibleDescription(/serviço externo/);
    await user.selectOptions(screen.getByLabelText("Operação"), "Derivar");
    expect(screen.queryByRole("checkbox", { name: "Permitir IA" })).not.toBeInTheDocument();
  });

  it("sends allow_ai only when ticked", async () => {
    // A new Response each time: a body can be read only once.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse(fixtures.aiEquation))),
    );
    const user = userEvent.setup();
    render(<Calculator />);
    const input = screen.getByLabelText("Expressão ou equação");

    await user.type(input, "resolva x mais 3 igual a 10{Enter}");
    await screen.findByRole("region", { name: "Resultado" });
    await user.click(screen.getByRole("checkbox", { name: "Permitir IA" }));
    await user.click(screen.getByRole("button", { name: "Calcular" }));
    await screen.findByRole("region", { name: "Resultado" });

    const bodies = vi
      .mocked(fetch)
      .mock.calls.map((call) => JSON.parse(call[1]!.body as string) as unknown);
    expect(bodies).toEqual([
      { input: "resolva x mais 3 igual a 10" },
      { input: "resolva x mais 3 igual a 10", allow_ai: true },
    ]);
  });

  it("never sends allow_ai with a chosen operation", async () => {
    answer(fixtures.derivative);
    const user = userEvent.setup();
    render(<Calculator />);
    await user.click(screen.getByRole("checkbox", { name: "Permitir IA" }));
    await user.selectOptions(screen.getByLabelText("Operação"), "Derivar");
    await user.type(screen.getByLabelText("Expressão ou equação"), "x^2{Enter}");
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body.allow_ai).toBeUndefined();
  });

  it("shows what the AI understood and asks the user to check it", async () => {
    answer(fixtures.aiEquation);
    await calculateText("resolva x mais 3 igual a 10");

    const result = await screen.findByRole("region", { name: "Resultado" });
    const note = within(result).getByLabelText("Interpretação da frase");
    expect(note).toHaveTextContent(
      "Frase interpretada pela IA (opencode/space-bunny-free) como Equação: x + 3 = 10 (variável: x).",
    );
    expect(note).toHaveTextContent(/Confira se é o que você pediu/);
    expect(result.querySelector("annotation")).toHaveTextContent("x = 7");
  });

  it("shows a phrase read by the local rules, without the AI warning", async () => {
    answer(fixtures.phraseRules);
    await calculateText("qual a derivada de x^3 - 2x?");

    const result = await screen.findByRole("region", { name: "Resultado" });
    const note = within(result).getByLabelText("Interpretação da frase");
    expect(note).toHaveTextContent("Frase interpretada pelas regras locais como Derivada: x^3 - 2x.");
    expect(note).not.toHaveTextContent(/Confira/);
  });

  it("shows the AI's question as the error", async () => {
    answer(fixtures.aiClarification);
    await calculateText("integral dupla de x");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("A integral dupla ainda não é suportada.");
    expect(within(alert).getByLabelText("Interpretação da frase")).toHaveTextContent(
      "Frase lida pela IA (mock), sem uma conta para calcular.",
    );
  });

  it("explains when the server has no AI", async () => {
    answer(fixtures.aiUnavailable);
    await calculateText("quanto vale o dobro de sete");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/A IA não está ativada neste servidor/);
    expect(within(alert).queryByLabelText("Interpretação da frase")).not.toBeInTheDocument();
  });
});

describe("Calculator: statistics", () => {
  it("offers the operation and sends the data", async () => {
    answer(fixtures.statisticsSummary);
    await calculateText("2, 4, 4, 4, 5, 5, 7, 9", "Estatística");

    await screen.findByRole("region", { name: "Resultado" });
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body).toEqual({ input: "2, 4, 4, 4, 5, 5, 7, 9", intent: "statistics" });
  });

  it("shows the whole summary as a table", async () => {
    answer(fixtures.statisticsSummary);
    await calculateText("2, 4, 4, 4, 5, 5, 7, 9", "Estatística");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText("Estatística")).toBeInTheDocument();
    const table = within(result).getByRole("table", { name: "Resumo estatístico" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(13); // header + 12 measures
    expect(within(table).getByRole("rowheader", { name: /Desvio padrão populacional/ })).toBeInTheDocument();
    expect(within(result).getByText(/Dados em ordem \(n = 8\)/)).toHaveTextContent(
      "2; 4; 4; 4; 5; 5; 7; 9",
    );
    expect(within(result).getByText(/σ e σ² são populacionais/)).toBeInTheDocument();
  });

  it("highlights the measure asked for in a phrase", async () => {
    answer(fixtures.statisticsPhrase);
    await calculateText("qual o desvio padrão de 2, 4, 4, 4, 5, 5, 7, 9?");

    const result = await screen.findByRole("region", { name: "Resultado" });
    const asked = within(result)
      .getAllByRole("row")
      .filter((row) => row.getAttribute("aria-current") === "true");
    expect(asked).toHaveLength(1);
    expect(asked[0]).toHaveTextContent("Desvio padrão populacional");
  });

  it("shows undefined sample measures as a dash", async () => {
    answer(fixtures.statisticsSingle);
    await calculateText("5", "Estatística");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getAllByTitle("Não definido para estes dados")).toHaveLength(2);
    expect(within(result).getByText(/Com um só valor/)).toBeInTheDocument();
  });
});

/** The LaTeX of every formula drawn inside an element. */
function latexOf(element: HTMLElement): string[] {
  return Array.from(element.querySelectorAll("[data-latex]"), (node) =>
    node.getAttribute("data-latex") ?? "",
  );
}

describe("Calculator: matrices", () => {
  it("offers the operation with its calculation field and sends both", async () => {
    answer(fixtures.matrixDeterminant);
    const user = userEvent.setup();
    render(<Calculator />);
    await user.selectOptions(screen.getByLabelText("Operação"), "Matrizes");
    expect(screen.getByLabelText("Cálculo")).toHaveValue("determinant");
    await user.selectOptions(screen.getByLabelText("Cálculo"), "Inversa");
    await user.type(screen.getByLabelText("Expressão ou equação"), "[[[[1, 2], [[3, 4]]{Enter}");
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body).toEqual({
      input: "[[1, 2], [3, 4]]",
      intent: "matrix",
      options: { operation: "inverse" },
    });
  });

  it("shows the result and the matrix it was computed from", async () => {
    answer(fixtures.matrixDeterminant);
    await calculateText("[[1, 2], [3, 4]]", "Matrizes");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText("Matriz")).toBeInTheDocument();
    expect(within(result).getByText(/Matriz A \(2×2\)/)).toBeInTheDocument();
    expect(latexOf(result).some((latex) => latex.startsWith("\\det(A) = -2"))).toBe(true);
  });

  it("draws a matrix result as a formula, not as text", async () => {
    answer(fixtures.matrixProduct);
    await calculateText("[[1, 2], [3, 4]] * [[5, 6], [7, 8]]");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(latexOf(result).some((latex) => latex.includes("\\begin{matrix}"))).toBe(true);
    expect(within(result).queryByText(/Matriz A/)).not.toBeInTheDocument(); // evaluate: A is the result
  });

  it("names the calculation of a phrase in Portuguese", async () => {
    answer(fixtures.matrixInversePhrase);
    await calculateText("qual a inversa de [[1, 2], [3, 4]]?");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByLabelText("Interpretação da frase")).toHaveTextContent(
      "(cálculo: inversa)",
    );
  });

  it("explains a singular matrix", async () => {
    answer(fixtures.matrixSingular);
    await calculateText("[[1, 2], [2, 4]]", "Matrizes");

    expect(await screen.findByRole("alert")).toHaveTextContent(/singular/);
  });
});

describe("Calculator: vectors", () => {
  it("offers the operation with its calculation field and sends both", async () => {
    answer(fixtures.vectorCross);
    const user = userEvent.setup();
    render(<Calculator />);
    await user.selectOptions(screen.getByLabelText("Operação"), "Vetores");
    expect(screen.getByLabelText("Cálculo")).toHaveValue("norm");
    await user.selectOptions(screen.getByLabelText("Cálculo"), "Produto vetorial");
    await user.type(screen.getByLabelText("Expressão ou equação"), "[[1, 2, 3]; [[4, 5, 6]{Enter}");
    await screen.findByRole("region", { name: "Resultado" });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0]![1]!.body as string);
    expect(body).toEqual({
      input: "[1, 2, 3]; [4, 5, 6]",
      intent: "vector",
      options: { operation: "cross" },
    });
  });

  it("shows the result and the vectors it was computed from", async () => {
    answer(fixtures.vectorCross);
    await calculateText("[1, 2, 3]; [4, 5, 6]", "Vetores");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(within(result).getByText("Vetor")).toBeInTheDocument();
    const formulas = latexOf(result);
    expect(formulas).toContain("u \\times v = \\left(-3,\\ 6,\\ -3\\right)");
    expect(formulas).toContain("u = \\left(1,\\ 2,\\ 3\\right)");
    expect(formulas).toContain("v = \\left(4,\\ 5,\\ 6\\right)");
  });

  it("shows an angle in radians and degrees", async () => {
    answer(fixtures.vectorAnglePhrase);
    await calculateText("ângulo entre os vetores [1, 0] e [1, 1]");

    const result = await screen.findByRole("region", { name: "Resultado" });
    expect(latexOf(result)).toContain("\\theta = \\frac{\\pi}{4} = 45^\\circ");
    expect(within(result).getByLabelText("Interpretação da frase")).toHaveTextContent(
      "(cálculo: ângulo)",
    );
  });

  it("explains the zero vector", async () => {
    answer(fixtures.vectorZeroUnit);
    await calculateText("[0, 0]", "Vetores");

    expect(await screen.findByRole("alert")).toHaveTextContent(/vetor nulo/);
  });
});
