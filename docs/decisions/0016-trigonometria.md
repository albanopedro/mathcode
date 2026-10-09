# ADR 0016 — Trigonometria (Fase 10, 6º domínio)

- **Status:** aceita
- **Data:** 2026-10-09

## Contexto

Antes desta etapa:
- `sin(30°) = 1/2` já funcionava;
- a simplificação já reduzia `sin(2x) − 2sin(x)cos(x)` a 0;
- `sin(x) = 1/2` dava o erro "soluções periódicas não suportadas";
- `sec`, `csc` e `cot` não existiam;
- não havia conversão de ângulos, redução ao 1º quadrante, verificação de
  identidades nem resolução de triângulos.

## Decisões do usuário

1. **Conteúdos (todos):**
   - valores e conversões: sec, csc e cot; graus ↔ radianos; redução ao 1º
     quadrante;
   - equações trigonométricas;
   - identidades, com prova ou contraexemplo;
   - resolução de triângulos, pelas leis dos senos e dos cossenos.
2. **Interface:** operação "Trigonometria", com o campo Cálculo (converter,
   reduzir, identidade, triângulo). As equações como `sin(x) = 1/2` passam a
   funcionar onde já eram digitadas: em "Resolver equação" e no Automático.
3. **Equações:** a solução geral (`x = π/6 + 2kπ ou x = 5π/6 + 2kπ`) mais as
   soluções em [0, 2π). Os campos "Soluções de / até" mudam o intervalo.
4. **Triângulos:** entram como `a = 5; b = 7; C = 60°`, com os lados em
   minúsculas e os ângulos opostos em maiúsculas. A resposta é o triângulo
   completo, com os ângulos em graus. No caso ambíguo, aparecem os dois
   triângulos.
5. **Identidades:** prova ou contraexemplo (`tan(x) = sin(x)` falha em x = π/6).

## Decisão

### sec, csc e cot

São funções da linguagem, com os aliases `cossec`, `cosec`, `cotg` e `cotan`.
Elas entram nos lugares onde as outras funções já estavam:
- o construtor do SymPy;
- o avaliador independente, que recusa os polos;
- a continuidade, que reconhece os polos onde o cosseno ou o seno se anula;
- o derivador próprio.

Por isso derivadas, integrais e limites delas são verificados como os outros.

### Equações periódicas (`math_engine/periodic.py`)

O `solveset` devolve uniões de `ImageSet(Lambda(n, a + T·n), Integers)`. Cada
uma vira uma `Family(offset, period)`, com o deslocamento em [0, período). Três
tratamentos:
- **Juntar famílias:** famílias com o mesmo período e deslocamentos igualmente
  espaçados formam uma só. `2kπ ∪ π + 2kπ` vira `kπ`, e as quatro de
  `2cos²x − 1 = 0` viram `π/4 + kπ/2`.
- **Soluções isoladas:** convivem com as famílias. `(x − 1)·sin(x) = 0` tem
  x = 1 e x = kπ.
- **Domínio:** famílias fora do domínio da equação original são descartadas, com
  aviso na verificação. Em `cos(x)·tan(x) = 1`, o SymPy simplifica e oferece
  π/2 + 2kπ, onde a tangente não existe.

**Lista no intervalo:**
- **Padrão:** [0, 2π), aberto no fim.
- **Intervalo digitado:** `lower`/`upper`, fechado. Os valores aceitam `pi`, e
  o intervalo precisa ser limitado.
- **Limite:** até 100 soluções listadas, com o aviso `SOLUTIONS_TRUNCATED` e o
  total.
- **Equação sem soluções periódicas:** o intervalo é ignorado, com o aviso
  `INTERVAL_IGNORED`.

**O letreiro:** `x = π/6 + 2kπ` (k inteiro). Se a variável for `k`, o inteiro
passa a ser `n`.

**Gráficos:** o motor de equações agora recebe a faixa visível do eixo x como
intervalo, e as raízes de `sin(x)` no gráfico passam a ser exatas.

### Verificação das equações periódicas (`verification/periodic.py`)

Nada usa o `solveset`:

| Checagem | Como |
|---|---|
| substituição | a solução geral, com k inteiro simbólico, zera a diferença entre os lados; o avaliador independente confirma em k = −1, 0, 1, 2 |
| lista | a contagem dos k de cada família dentro do intervalo é refeita com mpmath |
| completude | redução a um polinômio: se a equação é um polinômio numa só função de um só argumento a·x + b (sec, csc e cot viram 1/cos, 1/sin e 1/tan; sin² = 1 − cos² quando um deles só aparece em potências pares), u = sin(a·x + b) dá P(u) = 0. As raízes reais são exatas e contadas por Sturm (em grau 1, qualquer coeficiente real serve). Cada raiz dá as suas famílias por asin, acos ou atan, que precisam coincidir com a resposta ponto a ponto num período comum |
| sem redução | varredura numérica de um período (720 pontos, bisseção nas trocas de sinal, polos descartados). Uma raiz que a resposta não tem reprova; não achar nenhuma é só evidência, e o status fica `partial` |

A mesma redução também prova:
- **Equação sem solução:** `cos(x) = 2`, porque u = 2 está fora de [−1, 1].
- **Identidade:** `sin(x)² + cos(x)² = 1`, porque com u = cos(x) a diferença é o
  polinômio nulo.

**Um bug do SymPy:** `tan(2kπ + 2π/3)`, com k inteiro, dá √3/3, e o certo é −√3.
Seno e cosseno de t + 2kπ estão certos (testados em 24 ângulos). Por isso, na
substituição:
- tan, cot, sec e csc são reescritas com sin e cos;
- a família é dividida em N subfamílias, para que cada argumento avance
  múltiplos de 2π.

Um teste mantém o bug documentado.

### A operação Trigonometria (`math_engine/trigonometry.py`)

`TrigonometryParams(expression, calculation)`:

| Cálculo | Entrada | Resposta | Verificação |
|---|---|---|---|
| `convert` | um ângulo; com ° vira radianos, sem ° vira graus | `π/6 rad`, `30°`, `(360/π)° ≈ 114.592°` | o avaliador independente relê o ângulo; para múltiplos racionais de π, a mesma fração de volta, exata |
| `reduce` | um ângulo ou uma função dele (`sin(150°)`) | primeira determinação em [0, 2π) e voltas, quadrante, ângulo de referência, sin, cos e tan com sinal; `sin(150°) = sin(30°) = 1/2` | os valores calculados direto do ângulo original pelo avaliador independente; ±f(referência) conferido numericamente e exatamente; voltas inteiras |
| `identity` | `lhs = rhs`, com 1 a 3 variáveis | `≡` (prova por simplificação, com limite de 2 s) ou `≢` com um contraexemplo, procurado primeiro em ângulos notáveis | prova por outro caminho (exponenciais, fórmula de Euler) e pontos sorteados; o contraexemplo é reavaliado e os lados precisam diferir |
| `triangle` | três medidas com pelo menos um lado: LLL, LAL, LLA (ambíguo) ou ALA/LAA | os 3 lados e os 3 ângulos, exatos (`√39`, `5√6 − 5√2`) e em graus | o triângulo montado num plano (distâncias e ângulos pelo produto escalar); soma dos ângulos = π e lei dos cossenos exatas; no caso ambíguo, a quantidade de triângulos pelas raízes positivas de uma equação do 2º grau |

**Detalhes dos triângulos:**
- **Ângulo sem °:** é lido em radianos, com aviso. `C = 60` sem ° é recusado,
  porque 60 rad não cabe num triângulo, e a mensagem sugere `C = 60°`.
- **Soma dos ângulos:** o SymPy não vê que acos(4/5) + acos(3/5) = π/2. Então a
  soma é provada por cos(S) = −1 e sin(S) = 0, com cada ângulo em (0, π).
- **Celular:** a manchete traz os valores calculados, com a forma exata só quando
  é curta (√39); a tabela abaixo traz os seis valores, com "*" nos informados.

### Frases (`interpreter/language.py`)

Exemplos de cada tipo:
- **Conversão:** "converta 30° para radianos", "30 graus em radianos",
  "pi/6 em graus".
- **Redução:** "reduza 150° ao primeiro quadrante", "redução ao 1º quadrante de
  sin(150°)", "em que quadrante está 300°?".
- **Identidade:** "verifique a identidade …", "prove que …", "… é uma
  identidade?".
- **Triângulo:** "resolva o triângulo com a = 5, b = 7 e C = 60°", "lei dos
  cossenos com …", "ângulos do triângulo de lados 3, 4 e 5".
- **Intervalo nas equações:** "resolva sin(x) = 1/2 de 0 a 4pi", "… no
  intervalo [0, pi]", "raízes de cos(x) entre 0 e 2pi".

"Mostre o gráfico de y = …" continua sendo gráfico. O prompt da IA ganhou o
intent `trigonometry`, as funções sec/csc/cot e as opções de intervalo. Nenhuma
chamada real foi feita.

## Consequências

- **O que muda:**
  - há um intent novo, `trigonometry`;
  - `solve_equation` aceita `lower`/`upper` e devolve o conjunto `periodic`;
  - equações que antes davam "não suportado" agora são resolvidas;
  - os testes antigos que usavam `sin(x)` como exemplo de raiz só numérica
    passaram a usar `sin(x) − x/10`.
- **Sugestões registradas:**
  - inequações trigonométricas;
  - equações com seno e cosseno de grau ímpar, como sin(x) = cos(x), com
    completude provada (hoje `partial`);
  - graus, minutos e segundos;
  - área do triângulo pela fórmula de senos;
  - funções trigonométricas inversas com intervalo;
  - filtrar por intervalo as equações com soluções finitas.
