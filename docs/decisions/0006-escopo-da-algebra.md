# ADR 0006 — Escopo da álgebra (Fase 5)

- **Status:** aceita
- **Data:** 2026-10-06

## Contexto

O roadmap pedia "simplificação, fatoração, expansão, equações, sistemas e
polinômios" sem detalhar. Três pontos dependiam do usuário. Os demais eram
técnicos.

## Decisões do usuário

1. **Seletor de operação na interface.** Fatorar, expandir e dividir não podem
   ser deduzidos da entrada: `x^2 - 4` sozinho é uma simplificação. O seletor
   usa o campo `intent` da API. Frases como "fatore x² - 4" ficam para a Fase 8.
2. **"Polinômios" significa divisão de polinômios:** quociente e resto de
   `A / B`. É o único item que fatorar, expandir e resolver não cobrem.
3. **Sistemas só lineares.** Os não lineares ficam registrados como sugestão.

## Decisões técnicas

### Detecção automática da operação

| Entrada | Operação |
|---|---|
| equações separadas por `;` (ou `, ` com espaço) | `solve_system` |
| uma equação | `solve_equation` |
| expressão com variável | `simplify` |
| expressão só com números | `arithmetic` |

`factor`, `expand` e `polynomial_division` só rodam quando pedidos.

### Equações: a forma decide o método

A forma vem da **AST**, antes de o SymPy simplificar
(`math_engine/polynomials.py`).

| Forma | Método | Completude ("não há outras soluções") |
|---|---|---|
| Polinomial, coeficientes racionais | `real_roots` (exato, com multiplicidade) | **Provada pelo teorema de Sturm** (`count_roots`), um algoritmo diferente do que encontra as raízes |
| Polinomial, coeficientes irracionais | `solveset` sobre ℝ | Provada só no 1º grau (coeficiente ≠ 0). Nos demais casos: `partial` |
| Racional (variável no denominador) | raízes do numerador menos os zeros dos denominadores | Sturm no numerador, quando racional |
| Outras (raiz, módulo, log, exponencial) | `solveset` sobre ℝ | `partial` |
| Infinitas soluções periódicas (trigonométricas) ou sem forma fechada | — | `UNSUPPORTED_FEATURE` |

- Se Sturm conta mais raízes do que foram encontradas, a verificação é
  **`failed`**, não `partial`: é uma prova de que faltou alguma.
- Toda solução é substituída na equação **original** pelo avaliador
  independente. Isso pega raízes estranhas, como `x = -1` em `sqrt(x + 2) = x`.
- Equações polinomiais com menos raízes reais que o grau recebem o aviso
  `COMPLEX_SOLUTIONS_OMITTED`.
- **Raízes sem forma radical real** (`CRootOf`, como as três raízes de
  `x³ = 3x − 1`) continuam exatas no cálculo e na verificação, mas são
  **exibidas aproximadas**, com o aviso `ROOTS_SHOWN_APPROXIMATELY`. A fórmula
  de Cardano daria expressões com números complexos.
- "Todo real exceto pontos" (`x/x = 1`) aparece como `x ∈ ℝ \ {0}`.
- Várias raízes aparecem **uma por linha** no LaTeX (x₁, x₂, ...). Numa linha
  só, não cabiam na tela do celular.

### Sistemas lineares

- `linsolve` dá três casos: solução única, infinitas (forma paramétrica, com
  variáveis livres) ou nenhuma.
- **Verificação:** a solução é substituída de forma simbólica e pelo avaliador
  independente; nas infinitas, com valores sorteados para as variáveis livres.
  A completude vem dos **postos** da matriz dos coeficientes e da ampliada.
- Limite de 10 equações e 10 variáveis. Uma equação sozinha é aceita como
  sistema de uma equação.

### Fatoração, expansão e divisão

- **Fatoração sobre ℚ** (`x² − 2` não muda, e a interface explica isso).
  **Inteiros** viram fatoração em primos. A verificação refaz o produto exato e
  testa a primalidade de cada fator: o teste é determinístico abaixo de 2⁶⁴; acima
  disso é o BPSW, e o relatório diz qual foi usado.
- **Fatorar e expandir** são verificados por `expand(original − resultado) = 0`
  e por pontos sorteados.
- **Divisão:** A e B são construídos separadamente, para o SymPy não cancelar
  fatores antes. Verificação: `B·Q + R = A` exato, `grau R < grau B`, e pontos
  sorteados. Só uma variável.

## Consequências

- O campo `details` do `MathResult` depende do intent:
  - `changed`;
  - `solutions`, `multiplicities` e `excluded`;
  - `variables` e `free_variables`;
  - `quotient`, `remainder` e `exact`;
  - `prime_factors`.

  O frontend monta legendas a partir desses campos (`utils/captions.ts`) sem
  calcular nada.
- Sistemas não lineares, equações trigonométricas e divisão com várias variáveis
  ficam como sugestões.
