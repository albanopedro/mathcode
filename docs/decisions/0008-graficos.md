# ADR 0008 — Gráficos (Fase 7)

- **Status:** aceita
- **Data:** 2026-10-07

## Contexto

O roadmap pede funções cartesianas com domínio, amostragem, várias funções e
pontos relevantes. A stack preferencial previa NumPy (amostragem) e Plotly.js
(desenho).

## Decisões do usuário

1. **Plotly.js básico** (`plotly.js-basic-dist-min`, MIT), **carregado sob
   demanda**: o pedaço de ~1,2 MB (384 KB comprimido) só é baixado quando o
   primeiro gráfico aparece. A página inicial não fica mais pesada.
2. **Faixa de x por campos "x de / x até"**, com padrão −10 a 10. Os campos
   aceitam expressões (`-2pi`) e aparecem no resultado como foram digitados.

## Decisões técnicas

### Entrada e detecção

- Várias funções são separadas por `;`: `sen(x); cos(x)`. O parser ganhou o nó
  `ExpressionList`. Uma lista só de números (`1, 2`) continua sendo erro, porque
  quase sempre é vírgula decimal com espaço.
- `y = f(x)` e listas de expressões são **detectadas automaticamente** como
  gráfico. Antes, `y = x^2` dava erro, por parecer uma equação de duas
  variáveis.
- Até 5 funções, de uma variável só. A largura máxima da faixa é 10⁶.

### Amostragem pelo avaliador independente, sem NumPy

- 801 pontos por função, calculados pelo **avaliador da AST**
  (`verification/numeric.py`), que leva cerca de 0,03 s. Assim o gráfico usa
  exatamente as convenções do resto do projeto (log na base 10, raiz real de
  índice ímpar, graus), e o que está fora do domínio vira **corte** (`null`).
  O NumPy exigiria uma terceira implementação dessas convenções.
- O motor (`math_engine/graphing.py`) importa o avaliador do módulo de
  verificação. A independência continua onde importa: as **raízes** vêm do
  motor de equações (SymPy) e são conferidas pelo avaliador.
- **Assíntotas:** a linha é cortada quando dois pontos vizinhos têm sinais
  opostos e um salto maior que toda a faixa visível, como na tangente.
- **Eixo y:** usa os percentis 2 a 98. Se os extremos passam de 3× essa faixa
  (perto de assíntotas), eles são cortados, com o aviso `Y_RANGE_CLIPPED`. Uma
  função íngreme mas regular (eˣ) aparece inteira.

### Pontos relevantes

- **Raízes:**
  - primeiro pelo motor de equações (exatas; a completude vem da verificação
    da Fase 5, com Sturm);
  - quando ele não resolve (sin, tan), por **mudança de sinal + bisseção** sobre
    o avaliador, com o aviso `NUMERIC_ROOTS`. Raízes em que o gráfico só toca o
    eixo podem faltar;
  - até 20 por função (`POINTS_TRUNCATED`).
- **Intercepto em y**, quando 0 está na faixa e no domínio.
- Uma amostra é "zero" se |y| ≤ 10⁻¹² × a escala da **faixa visível**. Usar o
  maior |y| das amostras foi um bug encontrado na fase: perto de um polo da
  tangente, uma amostra valia ~10¹⁴, e valores até ~100 passavam por zero.

### Verificação

| Situação | Status |
|---|---|
| Sem raízes nem intercepto na faixa | `not_applicable` |
| Pontos conferidos, raízes exatas e completas | `verified_numeric` |
| Raízes numéricas, ou exatas sem prova de completude | `partial` |
| Um ponto não confere (f(raiz) ≠ 0, intercepto errado) | `failed` |

### Privacidade e custo

- O botão **"Share chart"** do Plotly envia o gráfico para a nuvem do Plotly
  (Chart Studio), e no Plotly 4 ele vem **ligado por padrão**. Foi desligado
  (`showSendToCloud: false`), com teste. Na verificação no navegador, todas as
  requisições foram locais.

## Consequências

- O pacote principal do frontend passou de 500 KB (503 KB) e o Vite avisa. O
  aviso não foi silenciado: carregar o KaTeX sob demanda é a correção
  registrada como sugestão.
- Ficam como sugestão:
  - extremos locais e vértice;
  - assíntotas desenhadas;
  - gráficos paramétricos, polares e 3D;
  - reamostrar ao dar zoom.
