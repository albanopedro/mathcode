# Arquitetura do Mathcode

> Estado: proposta aprovada na Fase 0 (2026-10-06). Na Fase 1 foram criados
> `api/`, `core/` e `models/` no backend e a base do frontend. As demais pastas
> são criadas nas fases em que ganham código.

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
  ▼  planner/              ExecutionPlan: lista de passos tipados
  │                        (1 passo até a Fase 12)
  ▼  math_engine/<domínio> executor do intent (SymPy), em processo isolado com timeout
  ▼  verification/         estratégia do intent → VerificationReport
  ▼  formatting/           plain + LaTeX + aproximação + avisos
  ▼  models/MathResult     resposta padronizada
  │
  ▼  api/ (FastAPI)  →  frontend (React)
```

Onde a IA atua: interpretação, desambiguação, planejamento (Fase 12) e,
opcionalmente, explicação. Ela **nunca** atua no cálculo nem na verificação.

## 3. Contrato de um intent

Cada intent é registrado em `interpreter/registry.py` com:

| Peça | Responsabilidade |
|---|---|
| `name` | identificador estável (`arithmetic`, `simplify`, `solve_equation`...) |
| `InputSchema` | modelo Pydantic com os parâmetros (`expression`, `variable`, `order`...) |
| `execute(params) → RawResult` | cálculo no domínio correspondente do `math_engine` |
| `verify(params, raw) → VerificationReport` | estratégia do ADR 0003 |
| `format(raw) → ResultValue` | plain/LaTeX/aproximação |

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

Códigos de erro iniciais:

- `EMPTY_INPUT`, `INPUT_TOO_LONG`, `PARSE_ERROR`, `AMBIGUOUS_INPUT`;
- `UNKNOWN_SYMBOL`, `UNKNOWN_FUNCTION`, `UNSUPPORTED_FEATURE`;
- `DIVISION_BY_ZERO`, `DOMAIN_ERROR`, `LIMIT_EXCEEDED`, `TIMEOUT`;
- `UNSUPPORTED_INTENT`, `VERIFICATION_FAILED`, `INTERNAL_ERROR`.

"Sem solução" **não** é erro: é um sucesso com conjunto vazio.

**Passos:** o SymPy não gera passos de resolução. A lista `steps` só será
preenchida quando existirem regras próprias que produzam passos verdadeiros.
Até lá, a interface não mostra uma seção de passos.

## 5. Estrutura de pastas

```
Mathcode/
├── backend/
│   ├── app/
│   │   ├── main.py             cria o app FastAPI
│   │   ├── api/                rotas (health, calculate)
│   │   ├── core/               config, erros, limites, pool de processos
│   │   ├── models/             schemas Pydantic (MathResult...)
│   │   ├── parsing/            normalize, tokenizer, parser, ast, build
│   │   ├── interpreter/        registry + detecção por regras
│   │   ├── planner/            ExecutionPlan
│   │   ├── math_engine/        arithmetic/ algebra/ calculus/ graphing/ ...
│   │   ├── verification/       estratégias por intent
│   │   ├── formatting/         plain/LaTeX/aproximação
│   │   └── ai/                 AIProvider + provedores gratuitos (Fase 8)
│   ├── tests/                  unit/ e integration/
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

## 6. Testes

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

## 7. Ambiente (2026-10-06)

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

## 8. Decisões registradas

| ADR | Tema |
|---|---|
| [0001](decisions/0001-custo-zero.md) | Custo zero (regra primordial) |
| [0002](decisions/0002-parser-sem-eval.md) | Parser próprio sem `eval`, limites e execução isolada |
| [0003](decisions/0003-verificacao.md) | Estratégia e níveis de verificação |
| [0004](decisions/0004-ai-provider.md) | Camada de IA só com provedores gratuitos |
| [0005](decisions/0005-dominio-e-exatidao.md) | Domínio ℝ, exatidão e convenções |
