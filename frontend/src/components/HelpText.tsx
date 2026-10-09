/** One short line, and the examples by subject on demand. */
export function HelpText({ id }: { id: string }) {
  return (
    <div className="text-sm text-slate-500">
      <p id={id}>
        Use ^ para potência, √ ou sqrt(x) para raiz, ° para graus e ; para separar; frases
        simples também funcionam.
      </p>
      <details className="mt-1">
        <summary className="cursor-pointer text-slate-600">Ver exemplos</summary>
        <dl className="mt-2 grid gap-x-3 gap-y-1 sm:grid-cols-[auto_1fr]">
          {EXAMPLES.map(([subject, text]) => (
            <div key={subject} className="contents">
              <dt className="font-medium text-slate-600">{subject}</dt>
              <dd className="mb-1 font-mono text-slate-700 sm:mb-0">{text}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}

const EXAMPLES: readonly (readonly [string, string])[] = [
  ["Contas", "0.1 + 0.2 · 2^10 · sqrt(8) · log(8; 2) · sen(30°)"],
  ["Equações", "2x + 5 = 17 · x² - 5x + 6 = 0 · sin(x) = 1/2"],
  ["Sistemas", "x + y = 3; x - y = 1"],
  ["Cálculo", "derivada de x^3 · integral de x^2 de 0 a 1"],
  ["Gráficos", "y = x² - 4x + 3 · sen(x); cos(x)"],
  ["Estatística", "média de 10, 20, 30"],
  ["Matrizes e vetores", "[[1, 2], [3, 4]] · [1, 2, 3]"],
  ["Geometria", "área do círculo de raio 5 · (1, 2); (4, 6)"],
  ["Contagem", "5! · C(10, 3) · A(6, 2) · anagramas de BANANA"],
  ["Trigonometria", "converta 30° para radianos · tan(x) = sin(x) é uma identidade?"],
];
