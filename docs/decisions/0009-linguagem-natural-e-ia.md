# ADR 0009 — Linguagem natural e IA (Fase 8)

- **Status:** aceita
- **Data:** 2026-10-07
- **Complementa:** [ADR 0004](0004-ai-provider.md) (camada de IA) e
  [ADR 0001](0001-custo-zero.md) (custo zero)

## Contexto

O Mathcode precisa entender pedidos em português ("qual a derivada de x^3?"),
mas a IA nunca pode ser a autoridade matemática, nada pode ter custo, e o texto
do usuário só pode sair do computador com permissão.

## Decisões do usuário

1. **Caixa "Permitir IA" por pedido**, desmarcada por padrão. Sem ela, só as
   regras locais entendem frases, e nada sai do servidor.
2. **Chamadas reais ao OpenCode autorizadas**, poucas (de 3 a 5) e com frases
   fictícias, para validar o formato das respostas.
3. **Ollama adiado** até estar instalado (fica como sugestão).

## Decisão

### 1. Regras locais primeiro (`interpreter/language.py`)

Frases comuns são entendidas sem IA, no worker, antes da detecção normal:

- palavras de preenchimento no início ("qual é", "quanto vale", "calcule",
  "por favor") e um artigo antes da palavra-chave são ignorados;
- regras, em ordem:
  - `future` (estatística, matrizes, geometria, vértice e máximo dão
    `UNSUPPORTED_FEATURE`, com a explicação de que virão depois);
  - `derivative` (com ordem por extenso e "em relação a");
  - `integral` (com limites "de 0 a 1" e "dx");
  - `limit` (com "pela esquerda/direita");
  - `roots` e `solve` (sem "=", acrescenta "= 0");
  - `factor`, `expand`, `simplify`;
  - `graph` e `graph_verb`;
  - `divide`;
  - `percent` ("15% de 780" vira `15/100*(780)`);
- o casamento ignora acentos e maiúsculas, mas preserva o comprimento do texto:
  a posição de um erro continua apontando para o que foi digitado;
- a parte matemática passa pelo mesmo parser seguro de sempre
  ([ADR 0002](0002-parser-sem-eval.md)).

O resultado traz `interpretation: {method: "rules", intent, expression, ...}`.

### 2. Quando a IA é chamada

Só quando **todas** as condições valem (`app/ai/__init__.py`, `needs_ai`):

- o pedido traz `allow_ai: true`, sem `intent` e sem `options`;
- a entrada tem no máximo 500 caracteres;
- as regras não resolvem o pedido, ou acham a operação mas deixam a parte
  matemática em palavras ("derivada de x ao quadrado");
- essa parte não passa no parser **e** tem palavras fora do vocabulário de
  funções. "2 +" é erro de digitação: a mensagem do parser é mais útil que um
  palpite da IA.

### 3. Onde a IA roda

No **processo da API**, fora do pool de cálculo (`app/ai/service.py`):

- a chamada é espera de rede, não conta: não deve ocupar um worker nem usar o
  timeout de cálculo (5 s);
- no máximo **2 chamadas simultâneas** (semáforo);
- timeout próprio, `MATHCODE_AI_TIMEOUT` (90 s por padrão, de 5 a 300).

### 4. OpenCode isolado

O provedor `opencode` (`app/ai/opencode.py`) roda o OpenCode v2 do próprio
usuário:

- `opencode run --standalone --model <m> --agent mathcode --format json`, com
  argumentos fixos, sem shell e com a entrada padrão fechada;
- num **diretório temporário vazio**, porque o OpenCode observa o diretório em
  que roda;
- com `OPENCODE_CONFIG_CONTENT` definindo o agente `mathcode` com **todas as
  permissões negadas** (sem ler arquivos, sem comandos) e com o prompt do
  Mathcode (`app/ai/prompt.py`).

### 5. Só modelos gratuitos

- `MATHCODE_AI_MODEL` só aceita `opencode/<nome>-free` ou `opencode/big-pickle`;
  qualquer outro valor impede o servidor de iniciar;
- um evento de custo maior que zero descarta a resposta;
- nas execuções observadas, o OpenCode v2 **não informou custo**. A garantia
  vem, portanto, da lista de modelos gratuitos.

### 6. A resposta da IA é um pedido como outro qualquer

- `IntentCandidate` (Pydantic, `extra="forbid"`): `intent`, `expression`,
  `options` (com os mesmos limites de tipo do corpo HTTP) e `clarification`;
- um campo a mais (como o resultado da conta), um intent desconhecido ou JSON
  inválido fazem a resposta ser rejeitada (`AI_FAILED`), sem conserto;
- a `expression` vai para o **mesmo pipeline**: parser seguro, schema do
  intent, motor e verificação. Se o modelo escrever a resposta na expressão
  ("d/dx (x^2) = 2x"), o parser recusa;
- o erro de um cálculo vindo da IA não tem `position` (apontaria para o texto
  da IA, não para o digitado);
- o resultado traz `interpretation: {method: "ai", intent, expression,
  options, provider, model}`, e a interface pede ao usuário que **confira**.

### 7. Erros novos

| Código | Quando |
|---|---|
| `AI_UNAVAILABLE` | `allow_ai`, mas o servidor está com `MATHCODE_AI_PROVIDER=none` |
| `AI_FAILED` | OpenCode ausente, falha, timeout, limite gratuito, custo ou resposta fora do formato |
| `AMBIGUOUS_INPUT` | a IA respondeu com uma pergunta (`clarification`) ou sem operação |

Todos são HTTP 200 com `success: false`, como os demais erros de matemática.

## Validação com o modelo real

Foram feitas 5 chamadas reais a `opencode/space-bunny-free`, todas
autorizadas e com frases fictícias:

| Frase | Resposta | Observação |
|---|---|---|
| derivada de x ao quadrado mais 3x (prompt inicial) | intent `derivada`, expressão `d/dx (x^2 + 3x) = 2x + 3` | O modelo **calculou**. Isso motivou o prompt estrito e a validação em duas etapas. |
| quanto vale o dobro de sete | `arithmetic`, `2 * 7` | 2,2 s |
| resolva x mais 3 igual a 10 | `solve_equation`, `x + 3 = 10`, variável x | 3,1 s |
| integral dupla de x | pergunta: "A integral dupla ainda não é suportada." | Graças à linha do prompt que proíbe trocar por uma operação parecida. |
| resolva x mais 3 igual a 10 (pela API) | `x = 7`, verificado simbolicamente | Virou o fixture `ai-equation.json`. |

## Diferenças em relação ao ADR 0004

- `interpret(text)` não recebe `context`; ainda não há contexto a passar.
- `parameters` virou `options`, igual ao corpo HTTP.
- Não há `confidence`: modelos não dão uma confiança calibrada, e o que decide
  é a validação pelo pipeline e a conferência do usuário.
- `mock` existe só nos testes, não como configuração.
- Quando a IA falha, a resposta é um erro claro (`AI_FAILED` ou
  `AI_UNAVAILABLE`), não um "modo none" silencioso. Os cálculos digitados não
  dependem da IA e continuam funcionando.

## Consequências

- Com "Permitir IA", a frase vai para um serviço externo. A interface diz isso
  ao lado da caixa, e a caixa começa desmarcada a cada carregamento.
- Modelos gratuitos podem mudar, sair do ar ou atingir limites. O nome do
  modelo é configurável, mas sempre dentro da lista gratuita.
- Uma resposta da IA leva de 2 a 8 s (nas chamadas observadas); um cálculo
  digitado continua levando milissegundos.
- Sugestões registradas: provedor Ollama local, quando estiver instalado;
  novas regras locais para frases frequentes ("o dobro de", "a metade de").
