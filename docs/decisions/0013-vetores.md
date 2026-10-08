# ADR 0013 — Vetores (Fase 10, 3º domínio)

- **Status:** aceita
- **Data:** 2026-10-07
- **Complementa:** [ADR 0012](0012-matrizes.md) (matrizes)

## Contexto

Vetores são a continuação natural das matrizes: usam a mesma sintaxe de
colchetes e a mesma álgebra (soma, múltiplo, produto por matriz). Antes desta
etapa, `[1, 2, 3]`, com um colchete só, era recusado com a mensagem "escreva
cada linha da matriz entre colchetes".

## Decisões do usuário

1. **Operações:**
   - soma, subtração e multiplicação por número, escritas como expressão;
   - produto escalar, norma, vetor unitário e ângulo;
   - produto vetorial (3D);
   - matriz × vetor, com o vetor tratado como coluna.
2. **Interface:** operação "Vetores" com o campo "Cálculo" (Norma, Vetor
   unitário, Produto escalar, Produto vetorial, Ângulo, Calcular expressão).
   Dois vetores vão separados por `;`. Frases e o Automático também funcionam.
3. **Ângulo:** em radianos exatos **e** em graus (θ = π/4 = 45°).

Ficam valendo, das matrizes: só números exatos e até 8 componentes.

## Decisão

### Sintaxe

- `[1, 2, 3]` é o nó `Vector(entries)`; `[[…]]` continua sendo `Matrix`. Os
  dois são termos da expressão, então `2*[1, 0] + [0, 3]` e
  `[[1, 2], [3, 4]] * [5, 6]` são expressões comuns.
- `u; v` forma uma lista. Uma lista com vetores ou matrizes não cai mais no
  erro de "lista de números" (`has_brackets`).
- No Automático, entrada com matriz vai para `matrix`, e entrada só com
  vetores vai para `vector`.

### Uma álgebra só (`math_engine/matrices.py`)

O avaliador das matrizes virou o `LinearEvaluator`, com três tipos de valor:
número, `VectorValue` (uma coluna n×1) e matriz. As operações Matrizes e
Vetores usam o mesmo avaliador e as mesmas regras:

| Expressão | Resultado |
|---|---|
| vetor ± vetor (mesmo tamanho) | vetor |
| número · vetor, vetor · número, vetor / número | vetor |
| matriz · vetor (colunas de A = componentes) | vetor (A·v) |
| vetor · matriz | erro: "escreva a matriz antes: A*v" |
| vetor · vetor | erro: ambíguo, use Produto escalar ou vetorial |
| vetor ^ n, número ± vetor, ÷ vetor | erro explicado |

Na operação Matrizes, "Calcular expressão" aceita um resultado vetor (A·v); os
outros cálculos de matriz recusam vetores e apontam a operação Vetores.

### Operações (`math_engine/vectors.py`)

- `VectorParams(expression, operation)`, com `operation` em `evaluate`,
  `norm`, `unit`, `dot`, `cross` e `angle`.
- `norm` e `unit` usam um vetor; `dot`, `cross` e `angle` usam dois, do mesmo
  tamanho. `cross` só existe em 3D.
- O vetor nulo não tem unitário nem ângulo (`DOMAIN_ERROR`).
- Ângulo: θ = acos(u·v / (‖u‖‖v‖)), exato, em radianos (π/4, ou acos(24/25)).

### Verificação (`verification/vectors.py`)

Os vetores são reavaliados sem o SymPy, pelos mesmos reavaliadores das
matrizes: com frações quando todo número é racional, ou com mpmath a 60
dígitos. Depois, cada operação é conferida por outro caminho:

| Operação | Conferência |
|---|---|
| norma | ‖u‖² = u·u (refeito) e ‖u‖ ≥ 0 |
| unitário | ‖û‖ = 1 e û·‖u‖ = u (mesma direção e sentido) |
| escalar | a soma dos produtos, refeita |
| vetorial | a fórmula refeita; u×v ⟂ u e u×v ⟂ v; identidade de Lagrange ‖u×v‖² = ‖u‖²‖v‖² − (u·v)² |
| ângulo | o mpmath refaz acos a partir das frações; cos θ = u·v/(‖u‖‖v‖) exato, com 0 ≤ θ ≤ π |

Com números racionais, o resultado é `verified_symbolic`. Com irracionais, ou
quando o cosseno exato não é igualado (ângulo), é `verified_numeric`. A matriz
de adulteração ganhou o caso de vetor.

### Apresentação

- Vetor: `plain` `[1, 2, 3]` e LaTeX `\left(1,\ 2,\ 3\right)`.
- Prefixos: `‖u‖ = `, `û = `, `u·v = `, `u×v = `, `θ = ` (com `\lVert u
  \rVert`, `\hat{u}`, `u \cdot v`, `u \times v` e `\theta` no LaTeX).
- Ângulo:
  - em graus exatos quando possível: `θ = pi/4 rad = 45°`;
  - senão, `θ = acos(24/25) rad ≈ 16.2602°`, com 6 algarismos na manchete
    (15 em `details.degrees_approx`);
  - a aproximação em radianos traz a unidade: `0.785398163397448 rad`.
- `details`: `operation`, `dimension`, `vectors` e `vectors_latex`; no ângulo,
  também `degrees` (ou `null`) e `degrees_approx`.
- A interface mostra "u = (…)" e "v = (…)" abaixo do resultado. Vetores são
  sempre desenhados como fórmula.

### Frases (`interpreter/language.py`)

- "norma / módulo / comprimento de", "vetor unitário / versor de", "produto
  escalar / interno de … e …", "produto vetorial entre … e …", "ângulo entre
  (os vetores) … e …", seguidos de vetores entre colchetes. O " e " entre dois
  vetores vira `;`.
- "produto escalar de u e v", sem colchetes, recebe a orientação de sintaxe.
  "módulo de −3" não vira vetor.
- O prompt da IA ganhou o intent `vector`; nenhuma chamada real foi feita.

## Consequências

- Há um intent novo, `vector`. `[1, 2]`, antes recusado, agora é um vetor.
- Sugestões registradas:
  - projeção de um vetor sobre outro;
  - produto misto;
  - vetor × matriz (linha);
  - vetores com letras.
