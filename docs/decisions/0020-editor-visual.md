# ADR 0020 — Editor visual MathLive (Fase 11, etapa 4)

- **Status:** aceita
- **Data:** 2026-10-09

## Decisões do usuário

1. **Botão "Editor visual":** o campo de texto continua sendo o padrão, e o
   botão troca para o editor visual (frações, raízes e potências desenhadas). A
   escolha fica lembrada, e o MathLive só é baixado quando o editor é aberto.
2. **Teclado matemático:** abre sozinho ao tocar, em telas de toque. No
   computador, abre pelo botão "Teclado matemático".
3. **Conversão visível:** o que foi desenhado vira a sintaxe da calculadora,
   mostrada em "Será calculado: …". O backend não muda: continua recebendo texto
   e passando pelo parser seguro (ADR 0002).

## Decisão

- **Dependência:** `mathlive` **0.111.1**, versão fixa, licença MIT, gratuita
  (ADR 0001).
  - **Sob demanda:** é carregado com `import()` só ao abrir o editor, num pedaço
    próprio de 801 kB (220 kB comprimido). A página não fica mais pesada para
    quem não usa o editor.
  - **Nada de fora:** `fontsDirectory = null` usa as fontes KaTeX que a página
    já carrega (o MathLive usa as mesmas famílias), e `soundsDirectory = null`
    deixa o editor sem sons. Conferi no navegador: todas as requisições foram ao
    `localhost`.
  - **Aparência:** o campo do MathLive fica transparente, sem borda e com a cor do
    tema (`index.css`); a caixa em volta é a do app, nos dois temas.
- **Conversor próprio (`utils/latexToInput.ts`):** o LaTeX do editor vira a
  sintaxe da calculadora. Não usei o "ascii-math" do MathLive, para a conversão
  ser determinística, testável sem navegador e alinhada ao parser.
  - **Conversões:** `\frac{a}{b}` → `(a)/(b)`; `\sqrt{x}` → `sqrt(x)`;
    `\sqrt[n]{x}` → `(x)^(1/(n))`; `^{..}` → `^(..)`; `30^{\circ}` → `30°`;
    `\cdot`, `\times` → `*`; `\div` → `/`; `\left|x\right|` → `abs(x)`;
    `\sin x` → `sin(x)`; `\log_{2}(8)` → `log(8; 2)`; `\pi` → `pi`.
  - **Comandos desconhecidos:** ficam como estão, para o parser explicar.
- **`components/MathEditor.tsx`:** Enter no editor calcula. Ao abrir, o editor
  começa do texto já digitado. Ao refazer um cálculo do histórico, o editor
  recomeça a partir dele.
- **Preferência:** `mathcode.editor.v1`, em `utils/editor.ts`.

## Consequências

- O `mathlive` passa a ser a segunda dependência pesada sob demanda, depois do
  Plotly. O aviso de pedaços acima de 500 kB do build continua, e é esperado.
- Nos testes, o MathLive é simulado (o jsdom não desenha); o editor real foi
  conferido no navegador, no computador e no celular.
- **Sugestões registradas:**
  - matrizes no editor visual;
  - converter o texto de volta para o editor com mais fidelidade (hoje via
    ascii-math do MathLive);
  - teclado matemático com as funções em português (sen, tg).
