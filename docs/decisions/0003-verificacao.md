# ADR 0003 — Estratégia de verificação

- **Status:** aceita; formalizada e expandida na Fase 9 pelo
  [ADR 0010](0010-verification-engine.md)
- **Data:** 2026-10-06

> Desde a Fase 9, o relatório é estruturado (cada checagem tem tipo e
> resultado), há comparação de métodos e a verificação tem prazo próprio. A
> tabela abaixo foi atualizada; os detalhes estão no ADR 0010.

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

O relatório (`VerificationReport`) traz `status`, as checagens feitas (cada uma
com tipo e resultado), as estratégias usadas, o motivo quando não verifica e um
texto curto para o usuário ([ADR 0010](0010-verification-engine.md)). A palavra
"garantido" nunca é usada.

### Estratégia por intent

| Intent | Verificação | Status máximo |
|---|---|---|
| arithmetic | Avaliar a **AST original** com `mpmath` (um avaliador próprio, sem SymPy, com precisão adaptativa) e comparar com `N(resultado, 50)`; só com racionais, refazer com frações exatas (Fase 9) | `verified_numeric`; `verified_symbolic` com frações exatas |
| simplify | Original (avaliador independente) e resultado (SymPy) em 6 pontos sorteados; se `simplify(original − resultado) == 0`, também simbólico | `verified_symbolic` |
| solve_equation (polinomial ou racional, coeficientes racionais) | Cada solução substituída na equação original, de forma exata (raízes `CRootOf` por divisibilidade, Fase 9) e com o avaliador independente. Completude: o **teorema de Sturm** conta as raízes reais distintas; se contar mais do que as encontradas, o status é `failed` ([ADR 0006](0006-escopo-da-algebra.md)) | `verified_symbolic` |
| solve_equation (1º grau, qualquer coeficiente) | Substituição; coeficiente de `x` ≠ 0 ⇒ no máximo uma solução | `verified_symbolic` |
| solve_equation (outras: raiz, módulo, log, exponencial) | Substituição; pega raízes estranhas, mas a completude não é provada | `partial` |
| "sem solução" e "todo x real" | Diferença entre os lados (ou numerador) constante ou nula, mais pontos sorteados | `verified_symbolic` / `partial`; "nenhuma encontrada" sem prova: `unverified` (Fase 9) |
| factor / expand | `expand(resultado) − expand(original) == 0` + pontos numéricos | `verified_symbolic` |
| fatoração de inteiros | Produto exato dos fatores + primalidade de cada um (determinística abaixo de 2⁶⁴; BPSW acima) | `verified_symbolic` |
| polynomial_division | `B·Q + R = A` exato, `grau R < grau B`, mais pontos sorteados | `verified_symbolic` |
| derivative | Diferenças finitas (`mpmath.diff`, 80 + 10·ordem dígitos) sobre o avaliador independente, em 6 pontos sorteados; erro relativo até 1e-8 ([ADR 0007](0007-calculo.md)); comparação com um derivador próprio (Fase 9) | `verified_symbolic` |
| integral indefinida | A primitiva precisa ser real onde o integrando é definido; `diff(F) − f == 0` (derivar é um algoritmo diferente de integrar) + pontos | `verified_symbolic` |
| integral definida | Quadratura tanh-sinh (`mpmath.quad`, sem SciPy), erro até 1e-10; polinômios e racionais: Newton–Leibniz (Fase 9); divergente: `unverified` | `verified_numeric`; `verified_symbolic` por Newton–Leibniz |
| limit | Avaliação aproximando-se do ponto até 1e-24 (ou até 1e24) por cada lado pedido; `failed` só se a sequência estabiliza longe do valor; continuidade no ponto prova o limite (Fase 9) | `partial`; `verified_symbolic` por continuidade |
| solve_system (linear) | Substituição (simbólica e pelo avaliador independente) + **postos** da matriz dos coeficientes e da ampliada, para única, infinitas e nenhuma | `verified_symbolic` |
| graph | As amostras são do próprio avaliador independente; os pontos destacados (raízes, intercepto) são conferidos por ele. Raízes numéricas resultam em `partial`; sem pontos, `not_applicable` ([ADR 0008](0008-graficos.md)) | `verified_numeric` |

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
- A Fase 9 expandiu e formalizou este módulo
  ([ADR 0010](0010-verification-engine.md)).
