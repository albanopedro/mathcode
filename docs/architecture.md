# Arquitetura do Mathcode

> Estado: proposta aprovada na Fase 0 (2026-10-06). A Fase 1 criou `api/`,
> `core/` e `models/` e a base do frontend. A Fase 2 criou `parsing/`,
> `interpreter/`, `math_engine/`, `verification/`, `formatting/` e
> `calculator.py`. A Fase 3 criou `POST /api/calculate` e o pool de workers
> (`core/workers.py`). A Fase 4 criou a interface de cálculo (seção 6). A
> Fase 5 trouxe a álgebra: fatorar, expandir, equações gerais, sistemas lineares
> e divisão de polinômios ([ADR 0006](decisions/0006-escopo-da-algebra.md)). A
> Fase 6 trouxe o cálculo: derivadas, integrais e limites
> ([ADR 0007](decisions/0007-calculo.md)). A Fase 7 trouxe os gráficos
> ([ADR 0008](decisions/0008-graficos.md)). As
> demais pastas são criadas nas fases em que ganham código.

## 1. Princípios

1. **Custo zero.** Nada pode gerar cobrança ([ADR 0001](decisions/0001-custo-zero.md)).
2. **A IA não é a autoridade matemática.** Ela interpreta, mas quem calcula é
   um motor determinístico (SymPy/mpmath).
3. **Nenhuma entrada vira código.** Sem `eval`, com parser próprio e lista
   fechada ([ADR 0002](decisions/0002-parser-sem-eval.md)).
4. **Todo resultado diz o quanto foi verificado**
   ([ADR 0003](decisions/0003-verificacao.md)).
5. **Convenções explícitas.** Domínio ℝ, exatidão, `log` na base 10 e radianos,
   sempre com aviso ([ADR 0005](decisions/0005-dominio-e-exatidao.md)).

## 2. Pipeline

```
Entrada (texto; LaTeX/MathJSON do MathLive na Fase 11)
  │
  ▼  parsing/normalize     Unicode, aliases PT (sen→sin), x²→x^2, vírgula decimal
  ▼  parsing/parser        tokenizer + Pratt → AST própria (sem eval)
  ▼  interpreter/          frases em PT (language.py) → detecta o intent +
  │                        extrai parâmetros; IA opcional antes, na API (ai/)
  ▼  planner/              ExecutionPlan: lista de passos tipados (Fase 12;
  │                        até lá, cada pedido é um passo só e não há planner)
  ▼  math_engine/<domínio> executor do intent (SymPy), num worker isolado com
  │                        timeout (core/workers.py)
  ▼  verification/         estratégia do intent → VerificationReport
  ▼  formatting/           plain + LaTeX + aproximação + avisos
  ▼  models/MathResult     resposta padronizada
  │
  ▼  api/ (FastAPI)  →  frontend (React)
```

Onde a IA atua: interpretação, desambiguação, planejamento (Fase 12) e,
opcionalmente, explicação. Ela **nunca** atua no cálculo nem na verificação.

**Frases** ([ADR 0009](decisions/0009-linguagem-natural-e-ia.md)): sem
`intent`, o `calculator.py` tenta primeiro as regras de `interpreter/language.py`
("qual a derivada de x^3?" vira `derivative` de `x^3`). Se elas não resolvem, o
pedido traz `allow_ai: true` e há palavras que o parser não conhece, a API
consulta a IA **antes** do pool (`ai/service.py`: no máximo 2 consultas
simultâneas, timeout próprio). A resposta da IA vira um pedido comum (intent,
expressão e opções) e passa pelo mesmo parser, schema e verificação. Os dois
caminhos preenchem `interpretation` no resultado.

Quem amarra as etapas é `app/calculator.py`: `calculate(texto, intent=None)`
devolve sempre um `MathResult`. Um `MathError` (erro esperado) vira uma resposta
com `error`. Qualquer outra exceção é registrada no log e vira
`INTERNAL_ERROR`, sem expor detalhes internos ao usuário.

## 3. Contrato de um intent

Cada intent é registrado em `interpreter/registry.py` com:

| Peça | Responsabilidade |
|---|---|
| `name` | identificador estável (`arithmetic`, `simplify`, `solve_equation`...) |
| `params_model` | modelo Pydantic com os parâmetros (`models/intents.py`) |
| `execute(params) → Outcome` | cálculo no domínio correspondente do `math_engine` |
| `verify(outcome) → VerificationReport` | estratégia do ADR 0003 (`verification/`), com checagens estruturadas e comparação de métodos (ADR 0010) |
| `present(outcome) → Presentation` | `ResultValue` (plain/LaTeX/aproximação) + `details` (`formatting/results.py`) |

Intents disponíveis (`models/intents.py`):

- `arithmetic`, `simplify`, `factor` e `expand`;
- `solve_equation` (polinomial, racional e outras, com uma variável);
- `solve_system` (linear);
- `polynomial_division` (`A / B`);
- `derivative`, `integral` e `limit`, com parâmetros em `options` (ADR 0007);
- `graph`: uma ou mais funções, separadas por `;`, ou `y = f(x)` (ADR 0008);
- `statistics`: uma lista de números, com o resumo ou uma medida (ADR 0011);
- `matrix`: uma expressão com matrizes (`[[1, 2], [3, 4]]`) e o cálculo pedido
  (ADR 0012);
- `vector`: um vetor (`[1, 2, 3]`) ou dois separados por `;`, e o cálculo
  pedido (ADR 0013);
- `geometry`: as medidas de uma figura (`r = 5`, `b = 4; h = 3`) ou pontos
  (`(1, 2); (4, 6)`), com a figura e o cálculo (ADR 0014).

Sem intent explícito, a detecção por regras usa a forma da entrada:

- com matriz entre colchetes, é `matrix` (calcular a expressão);
- só com vetores, é `vector` (calcular a expressão);
- com pontos, é recusada com a orientação de escolher Geometria;
- listas de expressões (`x^2; 2x + 1`) e `y = f(x)` formam um gráfico;
- equações separadas por `;` formam um sistema;
- com `=`, é uma equação;
- com variável, é uma simplificação;
- caso contrário, é aritmética.

Fatorar, expandir, dividir, as operações de cálculo e a estatística só rodam
quando pedidos, pela operação ou por uma frase (ADRs 0006, 0007 e 0011). Uma
lista só de números, sem operação, é recusada com a orientação de escolher
Estatística (pode ser uma vírgula decimal digitada com espaço).

| Intent | Executor | Verificador |
|---|---|---|
| arithmetic | `math_engine/arithmetic.py` | `verification/arithmetic.py` |
| simplify, factor, expand, polynomial_division | `math_engine/algebra.py` | `verification/algebra.py` |
| solve_equation | `math_engine/equations.py` (com `polynomials.py`) | `verification/equations.py` |
| solve_system | `math_engine/systems.py` | `verification/equations.py` |
| statistics | `math_engine/statistics.py` | `verification/statistics.py` |
| matrix | `math_engine/matrices.py` (o `LinearEvaluator`, comum a matrizes e vetores) | `verification/matrices.py` |
| vector | `math_engine/vectors.py` | `verification/vectors.py` |
| geometry | `math_engine/geometry.py` (catálogo de figuras) | `verification/geometry.py` |

Para adicionar um intent, cria-se um módulo e registra-se o intent. O fluxo
principal não muda.

## 4. Resposta padronizada (`MathResult`)

```text
MathResult
├── success: bool
├── intent: str | null
├── input: str                      texto original
├── normalized_input: str | null    como o parser entendeu
├── result: ResultValue | null
│   ├── plain: str                  "2*x + 3"
│   ├── latex: str                  "2 x + 3"
│   └── approx: str | null          "1.4142135623731" quando não exato
├── steps: list[Step]               vazio até existirem regras reais de passos
├── details: dict                   dados extras tipados por intent (raízes, vértice...)
├── verification: VerificationReport           (ADR 0010)
│   ├── status: verified_symbolic | verified_numeric | partial
│   │           | unverified | not_applicable | failed
│   ├── methods: list[kind]         as estratégias usadas, em ordem
│   ├── checks: list[{kind, outcome, message}]
│   │     kind: symbolic | substitution | numeric | comparison
│   │           | completeness | domain | execution
│   │     outcome: passed | failed | inconclusive
│   ├── message: str                a manchete mostrada ao usuário
│   └── reason: str | null          por que é partial/unverified (deadline...)
├── warnings: list[{code, message}]
├── error: {code, message, position?} | null
└── interpretation: Interpretation | null     só quando a entrada era uma frase
    ├── method: rules | ai
    ├── intent: str | null
    ├── expression: str             o texto matemático que foi calculado
    ├── options: dict
    └── provider, model: str | null só com a IA (ex.: opencode, opencode/space-bunny-free)
```

Códigos de erro (`core/errors.py`):

- `EMPTY_INPUT`, `INPUT_TOO_LONG`, `PARSE_ERROR`, `AMBIGUOUS_INPUT`;
- `UNKNOWN_SYMBOL`, `UNKNOWN_FUNCTION`, `UNSUPPORTED_FEATURE`;
- `DIVISION_BY_ZERO`, `DOMAIN_ERROR`, `LIMIT_EXCEEDED`;
- `UNSUPPORTED_INTENT`, `INVALID_INPUT_FOR_INTENT` (ex.: pedir aritmética de
  uma expressão com variáveis), `VERIFICATION_FAILED`, `INTERNAL_ERROR`;
- `TIMEOUT` e `SERVER_BUSY`, que vêm do pool de workers;
- `AI_UNAVAILABLE` (pediu IA, mas o servidor está sem provedor) e `AI_FAILED`
  (a IA falhou ou respondeu fora do formato). Quando a IA responde com uma
  pergunta, o erro é `AMBIGUOUS_INPUT`, com a pergunta como mensagem.

Avisos (`core/notices.py`), cada um uma vez por resultado:

- `AMBIGUOUS_IMPLICIT_MULTIPLICATION`, `DECIMAL_COMMA`, `LOG_BASE_10`;
- `ANGLE_IN_RADIANS`, `REAL_ROOT`, `DOMAIN_CHANGED`;
- `COMPLEX_SOLUTIONS_OMITTED` e `ROOTS_SHOWN_APPROXIMATELY` (Fase 5).

`details` depende do intent:

| Intent | Campos |
|---|---|
| simplify, factor, expand | `changed` |
| factor de um inteiro | `number`, `prime_factors` |
| solve_equation | `variable`, `solution_set` (`finite`, `none` ou `all_reals`), `solutions`, `multiplicities`, `excluded` |
| solve_system | `variables`, `solution_set` (`unique`, `infinite` ou `none`), `solutions`, `free_variables` |
| polynomial_division | `variable`, `quotient`, `remainder`, `exact` |
| derivative | `variable`, `order` |
| integral | `variable`, `definite`; se definida: `lower`, `upper`, `converges` |
| limit | `variable`, `point`, `side` (o lado usado), `requested_side`, `exists`, `oscillates`; se os laterais diferem: `left`, `right` |
| statistics | `measure` (pedida ou `null`), `count`, `data` e `sorted` (decimais finitos como decimais), `modes` e `measures` (12 entradas: `name`, `label`, `symbol`, `plain`, `latex`, `approx`; `null` quando não definida) |
| matrix | `operation`, `rows`, `cols`, `matrix` e `matrix_latex` (a matriz A sobre a qual o cálculo foi feito; com A·v, o vetor resultante como coluna) |
| vector | `operation`, `dimension`, `vectors` e `vectors_latex` (u e v); no ângulo, `degrees` (exato ou `null`) e `degrees_approx` |
| geometry | `figure`, `calculation`, `measures`, `points`, `formula` (LaTeX da fórmula usada), `quantity` (`length`, `area`, `volume` ou `null`); na reta, `equation` e `slope`; na classificação, `by_sides` e `by_angles` |
| graph | `variable`, `x_range` (números), `x_range_text` (como digitado), `y_range`, `y_clipped`, `functions` (`label`, `latex`, `x`, `y` com `null` nos cortes) e `points` (`function`, `kind`: `root` ou `y_intercept`, `x`, `y`, `x_value`, `y_value`, `exact`) |

`error.position` é um índice no texto **original** digitado pelo usuário. Num
cálculo vindo da IA, ele é `null`, porque apontaria para o texto da IA.

"Sem solução" **não** é erro: é um sucesso com conjunto vazio.

**Passos:** o SymPy não gera passos de resolução. A lista `steps` só será
preenchida quando existirem regras próprias que produzam passos verdadeiros.
Até lá, a interface não mostra uma seção de passos.

## 5. API HTTP

Todas as rotas ficam sob `/api`. A documentação interativa fica em `/api/docs`
(desligada em produção).

| Rota | Função |
|---|---|
| `GET /api/health` | status, versão e ambiente |
| `POST /api/calculate` | corpo `{"input": "x^2", "intent": "integral", "options": {"lower": "0", "upper": "1"}}`; responde um `MathResult` |

`intent` é opcional (a lista está na seção 3). Sem ele, a operação é detectada
pela entrada, inclusive em frases como "derivada de x^3".

`allow_ai` (booleano, padrão `false`) permite que uma frase que as regras não
entendem seja enviada ao modelo de IA configurado no servidor. Só vale sem
`intent` e sem `options` (ADR 0009).

`options` só vale com `intent` e leva os parâmetros da operação:

| Intent | Opções |
|---|---|
| solve_equation | `variable` |
| derivative | `variable`, `order` (1 a 10) |
| integral | `variable`, `lower`, `upper` (os dois ou nenhum; aceitam `pi/2`, `inf`) |
| limit | `variable`, `point` (obrigatório), `side` (`both`, `left` ou `right`) |
| graph | `x_min`, `x_max` (opcionais; padrão −10 e 10; aceitam `-2pi`) |
| statistics | `measure`: `count`, `sum`, `mean`, `median`, `mode`, `min`, `max`, `range`, `variance`, `std`, `sample_variance` ou `sample_std` (sem ela, o resumo) |
| matrix | `operation`: `evaluate` (padrão), `determinant`, `inverse`, `transpose`, `trace` ou `rank` |
| vector | `operation`: `evaluate` (padrão), `norm`, `unit`, `dot`, `cross` ou `angle` (os três últimos com dois vetores, `u; v`) |
| geometry | `figure` e `calculation`, os dois obrigatórios; as combinações válidas estão no catálogo (ADR 0014) |

Valores inválidos são respostas (200, `INVALID_INPUT_FOR_INTENT`, mensagem em
português). Tipos fora do formato recebem 422: texto até 100 caracteres, número
de −1000 a 1000, no máximo 8 opções.

**Códigos HTTP**: a resposta é sempre um `MathResult`, exceto no 422.

| Situação | HTTP | `error.code` |
|---|---|---|
| Sucesso | 200 | — |
| Erro de matemática ou de entrada (divisão por zero, sintaxe, domínio, limite, timeout...) | **200**, com `success: false` | o código específico |
| Requisição malformada (JSON inválido, campo faltando ou extra, `intent` desconhecido, `input` acima de 2 000 caracteres) | 422 | formato padrão do FastAPI (`detail`) |
| Falha interna (bug, worker morto) | 500 | `INTERNAL_ERROR` |
| Todos os workers ocupados além do `queue_timeout` | 503 | `SERVER_BUSY` |

Por que erro de matemática é 200: o pedido foi entendido e respondido, e a
resposta é que a conta não tem valor. Assim, o frontend trata tudo com o mesmo
formato.

**Execução:** cada pedido vai para um worker do pool (ADR 0002, seção 4). O
`lifespan` do FastAPI cria o pool na inicialização e o encerra no desligamento.

**Prazo da verificação** (ADR 0010): dentro do worker, a verificação pode usar
até 80% do timeout do cálculo (4 s de 5 s). Se o prazo acabar, ou se o
verificador quebrar, o resultado é entregue com `unverified` e o motivo
(`deadline` ou `internal_error`), em vez de virar erro.

## 6. Frontend

Uma página só, `App.tsx`, com cabeçalho, `Calculator` e, no rodapé, o
`ApiStatus` da Fase 1.

| Peça | Papel |
|---|---|
| `types/math.ts` | tipos que espelham o `MathResult` e `isMathResult()`, que valida cada resposta antes de usá-la, com a mesma regra de consistência do backend |
| `services/api.ts` | `calculate(input, intent?, options?, allowAi?)`: decide pelo **corpo**, não pelo status, porque 200, 500 e 503 trazem `MathResult`. Trata 502–504 sem corpo como API inacessível e 422 como pedido recusado |
| `hooks/useCalculator.ts` | estados `idle`, `loading`, `done` e `failed` (este último sem `MathResult`, ou seja, erro de rede); cancela o pedido anterior |
| `components/Calculator.tsx` | seletor de **operação** (`utils/operations.ts`: Automático ou um intent, com exemplo próprio), formulário (Enter envia; botão desativado com o campo vazio ou durante o cálculo), caixa **"Permitir IA"** (só no Automático, desmarcada, com o aviso de que a frase vai para um serviço externo) e região `aria-live` |
| `components/InterpretationNote.tsx` | como a frase foi lida: pelas regras locais (discreto) ou pela IA (destacado, com o modelo e "Confira se é o que você pediu"); textos montados em `utils/interpretation.ts` |
| `utils/captions.ts` | frases explicativas montadas **só** a partir de `details`: sem solução, todo real exceto, raiz dupla, infinitas soluções, divisão exata, fatoração inalterada, ordem da derivada, intervalo da integral, divergência, ponto e lado do limite, limite inexistente |
| `components/GraphView.tsx` | carrega o Plotly **sob demanda** (`import()`), desenha linhas (cortes como `null`, `connectgaps: false`) e pontos; sem envio à nuvem; `utils/graph.ts` valida os `details` e monta traços e layout |
| geometria no `ResultView` | "em unidades de área/comprimento/volume", a fórmula usada (KaTeX) e, na reta, a equação geral e a inclinação; os campos Figura (com grupos) e Cálculo ficam em `OperationFields`, com o catálogo espelhado em `utils/geometry.ts` |
| vetores no `ResultView` | resultado vetor sempre em KaTeX e "u = (…)", "v = (…)" abaixo; o campo "Cálculo" de vetores fica em `OperationFields`; `utils/vectors.ts` valida os `details` |
| matriz no `ResultView` | resultado matriz sempre em KaTeX (sem o limite de texto longo) e "Matriz A (m×n)" abaixo do resultado; o campo "Cálculo" fica em `OperationFields`; `utils/matrices.ts` valida os `details` |
| `components/StatisticsView.tsx` | tabela do resumo estatístico (Medida, Valor em KaTeX, Aproximado), com a medida pedida destacada e os dados em ordem; `utils/statistics.ts` valida os `details` |
| `components/OperationFields.tsx` | os campos extras da operação escolhida (variável, ordem, de/até, ponto, lado), descritos em `utils/operations.ts`; `buildOptions` envia só os preenchidos e não valida nada: a API explica o que estiver errado |
| `components/ResultView.tsx` | fórmula em KaTeX, aproximação `≈`, tipo de operação, interpretação da frase, "Entendido como", verificação, avisos e legenda para `∅` ou ℝ |
| `components/ErrorView.tsx` | `role="alert"`, mensagem e a entrada com o caractere de `error.position` destacado (contando code points, como o Python) e, se houver, a interpretação da frase |
| `components/Verification.tsx` | a mensagem do backend como título, com ícone e cor por status, e "Como foi verificado" (`<details>`) com cada checagem: ✓, ✗ ou ? (e "Passou", "Falhou" ou "Inconclusiva" para leitores de tela) e o tipo (`utils/verification.ts`) |
| `components/MathFormula.tsx` | `katex.render` num `ref` (sem `innerHTML` vindo do React); gera HTML e MathML, que é o que leitores de tela leem |

Decisões:

- **KaTeX local:** CSS e fontes são empacotados pelo Vite (`dist/assets`), sem
  CDN, então funcionam offline (ADR 0001).
- **Resultados longos** (mais de 120 caracteres, `utils/display.ts`) aparecem
  como texto que quebra linha. O KaTeX não quebra um número como `2^10000`
  (3 011 dígitos) e precisaria de cerca de 36 000 px de largura.
- **Passos** não são exibidos enquanto a lista vier vazia (seção 4).
- Os testes usam **respostas reais da API** (`src/test/fixtures/*.json`), para
  que os tipos não se afastem do backend.

## 7. Estrutura de pastas

```
Mathcode/
├── backend/
│   ├── app/
│   │   ├── main.py             cria o app FastAPI
│   │   ├── calculator.py       pipeline: interpret → execute → verify → present
│   │   ├── api/                rotas: health, calculate
│   │   ├── core/               config, erros, avisos, limites, workers (pool)
│   │   ├── models/             schemas Pydantic (MathResult...)
│   │   ├── parsing/            normalize, tokenizer, parser, ast, printer, build
│   │   ├── interpreter/        registry + detecção + frases em PT (language.py)
│   │   ├── planner/            ExecutionPlan (Fase 12)
│   │   ├── math_engine/        arithmetic, algebra, equations, systems, polynomials, calculus, graphing, statistics, matrices, vectors, geometry
│   │   ├── verification/       estratégias por intent + avaliador independente, frações exatas,
│   │   │                       derivador próprio, continuidade, Newton–Leibniz, prazos
│   │   ├── formatting/         plain/LaTeX/aproximação
│   │   └── ai/                 AIProvider, OpenCode (só modelos gratuitos), mock, prompt e serviço
│   ├── tests/                  parsing/ math_engine/ verification/ api/ + integração
│   └── pyproject.toml
├── frontend/
│   └── src/  components/ pages/ hooks/ services/ types/ utils/ App.tsx
├── docs/
│   ├── architecture.md         este arquivo
│   ├── roadmap.md
│   └── decisions/              ADRs
├── README.md
├── .env.example
├── .gitignore
└── LICENSE                     MIT
```

Esta estrutura difere do prompt original em três pontos:

- `parsing/` é separado de `interpreter/`, para que a superfície de segurança
  fique num lugar só.
- Os testes ficam dentro de `backend/` e `frontend/`, que é o padrão do pytest e
  do Vitest. Um `tests/` na raiz só faria sentido para E2E, mais tarde.
- O `docker-compose.yml` fica adiado: o Docker não está instalado, e um arquivo
  que não pode ser testado não deve entrar.

## 8. Testes

- **Unitários:** normalize, tokenizer, parser (válidos, inválidos e
  maliciosos), cada executor, cada verificador e os schemas.
- **Integração:** API → engine → verificação; interpretação → execução.
- **Frontend:** componentes principais e os estados de carregamento, sucesso e
  erro.
- **Casos obrigatórios:**
  - entrada vazia, expressão inválida e variável desconhecida;
  - divisão por zero, domínio inválido e potência gigante;
  - solução inexistente, múltiplas soluções e soluções complexas omitidas;
  - timeout.

## 9. Ambiente (2026-10-06)

| Ferramenta | Versão |
|---|---|
| Python | 3.14.3 (venv em `backend/.venv`) |
| Node | 26.7.0, com npm 11.19 |
| Docker | não instalado |

Na Fase 1 foi conferido que todas as bibliotecas previstas têm versão para o
Python 3.14 (SymPy 1.14, NumPy 2.5, SciPy 1.18).

Portas de desenvolvimento: API em **8100**, frontend em **5180**. O Vite
encaminha `/api` para a API, então o navegador fala com uma origem só, e não é
preciso configurar CORS. Todas as rotas da API ficam sob `/api`.

## 10. Decisões registradas

| ADR | Tema |
|---|---|
| [0001](decisions/0001-custo-zero.md) | Custo zero (regra primordial) |
| [0002](decisions/0002-parser-sem-eval.md) | Parser próprio sem `eval`, limites e execução isolada |
| [0003](decisions/0003-verificacao.md) | Estratégia e níveis de verificação |
| [0004](decisions/0004-ai-provider.md) | Camada de IA só com provedores gratuitos |
| [0005](decisions/0005-dominio-e-exatidao.md) | Domínio ℝ, exatidão e convenções |
| [0006](decisions/0006-escopo-da-algebra.md) | Escopo da álgebra (Fase 5): seletor, divisão, sistemas lineares, Sturm |
| [0008](decisions/0008-graficos.md) | Gráficos (Fase 7): Plotly sob demanda, amostragem pelo avaliador, cortes, raízes |
| [0007](decisions/0007-calculo.md) | Cálculo (Fase 6): campos, ln\|u\|, limites no domínio real, `mpmath.quad` |
| [0014](decisions/0014-geometria.md) | Geometria (Fase 10, 4º domínio): catálogo de figuras, medidas `r = 5`, pontos `(1, 2)`, verificação por vértices, integração e coordenadas |
| [0013](decisions/0013-vetores.md) | Vetores (Fase 10, 3º domínio): `[1, 2, 3]`, álgebra comum com matrizes, escalar, vetorial, norma, unitário, ângulo em rad e graus |
| [0012](decisions/0012-matrizes.md) | Matrizes (Fase 10, 2º domínio): sintaxe com colchetes, operações, verificação exata (frações) ou numérica (mpmath) |
| [0011](decisions/0011-estatistica-descritiva.md) | Estatística descritiva (Fase 10, 1º domínio): medidas, σ populacional + s amostral, frases, verificação pelo módulo statistics |
| [0010](decisions/0010-verification-engine.md) | Verification Engine (Fase 9): checagens estruturadas, comparação de métodos, prazos, não verificável sem perder o resultado |
| [0009](decisions/0009-linguagem-natural-e-ia.md) | Linguagem natural e IA (Fase 8): regras em PT, "Permitir IA", OpenCode isolado, só modelos gratuitos |
