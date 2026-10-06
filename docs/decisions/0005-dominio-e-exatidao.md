# ADR 0005 — Domínio padrão, exatidão e convenções

- **Status:** aceita
- **Data:** 2026-10-06

## Contexto

A mesma pergunta tem respostas diferentes conforme as convenções adotadas:
`x² + 1 = 0`, `sqrt(-4)`, `log(100)`, `sen(30)`, `0.1 + 0.2`. Escolher sem
avisar o usuário seria uma forma de esconder erro.

## Decisão

| Tema | Convenção | Aviso ao usuário |
|---|---|---|
| Domínio | **ℝ** (números reais); toda variável é real | Se existirem soluções complexas descartadas: `COMPLEX_SOLUTIONS_OMITTED` |
| Raiz de índice par de negativo (`sqrt(-4)`, `(-4)^(1/2)`) | erro `DOMAIN_ERROR` | — |
| Raiz de índice ímpar de negativo (`(-8)^(1/3)`) | **raiz real** (`-2`), e não a raiz principal complexa do SymPy | `REAL_ROOT` |
| Negativo elevado a expoente irracional (`(-2)^pi`) | erro `DOMAIN_ERROR` | — |
| `0^0` | erro `DOMAIN_ERROR` (indeterminação, como no ensino médio). O SymPy e o Python dariam `1`. | — |
| Decimais digitados | viram **frações exatas** (`0.1` → `1/10`) | — |
| Saída | forma **exata** + aproximação decimal (15 algarismos significativos) quando o resultado não for inteiro | — |
| `log(x)` | **base 10** (convenção do ensino brasileiro) | `LOG_BASE_10`, uma vez por resultado |
| `ln(x)` | logaritmo natural | — |
| `log(x; b)` ou `log(x, b)` | base `b`, que precisa ser positiva e diferente de 1 | — |
| Ângulos | **radianos** | `ANGLE_IN_RADIANS` quando uma função trigonométrica recebe um número puro; `30°` é aceito como graus |
| Divisão por zero | erro `DIVISION_BY_ZERO` (não devolve `zoo`/`nan`) | — |
| Sem solução | **sucesso** com conjunto vazio (`∅`), não erro | `COMPLEX_SOLUTIONS_OMITTED` quando há raízes complexas (Fase 5) |
| Todo real exceto pontos (`x/x = 1`) | `x ∈ ℝ \ {0}`: os zeros dos denominadores ficam de fora | — |

## Consequências

- O parser reconhece `°` como operador pós-fixo (ver a gramática no
  [ADR 0002](0002-parser-sem-eval.md)).
- Cada convenção acima tem um teste próprio, para que nenhuma mude sem querer.
- O domínio complexo pode virar uma opção explícita no futuro, como sugestão
  registrada, mas não está no escopo atual.
