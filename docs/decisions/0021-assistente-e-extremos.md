# ADR 0021 — Assistente matemático e extremos (Fase 12)

- **Status:** aceita
- **Data:** 2026-10-09

## Contexto

A Fase 12 pede que pedidos compostos, como "raízes, vértice e gráfico de f(x)",
virem um `ExecutionPlan` com vários passos, cada um executado e verificado de
forma determinística.

Antes desta fase:
- cada pedido era um cálculo só;
- "vértice", "máximo" e "mínimo" de uma função davam "ainda não suportado"
  (regra `future`);
- não existia o domínio de uma função.

## Decisões do usuário

1. **Pedidos:**
   - a lista com "e", em que cada item vira um passo;
   - "estude a função f", um pacote fixo de passos.
2. **Planejador:**
   - as regras locais montam o plano;
   - se elas não entenderem e "Permitir IA" estiver marcado, a IA gratuita
     sugere os passos;
   - o motor calcula e verifica cada passo, e a IA nunca calcula.
3. **Resposta:**
   - um cartão com os passos numerados, cada um com a sua manchete, o seu selo
     de verificação e, se houver, o seu gráfico;
   - um passo que falha não derruba os outros.
4. **Entrada:** o Automático detecta o pedido composto, e a operação
   "Assistente" força esse modo.
5. **Escopo:**
   - vértice e extremos entram como um cálculo novo e verificado;
   - o estudo da função tem raízes, f(0), derivada, extremos e gráfico;
   - o domínio vira sugestão.

## Decisão

### Extremos: o intent `extrema` (`math_engine/extrema.py`)

`ExtremaParams(expression, variable?)`. Os pontos críticos vêm de f'(x) = 0, e
quem resolve essa equação é o **motor de equações** já existente. Por isso eles
são:
- exatos;
- completos pelo teorema de Sturm, em polinômios e funções racionais.

**A volta pelo texto:** f' é escrita como texto e relida pelo parser seguro.
- O texto simples comum escreve o logaritmo natural como `log`, que na entrada é
  base 10.
- Por isso foi criado `formatting.parser_text`, que escreve `ln`.
- Sem ele, x·ln(x) teria o ponto crítico errado.

**A classificação** é pelo **teste da derivada primeira**: o sinal de f' logo
antes e logo depois de cada ponto.
- Os vizinhos são os outros pontos críticos e os polos de f', então o sinal não
  muda no meio do caminho.
- Assim, x⁴ (f'' = 0 em 0) é mínimo, e x³ é "sem extremo".
- Perto da borda do domínio (x·ln x), o ponto de teste se aproxima até f'
  existir.

**A resposta:**
- uma parábola dá o **vértice**, `V = (2, −1), mínimo`;
- as outras funções dão uma linha por ponto, como `máximo local (−1, 2)`;
- uma reta, ou uma função sem pontos críticos, dá "sem máximos nem mínimos
  locais".

**Fora do escopo, com explicação:**
- pontos críticos periódicos, como em sin(x);
- funções com módulo, que não têm derivada onde o módulo zera;
- funções de várias variáveis;
- funções constantes.

Se f não é racional, um aviso diz que só os pontos com f'(x) = 0 foram
considerados.

### Verificação dos extremos (`verification/extrema.py`)

| Checagem | Como |
|---|---|
| derivada | um segundo derivador (`differentiate.py`, regras de derivação, sem o `diff` do SymPy) dá a mesma f' que foi igualada a zero; em caso de dúvida, compara em 6 pontos |
| pontos críticos | a equação f'(x) = 0 passa pela verificação das equações (substituição, e completude por Sturm) |
| valores | f(x₀) é recalculado pelo avaliador independente na expressão original |
| classificação | f no ponto é comparado com f nos pontos de teste dos dois lados: um máximo fica acima dos dois |
| vértice | x = −b/(2a), e o sinal de a diz se é mínimo ou máximo |

Os status ficam assim:
- `verified_symbolic` para polinômios e racionais;
- `partial` (completude não provada) nas outras funções.

### O plano (`interpreter/planner.py`)

`plan_request(texto)` devolve um `ExecutionPlan(steps, function, rule)`, ou
`None` quando o pedido não é composto. Cada `PlanStep(title, intent, input,
options)` é um pedido comum. Os itens reconhecidos são:
- raízes;
- vértice;
- máximos e mínimos, extremos ou pontos críticos;
- derivada e segunda derivada;
- integral;
- gráfico;
- fatoração;
- f(0), ou interseção com o eixo y.

**Regras do plano:**
- pedidos repetidos viram um passo só;
- um plano de um passo só devolve `None`, então "o máximo e o mínimo de f"
  segue as regras comuns;
- o limite é de 6 passos;
- `f(x) =` e `y =` são tirados da frente da função;
- uma equação, um número ou duas variáveis no lugar da função recebem uma
  explicação.

O planejador não importa o SymPy nem o mpmath, porque roda no processo da API.

### A execução (`app/assistant.py`)

- **Na API:** `run_plan` manda os passos **em paralelo** para o pool. Cada passo
  tem o seu timeout, e os passos são independentes, sem encadeamento.
- **Em processo:** `calculator.calculate(texto)` faz o mesmo, um passo depois
  do outro. Assim o pipeline continua respondendo tudo sozinho.

`compose` monta o `MathResult`:
- `intent: "assistant"`;
- **`plan`:** a lista de `PlanStepResult(title, intent, input, options,
  result)`, em que `result` é o `MathResult` completo do passo;
- **sucesso:** se ao menos um passo deu certo;
- **`result.plain`:** o resumo `Título: resultado; …`;
- **`details`:** `function`, `steps` e `calculated`.

A verificação do conjunto:
- traz todas as checagens dos passos, com o nome do passo na frente;
- tem o status do **passo mais fraco**;
- um gráfico sem nada a conferir (`not_applicable`) só conta quando não há
  outro passo.

Se todos os passos falham, o resultado é um erro, e os passos continuam em
`plan`.

### A IA (opcional)

`IntentCandidate` ganhou `steps`, uma lista de 1 a 6 `StepCandidate(title,
intent, expression, options)`, e nenhum passo pode ser outro plano. O prompt
explica o formato. Cada passo sugerido é validado e calculado como um pedido
comum. Nenhuma chamada real foi feita: os testes usam o `MockProvider`.

### A API

- **Pedidos que viram plano:** sem `intent` (Automático) ou com `intent:
  "assistant"`, e sem `options`.
- **"Assistente" sem plano:**
  - se a IA está permitida, a IA é consultada;
  - se não, a resposta explica os formatos aceitos.
- **"Assistente" com `options`:** erro explicado.
- **`interpret()`:** recusa `assistant` como passo.

### Frontend

- `types/math.ts` ganhou `PlanStepResult` e `MathResult.plan`. A validação
  checa cada passo como um `MathResult` sem plano próprio.
- `ResultView` foi dividido:
  - `ResultBody` é o corpo de um resultado;
  - `PlanSteps` é a lista numerada, com um `ResultBody` por passo, ou o motivo
    da falha.
- `ErrorView` também mostra os passos.
- **Operações novas:** "Assistente" e "Máximos e mínimos" (com o campo
  Variável).
- "Permitir IA" aparece no Automático e no Assistente.
- Os extremos mostram f'(x) e uma frase sobre a classificação.

## Consequências

- **Novidades:**
  - dois intents, `extrema` e `assistant`;
  - o campo `plan` em toda resposta, vazio fora do assistente. As fixtures
    antigas receberam `"plan": []`, que é exatamente o que a API devolve para
    elas.
- **O que muda:** "vértice / máximo / mínimo de f" deixa de ser "ainda não
  suportado".
- **Sugestões registradas:**
  - domínio de uma função;
  - passos encadeados ("derive e ache onde a derivada zera");
  - extremos de funções periódicas e com módulo;
  - extremos nas bordas de um intervalo (máximo absoluto em [a, b]);
  - pontos de inflexão e concavidade;
  - assíntotas no estudo da função.
