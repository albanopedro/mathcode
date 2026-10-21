# ADR 0031 — Quartis e IQR (estatística descritiva)

- **Status:** aceita
- **Data:** 2026-10-21

## Contexto

A ADR 0011 deixou os quartis como sugestão porque há várias convenções: livros,
calculadoras e planilhas dão valores diferentes para o mesmo conjunto. O item
foi escolhido no backlog e agora precisa de uma convenção explícita, exata e
verificável por outro caminho.

## Decisão

### Convenção

- **Q1 e Q3 são as medianas das metades.** Ordenados os dados, a metade
  inferior e a metade superior são divididas na mediana.
- Com quantidade **par**, as metades têm o mesmo tamanho: `1, 2, 3, 4` →
  inferior `1, 2`, superior `3, 4`; Q1 = 1,5 e Q3 = 3,5.
- Com quantidade **ímpar**, o valor central (a mediana) **não entra em nenhuma
  metade**: `1, 2, 3, 4, 5` → inferior `1, 2`, superior `4, 5`; Q1 = 1,5 e
  Q3 = 4,5.
- **IQR = Q3 − Q1**.
- **Q2 é a mediana**, já existente; não há uma linha duplicada "Q2" no resumo.
- São necessários **pelo menos 4 valores**. Com 2 ou 3, Q1 e Q3 seriam os
  extremos (ou quase), o que não diz nada sobre a dispersão.
- Tudo é exato (`Fraction`): não há interpolação, arredondamento nem posição
  fracionária.

### Exemplos

| Dados | Q1 | Mediana | Q3 | IQR |
|---|---|---|---|---|
| `1, 2, 3, 4` | 3/2 | 5/2 | 7/2 | 2 |
| `1, 2, 3, 4, 5, 6, 7, 8, 9` | 5/2 | 5 | 15/2 | 5 |
| `2, 4, 4, 4, 5, 5, 7, 9` | 4 | 9/2 | 6 | 2 |

### Alternativas descartadas

- **Interpolação** (Excel `QUARTILE.INC/EXC`, `numpy.percentile`, módulo
  `statistics.quantiles` do Python): para `1, 2, 3, 4` dá Q1 = 1,25 e
  Q3 = 3,75 na convenção exclusiva, ou 1,75 e 3,25 na inclusiva. É defensável,
  mas menos intuitiva na escola e mais difícil de explicar sem uma fórmula.
- **Dobradiças de Tukey** (incluir a mediana nas duas metades quando ímpar):
  para `1, …, 9` dá Q1 = 3 e Q3 = 7, e não 2,5 e 7,5. Também é comum, mas
  contraria a ideia de "metade inferior" e "metade superior".
- **Posto mais próximo**: joga os quartis para valores observados e perde a
  simetria da mediana.

A convenção escolhida é a que o projeto consegue explicar em uma frase e
recomputar com `statistics.median` sobre as metades, sem depender do motor.

### Entrada

- `Measure` ganhou `q1`, `q3` e `iqr`; `q2` não existe como opção porque é a
  mediana.
- Frases: `primeiro quartil`, `1º quartil` e `q1`; `terceiro quartil`,
  `3º quartil` e `q3`; `IQR` e `intervalo interquartil`; `segundo quartil`,
  `2º quartil` e `q2` viram `median`; `quartil`/`quartis` sem ordinal pedem o
  resumo completo (que já mostra Q1, Q3 e IQR).
- Com menos de 4 valores, o resumo mostra "—" e um aviso
  (`QUARTILES_NOT_DEFINED`); pedir a medida diretamente dá erro explicado.

### Cálculo (`math_engine/statistics.py`)

- `_median` centraliza a mediana (par: média dos dois centrais).
- `_quartiles` recebe os dados já ordenados e devolve `(None, None)` abaixo de
  4 valores; senão, `median(lower)` e `median(upper)`.
- `iqr` é uma propriedade, sempre `Q3 − Q1` (não pode divergir dos quartis).
- O aviso novo é `QUARTILES_NOT_DEFINED`.

### Verificação (`verification/statistics.py`)

1. A verificação **ordena os dados de novo** e separa as metades com a mesma
   convenção, sem usar `outcome.q1/q3` para calcular o esperado.
2. Recalcula Q1 e Q3 com `statistics.median` nas metades e o IQR como
   `Q3 − Q1`, comparando exatamente.
3. Propriedades: `Q1 ≤ mediana ≤ Q3` e `IQR = Q3 − Q1`; abaixo de 4 valores,
   os três precisam ser `None`.
4. A matriz de adulteração ganhou Q1 e Q3 alterados por `1/10⁹`.

Status: `verified_symbolic`, como o resto da estatística.

### Apresentação

- O resumo passa de 12 para **15 medidas**: `q1`, `q3` e `iqr` entram logo
  depois da mediana.
- Rótulos: "1º quartil" (`Q_{1}`), "3º quartil" (`Q_{3}`) e "Intervalo
  interquartil" (`\mathrm{IQR}`).
- Pedidos diretamente, a manchete é `Q₁ = 3/2`, `Q₃ = 7/2` ou `IQR = 2`.
- O frontend só precisou dos rótulos da interpretação (`utils/interpretation.ts`):
  a tabela é genérica e valida os `details`; os três fixtures de estatística
  foram recapturados da API.

## Consequências

- A API aceita `{"intent": "statistics", "options": {"measure": "q1"}}` (e
  `q3`, `iqr`).
- O prompt da IA lista as três medidas e explica a convenção em uma linha.
- `docs/architecture.md` reflete as 15 medidas; os rótulos da interpretação
  ("medida: 1º quartil") foram atualizados no frontend.
- Testes: 1 713 no backend (eram 1 689) e 355 no frontend (eram 354).
- Fica registrado para o futuro: média ponderada, tabela de frequências e
  dados irracionais continuam no backlog.
