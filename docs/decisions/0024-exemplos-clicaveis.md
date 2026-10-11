# ADR 0024 — Exemplos clicáveis

- **Status:** aceita
- **Data:** 2026-10-11

## Contexto

Na linha da interface mais dinâmica (ADR 0023), o usuário escolheu os
exemplos clicáveis. Antes, o "Ver exemplos" era um texto com 10 linhas que o
usuário precisava copiar e colar no campo.

## Decisão

- **Cartões:** o texto de ajuda mostra a mesma linha curta de antes e, abaixo,
  um bloco "Exemplos (clique para calcular)" com um cartão por assunto: contas,
  equação, sistema, derivada, integral, gráfico, assistente, máximos e mínimos,
  estatística, matriz, geometria, contagem e trigonometria.
- **Um clique faz tudo:**
  - o exemplo vai para o campo;
  - a operação volta para Automático, os campos extras são limpos e a IA fica
    desligada;
  - o cálculo é feito, e o resultado entra no histórico, como em qualquer
    cálculo pedido pelo usuário.
- **Fora do caminho:**
  - o bloco abre na primeira visita, para quem chega e não sabe o que
    escrever;
  - ao escolher um exemplo, ele se recolhe, para o resultado não ser empurrado
    para baixo da página.
- **Todos em Automático:** assim o clique também mostra que a calculadora lê
  frases e descobre a operação sozinha.
- **Lista única:** `utils/examples.ts`.
- **Os exemplos funcionam de verdade:** `tests/test_frontend_examples.py` lê
  essa lista e calcula cada exemplo com o motor real, exigindo sucesso. Se um
  exemplo parar de funcionar, o teste reprova.
- **Acessibilidade:** os cartões são botões numa lista com nome ("Exemplos"),
  o movimento é reduzido quando o sistema pede, e o tema escuro vale pela
  paleta espelhada.

## Consequências

- A ajuda por exemplos deixa de exigir digitação, o que também vale no celular.
- Os exemplos passam a ser testados, então a ajuda não envelhece sozinha.
- **Sugestões registradas:** exemplos por operação escolhida (por exemplo, só
  de derivadas ao escolher "Derivar").
