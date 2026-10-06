# ADR 0001 — Custo zero (regra primordial)

- **Status:** aceita
- **Data:** 2026-10-06

## Contexto

O Mathcode é um projeto pessoal. Nenhuma parte dele pode gerar cobrança em
dinheiro, nem agora nem por acidente no futuro (uma chave de API esquecida, um
plano que deixa de ser gratuito, um serviço com cobrança por uso).

## Decisão

**Nada no projeto pode ter custo em dinheiro.** Esta regra está acima de todas
as outras decisões. Toda proposta (biblioteca, serviço, provedor de IA,
hospedagem, CI) passa primeiro por este filtro.

Na prática, isso significa:

1. **Bibliotecas:** apenas software livre com licença permissiva (MIT, BSD,
   Apache-2.0). Nada de SDKs com cobrança por uso.
2. **IA:** apenas provedores sem custo (ver [ADR 0004](0004-ai-provider.md)).
   - Permitido: `MockProvider` (testes), Ollama (local) e `opencode run` com
     modelos marcados como gratuitos.
   - **Excluído:** as APIs pagas da OpenAI e da Anthropic, ou de qualquer outro
     fornecedor que cobre por token.
   - Uma resposta que informe custo maior que zero é tratada como **erro**, e a
     chamada não é repetida.
3. **Gráficos:** apenas o Plotly.js local, que roda no navegador. O Plotly
   Chart Studio, que é um serviço em nuvem, não é usado.
4. **Execução:** o projeto roda localmente. Hospedagem, banco de dados gerenciado
   e CI só entram se forem gratuitos, e mesmo assim só com uma decisão explícita
   registrada aqui.
5. **Recursos externos:** as fontes do KaTeX vêm empacotadas com a própria
   biblioteca. Não há CDN pago nem serviço de terceiros em tempo de execução.

## Bibliotecas previstas e licenças

| Biblioteca | Uso | Licença | Entra na fase |
|---|---|---|---|
| FastAPI / Starlette / Uvicorn | API | MIT / BSD-3 / BSD-3 | 1 |
| Pydantic v2 | schemas | MIT | 1 |
| SymPy (+ mpmath) | motor simbólico | BSD-3 | 2 |
| NumPy | amostragem de gráficos | BSD-3 | 7 |
| SciPy | verificação numérica, estatística | BSD-3 | 6/10 |
| pytest, pytest-cov, httpx | testes | MIT / MIT / BSD-3 | 1 |
| ruff | lint/format | MIT | 1 |
| React, Vite | frontend | MIT | 1 |
| TypeScript | frontend | Apache-2.0 | 1 |
| Tailwind CSS | estilos | MIT | 1 |
| Vitest, Testing Library, jsdom | testes frontend | MIT | 1 |
| KaTeX | renderizar LaTeX | MIT | 4 |
| Plotly.js | gráficos | MIT | 7 |
| MathLive | teclado/entrada matemática | MIT | 11 |
| opencode (CLI) | provedor de IA gratuito | MIT | 8 |
| Ollama | provedor de IA local (opcional) | MIT | 8 |

Antes de instalar qualquer biblioteca, a licença é conferida de novo.

## Consequências

- Os provedores pagos não serão implementados. A interface `AIProvider` continua
  neutra, mas este ADR teria de ser revisado antes de qualquer provedor pago.
- Os modelos gratuitos podem mudar ou sair do ar. Por isso o sistema funciona
  sem IA: o interpretador por regras é o padrão, e a IA é opcional.
