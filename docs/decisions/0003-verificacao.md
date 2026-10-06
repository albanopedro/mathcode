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
| arithmetic | Avaliar a **AST original** com `mpmath` (um avaliador próprio, sem SymPy, com precisão adaptativa) e comparar com `N(resultado, 50)` | `verified_numeric` |
| simplify | Original (avaliador independente) e resultado (SymPy) em 6 pontos sorteados; se `simplify(original − resultado) == 0`, também simbólico | `verified_symbolic` |
| solve_equation (linear) | Substituir a solução na equação original, de forma simbólica e com o avaliador independente. Coeficiente de `x` ≠ 0 ⇒ grau 1 ⇒ no máximo uma solução, então a completude também fica provada. "Sem solução" e "todo x real" são conferidos pela diferença entre os lados e em pontos sorteados | `verified_symbolic` |
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
- Os pontos são **decimais exatos** (6 casas). O avaliador independente e o
  SymPy recebem exatamente o mesmo número.
- **Precisão adaptativa** (decidido na Fase 2): o avaliador independente começa
  com 60 dígitos e, se encontrar valores intermediários grandes, refaz a conta
  com 60 dígitos **além** do maior deles, até o máximo de 8 060. Sem isso,
  `10^3999 + 1 - 10^3999` daria `0` e um resultado correto (`1`) seria
  rejeitado. Acima do máximo, a verificação devolve `unverified`, e não um falso
  "verificado".
- **Comparação:** cada avaliação informa o próprio limite de erro (absoluto). Dois
  valores concordam se a diferença for menor que 30 algarismos significativos
  (`1e-30` relativo) ou menor que esse limite de erro. A proposta inicial
  (`1e-9` relativo, `1e-12` absoluto) foi abandonada porque aceitava
  `1.4142135623` como valor de `√2`. Um teste garante que esse erro, na 11ª
  casa, agora é detectado.
- Quando uma simplificação **remove uma singularidade** (`x²/x → x`), o
  resultado sai com o aviso `DOMAIN_CHANGED` ("válido para x ≠ 0").

## Consequências

- Cada executor de intent tem um verificador correspondente, e um intent sem
  verificador declara isso explicitamente (`unverified`), em vez de omitir.
- Os testes em `tests/verification/test_verifiers.py` **adulteram** resultados
  (valor errado, solução errada, "sem solução" falso) e exigem `failed`. Um
  resultado com verificação `failed` nunca é exibido: a resposta vira o erro
  `VERIFICATION_FAILED`.
- Limitação conhecida: o aviso `DOMAIN_CHANGED` só detecta denominadores com
  uma variável. Restrições vindas de `sqrt` e `log` ainda não são detectadas.
- A Fase 9 expande e formaliza este módulo, mas a verificação existe desde a
  Fase 2.
