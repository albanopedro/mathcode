# Arquitetura do Mathcode

> Estado: proposta aprovada na Fase 0 (2026-10-06). A Fase 1 criou `api/`,
> `core/` e `models/` e a base do frontend. A Fase 2 criou `parsing/`,
> `interpreter/`, `math_engine/`, `verification/`, `formatting/` e
> `calculator.py`. A Fase 3 criou `POST /api/calculate` e o pool de workers
> (`core/workers.py`). A Fase 4 criou a interface de cálculo (seção 6). A
> Fase 5 trouxe a álgebra: fatorar, expandir, equações gerais, sistemas lineares
> e divisão de polinômios ([ADR 0006](decisions/0006-escopo-da-algebra.md)). A
> Fase 6 trouxe o cálculo: derivadas, integrais e limites
> ([ADR 0007](decisions/0007-calculo.md)). As
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
  ▼  interpreter/          detecta o intent + extrai parâmetros
  │                        (regras; IA opcional na Fase 8)
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
| `verify(outcome) → VerificationReport` | estratégia do ADR 0003 (`verification/`) |
| `present(outcome) → Presentation` | `ResultValue` (plain/LaTeX/aproximação) + `details` (`formatting/results.py`) |

Intents disponíveis (`models/intents.py`):

- `arithmetic`, `simplify`, `factor` e `expand`;
- `solve_equation` (polinomial, racional e outras, com uma variável);
- `solve_system` (linear);
- `polynomial_division` (`A / B`);
- `derivative`, `integral` e `limit`, com parâmetros em `options` (ADR 0007).

Sem intent explícito, a detecção por regras usa a forma da entrada:

- equações separadas por `;` formam um sistema;
- com `=`, é uma equação;
- com variável, é uma simplificação;
- caso contrário, é aritmética.

Fatorar, expandir, dividir e as operações de cálculo só rodam quando pedidos
(ADRs 0006 e 0007).

| Intent | Executor | Verificador |
|---|---|---|
| arithmetic | `math_engine/arithmetic.py` | `verification/arithmetic.py` |
| simplify, factor, expand, polynomial_division | `math_engine/algebra.py` | `verification/algebra.py` |
| solve_equation | `math_engine/equations.py` (com `polynomials.py`) | `verification/equations.py` |
| solve_system | `math_engine/systems.py` | `verification/equations.py` |

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
├── verification: VerificationReport
│   ├── status: verified_symbolic | verified_numeric | partial
│   │           | unverified | not_applicable | failed
│   ├── method: str
│   ├── checks: list[str]
│   └── message: str
├── warnings: list[{code, message}]
└── error: {code, message, position?} | null
```

Códigos de erro (`core/errors.py`):

- `EMPTY_INPUT`, `INPUT_TOO_LONG`, `PARSE_ERROR`, `AMBIGUOUS_INPUT`;
- `UNKNOWN_SYMBOL`, `UNKNOWN_FUNCTION`, `UNSUPPORTED_FEATURE`;
- `DIVISION_BY_ZERO`, `DOMAIN_ERROR`, `LIMIT_EXCEEDED`;
- `UNSUPPORTED_INTENT`, `INVALID_INPUT_FOR_INTENT` (ex.: pedir aritmética de
  uma expressão com variáveis), `VERIFICATION_FAILED`, `INTERNAL_ERROR`;
- `TIMEOUT` e `SERVER_BUSY`, que vêm do pool de workers.

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

`error.position` é um índice no texto **original** digitado pelo usuário.

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
pela entrada.

`options` só vale com `intent` e leva os parâmetros da operação:

| Intent | Opções |
|---|---|
| solve_equation | `variable` |
| derivative | `variable`, `order` (1 a 10) |
| integral | `variable`, `lower`, `upper` (os dois ou nenhum; aceitam `pi/2`, `inf`) |
| limit | `variable`, `point` (obrigatório), `side` (`both`, `left` ou `right`) |

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

## 6. Frontend

Uma página só, `App.tsx`, com cabeçalho, `Calculator` e, no rodapé, o
`ApiStatus` da Fase 1.

| Peça | Papel |
|---|---|
| `types/math.ts` | tipos que espelham o `MathResult` e `isMathResult()`, que valida cada resposta antes de usá-la, com a mesma regra de consistência do backend |
| `services/api.ts` | `calculate(input, intent?)`: decide pelo **corpo**, não pelo status, porque 200, 500 e 503 trazem `MathResult`. Trata 502–504 sem corpo como API inacessível e 422 como pedido recusado |
| `hooks/useCalculator.ts` | estados `idle`, `loading`, `done` e `failed` (este último sem `MathResult`, ou seja, erro de rede); cancela o pedido anterior |
| `components/Calculator.tsx` | seletor de **operação** (`utils/operations.ts`: Automático ou um intent, com exemplo próprio), formulário (Enter envia; botão desativado com o campo vazio ou durante o cálculo) e região `aria-live` |
| `utils/captions.ts` | frases explicativas montadas **só** a partir de `details`: sem solução, todo real exceto, raiz dupla, infinitas soluções, divisão exata, fatoração inalterada, ordem da derivada, intervalo da integral, divergência, ponto e lado do limite, limite inexistente |
| `components/OperationFields.tsx` | os campos extras da operação escolhida (variável, ordem, de/até, ponto, lado), descritos em `utils/operations.ts`; `buildOptions` envia só os preenchidos e não valida nada: a API explica o que estiver errado |
| `components/ResultView.tsx` | fórmula em KaTeX, aproximação `≈`, tipo de operação, "Entendido como", verificação, avisos e legenda para `∅` ou ℝ |
| `components/ErrorView.tsx` | `role="alert"`, mensagem e a entrada com o caractere de `error.position` destacado (contando code points, como o Python) |
| `components/Verification.tsx` | a mensagem do backend como título, com ícone e cor por status, e "Como foi verificado" (`<details>`) com os `checks` |
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
│   │   ├── interpreter/        registry + detecção por regras
│   │   ├── planner/            ExecutionPlan (Fase 12)
│   │   ├── math_engine/        arithmetic, algebra, equations, systems, polynomials (depois: calculus, graphing...)
│   │   ├── verification/       estratégias por intent
│   │   ├── formatting/         plain/LaTeX/aproximação
│   │   └── ai/                 AIProvider + provedores gratuitos (Fase 8)
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
| [0007](decisions/0007-calculo.md) | Cálculo (Fase 6): campos, ln\|u\|, limites no domínio real, `mpmath.quad` |
