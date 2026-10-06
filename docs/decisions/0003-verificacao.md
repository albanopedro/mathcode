# ADR 0003 — Estratégia de verificação

- **Status:** aceita
- **Data:** 2026-10-06

## Contexto

O projeto promete não apresentar um resultado sem dizer **o quanto ele foi
conferido**. Existe uma armadilha nisso: recalcular com o mesmo algoritmo do
SymPy não é uma verificação independente. Se `diff` tiver um bug, chamar `diff`
de novo repete o bug.

## Decisão

### Níveis de verificação

| `status` | Significado |
|---|---|
| `verified_symbolic` | Um caminho simbólico **diferente** do cálculo confirmou o resultado (ex.: derivar a integral). |
| `verified_numeric` | Avaliação numérica independente em vários pontos, dentro da tolerância. |
| `partial` | Uma parte foi confirmada e outra não (ex.: as soluções satisfazem a equação, mas não foi provado que não existem outras). |
| `unverified` | Não há uma estratégia adequada. A interface mostra isso de forma explícita. |
| `not_applicable` | O pedido não tem um "resultado" a conferir (ex.: dados de um gráfico). |
| `failed` | A verificação **contradiz** o resultado. A resposta vira erro (`VERIFICATION_FAILED`) e o resultado **não** é apresentado como resposta. |

O relatório (`VerificationReport`) traz `status`, `method`, a lista de `checks`
feitos e um texto curto para o usuário. A palavra "garantido" nunca é usada.

### Estratégia por intent

| Intent | Verificação | Status máximo |
|---|---|---|
| arithmetic | Avaliar a **AST original** com `mpmath` a 50 dígitos (um avaliador próprio, sem SymPy) e comparar com `N(resultado, 50)` | `verified_numeric` |
| simplify | `original − resultado` em pontos aleatórios; se `simplify(original − resultado) == 0`, também simbólico | `verified_symbolic` |
| solve_equation (linear) | Substituir cada solução na equação original. Grau 1 ⇒ no máximo uma solução, então a completude também fica provada | `verified_symbolic` |
| solve_equation (geral) | Substituição + aviso de que não foi provado que não há outras soluções | `partial` |
| factor / expand | `expand(resultado) − expand(original) == 0` + pontos numéricos | `verified_symbolic` |
| derivative | Diferença finita central em pontos aleatórios (mpmath) | `verified_numeric` |
| integral indefinida | `diff(F) − f == 0` (derivar é um algoritmo diferente de integrar) + pontos | `verified_symbolic` |
| integral definida | Comparar com quadratura numérica (`scipy.integrate.quad` ou `mpmath.quad`) | `verified_numeric` |
| limit | Avaliação numérica aproximando-se pelos dois lados | `partial` |
| solve_system | Substituir as soluções em todas as equações | `partial` / `verified_symbolic` (sistema linear com determinante ≠ 0) |
| graph | — | `not_applicable` |

### Regras da verificação numérica

- Os pontos são **pseudoaleatórios com semente derivada da entrada** (hash),
  então a mesma entrada sempre é verificada nos mesmos pontos.
- Pontos fora do domínio (divisão por zero, raiz de negativo em ℝ) são
  descartados e sorteados de novo. Se não houver pontos válidos suficientes, o
  status cai para `unverified`.
- A tolerância é relativa (`1e-9`) e absoluta para valores perto de zero
  (`1e-12`).
- Quando uma simplificação **remove uma singularidade** (`x²/x → x`), o
  resultado sai com o aviso `DOMAIN_CHANGED` ("válido para x ≠ 0").

## Consequências

- Cada executor de intent tem um verificador correspondente, e um intent sem
  verificador declara isso explicitamente (`unverified`), em vez de omitir.
- A Fase 9 expande e formaliza este módulo, mas a verificação existe desde a
  Fase 2.
