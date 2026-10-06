# Roadmap

Regras gerais:

- uma fase por vez;
- ao fim de cada fase: testes + build + relatório, e depois **parada até a
  autorização**;
- nenhum commit é feito pelo assistente;
- custo zero ([ADR 0001](decisions/0001-custo-zero.md)).

| Fase | Nome | Status |
|---|---|---|
| 0 | Auditoria e arquitetura | concluída |
| 1 | Foundation | concluída (aguardando revisão) |
| 2 | Core matemático | — |
| 3 | API | — |
| 4 | Frontend básico | — |
| 5 | Álgebra | — |
| 6 | Cálculo | — |
| 7 | Gráficos | — |
| 8 | Linguagem natural / IA | — |
| 9 | Verification Engine | — |
| 10 | Matemática avançada | — |
| 11 | UX e histórico | — |
| 12 | Assistente matemático | — |

## Fase 0 — Auditoria e arquitetura

Entregou `docs/architecture.md`, este roadmap e os ADRs de 0001 a 0005.
Nenhum código foi escrito.

## Fase 1 — Foundation

- **Backend (porta 8100):**
  - `pyproject.toml` com FastAPI, Uvicorn, Pydantic e pydantic-settings, mais
    pytest, httpx2 e ruff como dependências de desenvolvimento;
  - `app/main.py` (`create_app`) e `GET /api/health` (status, versão e
    ambiente);
  - `core/config.py` lendo variáveis `MATHCODE_*` e o `.env` da raiz;
    `/api/docs` fica desligado em produção;
  - testes do health check e da configuração; avisos contam como erro no
    pytest.
- **Frontend (porta 5180):**
  - Vite + React + TypeScript + Tailwind;
  - o Vite encaminha `/api` para o backend, então não é preciso CORS;
  - a página inicial mostra apenas o status da API, com botão "Tentar de novo",
    sem recursos falsos; a resposta da API é validada antes de ser usada;
  - Vitest + Testing Library.
- **Raiz:** `README.md`, `.env.example`, `.gitignore`, `LICENSE` (MIT).
- **Fora do projeto:** entradas `mathcode-api` e `mathcode-web` no
  `codes(dw)/.claude/launch.json`.
- **Compatibilidade conferida:** FastAPI, SymPy 1.14, NumPy 2.5 e SciPy 1.18
  têm versão para Python 3.14 (as três últimas só serão instaladas nas fases
  em que forem usadas).
- **Critério de saída:** `pytest`, `ruff check`, `npm test` e `npm run build`
  passando, e o health check visível no navegador.

## Fase 2 — Core matemático (sem API e sem IA)

- `parsing/` completo para a gramática do ADR 0002, com limites.
- Intents: `arithmetic`, `simplify` (básico) e `solve_equation` (linear, uma
  variável).
- Verificação conforme o ADR 0003, para esses três intents.
- `MathResult` e os códigos de erro.
- **Critério de saída:** testes unitários com casos normais, inválidos e
  maliciosos.

## Fase 3 — API

- `POST /api/calculate` → `MathResult`.
- Pool de processos com timeout (ADR 0002, seção 4).
- Mapeamento de erros para HTTP. Todo erro de matemática é `200` com
  `success: false`; `422` fica reservado para requisições malformadas.
- Testes de integração.

## Fase 4 — Frontend básico

- Campo de entrada, botão Calcular e exibição do resultado com KaTeX.
- Estados de carregamento, erro e verificação.
- Testes de componentes.

## Fase 5 — Álgebra

Fatoração, expansão, polinômios, equações gerais (quadráticas, polinomiais e
racionais) e sistemas. Cada item tem testes e uma estratégia de verificação.

## Fase 6 — Cálculo

Derivadas, integrais indefinidas e definidas, e limites. A verificação segue a
tabela do ADR 0003.

## Fase 7 — Gráficos

- Funções cartesianas, com amostragem pelo NumPy no backend.
- Domínio e descontinuidades: os pontos fora do domínio são cortados, não
  ligados por uma linha.
- Múltiplas funções e pontos relevantes (raízes, interceptos).
- Plotly.js no frontend.

## Fase 8 — Linguagem natural / IA

- `AIProvider` com os provedores `none`, `mock`, `opencode` e `ollama`
  (ADR 0004).
- Interpretador por regras para frases comuns em português.
- Testes só com o mock. Uma chamada real só acontece com autorização.

## Fase 9 — Verification Engine

Formalizar e expandir a verificação: comparação de métodos, relatórios
detalhados e cobertura de todos os intents.

## Fase 10 — Matemática avançada

Estatística, probabilidade, matrizes/vetores, geometria e trigonometria, **um
domínio por alteração**.

## Fase 11 — UX e histórico

Histórico local, copiar resultado, alternar entre exato e aproximado, teclado
MathLive, acessibilidade, responsividade e dark mode.

## Fase 12 — Assistente matemático

Pedidos compostos ("raízes, vértice e gráfico de f(x)") viram um
`ExecutionPlan` com vários passos. Cada passo é executado e verificado de forma
determinística.

## Sugestões registradas (fora do escopo atual)

- Domínio complexo como opção explícita.
- Passos de resolução gerados por regras próprias.
- `docker-compose.yml`, quando houver Docker para testar.
- Atalho para iniciar o projeto no macOS (como o `DevAI.command`), se fizer
  sentido.
