# ADR 0022 — Pendências técnicas e inicializador

- **Status:** aceita
- **Data:** 2026-10-09

## Contexto

Com as fases 0 a 12 concluídas, o usuário escolheu as pendências técnicas
registradas e pediu um inicializador para abrir o projeto com mais facilidade.
As pendências eram três:

1. O texto simples escrevia o logaritmo natural como `log`. Na entrada, `log` é
   base 10, então o "Copiar texto" de ∫1/x dx dava uma expressão diferente.
2. O pacote principal do frontend tinha 548 kB, e o build avisava, porque o
   KaTeX entrava nele.
3. A página `/api/docs`, que só existe fora de produção, baixava o Swagger UI do
   jsDelivr.

## Decisões

### 1. `ln` no texto simples

`formatting.plain` passa a escrever `ln(x)`, e `parser_text` (ADR 0021) virou
o mesmo texto. Assim, o que se copia volta para a calculadora com o mesmo
significado. O texto da integral de 1/x mudou de `log(abs(x)) + C` para
`ln(abs(x)) + C`, e a fixture foi atualizada.

### 2. KaTeX sob demanda

- **`utils/katex.ts`:** `loadKatex()` faz `import("katex")` uma única vez e
  guarda o módulo, e `katexIfLoaded()` devolve o módulo já carregado.
- **`MathFormula`:**
  - desenha assim que o KaTeX existe;
  - até lá, o elemento fica vazio, com `aria-busy`.
- **CSS e fontes:** continuam no pacote, sem CDN.
- **Testes:** `test/setup.ts` carrega o KaTeX antes de tudo, então as fórmulas
  aparecem junto com o componente.
- **Resultado:** o pacote principal caiu de 548 kB para 289 kB (89 kB
  comprimido), e o KaTeX ganhou um pedaço próprio de 259 kB. O aviso de 500 kB
  continua, mas agora só pelo MathLive e pelo Plotly, que já carregam sob
  demanda.

### 3. Swagger UI local

O usuário escolheu copiá-lo do npm.
- **Pacote:** `swagger-ui-dist` 5.33.1 (Apache-2.0, gratuito) é dependência de
  desenvolvimento do frontend, numa versão fixa.
- **Cópia:** `frontend/scripts/copy-swagger.mjs` copia `swagger-ui-bundle.js`,
  `swagger-ui.css`, o favicon e a licença para `backend/app/static/swagger/`.
  - **Quando roda:** no `postinstall` do `npm install`/`npm ci` e no
    `npm run swagger`.
  - **Git:** a pasta fica fora dele (`.gitignore`).
- **Servidor:**
  - o backend serve a pasta em `/api/static/swagger`;
  - `/api/docs` é montada com `get_swagger_ui_html`, apontando para os arquivos
    locais e com `validatorUrl: null`, porque o selo de validação online
    enviaria o endereço da especificação para fora;
  - sem os arquivos, a página explica como gerá-los.
- **Telemetria:** o `swagger-ui-dist` depende do `@scarf/scarf`, que coleta
  estatísticas de instalação. O npm 11 já bloqueia o script dele, e o
  `package.json` também o desliga (`"scarfSettings": {"enabled": false}`).

### 4. Inicializador `Mathcode.command`

Fica na raiz do projeto e abre com dois cliques no Finder. Segue o padrão do
`DevAI.command`.

**Preparação, só quando precisa:**
- **Backend:** cria `backend/.venv` com o Python 3.14 e instala
  `backend[dev]`. Refaz a instalação quando o `pyproject.toml` muda.
- **Frontend:** roda `npm ci` quando falta `node_modules` ou quando o
  `package-lock.json` muda. Isso também copia o Swagger.

**Execução:**
- **Servidores:** sobe a API (8100) e o Vite (5180), espera os dois
  responderem e abre o navegador.
- **Já está rodando:** só abre o navegador.
- **Porta ocupada por outro programa:** explica.
- **Para fechar:** Ctrl+C ou fechar a janela param os dois servidores, sem
  deixar processos para trás.
- **Teste:** `MATHCODE_NO_BROWSER=1` não abre o navegador.

**Mensagens:** ficam em português, e os comentários em inglês.

## Consequências

- O texto copiado com ln agora pode ser colado de volta na calculadora.
- O primeiro desenho de uma fórmula espera o pedaço do KaTeX, que vem do
  próprio servidor.
- `/api/docs` não depende de internet.
- Para usar o projeto no dia a dia, basta o `Mathcode.command`.
