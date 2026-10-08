# ADR 0012 — Matrizes (Fase 10, 2º domínio)

- **Status:** aceita; ampliada pelo [ADR 0013](0013-vetores.md) (vetores: o avaliador
  passou a ser comum, e A·v dá um vetor)
- **Data:** 2026-10-07

## Contexto

O prompt mestre pede, entre os objetivos, "calcule o determinante dessa
matriz". Até esta etapa, o parser não tinha colchetes e as frases com
"determinante" ou "matriz" caíam na regra "ainda não suportado".

## Decisões do usuário

1. **Operações:**
   - determinante, inversa, transposta, traço e posto;
   - aritmética de matrizes (soma, subtração, produto, multiplicação e divisão
     por número, potência inteira), escrita como expressão.

   Autovalores ficam como sugestão: podem ser complexos, e o domínio do
   projeto é ℝ ([ADR 0005](0005-dominio-e-exatidao.md)).
2. **Entradas:** só números exatos (inteiros, decimais, frações, √2, π...),
   até 8×8.
3. **Sintaxe:** `[[1, 2], [3, 4]]`, uma linha por colchete, com os separadores
   que o projeto já usa (`, ` ou `; `; `1,5` continua decimal).
4. **Interface:** operação "Matrizes" + campo "Cálculo" (Determinante, Inversa,
   Transposta, Traço, Posto, Calcular expressão). Frases e expressões com
   colchetes no Automático também funcionam.

## Decisão

### Sintaxe (`parsing/`)

- Tokens `[` e `]`; nó `Matrix(rows, position)` na AST, que é um termo da
  expressão. Por isso, `[[1, 2], [3, 4]] * [[5, 6], [7, 8]]` e `A^-1` são
  expressões comuns para o parser.
- Erros com posição, explicados:
  - linhas de tamanhos diferentes;
  - linha sem colchete (`[1, 2]`);
  - colchete sem par;
  - matriz dentro de matriz;
  - mais de 8 linhas ou colunas;
  - multiplicação sem `*` (`2[[1]]`).
- As outras operações recusam matrizes (o builder do SymPy dá uma mensagem que
  aponta a operação Matrizes). No Automático, uma expressão com matriz é
  detectada como `matrix`.

### Cálculo (`math_engine/matrices.py`)

- `MatrixParams(expression, operation)`, com `operation` em `evaluate`,
  `determinant`, `inverse`, `transpose`, `trace` e `rank` (padrão:
  `evaluate`).
- A expressão é avaliada pela árvore. As regras da álgebra de matrizes valem, e
  cada caso incompatível tem uma explicação:
  - soma só entre matrizes do mesmo tamanho;
  - produto só com colunas de A = linhas de B;
  - número com matriz só por multiplicação ou divisão;
  - não existe divisão por matriz;
  - potência só de matriz quadrada, com expoente inteiro de −20 a 20, e
    potência negativa só de matriz invertível.
- Depois, a operação é aplicada à matriz A resultante:
  - determinante, inversa e traço exigem matriz quadrada;
  - matriz singular (determinante 0) não tem inversa (`DOMAIN_ERROR`).
- Elementos irracionais são simplificados (`sp.simplify`); o limite de 4 000
  dígitos vale para cada elemento.

### Verificação (`verification/matrices.py`)

A expressão é reavaliada sem o SymPy:

- **Modo exato:** quando todo número é racional. Usa `Fraction` e álgebra de
  matrizes escrita no próprio verificador (soma, produto, potência,
  Gauss–Jordan). O resultado é `verified_symbolic`.
- **Modo numérico:** com √2, π etc. Usa o avaliador independente e matrizes do
  mpmath a 60 dígitos, com tolerância de 30 algarismos. O resultado é
  `verified_numeric`.

Depois, cada operação é conferida por outro caminho:

| Operação | Conferência |
|---|---|
| todas | a matriz A, recalculada, é a mesma |
| determinante | eliminação de Gauss com frações (o SymPy usa Bareiss); no numérico, LU do mpmath |
| inversa | A·A⁻¹ = I **e** A⁻¹·A = I |
| transposta | elemento (i, j) do resultado = elemento (j, i) de A |
| traço | soma da diagonal refeita |
| posto | eliminação de Gauss (no numérico, com pivô e tolerância) |

A matriz de adulteração ganhou o caso de matriz (inversa trocada pela
transposta).

### Apresentação

- Matriz: `plain` como `[[19, 22], [43, 50]]` e LaTeX `\left[\begin{matrix}…`.
  Com irracionais, `approx` traz a matriz em decimais.
- Prefixos: `det = `, `A⁻¹ = `, `Aᵀ = `, `traço = `, `posto = ` (e
  `\det(A)`, `A^{-1}`, `A^{T}`, `\operatorname{tr}(A)`,
  `\operatorname{posto}(A)` no LaTeX).
- `details`: `operation`, `rows`, `cols`, `matrix` e `matrix_latex` (a matriz A
  usada). A interface mostra "Matriz A (m×n)" abaixo do resultado, exceto em
  "Calcular expressão", em que A é o próprio resultado.
- Um resultado matriz é sempre desenhado como fórmula, mesmo com texto longo: a
  largura dele depende das colunas (no máximo 8).

### Frases (`interpreter/language.py`)

- "determinante de", "(matriz) inversa de", "transposta de", "traço da
  matriz", "posto de", seguidos de uma matriz entre colchetes.
- Sem colchetes, "determinante"/"matriz" recebem a orientação de sintaxe.
  "inversa de x^2" não vira matriz.
- O prompt da IA ganhou o intent `matrix`; nenhuma chamada real foi feita.

## Consequências

- Há um intent novo, `matrix`, e o parser ganhou colchetes. Nenhuma entrada
  antiga muda de significado, porque `[` era um caractere recusado.
- Sugestões registradas:
  - autovalores e autovetores (decidir o tratamento dos complexos);
  - matrizes com letras (ex.: det de [[a, b], [c, d]]);
  - vetores (produto escalar, vetorial, norma);
  - um editor de matriz em grade (Fase 11).
