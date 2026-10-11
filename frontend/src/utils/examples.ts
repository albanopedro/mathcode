/**
 * The clickable examples (ADR 0024): one per subject, all in Automático, so a click
 * shows that the calculator reads phrases and detects the operation by itself.
 * Each one is checked against the real engine in the backend's tests.
 */
export interface Example {
  subject: string;
  text: string;
}

export const EXAMPLES: readonly Example[] = [
  { subject: "Contas", text: "0.1 + 0.2" },
  { subject: "Equação", text: "x² - 5x + 6 = 0" },
  { subject: "Sistema", text: "x + y = 3; x - y = 1" },
  { subject: "Derivada", text: "derivada de x^3" },
  { subject: "Integral", text: "integral de x^2 de 0 a 1" },
  { subject: "Gráfico", text: "y = x² - 4x + 3" },
  { subject: "Assistente", text: "raízes, vértice e gráfico de x² - 4x + 3" },
  { subject: "Máximos e mínimos", text: "máximos e mínimos de x^3 - 3x" },
  { subject: "Estatística", text: "média de 10, 20, 30" },
  { subject: "Matriz", text: "determinante de [[1, 2], [3, 4]]" },
  { subject: "Geometria", text: "área do círculo de raio 5" },
  { subject: "Contagem", text: "quantos anagramas tem a palavra BANANA?" },
  { subject: "Trigonometria", text: "converta 30° para radianos" },
];
