# ADR 0015 — Probabilidade e contagem (Fase 10, 5º domínio)

- **Status:** aceita
- **Data:** 2026-10-08

## Contexto

Antes desta etapa:
- "probabilidade" caía na regra "ainda não suportado";
- `5!` era um caractere inválido;
- `C(10, 3)` era lido como `C·(10, 3)`, um ponto fora da Geometria.

O usuário pediu os dois domínios que faltavam (probabilidade/combinatória e
trigonometria), um por alteração, começando pela probabilidade.

## Decisões do usuário

1. **Conteúdos (todos):**
   - fatorial e contagem (permutação, arranjo e combinação, com e sem repetição);
   - anagramas;
   - probabilidade de eventos (complementar, "e", "ou", condicional);
   - distribuição binomial.
2. **Contagem na linguagem:** `5!`, `C(10, 3)` e `A(6, 2)` valem em qualquer
   conta. `C` e `A` só viram funções com dois argumentos, e `C(x + 1)`
   continua sendo `C·(x + 1)`.
3. **Eventos:** `P(A) = 1/2; P(B) = 1/3`, com `P(A e B)` opcional. Sem ele, "A e
   B" e "A ou B" só têm resposta no cálculo que diz "independentes".
4. **Resultado:** fração e porcentagem (`P = 3/8`, "37,5%"). Na entrada da
   operação, `30%` vale 3/10. Fora dela, `%` continua sendo erro, porque
   `50 + 10%` é ambíguo.
5. **Interface:** operação "Probabilidade" com o campo Cálculo (em grupos), como
   matrizes, vetores e geometria.

## Decisão

### Contagem na linguagem (parser)

| Entrada | Leitura |
|---|---|
| `5!` | `Call("factorial", (5,))`, pós-fixo com a força do `°`: `2^3! = 2^(3!)`, `-3! = -(3!)` |
| `C(10, 3)`, `A(6, 2)` | funções, só quando há uma vírgula logo dentro dos parênteses (*lookahead*) |
| `C(x + 1)` | `C·(x + 1)`, como antes (variável e multiplicação implícita, com aviso) |
| `3!!` | erro: fatorial duplo ou `(3!)!`? |
| `C(10,3)` | erro: `C(10, 3)` ou `C·10,3` com vírgula decimal? |
| `c(10, 3)` | erro com a dica da letra maiúscula |

Os argumentos são **números inteiros não negativos**, sem variáveis. `(1/2)!`,
`pi!` e `x!` são erros explicados. Há duas proteções de tamanho:
- **Antes de calcular:** o tamanho do resultado é estimado (`lgamma`), e mais de
  4 000 dígitos é recusado. `1500!` é recusado na hora.
- **Escolher mais do que existe:** `C(3, 5) = 0`, com o aviso `COUNT_IS_ZERO`,
  que lembra a ordem `C(n, k)`.

O texto canônico imprime `5!` e `C(10, 3)`, e `(3!)!` mantém os parênteses. Os
dois avaliadores independentes também aprenderam a contagem:
- **`exact.py`:** pelas definições, produto fator a fator, com inteiros do Python;
- **`numeric.py`:** pelo mpmath, com `factorial`, `binomial` e `ff`. Argumentos
  como `0,1·30` são arredondados ao inteiro, porque são inteiros a menos do
  arredondamento.

Assim, `C(4, 2)/C(52, 2) = 1/221` é aritmética comum, verificada simbolicamente.

O leitor de frases deixou de apagar o `!` final depois de um número ou de `)`:
"quanto é 5!" é um fatorial, não uma exclamação.

### O intent `probability`

`ProbabilityParams(data, calculation)`. O catálogo fica em
`math_engine/probability.py`, com um espelho em `frontend/src/utils/probability.ts`.

| Grupo | Cálculo | Valores | Fórmula |
|---|---|---|---|
| contagem | `factorial` | `n` (pode ir sem nome) | n! |
| | `arrangement` | `n`, `k` | A(n, k) = n!/(n − k)! |
| | `arrangement_repetition` | `n` ≥ 1, `k` | AR(n, k) = nᵏ |
| | `combination` | `n`, `k` | C(n, k) = n!/(k!(n − k)!) |
| | `combination_repetition` | `n` ≥ 1, `k` | CR(n, k) = C(n + k − 1, k) |
| | `anagrams` | uma palavra | P₆^{3,2} = 6!/(3!·2!) (BANANA) |
| eventos | `complement` | `P(A)` | 1 − P(A) |
| | `intersection` | `P(A)`, `P(B)`, `P(A ou B)` | P(A) + P(B) − P(A ∪ B) |
| | `intersection_independent` | `P(A)`, `P(B)` | P(A)·P(B) |
| | `union` | `P(A)`, `P(B)`, `P(A e B)` | P(A) + P(B) − P(A ∩ B) |
| | `union_independent` | `P(A)`, `P(B)` | P(A) + P(B) − P(A)·P(B) |
| | `conditional` | `P(A e B)`, `P(B)` | P(A ∩ B)/P(B) |
| binomial | `binomial_exact` | `n`, `k`, `p` | C(n, k)·pᵏ·(1 − p)ⁿ⁻ᵏ |
| | `binomial_at_most`, `binomial_at_least` | `n`, `k`, `p` | somas dos termos |
| | `binomial_summary` | `n`, `p` | μ = np, σ² = np(1 − p), σ |

**Leitura dos valores:**
- **Separadores:** `;` ou `, ` com espaço, porque `0,5` é um decimal.
- **Leitura:** cada valor passa pelo parser seguro. Os eventos aceitam
  `P(A e B)`, `P(A ∩ B)`, `P(A ou B)` e `P(A ∪ B)`. Uma probabilidade pode
  terminar em `%`.
- **Racionais:** as probabilidades precisam ser números racionais. Uma
  probabilidade como √2/2 é recusada, como os dados da estatística (ADR 0011).
- **Texto canônico:** "Entendido como" mostra o que foi lido, como
  `P(A ∩ B) = 1/6`.

**Erros e avisos:**
- **Erros explicados:**
  - valor que falta, com o exemplo do cálculo;
  - valor repetido;
  - nome de outro grupo;
  - probabilidade fora de [0, 1];
  - P(A ∩ B) maior que P(A), ou menor que P(A) + P(B) − 1;
  - valores que não combinam (P(A ∪ B) ≠ P(A) + P(B) − P(A ∩ B));
  - eventos declarados independentes que não são;
  - P(B) = 0 na condicional;
  - k > n na binomial.
- **Avisos:**
  - um valor do grupo que o cálculo não usa recebe o aviso `UNUSED_VALUES`. Isso
    permite trocar de cálculo sem reescrever a entrada;
  - nos eventos, os valores a mais são conferidos;
  - os acentos dos anagramas são ignorados com o aviso `ACCENTS_IGNORED`
    (MATEMÁTICA = MATEMATICA).
- **Limites:**
  - binomial até n = 1 000 tentativas;
  - frações até 4 000 dígitos, estimados antes de somar;
  - palavras de até 30 letras.

### Apresentação

- **Contagens:** um inteiro (`C(10, 3) = 120`). Nos anagramas, aparece a notação
  P₆^{3,2}, que cabe no celular, e as letras repetidas.
- **Probabilidades:** fração exata, sem a aproximação decimal, e a porcentagem em
  `details.percent`, com vírgula. Ela é exata até 6 casas (`37,5%`, `0,03125%`).
  Fora disso é arredondada, e a interface mostra "≈":
  - 2 casas a partir de 1% (`16,67%`);
  - 4 algarismos significativos abaixo de 1% (`9,333·10⁻³⁰⁰%`).
- **Resumo da binomial:** μ, σ² e σ em três linhas, com σ aproximado em 6
  algarismos.

### Verificação (`verification/probability.py`)

Nada vem do SymPy do motor:

| Caso | Segundo método |
|---|---|
| valores | relidos com frações exatas (`exact_value`), divididos por 100 se tinham `%` |
| fatorial, arranjo, nᵏ | produtos fator a fator com inteiros do Python |
| combinação (com e sem repetição) | C·k! = produto de k inteiros consecutivos (as mesmas escolhas, em ordem) |
| anagramas | as posições de cada letra escolhidas uma letra por vez; as letras recontadas |
| contagens até 100 000 | **listagem uma a uma** (`itertools`; anagramas por um gerador de ordens distintas) |
| eventos | as quatro regiões do diagrama de Venn são probabilidades que somam 1; e regras que o motor não usa (P(A ∣ B)·P(B) = P(A ∩ B); 1 − P(A ∪ B) = P(Ā)·P(B̄) e P(A∩B)·P(nem A nem B) = P(só A)·P(só B) para independentes) |
| binomial | a distribuição refeita pela recorrência P(i+1) = P(i)·(n − i)/(i + 1)·p/(1 − p) soma 1; P(X ≥ k) = 1 − P(X < k); μ = Σ i·P(i) e σ² = Σ i²·P(i) − μ² |

Tudo é exato, e o status é `verified_symbolic`. A matriz de adulteração ganhou o
caso de probabilidade.

### Frases (`interpreter/language.py`)

As regras de probabilidade vêm antes das de estatística, porque "média da
binomial com n = 10…" não é uma lista de dados. Exemplos:
- **Contagem:**
  - "fatorial de 6", "8 fatorial", "permutação de 5 elementos";
  - "combinação de 10 tomados 3 a 3", "arranjos com repetição de 3 tomados 2 a 2";
  - "quantos anagramas tem a palavra BANANA?".
- **Binomial:**
  - "binomial com n = 5, k = 3 e p = 1/2" (com "no máximo" e "pelo menos");
  - "média e variância da binomial com n = 10 e p = 0,3".
- **Eventos:**
  - "probabilidade de A ou B com P(A) = 1/2, P(B) = 1/3 e P(A e B) = 1/6";
  - "… independentes";
  - "probabilidade de não A sendo P(A) = 30%".

Problemas em palavras ("probabilidade de tirar 6 num dado") não têm regra: com
"Permitir IA", vão para a IA. O prompt ganhou o intent `probability` e a sintaxe
`n!`, `C(n, k)` e `A(n, k)`, que permitem traduzir sem calcular (exemplo:
"de quantas formas posso escolher 3 de 10 pessoas?" → `C(10, 3)`). Nenhuma
chamada real foi feita.

## Consequências

- **O que muda:**
  - há um intent novo, `probability`;
  - o parser ganhou `!`, `C(n, k)` e `A(n, k)`;
  - "probabilidade" saiu da regra "ainda não suportado";
  - `!` não é mais um caractere inválido.
- **Configuração:** o `ruff` aceita `∪` como símbolo matemático
  (`allowed-confusables`).
- **Sugestões registradas:**
  - fatorial com variáveis, como simplificar `(n + 1)!/n!`;
  - fatorial duplo;
  - permutação circular;
  - outras distribuições (geométrica, Poisson, normal);
  - tabela e gráfico da distribuição binomial;
  - mais de dois eventos;
  - probabilidades irracionais;
  - pontos com nome na geometria (`A(1, 2)` hoje é um arranjo).
