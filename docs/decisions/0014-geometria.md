# ADR 0014 — Geometria (Fase 10, 4º domínio)

- **Status:** aceita
- **Data:** 2026-10-07

## Contexto

"Qual a área de um círculo de raio 5?" era o último objetivo explícito do
prompt mestre ainda pendente. Antes desta etapa, frases com "área",
"perímetro" e "volume" caíam na regra "ainda não suportado", e `(1, 2)` era um
erro de parêntese.

## Decisões do usuário

1. **Conteúdos:**
   - figuras planas (área e perímetro);
   - sólidos (volume e área da superfície);
   - geometria analítica (distância, ponto médio, reta, área de polígono);
   - Pitágoras e classificação de triângulos.
2. **Interface:** operação "Geometria" com os campos Figura e Cálculo; as
   medidas vão no campo de texto, como `r = 5` ou `b = 4; h = 3`. Frases
   também funcionam.
3. **Pontos:** `(1, 2)`, com parênteses; dois ou mais separados por `;`.
4. **Unidades:** nenhuma. As medidas são números puros, e o resultado diz se é
   comprimento, área ou volume.

## Decisão

### Catálogo (`math_engine/geometry.py`)

Um catálogo único diz, para cada figura, as medidas e os conjuntos de medidas
que cada cálculo aceita. O frontend tem um espelho dele (`utils/geometry.ts`),
com os rótulos e um exemplo de cada figura.

| Figura | Medidas | Cálculos |
|---|---|---|
| círculo | `r` ou `d` | área, circunferência |
| quadrado | `l` | área, perímetro |
| retângulo | `b`, `h` | área, perímetro |
| triângulo | `a`, `b`, `c` (lados), ou `b`, `h` (só área) | área (Heron com lados), perímetro, classificação |
| trapézio | `B`, `b`, `h` | área |
| losango | `D`, `d` (diagonais) | área, perímetro |
| paralelogramo | `b`, `h` (área); `a`, `b` (perímetro) | área, perímetro |
| cubo | `a` | volume, superfície |
| paralelepípedo | `a`, `b`, `c` | volume, superfície |
| esfera | `r` | volume, superfície |
| cilindro, cone | `r`, `h` | volume, superfície |
| triângulo retângulo | dois de `a`, `b` (catetos) e `c` (hipotenusa) | lado que falta |
| pontos | `(x, y)` ou `(x, y, z)` | distância, ponto médio, reta (2D), área do polígono (2D) |

### Entrada

- As medidas são lidas pelo parser seguro: `r = 5` é uma `Equation`, e
  `b = 4; h = 3` é um `System`. À esquerda de cada `=` vai o nome da medida; à
  direita, um número, que pode ser `√2` ou `2,5`.
- Quando o cálculo usa uma medida só, ela pode ir sem nome: `5` é o raio.
- Erros explicados:
  - medida que não existe na figura (com a lista das que existem);
  - medida repetida, faltando ou a mais (com a combinação esperada);
  - medida não positiva;
  - lados que não formam triângulo (desigualdade triangular);
  - hipotenusa menor que o cateto;
  - dois pontos iguais numa reta;
  - polígono com menos de 3 vértices, com pontos alinhados ou com lados que se
    cruzam.
- Pontos: o nó `Point` do parser. Uma vírgula dentro de parênteses faz um
  ponto, e `(x + 1)` continua sendo só um agrupamento. No Automático, pontos
  sozinhos pedem a escolha do cálculo.

### Resultados

- Exatos: π continua π (`A = 25π`, com a aproximação ao lado).
- Reta: `y = 4x/3 + 2/3`, ou `x = 1` (vertical), com a equação geral sem fator
  comum (`4x − 3y = −2`) e a inclinação.
- Classificação: "triângulo escaleno e retângulo" (por lados e por ângulos).
- `details`: `figure`, `calculation`, `measures`, `points`, `formula` (o LaTeX
  da fórmula usada), `quantity` (`length`, `area`, `volume` ou `null`) e, na
  reta, `equation` e `slope`. A interface mostra a fórmula e "em unidades de
  área" (comprimento, volume).

### Verificação (`verification/geometry.py`)

As medidas e os pontos são relidos sem o SymPy, com frações ou com o avaliador
mpmath. Depois, o resultado é obtido por um método diferente da fórmula usada:

| Caso | Segundo método |
|---|---|
| polígonos (quadrado, retângulo, trapézio, losango, paralelogramo, triângulo) | vértices de uma figura com essas medidas: área pela fórmula do cadarço, perímetro pela soma dos lados |
| triângulo pelos lados | coordenadas dos vértices (em vez de Heron) |
| círculo | integral da altura (∫ 2√(r² − x²) dx) e comprimento de arco |
| esfera, cilindro, cone | sólido de revolução (volume) e superfície de revolução (área) |
| cubo, paralelepípedo | seção integrada (volume); base, topo e faces laterais (superfície) |
| Pitágoras | os três lados satisfazem a² + b² = c² |
| classificação | lados comparados e o sinal do produto escalar no vértice do maior ângulo |
| distância | d² = Σ (diferenças)², com d ≥ 0 |
| ponto médio | médias refeitas e M à mesma distância dos dois pontos |
| reta | os dois pontos satisfazem a equação, e a inclinação Δy/Δx é refeita |
| área do polígono | leque de triângulos a partir do primeiro vértice (em vez do cadarço) |

O status:
- **`verified_symbolic`:** medidas racionais e igualdade exata.
- **`verified_numeric`:** medidas irracionais, ou igualdade só numérica.
- **`partial`:** quando o segundo método não termina a tempo (1,5 s).

A matriz de adulteração ganhou o caso de geometria.

### Frases (`interpreter/language.py`)

- **Figuras:** "área do círculo de raio 5", "comprimento da circunferência de
  raio 2", "área do triângulo de lados 3, 4 e 5", "área do trapézio de bases 6
  e 4 e altura 3", "volume do paralelepípedo de comprimento 2, largura 3 e
  altura 4", "classifique o triângulo de lados…". "Área" de um sólido é a da
  superfície.
- **Pitágoras:** "hipotenusa de um triângulo de catetos 3 e 4", "cateto do
  triângulo retângulo de hipotenusa 13 e cateto 5".
- **Pontos:** "distância entre (1, 2) e (4, 6)", "ponto médio entre…", "equação
  da reta que passa por…", "área do polígono de vértices…".
- **Sem medidas:** "área do círculo" recebe a orientação de formato. "Área sob
  a curva…" não é geometria e fica livre para a IA, quando permitida.
- O prompt da IA ganhou o intent `geometry`; nenhuma chamada real foi feita.

## Consequências

- Há um intent novo, `geometry`, e o parser ganhou pontos.
- Sugestões registradas:
  - unidades (cm, m, conversões);
  - perímetro do trapézio (exige os lados);
  - polígonos regulares;
  - setor circular;
  - pirâmide e prisma;
  - ângulos de um triângulo (fica para trigonometria);
  - distância de ponto a reta;
  - redução do texto de ajuda da calculadora (Fase 11).
