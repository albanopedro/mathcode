# ADR 0019 — Tema escuro e acessibilidade (Fase 11, etapa 3)

- **Status:** aceita
- **Data:** 2026-10-09

## Decisões do usuário

1. **Tema:** Sistema / Claro / Escuro. O padrão segue o sistema, e a escolha
   fica lembrada no navegador.
2. **Seletor:** no topo, ao lado do título.
3. **Acessibilidade (tudo):**
   - contraste e foco;
   - teclado;
   - leitores de tela;
   - movimento reduzido.

## Decisão

### Tema escuro por paleta espelhada

Em vez de acrescentar classes `dark:` em todos os componentes, o tema escuro
**redefine as variáveis de cor** do Tailwind 4 em `:root.dark`
(`src/index.css`):
- **Escala espelhada:** 50↔950, 100↔900, 200↔800, 300↔700, 400→500, 500→400,
  600→300, 700→200, 800→100, 900→50, nos tons usados (slate, rose, sky, emerald,
  amber e violet).
- **Branco:** `white` vira slate-900 (os cartões), e `black` vira slate-50.

Os pares de contraste do tema claro continuam valendo no escuro. O tom 500 vai
para o 400, para o texto secundário manter o contraste sobre os cartões
escuros. Os valores foram gerados de `node_modules/tailwindcss/theme.css`; se a
paleta do Tailwind mudar, o bloco precisa ser gerado de novo pelo mapeamento
acima.

- **`utils/theme.ts` e `hooks/useTheme.ts`:**
  - escolha `system | light | dark` em `mathcode.theme.v1` (o "system" não é
    gravado);
  - classe `dark` em `<html>`;
  - em "system", o tema acompanha a mudança do sistema (`matchMedia`).
- **Sem piscar:** um script curto no `index.html` aplica o tema antes do React,
  e a página não pisca branca no escuro. `color-scheme` acompanha o tema, para
  os controles nativos.
- **Gráfico:** o Plotly desenha fora do CSS. `layout` e `traces` recebem `dark`,
  e `useIsDark` redesenha o gráfico quando o tema muda.

### Acessibilidade

- **Contraste, conferido por cálculo:**
  - **Método:** um script no navegador percorre cada texto visível, acha a cor do
    fundo efetivo (com transparências), converte `oklch` para RGB e calcula a
    razão WCAG. O mínimo é 4,5:1, ou 3:1 para texto grande.
  - **Abrangência:** 9 estados (equação com checagens e histórico abertos, erro,
    aviso, estatística, gráfico, probabilidade, triângulo, frase, matriz), nos
    dois temas.
  - **Resultado:** nenhuma falha. Um controle (cinza-claro sobre branco, 1,48:1)
    confirmou que o script detecta falhas.
  - **Correção feita antes:** o horário do histórico (slate-400) passou para
    slate-500.
- **Contraste de componentes (WCAG 1.4.11):** a borda dos campos e seletores
  tinha 1,42:1 (slate-300). Agora é slate-500: 4,55:1 no claro e 7,66:1 no
  escuro.
- **Foco visível:** anel de 2 px (sky-600, 4,02:1; no escuro, 10,7:1) em todo
  elemento focável, por `:focus-visible`.
- **Teclado:**
  - "Pular para o resultado" é o primeiro elemento do Tab;
  - a área do resultado recebe o foco (`tabindex="-1"`);
  - **Esc** limpa o campo de expressão;
  - todos os controles são botões, campos ou seletores nativos.
- **Leitores de tela:**
  - a região `aria-live` envolvia o resultado inteiro, que era lido de uma vez,
    com as checagens. Agora há um anúncio curto em `role="status"`:
    "Calculando…", depois "Resultado: x = 6. Resultado verificado
    simbolicamente.", ou "Erro: …";
  - as fórmulas já levam MathML (KaTeX `htmlAndMathml`);
  - os grupos "Tema" e "Forma do resultado" usam `aria-pressed`.
- **Movimento reduzido:** com `prefers-reduced-motion`, as animações, as
  transições e a rolagem suave são desligadas.

## Consequências

- Uma cor nova (outro tom do Tailwind) precisa entrar no bloco espelhado. Sem
  isso, ela fica igual nos dois temas.
- **Sugestões registradas:**
  - teste automatizado de contraste no CI (axe-core);
  - alto contraste;
  - tamanho de fonte ajustável.
